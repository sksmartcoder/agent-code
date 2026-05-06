#!/usr/bin/env python3
"""
Local test runner — no real AWS needed.
Uses moto to mock DynamoDB/S3 and stubs Strands Agent for offline testing.

Usage:
    python test_local.py                                    # mock LLM
    USE_ANTHROPIC=true ANTHROPIC_API_KEY=sk-... python test_local.py  # real LLM
"""
import os, sys, json, unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

USE_REAL_LLM = os.environ.get("USE_ANTHROPIC", "").lower() == "true"

# ── Stub Strands Agent before any agent imports ───────────────────────────────
if not USE_REAL_LLM:
    class _Resp:
        def __init__(self, t): self._t = t
        def __str__(self): return self._t

    class _MockAgent:
        def __init__(self, model=None, system_prompt="", **kw):
            self._sys = system_prompt
        def __call__(self, prompt):
            p = prompt.lower()
            # classifier responses
            if "codepipeline" in p or ("ecs" in p and "memory" in p) or "oom" in p:
                return _Resp('{"category":"CI/CD","severity":"P2","rationale":"ECS OOM"}')
            if "glue" in p or "jdbc" in p or "claims_load" in p:
                return _Resp('{"category":"Data/ETL","severity":"P2","rationale":"Glue timeout"}')
            if "disk" in p or ("ec2" in p and "unreachable" in p):
                return _Resp('{"category":"Infrastructure","severity":"P1","rationale":"Disk full"}')
            if "lambda" in p and "s3" in p:
                return _Resp('{"category":"Access/IAM","severity":"P3","rationale":"Lambda S3 permission"}')
            if "503" in p or ("api gateway" in p) or "health check" in p:
                return _Resp('{"category":"Network","severity":"P1","rationale":"API Gateway 503"}')
            # sub-agent fix response
            return _Resp(json.dumps({
                "issue_summary": "Mock root cause for local testing.",
                "remediation_steps": "1. Check logs.\n2. Apply fix.\n3. Verify.",
                "aws_resources": ["arn:aws:mock::123456789:resource/test"]
            }))

    import strands as _strands
    _strands.Agent = _MockAgent
    from strands import models as _sm
    from unittest.mock import MagicMock
    _sm.BedrockModel = MagicMock(return_value=MagicMock())

# ── Moto must wrap boto3 usage ────────────────────────────────────────────────
from moto import mock_aws
import boto3

import config
config.TICKETS_TABLE    = "test_it_tickets"
config.PATTERNS_TABLE   = "test_ticket_patterns"
config.RESOLUTIONS_TABLE = "test_resolutions"
config.RUNBOOK_BUCKET   = "test-runbooks"

from tools.models import Ticket, TicketPattern, Resolution
from tools.ticket_store import (
    create_ticket, get_ticket, update_ticket,
    get_patterns_by_category, create_pattern,
    get_resolution_by_pattern, log_resolution, ValidationError,
)
from tools.classifier import classify_ticket
from tools.pattern_matcher import compute_confidence, route_ticket
from agent_core.master_agent import MasterAgent


# ── Helpers ───────────────────────────────────────────────────────────────────

def _create_tables(ddb):
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


