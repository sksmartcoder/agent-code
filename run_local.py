#!/usr/bin/env python3
"""
Run the IT Ticket Agent locally with REAL Bedrock LLM + mocked DynamoDB/S3.

- LLM: Amazon Bedrock (Claude Sonnet via Strands SDK) — real API calls
- DynamoDB/S3: moto in-memory mock — no real AWS tables needed

Usage:
    python run_local.py
    python run_local.py "CodePipeline deploy failed — ECS task OOM killed"
"""
import os, sys, json

# ── Set AWS credentials from environment (already exported in shell) ──────────
# If not set, fall back to values below for convenience
os.environ.setdefault("AWS_DEFAULT_REGION", "us-west-2")
os.environ.setdefault("BEDROCK_REGION", "us-west-2")
os.environ.setdefault("BEDROCK_MODEL_ID", "us.amazon.nova-lite-v1:0")
os.environ.setdefault("CONFIDENCE_THRESHOLD", "80")

# Use local table names (moto will create them in-memory)
os.environ["TICKETS_TABLE"]     = "local_it_tickets"
os.environ["PATTERNS_TABLE"]    = "local_ticket_patterns"
os.environ["RESOLUTIONS_TABLE"] = "local_resolutions"
os.environ["RUNBOOK_BUCKET"]    = "local-runbooks"

sys.path.insert(0, os.path.dirname(__file__))

# ── Create real Bedrock client BEFORE moto starts ────────────────────────────
import boto3 as _real_boto3
_real_bedrock = _real_boto3.client("bedrock-runtime", region_name=os.environ["BEDROCK_REGION"])

# ── Start moto mock for DynamoDB, S3, Glue ───────────────────────────────────
from moto import mock_aws
import boto3

mock = mock_aws()
mock.start()

import config

# ── Create DynamoDB tables in moto ────────────────────────────────────────────
ddb = boto3.resource("dynamodb", region_name="us-east-1")

ddb.create_table(
    TableName=config.TICKETS_TABLE,
    KeySchema=[{"AttributeName": "ticket_id", "KeyType": "HASH"}],
    AttributeDefinitions=[
        {"AttributeName": "ticket_id", "AttributeType": "S"},
        {"AttributeName": "category",  "AttributeType": "S"},
        {"AttributeName": "status",    "AttributeType": "S"},
    ],
    BillingMode="PAY_PER_REQUEST",
    GlobalSecondaryIndexes=[{
        "IndexName": "category-status-index",
        "KeySchema": [
            {"AttributeName": "category", "KeyType": "HASH"},
            {"AttributeName": "status",   "KeyType": "RANGE"},
        ],
        "Projection": {"ProjectionType": "ALL"},
    }],
)
ddb.create_table(
    TableName=config.PATTERNS_TABLE,
    KeySchema=[{"AttributeName": "pattern_id", "KeyType": "HASH"}],
    AttributeDefinitions=[
        {"AttributeName": "pattern_id", "AttributeType": "S"},
        {"AttributeName": "category",   "AttributeType": "S"},
    ],
    BillingMode="PAY_PER_REQUEST",
    GlobalSecondaryIndexes=[{
        "IndexName": "category-index",
        "KeySchema": [{"AttributeName": "category", "KeyType": "HASH"}],
        "Projection": {"ProjectionType": "ALL"},
    }],
)
ddb.create_table(
    TableName=config.RESOLUTIONS_TABLE,
    KeySchema=[{"AttributeName": "resolution_id", "KeyType": "HASH"}],
    AttributeDefinitions=[
        {"AttributeName": "resolution_id", "AttributeType": "S"},
        {"AttributeName": "ticket_id",     "AttributeType": "S"},
    ],
    BillingMode="PAY_PER_REQUEST",
    GlobalSecondaryIndexes=[{
        "IndexName": "ticket-index",
        "KeySchema": [{"AttributeName": "ticket_id", "KeyType": "HASH"}],
        "Projection": {"ProjectionType": "ALL"},
    }],
)

# ── Create S3 bucket and upload runbooks ──────────────────────────────────────
s3 = boto3.client("s3", region_name="us-east-1")
s3.create_bucket(Bucket=config.RUNBOOK_BUCKET)

