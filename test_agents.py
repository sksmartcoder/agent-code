#!/usr/bin/env python3
"""
Agent Routing & Tracing Test
Tests every specialist agent individually and verifies:
  - Correct agent is selected for each ticket type
  - Classifier routes to the right category
  - Trace log shows which agent handled the request
  - AgentCore Runtime invocation (if deployed)

Usage:
    python3 test_agents.py              # all tests, mock LLM
    python3 test_agents.py --real       # real Bedrock Nova
    python3 test_agents.py --agent cicd # test one agent only
    python3 test_agents.py --trace      # print full trace log after
"""
import os, sys, json, argparse
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("AWS_DEFAULT_REGION", "us-west-2")
os.environ.setdefault("BEDROCK_REGION",     "us-west-2")
os.environ.setdefault("BEDROCK_MODEL_ID",   "us.amazon.nova-lite-v1:0")
os.environ.setdefault("CONFIDENCE_THRESHOLD", "80")
os.environ["TICKETS_TABLE"]     = "test_routing_tickets"
os.environ["PATTERNS_TABLE"]    = "test_routing_patterns"
os.environ["RESOLUTIONS_TABLE"] = "test_routing_resolutions"
os.environ["RUNBOOK_BUCKET"]    = "test-routing-runbooks"

# ── Parse args ────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--real",  action="store_true", help="Use real Bedrock Nova")
parser.add_argument("--agent", help="Test one agent: cicd|data|infra|access|network")
parser.add_argument("--trace", action="store_true", help="Print full trace log after tests")
args = parser.parse_args()

USE_REAL = args.real

# ── ANSI ──────────────────────────────────────────────────────────────────────
R="\033[0m"; B="\033[1m"; GR="\033[92m"; YL="\033[93m"; RD="\033[91m"
CY="\033[96m"; BL="\033[94m"; MG="\033[95m"; DIM="\033[2m"

# ── Mock LLM if not using real Bedrock ───────────────────────────────────────
if not USE_REAL:
    import tools.classifier as _clf
    import agent_core.base_agent as _ba

    _MOCK_CLASSIFY = {
        "cicd":    '{"category":"CI/CD","severity":"P2","rationale":"ECS OOM during pipeline deploy"}',
        "data":    '{"category":"Data/ETL","severity":"P2","rationale":"Glue JDBC connection timeout"}',
        "infra":   '{"category":"Infrastructure","severity":"P1","rationale":"EC2 disk full"}',
        "access":  '{"category":"Access/IAM","severity":"P3","rationale":"Lambda missing S3 permission"}',
        "network": '{"category":"Network","severity":"P1","rationale":"API Gateway 503 health check failure"}',
    }
    _MOCK_FIX = json.dumps({
        "issue_summary": "Mock root cause identified by specialist agent.",
        "remediation_steps": "1. Identify affected resource.\n2. Apply fix.\n3. Verify resolution.",
        "aws_resources": ["arn:aws:mock::123456789:resource/test"]
    })

    def _mock_nova_clf(prompt):
        p = prompt.lower()
        if any(w in p for w in ["codepipeline","ecs","oom","codebuild","ecr","container","deploy","pipeline","build"]):
            return _MOCK_CLASSIFY["cicd"]
        if any(w in p for w in ["glue","jdbc","claims","redshift","rds","etl","database","connection refused","unreachable from"]):
            return _MOCK_CLASSIFY["data"]
        if any(w in p for w in ["disk","ebs","ec2","cpu","memory","instance","unreachable, disk","storage","running out"]):
            return _MOCK_CLASSIFY["infra"]
        if any(w in p for w in ["lambda","iam","s3 access","permission","role","policy","denied","missing permissions"]):
            return _MOCK_CLASSIFY["access"]
        if any(w in p for w in ["503","504","api gateway","vpc","alb","security group","health check","port 5432","subnet","unhealthy"]):
            return _MOCK_CLASSIFY["network"]
        return '{"category":"Unknown","severity":"P3","rationale":"Could not classify"}'

    def _mock_nova_ba(system_prompt, prompt): return _MOCK_FIX

    _clf._call_nova = _mock_nova_clf
    _ba._call_nova  = _mock_nova_ba
