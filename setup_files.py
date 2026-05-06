#!/usr/bin/env python3
"""Writes all project source files to the it-ticket-agent directory."""
import os

BASE = os.path.dirname(os.path.abspath(__file__))

def w(rel, content):
    path = os.path.join(BASE, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    print(f"  wrote {rel}")

w("requirements.txt", """boto3==1.34.144
strands-agents==0.1.6
strands-agents-tools==0.1.4
hypothesis==6.112.1
pytest==8.3.2
moto[dynamodb,s3]==5.0.12
python-dotenv==1.0.1
anthropic>=0.25.0
""")

w("config.py", """import os
REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "hackathon")
TICKETS_TABLE = os.environ.get("TICKETS_TABLE", f"{ENVIRONMENT}_it_tickets")
PATTERNS_TABLE = os.environ.get("PATTERNS_TABLE", f"{ENVIRONMENT}_ticket_patterns")
RESOLUTIONS_TABLE = os.environ.get("RESOLUTIONS_TABLE", f"{ENVIRONMENT}_resolutions")
RUNBOOK_BUCKET = os.environ.get("RUNBOOK_BUCKET", f"{ENVIRONMENT}-it-ticket-runbooks")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", REGION)
CONFIDENCE_THRESHOLD = int(os.environ.get("CONFIDENCE_THRESHOLD", "80"))
""")

w("tools/__init__.py", "")
w("agent_core/__init__.py", "")

w("tools/models.py", '''from __future__ import annotations
import json, uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

VALID_CATEGORIES = {"CI/CD", "Data/ETL", "Infrastructure", "Access/IAM", "Network", "Unknown"}
VALID_SEVERITIES = {"P1", "P2", "P3", "P4"}

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

@dataclass
class Ticket:
    description: str
    ticket_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    category: str = "Unknown"
    severity: str = "P3"
    status: str = "OPEN"
    pattern_id: Optional[str] = None
    fix_suggestion: Optional[str] = None
    fix_confidence: Optional[str] = None
    classification_rationale: Optional[str] = None
    intake_channel: str = "CLI"
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    status_history: list = field(default_factory=list)

    def add_status_transition(self, new_status, note=""):
        self.status_history.append({"from": self.status, "to": new_status, "timestamp": _now_iso(), "note": note})
        self.status = new_status
        self.updated_at = _now_iso()

    def to_dict(self): return asdict(self)
    def to_json(self): return json.dumps(self.to_dict(), indent=2, default=str)

    @classmethod
    def from_dict(cls, data):
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

@dataclass
class TicketPattern:
    category: str
    signature: str
    keywords: list
    resolution_id: str
    pattern_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurrence_count: int = 1
    last_seen: str = field(default_factory=_now_iso)

    def to_dict(self): return asdict(self)
    def to_json(self): return json.dumps(self.to_dict(), indent=2, default=str)

    @classmethod
    def from_dict(cls, data):
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

@dataclass
class Resolution:
    ticket_id: str
    category: str
    severity: str
    description_summary: str
    applied_fix: str
    resolution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pattern_id: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self): return asdict(self)
    def to_json(self): return json.dumps(self.to_dict(), indent=2, default=str)

    @classmethod
    def from_dict(cls, data):
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

@dataclass
class FixSuggestion:
    issue_summary: str
    remediation_steps: str
    confidence: str
    aws_resources: list = field(default_factory=list)

    def to_dict(self): return asdict(self)
''')

w("tools/ticket_store.py", '''from __future__ import annotations
import re, boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime, timezone
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from tools.models import Ticket, TicketPattern, Resolution

class ValidationError(ValueError):
    pass

def validate_description(description):
    if not description or not description.strip():
        raise ValidationError("Ticket description must not be empty or whitespace-only.")

def _get_table(table_name, dynamodb=None):
    if dynamodb is None:
        dynamodb = boto3.resource("dynamodb", region_name=config.REGION)
    return dynamodb.Table(table_name)

def create_ticket(description, intake_channel="CLI", dynamodb=None):
    validate_description(description)
    ticket = Ticket(description=description, intake_channel=intake_channel)
    ticket.add_status_transition("OPEN", "Ticket created")
    _get_table(config.TICKETS_TABLE, dynamodb).put_item(Item=ticket.to_dict())
    return ticket

def get_ticket(ticket_id, dynamodb=None):
    r = _get_table(config.TICKETS_TABLE, dynamodb).get_item(Key={"ticket_id": ticket_id})
    item = r.get("Item")
    return Ticket.from_dict(item) if item else None

def update_ticket(ticket, dynamodb=None):
    _get_table(config.TICKETS_TABLE, dynamodb).put_item(Item=ticket.to_dict())

def list_tickets_by_category(category, status=None, dynamodb=None):
    table = _get_table(config.TICKETS_TABLE, dynamodb)
    if status:
        r = table.query(IndexName="category-status-index",
            KeyConditionExpression=Key("category").eq(category) & Key("status").eq(status))
    else:
        r = table.query(IndexName="category-status-index",
            KeyConditionExpression=Key("category").eq(category))
    return [Ticket.from_dict(i) for i in r.get("Items", [])]

def get_patterns_by_category(category, dynamodb=None):
    r = _get_table(config.PATTERNS_TABLE, dynamodb).query(
        IndexName="category-index",
        KeyConditionExpression=Key("category").eq(category))
    return [TicketPattern.from_dict(i) for i in r.get("Items", [])]

def create_pattern(pattern, dynamodb=None):
    _get_table(config.PATTERNS_TABLE, dynamodb).put_item(Item=pattern.to_dict())

def increment_pattern_occurrence(pattern_id, dynamodb=None):
    _get_table(config.PATTERNS_TABLE, dynamodb).update_item(
        Key={"pattern_id": pattern_id},
        UpdateExpression="SET occurrence_count = occurrence_count + :inc, last_seen = :ts",
        ExpressionAttributeValues={":inc": 1, ":ts": datetime.now(timezone.utc).isoformat()},
    )

def create_resolution(resolution, dynamodb=None):
    _get_table(config.RESOLUTIONS_TABLE, dynamodb).put_item(Item=resolution.to_dict())

def get_resolution_by_pattern(pattern_id, dynamodb=None):
    r = _get_table(config.PATTERNS_TABLE, dynamodb).get_item(Key={"pattern_id": pattern_id})
    item = r.get("Item")
    if not item:
        return None
    res_id = item.get("resolution_id")
    if not res_id:
        return None
    r2 = _get_table(config.RESOLUTIONS_TABLE, dynamodb).get_item(Key={"resolution_id": res_id})
    item2 = r2.get("Item")
    return Resolution.from_dict(item2) if item2 else None

def log_resolution(ticket, applied_fix, dynamodb=None):
    resolution = Resolution(
        ticket_id=ticket.ticket_id, category=ticket.category, severity=ticket.severity,
        description_summary=ticket.description[:500], applied_fix=applied_fix,
        pattern_id=ticket.pattern_id,
    )
    create_resolution(resolution, dynamodb)
    if ticket.status == "RECURRING" and ticket.pattern_id:
        increment_pattern_occurrence(ticket.pattern_id, dynamodb)
    elif ticket.status in ("NEW", "PENDING_APPROVAL", "APPROVED"):
        words = list(set(re.findall(r"\\b[a-zA-Z]{5,}\\b", ticket.description.lower())))[:20]
        create_pattern(TicketPattern(
            category=ticket.category, signature=ticket.description[:200],
            keywords=words, resolution_id=resolution.resolution_id), dynamodb)
    return resolution
''')

w("tools/pattern_matcher.py", '''from __future__ import annotations
import re
from typing import Optional
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from tools.models import TicketPattern

def _tokenize(text):
    return set(re.findall(r"\\b[a-z]{3,}\\b", text.lower()))

def compute_confidence(description, pattern):
    desc_tokens = _tokenize(description)
    pattern_tokens = set(kw.lower() for kw in pattern.keywords)
    if not desc_tokens or not pattern_tokens:
        return 0
    intersection = desc_tokens & pattern_tokens
    union = desc_tokens | pattern_tokens
    jaccard = len(intersection) / len(union)
    keyword_hit_ratio = len(intersection) / len(pattern_tokens)
    return max(0, min(100, round((jaccard * 50) + (keyword_hit_ratio * 50))))

def find_best_match(description, patterns, threshold=None):
    if threshold is None:
        threshold = config.CONFIDENCE_THRESHOLD
    if not patterns:
        return None, 0
    best_pattern, best_score = None, 0
    for pattern in patterns:
        score = compute_confidence(description, pattern)
        if score > best_score:
            best_score = score
            best_pattern = pattern
    return best_pattern, best_score

def route_ticket(description, patterns):
    best_pattern, best_score = find_best_match(description, patterns)
    if best_score >= config.CONFIDENCE_THRESHOLD and best_pattern is not None:
        return {"status": "RECURRING", "pattern": best_pattern, "confidence": best_score}
    return {"status": "NEW", "pattern": None, "confidence": best_score}
''')

w("tools/knowledge_base.py", '''from __future__ import annotations
from typing import Optional
import boto3
from botocore.exceptions import ClientError
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

CATEGORY_RUNBOOK_MAP = {
    "CI/CD": "runbooks/cicd_runbook.md",
    "Data/ETL": "runbooks/data_runbook.md",
    "Infrastructure": "runbooks/infra_runbook.md",
    "Access/IAM": "runbooks/access_runbook.md",
    "Network": "runbooks/network_runbook.md",
}

def get_runbook(category, s3_client=None):
    key = CATEGORY_RUNBOOK_MAP.get(category)
    if not key:
        return None
    if s3_client is None:
        s3_client = boto3.client("s3", region_name=config.REGION)
    try:
        r = s3_client.get_object(Bucket=config.RUNBOOK_BUCKET, Key=key)
        return r["Body"].read().decode("utf-8")
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "NoSuchBucket"):
            return None
        raise
''')

w("tools/classifier.py", '''from __future__ import annotations
import json, os
from strands import Agent
from strands.models import BedrockModel
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from tools.models import VALID_CATEGORIES, VALID_SEVERITIES

SYSTEM_PROMPT = (
    "You are an IT support triage assistant. Classify the ticket. "
    "Respond with ONLY a JSON object: "
    \'{"category": "<CI/CD|Data/ETL|Infrastructure|Access/IAM|Network|Unknown>", "severity": "<P1|P2|P3|P4>", "rationale": "<one sentence>"}\' "\\n"
    "Severity: P1=production down, P2=major impact, P3=minor, P4=cosmetic\\n"
    "Category: CI/CD=pipelines/ECS, Data/ETL=Glue/RDS, Infrastructure=EC2/EBS, Access/IAM=IAM/Lambda, Network=VPC/SG/ALB"
)

def _build_model():
    if os.environ.get("USE_ANTHROPIC", "").lower() == "true":
        from strands.models.anthropic import AnthropicModel
        return AnthropicModel(
            client_args={"api_key": os.environ["ANTHROPIC_API_KEY"]},
            model_id="claude-3-5-sonnet-20241022", max_tokens=256)
    return BedrockModel(model_id=config.BEDROCK_MODEL_ID, region_name=config.BEDROCK_REGION,
                        max_tokens=256, temperature=0.1)

def classify_ticket(description, _bedrock_client=None):
    try:
        agent = Agent(model=_build_model(), system_prompt=SYSTEM_PROMPT)
        return _parse(str(agent(f"Classify this IT ticket:\\n\\n{description}")))
    except Exception as e:
        return {"category": "Unknown", "severity": "P3", "rationale": f"Error: {e}"}

def _parse(text):
    try:
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        s, e = text.find("{"), text.rfind("}") + 1
        if s == -1 or e == 0:
            return {"category": "Unknown", "severity": "P3", "rationale": "No JSON"}
        d = json.loads(text[s:e])
        cat = d.get("category", "Unknown")
        sev = d.get("severity", "P3")
        return {
            "category": cat if cat in VALID_CATEGORIES else "Unknown",
            "severity": sev if sev in VALID_SEVERITIES else "P3",
            "rationale": d.get("rationale", ""),
        }
    except Exception as ex:
        return {"category": "Unknown", "severity": "P3", "rationale": f"Parse error: {ex}"}
''')

w("tools/notifier.py", '''from __future__ import annotations
from datetime import datetime, timezone
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools.models import Ticket, FixSuggestion
from tools.ticket_store import update_ticket, log_resolution

SEP = "─" * 60

def present_fix_and_get_approval(ticket, fix, dynamodb=None):
    _display_fix(ticket, fix)
    ticket.add_status_transition("PENDING_APPROVAL", "Awaiting operator approval")
    update_ticket(ticket, dynamodb)
    decision = _prompt_decision()
    return _handle_approve(ticket, fix, dynamodb) if decision == "approve" else _handle_reject(ticket, dynamodb)

def _display_fix(ticket, fix):
    conf = "✓ HIGH" if fix.confidence == "HIGH" else "⚠ LOW CONFIDENCE"
    print(f"\\n{SEP}\\n  FIX SUGGESTION\\n{SEP}")
    print(f"  Ticket ID  : {ticket.ticket_id}")
    print(f"  Category   : {ticket.category}  |  Severity: {ticket.severity}  |  Confidence: {conf}")
    print(f"{SEP}\\n  Issue: {fix.issue_summary}\\n\\n  Fix:")
    for line in fix.remediation_steps.splitlines():
        print(f"    {line}")
    if fix.aws_resources:
        print(f"\\n  AWS Resources: {', '.join(fix.aws_resources)}")
    print(SEP)

def _prompt_decision():
    while True:
        try:
            raw = input("\\n  [approve / reject]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "reject"
        if raw in ("approve", "reject"):
            return raw
        print("  Please type \'approve\' or \'reject\'.")

def _handle_approve(ticket, fix, dynamodb):
    ticket.fix_suggestion = fix.issue_summary
    ticket.fix_confidence = fix.confidence
    ticket.resolved_at = datetime.now(timezone.utc).isoformat()
    ticket.resolved_by = "operator"
    ticket.add_status_transition("RESOLVED", "Operator approved fix")
    update_ticket(ticket, dynamodb)
    resolution = log_resolution(ticket, fix.remediation_steps, dynamodb)
    print(f"\\n  ✓ Resolved. Resolution ID: {resolution.resolution_id}")
    return "RESOLVED"

def _handle_reject(ticket, dynamodb):
    try:
        reason = input("  Rejection reason: ").strip()
    except (EOFError, KeyboardInterrupt):
        reason = "No reason provided"
    ticket.rejection_reason = reason or "No reason provided"
    ticket.add_status_transition("REJECTED", f"Rejected: {ticket.rejection_reason}")
    update_ticket(ticket, dynamodb)
    print("\\n  ✗ Rejected.")
    return "REJECTED"
''')

w("agent_core/base_agent.py", '''from __future__ import annotations
import json, os
from strands import Agent
from strands.models import BedrockModel
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from tools.models import FixSuggestion
from tools.knowledge_base import get_runbook

def _build_model():
    if os.environ.get("USE_ANTHROPIC", "").lower() == "true":
        from strands.models.anthropic import AnthropicModel
        return AnthropicModel(
            client_args={"api_key": os.environ["ANTHROPIC_API_KEY"]},
            model_id="claude-3-5-sonnet-20241022", max_tokens=1024)
    return BedrockModel(model_id=config.BEDROCK_MODEL_ID, region_name=config.BEDROCK_REGION,
                        max_tokens=1024, temperature=0.2)

class BaseSubAgent:
    domain = "Unknown"
    category = "Unknown"

    def investigate(self, ticket_id, description, category, severity, s3_client=None, bedrock_client=None):
        runbook = get_runbook(category, s3_client)
        has_runbook = runbook is not None
        runbook_ctx = f"Relevant runbook:\\n\\n{runbook[:3000]}" if has_runbook else "No runbook available."
        system_prompt = (
            f"You are a specialist IT engineer for {self.domain}.\\n{runbook_ctx}\\n"
            \'Respond ONLY with JSON: {"issue_summary":"<root cause>","remediation_steps":"<numbered steps>","aws_resources":["<ARNs>"]}\''
        )
        prompt = f"Ticket: {ticket_id}\\nCategory: {category}\\nSeverity: {severity}\\nDescription: {description}"
        try:
            agent = Agent(model=_build_model(), system_prompt=system_prompt)
            suggestion = self._parse_fix(str(agent(prompt)))
        except Exception as e:
            suggestion = FixSuggestion(
                issue_summary=f"Agent error: {e}",
                remediation_steps="Investigate manually.",
                aws_resources=[], confidence="LOW_CONFIDENCE")
        suggestion.confidence = "HIGH" if has_runbook else "LOW_CONFIDENCE"
        return suggestion

    def _parse_fix(self, text):
        try:
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            s, e = text.find("{"), text.rfind("}") + 1
            if s == -1 or e == 0:
                raise ValueError("No JSON")
            d = json.loads(text[s:e])
            return FixSuggestion(
                issue_summary=d.get("issue_summary", "Unknown issue."),
                remediation_steps=d.get("remediation_steps", "No steps."),
                aws_resources=d.get("aws_resources", []),
                confidence="HIGH")
        except Exception:
            return FixSuggestion(
                issue_summary="Could not parse response.",
                remediation_steps="Investigate manually.",
                aws_resources=[], confidence="LOW_CONFIDENCE")
''')

for fname, cls, dom in [
    ("cicd_agent", "CICDAgent", "CI/CD"),
    ("data_agent", "DataETLAgent", "Data/ETL"),
    ("infra_agent", "InfraAgent", "Infrastructure"),
    ("access_agent", "AccessIAMAgent", "Access/IAM"),
    ("network_agent", "NetworkAgent", "Network"),
]:
    w(f"agent_core/{fname}.py",
      f"from agent_core.base_agent import BaseSubAgent\n"
      f"class {cls}(BaseSubAgent):\n"
      f"    domain = '{dom}'\n"
      f"    category = '{dom}'\n")

w("agent_core/master_agent.py", '''from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools.ticket_store import create_ticket, update_ticket, get_patterns_by_category, get_resolution_by_pattern, ValidationError
from tools.classifier import classify_ticket
from tools.pattern_matcher import route_ticket
from tools.models import FixSuggestion
from tools.notifier import present_fix_and_get_approval
from agent_core.cicd_agent import CICDAgent
from agent_core.data_agent import DataETLAgent
from agent_core.infra_agent import InfraAgent
from agent_core.access_agent import AccessIAMAgent
from agent_core.network_agent import NetworkAgent

SEP = "─" * 60
SUB_AGENTS = {
    "CI/CD": CICDAgent(), "Data/ETL": DataETLAgent(),
    "Infrastructure": InfraAgent(), "Access/IAM": AccessIAMAgent(), "Network": NetworkAgent(),
}

class MasterAgent:
    def __init__(self, dynamodb=None, bedrock_client=None, s3_client=None):
        self.dynamodb = dynamodb
        self.bedrock_client = bedrock_client
        self.s3_client = s3_client

    def process(self, description):
        print(f"\\n{SEP}\\n  IT TICKET INTELLIGENCE AGENT\\n{SEP}")
        print("\\n[1/5] Creating ticket...")
        try:
            ticket = create_ticket(description, dynamodb=self.dynamodb)
        except ValidationError as e:
            print(f"  ✗ {e}")
            return {"ticket_id": None, "final_status": "REJECTED", "error": str(e)}
        print(f"  Ticket ID: {ticket.ticket_id}")

        print("\\n[2/5] Classifying ticket...")
        c = classify_ticket(description, self.bedrock_client)
        ticket.category = c["category"]
        ticket.severity = c["severity"]
        ticket.classification_rationale = c["rationale"]
        ticket.add_status_transition("NEW", "Classification complete")
        update_ticket(ticket, self.dynamodb)
        print(f"  Category: {ticket.category}  |  Severity: {ticket.severity}")
        print(f"  Rationale: {ticket.classification_rationale}")

        print("\\n[3/5] Checking for recurring patterns...")
        patterns = get_patterns_by_category(ticket.category, self.dynamodb)
        routing = route_ticket(description, patterns)

        if routing["status"] == "RECURRING":
            pattern = routing["pattern"]
            conf = routing["confidence"]
            print(f"  Match: Pattern {pattern.pattern_id} (confidence: {conf}%)")
            ticket.pattern_id = pattern.pattern_id
            ticket.add_status_transition("RECURRING", f"Confidence: {conf}%")
            update_ticket(ticket, self.dynamodb)
            print("\\n[4/5] Fetching proven fix...")
            resolution = get_resolution_by_pattern(pattern.pattern_id, self.dynamodb)
            if resolution:
                fix = FixSuggestion(
                    issue_summary=resolution.description_summary,
                    remediation_steps=resolution.applied_fix,
                    confidence="HIGH")
            else:
                fix = self._delegate(ticket)
        else:
            print(f"  No match (best: {routing[\'confidence\']}%). Delegating...")
            print(f"\\n[4/5] {ticket.category} sub-agent investigating...")
            fix = self._delegate(ticket)

        print("\\n[5/5] Awaiting approval...")
        final_status = present_fix_and_get_approval(ticket, fix, self.dynamodb)
        return {"ticket_id": ticket.ticket_id, "final_status": final_status}

    def _delegate(self, ticket):
        agent = SUB_AGENTS.get(ticket.category)
        if not agent:
            return FixSuggestion(
                issue_summary="Unknown category.",
                remediation_steps="Escalate to on-call.",
                confidence="LOW_CONFIDENCE")
        return agent.investigate(
            ticket.ticket_id, ticket.description,
            ticket.category, ticket.severity,
            self.s3_client, self.bedrock_client)
''')

w("app.py", '''#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from agent_core.master_agent import MasterAgent

def main():
    description = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Enter ticket description: ").strip()
    if not description:
        print("Error: description cannot be empty.")
        sys.exit(1)
    result = MasterAgent().process(description)
    print(f"\\nDone. Ticket: {result.get(\'ticket_id\')} | Status: {result.get(\'final_status\')}")

if __name__ == "__main__":
    main()
''')

print("\\nAll files written successfully.")