def _seed(ddb):
    seeds = [
        (TicketPattern(pattern_id="pat-cicd-oom-001", category="CI/CD",
            signature="ECS OOM", resolution_id="res-cicd-001",
            keywords=["codepipeline","ecs","task","memory","killed","oom","deploy","failed"]),
         Resolution(resolution_id="res-cicd-001", ticket_id="h1", pattern_id="pat-cicd-oom-001",
            category="CI/CD", severity="P2", description_summary="ECS OOM",
            applied_fix="1. Increase ECS memory to 1024MB.\n2. Redeploy service.")),
        (TicketPattern(pattern_id="pat-data-001", category="Data/ETL",
            signature="Glue JDBC timeout", resolution_id="res-data-001",
            keywords=["glue","job","failed","connection","timeout","jdbc","daily","load","claims"]),
         Resolution(resolution_id="res-data-001", ticket_id="h2", pattern_id="pat-data-001",
            category="Data/ETL", severity="P2", description_summary="Glue timeout",
            applied_fix="1. Increase JDBC timeout to 120s.\n2. Add retry logic.")),
        (TicketPattern(pattern_id="pat-infra-001", category="Infrastructure",
            signature="EC2 disk full", resolution_id="res-infra-001",
            keywords=["ec2","instance","disk","full","unreachable","storage","ebs","volume","percent"]),
         Resolution(resolution_id="res-infra-001", ticket_id="h3", pattern_id="pat-infra-001",
            category="Infrastructure", severity="P1", description_summary="Disk full",
            applied_fix="1. Clean /tmp.\n2. Extend EBS volume.")),
        (TicketPattern(pattern_id="pat-access-001", category="Access/IAM",
            signature="Lambda S3 denied", resolution_id="res-access-001",
            keywords=["lambda","function","s3","bucket","write","access","denied","permission","role"]),
         Resolution(resolution_id="res-access-001", ticket_id="h4", pattern_id="pat-access-001",
            category="Access/IAM", severity="P3", description_summary="Lambda S3 denied",
            applied_fix="1. Add s3:PutObject to Lambda role.")),
        (TicketPattern(pattern_id="pat-network-001", category="Network",
            signature="API Gateway 503", resolution_id="res-network-001",
            keywords=["api","gateway","503","backend","health","security","group","inbound","alb","port"]),
         Resolution(resolution_id="res-network-001", ticket_id="h5", pattern_id="pat-network-001",
            category="Network", severity="P1", description_summary="API Gateway 503",
            applied_fix="1. Add SG inbound rule port 8080 from ALB.")),
    ]
    for pattern, resolution in seeds:
        create_pattern(pattern, ddb)
        ddb.Table(config.RESOLUTIONS_TABLE).put_item(Item=resolution.to_dict())


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestValidation(unittest.TestCase):
    def test_empty_raises(self):
        from tools.ticket_store import validate_description
        with self.assertRaises(ValidationError):
            validate_description("")

    def test_whitespace_raises(self):
        from tools.ticket_store import validate_description
        for s in ["   ", "\t", "\n", " \t\n "]:
            with self.assertRaises(ValidationError):
                validate_description(s)

    def test_valid_passes(self):
        from tools.ticket_store import validate_description
        validate_description("CodePipeline deploy failed")


class TestPatternMatcher(unittest.TestCase):
    def _pat(self, kws):
        return TicketPattern(pattern_id="p1", category="CI/CD",
                             signature="test", keywords=kws, resolution_id="r1")

    def test_score_bounded(self):
        p = self._pat(["codepipeline","ecs","memory","oom","deploy"])
        s = compute_confidence("CodePipeline deploy failed ECS task OOM killed", p)
        self.assertGreaterEqual(s, 0)
        self.assertLessEqual(s, 100)

    def test_empty_desc_zero(self):
        self.assertEqual(compute_confidence("", self._pat(["ecs"])), 0)

    def test_high_overlap_high_score(self):
        p = self._pat(["codepipeline","ecs","memory","oom","deploy","failed","task"])
        s = compute_confidence("CodePipeline deploy failed ECS task OOM memory killed", p)
        self.assertGreater(s, 50)

    def test_no_overlap_low_score(self):
        p = self._pat(["codepipeline","ecs","memory"])
        s = compute_confidence("DNS resolution failure in VPC subnet", p)
        self.assertLess(s, 30)

    def test_empty_patterns_new(self):
        r = route_ticket("some ticket", [])
        self.assertEqual(r["status"], "NEW")
        self.assertEqual(r["confidence"], 0)


class TestClassifier(unittest.TestCase):
    def test_valid_output(self):
        r = classify_ticket("CodePipeline deploy failed — ECS task OOM killed")
        self.assertIn(r["category"], {"CI/CD","Data/ETL","Infrastructure","Access/IAM","Network","Unknown"})
        self.assertIn(r["severity"], {"P1","P2","P3","P4"})
        self.assertIn("rationale", r)