else:
    import boto3 as _real_boto3
    _real_bedrock = _real_boto3.client("bedrock-runtime", region_name=os.environ["BEDROCK_REGION"])
    import tools.classifier as _clf
    import agent_core.base_agent as _ba

    def _nova_clf(prompt):
        body = json.dumps({"system":[{"text":_clf.SYSTEM_PROMPT}],
            "messages":[{"role":"user","content":[{"text":prompt}]}],
            "inferenceConfig":{"maxTokens":256,"temperature":0.1}})
        r = _real_bedrock.invoke_model(modelId=os.environ["BEDROCK_MODEL_ID"],
            body=body, contentType="application/json", accept="application/json")
        return json.loads(r["body"].read())["output"]["message"]["content"][0]["text"]

    def _nova_ba(system_prompt, prompt):
        body = json.dumps({"system":[{"text":system_prompt}],
            "messages":[{"role":"user","content":[{"text":prompt}]}],
            "inferenceConfig":{"maxTokens":1024,"temperature":0.2}})
        r = _real_bedrock.invoke_model(modelId=os.environ["BEDROCK_MODEL_ID"],
            body=body, contentType="application/json", accept="application/json")
        return json.loads(r["body"].read())["output"]["message"]["content"][0]["text"]

    _clf._call_nova = _nova_clf
    _ba._call_nova  = _nova_ba

# ── Bootstrap moto ────────────────────────────────────────────────────────────
from moto import mock_aws
import boto3
_mock = mock_aws()
_mock.start()

import config
_ddb = boto3.resource("dynamodb", region_name="us-east-1")

def _make_table(name, pk, attrs, gsi):
    try:
        _ddb.create_table(TableName=name,
            KeySchema=[{"AttributeName": pk, "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": k, "AttributeType": v} for k,v in attrs],
            BillingMode="PAY_PER_REQUEST", GlobalSecondaryIndexes=gsi)
    except: pass

_make_table(config.TICKETS_TABLE, "ticket_id",
    [("ticket_id","S"),("category","S"),("status","S")],
    [{"IndexName":"category-status-index","KeySchema":[{"AttributeName":"category","KeyType":"HASH"},{"AttributeName":"status","KeyType":"RANGE"}],"Projection":{"ProjectionType":"ALL"}}])
_make_table(config.PATTERNS_TABLE, "pattern_id",
    [("pattern_id","S"),("category","S")],
    [{"IndexName":"category-index","KeySchema":[{"AttributeName":"category","KeyType":"HASH"}],"Projection":{"ProjectionType":"ALL"}}])
_make_table(config.RESOLUTIONS_TABLE, "resolution_id",
    [("resolution_id","S"),("ticket_id","S")],
    [{"IndexName":"ticket-index","KeySchema":[{"AttributeName":"ticket_id","KeyType":"HASH"}],"Projection":{"ProjectionType":"ALL"}}])

_s3 = boto3.client("s3", region_name="us-east-1")
try: _s3.create_bucket(Bucket=config.RUNBOOK_BUCKET)
except: pass

_glue = boto3.client("glue", region_name=config.REGION)
for _job in ["daily_claims_load", "etl_pipeline"]:
    try:
        _glue.create_job(Name=_job, Role="arn:aws:iam::123:role/GlueRole",
            Command={"Name":"glueetl","ScriptLocation":f"s3://mock/{_job}.py","PythonVersion":"3"})
        _glue.start_job_run(JobName=_job)
    except: pass