runbooks_dir = os.path.join(os.path.dirname(__file__), "knowledge_base")
if os.path.isdir(runbooks_dir):
    for fname in os.listdir(runbooks_dir):
        if fname.endswith(".md"):
            with open(os.path.join(runbooks_dir, fname)) as f:
                s3.put_object(Bucket=config.RUNBOOK_BUCKET, Key=f"runbooks/{fname}", Body=f.read())
    print(f"Uploaded {len([f for f in os.listdir(runbooks_dir) if f.endswith('.md')])} runbooks to mock S3.")

# ── Seed mock Glue jobs (simulates real failed ETL jobs) ─────────────────────
glue = boto3.client("glue", region_name=config.REGION)
for job_name, script in [
    ("daily_claims_load",  "s3://mock-scripts/daily_claims_load.py"),
    ("etl_pipeline",       "s3://mock-scripts/etl_pipeline.py"),
    ("claims_transform",   "s3://mock-scripts/claims_transform.py"),
]:
    glue.create_job(
        Name=job_name,
        Role="arn:aws:iam::123456789:role/GlueRole",
        Command={"Name": "glueetl", "ScriptLocation": script, "PythonVersion": "3"},
    )
    # Seed a failed run so the agent detects it and re-triggers
    glue.start_job_run(JobName=job_name)

print(f"Seeded 3 mock Glue jobs (daily_claims_load, etl_pipeline, claims_transform).")

# ── Seed recurring patterns and resolutions ───────────────────────────────────
from tools.models import TicketPattern, Resolution
from tools.ticket_store import create_pattern

seeds = [
    (TicketPattern(pattern_id="pat-cicd-oom-001", category="CI/CD",
        signature="ECS task OOM killed during CodePipeline deployment",
        keywords=["codepipeline","ecs","task","memory","killed","oom","deploy","failed","container"],
        occurrence_count=4, resolution_id="res-cicd-001"),
     Resolution(resolution_id="res-cicd-001", ticket_id="hist-1", pattern_id="pat-cicd-oom-001",
        category="CI/CD", severity="P2",
        description_summary="ECS task OOM killed during CodePipeline deployment",
        applied_fix="1. Open ECS task definition.\n2. Increase memory from 512MB to 1024MB.\n3. Create new revision.\n4. Update ECS service.\n5. Re-run CodePipeline.")),
    (TicketPattern(pattern_id="pat-data-001", category="Data/ETL",
        signature="Glue job JDBC connection timeout",
        keywords=["glue","job","failed","connection","timeout","jdbc","daily","load","claims","retry"],
        occurrence_count=3, resolution_id="res-data-001"),
     Resolution(resolution_id="res-data-001", ticket_id="hist-2", pattern_id="pat-data-001",
        category="Data/ETL", severity="P2",
        description_summary="Glue job JDBC connection timeout on daily ETL load",
        applied_fix="1. Increase JDBC timeout to 120s.\n2. Add retry: maxRetries=3, retryInterval=30s.\n3. Increase DPU from 2 to 4.\n4. Re-run job.")),
    (TicketPattern(pattern_id="pat-infra-001", category="Infrastructure",
        signature="EC2 instance disk full",
        keywords=["ec2","instance","disk","full","unreachable","storage","ebs","volume","percent","space"],
        occurrence_count=5, resolution_id="res-infra-001"),
     Resolution(resolution_id="res-infra-001", ticket_id="hist-3", pattern_id="pat-infra-001",
        category="Infrastructure", severity="P1",
        description_summary="EC2 instance disk full causing unreachability",
        applied_fix="1. SSH in: sudo du -sh /* | sort -rh | head -20\n2. Clean /tmp: sudo rm -rf /tmp/*\n3. Rotate logs: sudo journalctl --vacuum-size=500M\n4. Extend EBS volume via AWS console.\n5. Grow filesystem: sudo growpart /dev/xvda 1 && sudo resize2fs /dev/xvda1")),
    (TicketPattern(pattern_id="pat-access-001", category="Access/IAM",
        signature="Lambda function missing S3 write permission",
        keywords=["lambda","function","s3","bucket","write","access","denied","permission","role","policy"],
        occurrence_count=3, resolution_id="res-access-001"),
     Resolution(resolution_id="res-access-001", ticket_id="hist-4", pattern_id="pat-access-001",
        category="Access/IAM", severity="P3",
        description_summary="Lambda function missing S3 write permission",
        applied_fix="1. Open IAM console, find Lambda execution role.\n2. Add inline policy with s3:PutObject for arn:aws:s3:::prod-reports/*\n3. Save policy.\n4. Re-invoke Lambda to verify.")),
    (TicketPattern(pattern_id="pat-network-001", category="Network",
        signature="API Gateway 503 due to missing security group inbound rule",
        keywords=["api","gateway","503","backend","health","security","group","inbound","alb","port","rule"],
        occurrence_count=4, resolution_id="res-network-001"),
     Resolution(resolution_id="res-network-001", ticket_id="hist-5", pattern_id="pat-network-001",
        category="Network", severity="P1",
        description_summary="API Gateway 503 due to missing security group inbound rule",
        applied_fix="1. Open EC2 > Security Groups.\n2. Find backend SG.\n3. Add inbound rule: TCP port 8080 from ALB Security Group ID.\n4. Save rule.\n5. Verify ALB health checks pass.")),
]