@mock_aws
class TestDynamoDB(unittest.TestCase):
    def setUp(self):
        self.ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_tables(self.ddb)

    def test_create_and_get(self):
        t = create_ticket("EC2 disk full", dynamodb=self.ddb)
        f = get_ticket(t.ticket_id, dynamodb=self.ddb)
        self.assertIsNotNone(f)
        self.assertEqual(f.description, "EC2 disk full")

    def test_initial_status_open(self):
        t = create_ticket("Test", dynamodb=self.ddb)
        self.assertEqual(t.status, "OPEN")

    def test_empty_rejected(self):
        with self.assertRaises(ValidationError):
            create_ticket("", dynamodb=self.ddb)

    def test_update_persists(self):
        t = create_ticket("Test update", dynamodb=self.ddb)
        t.category = "CI/CD"
        update_ticket(t, dynamodb=self.ddb)
        f = get_ticket(t.ticket_id, dynamodb=self.ddb)
        self.assertEqual(f.category, "CI/CD")

    def test_audit_trail_grows(self):
        t = create_ticket("Audit test", dynamodb=self.ddb)
        n = len(t.status_history)
        t.add_status_transition("NEW", "classified")
        self.assertGreater(len(t.status_history), n)

    def test_resolution_logging(self):
        t = create_ticket("Lambda S3 denied", dynamodb=self.ddb)
        t.category = "Access/IAM"
        t.severity = "P3"
        t.add_status_transition("NEW", "classified")
        update_ticket(t, dynamodb=self.ddb)
        r = log_resolution(t, "Add s3:PutObject to Lambda role", dynamodb=self.ddb)
        self.assertEqual(r.ticket_id, t.ticket_id)
        self.assertEqual(r.applied_fix, "Add s3:PutObject to Lambda role")


@mock_aws
class TestDemoScenarios(unittest.TestCase):
    def setUp(self):
        self.ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_tables(self.ddb)
        _seed(self.ddb)
        self.s3 = boto3.client("s3", region_name="us-east-1")
        self.s3.create_bucket(Bucket=config.RUNBOOK_BUCKET)
        self._p = patch("builtins.input", return_value="approve")
        self._p.start()

    def tearDown(self):
        self._p.stop()

    def _run(self, desc):
        return MasterAgent(dynamodb=self.ddb, s3_client=self.s3).process(desc)

    def test_scenario_1_cicd_oom(self):
        print("\n[Scenario 1] CodePipeline OOM")
        r = self._run("CodePipeline deploy failed — ECS task OOM killed")
        self.assertIsNotNone(r["ticket_id"])
        print(f"  → {r}")

    def test_scenario_2_access_iam(self):
        print("\n[Scenario 2] Lambda S3 Access")
        r = self._run("Lambda function can't write to S3 bucket prod-reports")
        self.assertIsNotNone(r["ticket_id"])
        print(f"  → {r}")

    def test_scenario_3_data_timeout(self):
        print("\n[Scenario 3] Glue Job Timeout")
        r = self._run("Glue job daily_claims_load failed with connection timeout")
        self.assertIsNotNone(r["ticket_id"])
        print(f"  → {r}")

    def test_scenario_4_infra_disk(self):
        print("\n[Scenario 4] EC2 Disk Full")
        r = self._run("EC2 instance i-0abc123 unreachable, disk at 98%")
        self.assertIsNotNone(r["ticket_id"])
        print(f"  → {r}")

    def test_scenario_5_network_503(self):
        print("\n[Scenario 5] API Gateway 503")
        r = self._run("API gateway returning 503, backend health checks failing")
        self.assertIsNotNone(r["ticket_id"])
        print(f"  → {r}")

    def test_empty_rejected(self):
        r = self._run("")
        self.assertIsNone(r["ticket_id"])
        self.assertEqual(r["final_status"], "REJECTED")


if __name__ == "__main__":
    mode = "REAL LLM (Anthropic)" if USE_REAL_LLM else "MOCK (no credentials needed)"
    print(f"\nLocal test mode: {mode}\n{'='*60}")
    unittest.main(verbosity=2)