# ── Test cases ────────────────────────────────────────────────────────────────
TEST_CASES = {
    "cicd": {
        "name": "🔧 CI/CD Agent",
        "tickets": [
            "CodePipeline deploy failed — ECS task OOM killed",
            "CodeBuild job failing with exit code 137 — container killed",
            "ECR image pull failed during ECS deployment",
        ],
        "expected_category": "CI/CD",
        "expected_agent": "CICDAgent",
    },
    "data": {
        "name": "🗄  Data/ETL Agent",
        "tickets": [
            "Glue job daily_claims_load failed with connection timeout",
            "Redshift JDBC connection refused from ETL pipeline",
            "RDS database unreachable from Glue job etl_pipeline",
        ],
        "expected_category": "Data/ETL",
        "expected_agent": "DataETLAgent",
        "expect_glue_rerun": True,
    },
    "infra": {
        "name": "🖥  Infrastructure Agent",
        "tickets": [
            "EC2 instance i-0abc123 unreachable, disk at 98%",
            "EBS volume running out of space on production server",
            "EC2 instance CPU at 100% causing application timeouts",
        ],
        "expected_category": "Infrastructure",
        "expected_agent": "InfraAgent",
    },
    "access": {
        "name": "🔑 Access/IAM Agent",
        "tickets": [
            "Lambda function can't write to S3 bucket prod-reports",
            "IAM role missing permissions for DynamoDB access",
            "S3 access denied for Lambda execution role",
        ],
        "expected_category": "Access/IAM",
        "expected_agent": "AccessIAMAgent",
    },
    "network": {
        "name": "🌐 Network Agent",
        "tickets": [
            "API gateway returning 503, backend health checks failing",
            "VPC security group blocking traffic to RDS on port 5432",
            "ALB target group showing unhealthy instances",
        ],
        "expected_category": "Network",
        "expected_agent": "NetworkAgent",
    },
}

# ── Runner ────────────────────────────────────────────────────────────────────
from agent_core.master_agent import MasterAgent
from tools.tracer import print_trace_log
import tools.tracer as _tracer

results = []

def run_test(key, tc):
    print(f"\n{'═'*60}")
    print(f"  {B}{tc['name']} — Routing Test{R}")
    print(f"{'═'*60}")

    passed = 0
    failed = 0

    for i, ticket_desc in enumerate(tc["tickets"], 1):
        print(f"\n  {DIM}Test {i}/{len(tc['tickets'])}{R}")
        print(f"  {DIM}Input:{R} {ticket_desc}")

        with patch("builtins.input", return_value="approve"):
            agent = MasterAgent(dynamodb=_ddb, s3_client=_s3)
            result = agent.process(ticket_desc)

        # Verify category from trace log
        category_ok = False
        agent_ok = False
        glue_ok = True

        try:
            import json as _json
            # Clear trace before each ticket so we only check current run
            import tools.tracer as _t
            current_trace_id = _t._trace_id

            with open(_t.TRACE_FILE) as f:
                lines = [_json.loads(l) for l in f if l.strip()]

            # Only look at entries from this trace run
            run_lines = [l for l in lines if l.get("_trace_id") == current_trace_id]

            # Find classification
            for entry in reversed(run_lines):
                if entry.get("action") == "CLASSIFIED":
                    actual_cat = entry.get("outputs", {}).get("category", "")
                    category_ok = actual_cat == tc["expected_category"]
                    break

            # Find which agent was invoked
            for entry in reversed(run_lines):
                if entry.get("action") == "INVESTIGATE_START":
                    actual_agent = entry.get("agent", "")
                    agent_ok = actual_agent == tc["expected_agent"]
                    break

            # Check Glue rerun if expected
            if tc.get("expect_glue_rerun"):
                glue_ok = any(e.get("action") == "GLUE_RERUN_SUCCESS"
                              for e in run_lines)

        except Exception as e:
            print(f"  {YL}⚠ Could not read trace: {e}{R}")

        status_cat   = f"{GR}✓{R}" if category_ok else f"{RD}✗{R}"
        status_agent = f"{GR}✓{R}" if agent_ok   else f"{RD}✗{R}"

        print(f"  {status_cat} Category routed to: {B}{tc['expected_category']}{R}")
        print(f"  {status_agent} Agent invoked: {B}{tc['expected_agent']}{R}")

        if tc.get("expect_glue_rerun"):
            status_glue = f"{GR}✓{R}" if glue_ok else f"{RD}✗{R}"
            print(f"  {status_glue} Glue auto-rerun triggered")

        if result.get("final_status") == "RESOLVED":
            print(f"  {GR}✓{R} Final status: RESOLVED")
        else:
            print(f"  {RD}✗{R} Final status: {result.get('final_status')}")

        all_ok = category_ok and agent_ok and result.get("final_status") == "RESOLVED"
        if all_ok:
            passed += 1
        else:
            failed += 1

    print(f"\n  Result: {GR}{passed} passed{R}  {(RD+str(failed)+' failed'+R) if failed else ''}")
    results.append({"agent": key, "passed": passed, "failed": failed, "total": len(tc["tickets"])})