for pattern, resolution in seeds:
    create_pattern(pattern, ddb)
    ddb.Table(config.RESOLUTIONS_TABLE).put_item(Item=resolution.to_dict())

print(f"Seeded {len(seeds)} patterns and resolutions.\n")

# ── Inject real Bedrock client into classifier and base_agent ─────────────────
import tools.classifier as _clf
import agent_core.base_agent as _ba
_orig_clf = _clf._call_nova
_orig_ba  = _ba._call_nova

def _patched_nova_clf(prompt):
    import json
    body = json.dumps({
        "system": [{"text": _clf.SYSTEM_PROMPT}],
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": 256, "temperature": 0.1},
    })
    r = _real_bedrock.invoke_model(
        modelId=os.environ["BEDROCK_MODEL_ID"], body=body,
        contentType="application/json", accept="application/json")
    return json.loads(r["body"].read())["output"]["message"]["content"][0]["text"]

def _patched_nova_ba(system_prompt, prompt):
    import json
    body = json.dumps({
        "system": [{"text": system_prompt}],
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": 1024, "temperature": 0.2},
    })
    r = _real_bedrock.invoke_model(
        modelId=os.environ["BEDROCK_MODEL_ID"], body=body,
        contentType="application/json", accept="application/json")
    return json.loads(r["body"].read())["output"]["message"]["content"][0]["text"]

_clf._call_nova = _patched_nova_clf
_ba._call_nova  = _patched_nova_ba

# ── Run the agent ─────────────────────────────────────────────────────────────
from agent_core.master_agent import MasterAgent

# Demo scenarios to run
DEMO_TICKETS = [
    "CodePipeline deploy failed — ECS task OOM killed",
    "Lambda function can't write to S3 bucket prod-reports",
    "Glue job daily_claims_load failed with connection timeout",
    "EC2 instance i-0abc123 unreachable, disk at 98%",
    "API gateway returning 503, backend health checks failing",
]

def run_single(description: str):
    """Run one ticket through the full agent pipeline."""
    agent = MasterAgent(dynamodb=ddb, s3_client=s3)
    return agent.process(description)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Single ticket from CLI arg
        desc = " ".join(sys.argv[1:])
        result = run_single(desc)
        print(f"\nFinal: {result}")
    else:
        # Interactive menu
        print("=" * 60)
        print("  IT TICKET INTELLIGENCE AGENT — Local Runner")
        print("  LLM: Amazon Bedrock (Claude Sonnet) — REAL API")
        print("  DB : moto in-memory DynamoDB")
        print("=" * 60)
        print("\nDemo scenarios:")
        for i, t in enumerate(DEMO_TICKETS, 1):
            print(f"  {i}. {t}")
        print("  6. Enter custom ticket")
        print("  q. Quit\n")

        while True:
            choice = input("Select [1-6/q]: ").strip().lower()
            if choice == "q":
                break
            elif choice in ("1","2","3","4","5"):
                desc = DEMO_TICKETS[int(choice) - 1]
                print(f"\nRunning: {desc}")
                result = run_single(desc)
                print(f"\nFinal result: {result}\n")
            elif choice == "6":
                desc = input("Enter ticket description: ").strip()
                if desc:
                    result = run_single(desc)
                    print(f"\nFinal result: {result}\n")
            else:
                print("Invalid choice.")

    mock.stop()