# ── AgentCore Runtime test ────────────────────────────────────────────────────
def test_agentcore():
    print(f"\n{'═'*60}")
    print(f"  {B}{CY}☁  AgentCore Runtime — Invocation Test{R}")
    print(f"{'═'*60}")

    try:
        import boto3
        client = boto3.client("bedrock-agentcore-runtime", region_name="us-west-2")
        payload = json.dumps({"prompt": "CodePipeline deploy failed — ECS task OOM killed"})
        r = client.invoke_agent_runtime(
            agentRuntimeArn="arn:aws:bedrock-agentcore:us-west-2:628875594738:runtime/it_ticket_agent_agentcore_app-Y14wFRAyTO",
            qualifier="DEFAULT",
            payload=payload.encode()
        )
        response_body = r["response"].read().decode()
        data = json.loads(response_body)
        print(f"  {GR}✓{R} AgentCore invocation successful")
        print(f"  Category : {data.get('category','?')}")
        print(f"  Status   : {data.get('final_status','?')}")
    except Exception as e:
        print(f"  {YL}⚠ AgentCore test skipped: {str(e)[:80]}{R}")
        print(f"  {DIM}(Run 'agentcore invoke' from CLI to test manually){R}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    mode = f"{GR}REAL Bedrock Nova{R}" if USE_REAL else f"{YL}MOCK LLM{R}"
    print(f"\n{CY}{'═'*60}{R}")
    print(f"{CY}  IT TICKET AGENT — ROUTING & TRACE TESTS{R}")
    print(f"  Mode: {mode}")
    print(f"{CY}{'═'*60}{R}")

    filter_key = args.agent
    cases = {k: v for k, v in TEST_CASES.items()
             if not filter_key or k == filter_key}

    for key, tc in cases.items():
        run_test(key, tc)

    # AgentCore test
    if not filter_key:
        test_agentcore()

    # Summary
    print(f"\n{CY}{'═'*60}{R}")
    print(f"  {B}SUMMARY{R}")
    total_p = sum(r["passed"] for r in results)
    total_f = sum(r["failed"] for r in results)
    for r in results:
        bar = f"{GR}{'█'*r['passed']}{'░'*(r['total']-r['passed'])}{R}"
        print(f"  {bar}  {TEST_CASES[r['agent']]['name']}  "
              f"{GR}{r['passed']}/{r['total']}{R}")
    print(f"\n  Total: {GR}{total_p} passed{R}  "
          f"{(RD+str(total_f)+' failed'+R+' ') if total_f else ''}")
    print(f"  Trace log: {DIM}/tmp/agent_trace.jsonl{R}")
    print(f"{CY}{'═'*60}{R}\n")

    if args.trace:
        print_trace_log()


if __name__ == "__main__":
    main()
    _mock.stop()
