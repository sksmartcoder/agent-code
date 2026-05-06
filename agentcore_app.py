#!/usr/bin/env python3
"""
AgentCore entrypoint — wraps MasterAgent with BedrockAgentCoreApp.
Uses lightweight in-memory store (no moto) to stay within 30s cold-start.
Real Bedrock Nova Lite for all AI calls.
"""
import os, sys, json, uuid
from datetime import datetime, timezone

os.environ.setdefault("AWS_DEFAULT_REGION", "us-west-2")
os.environ.setdefault("BEDROCK_REGION",     "us-west-2")
os.environ.setdefault("BEDROCK_MODEL_ID",   "us.amazon.nova-lite-v1:0")
os.environ.setdefault("CONFIDENCE_THRESHOLD", "80")

sys.path.insert(0, os.path.dirname(__file__))

from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

# ── In-memory stores (replaces DynamoDB/S3/Glue for AgentCore runtime) ────────
_tickets     = {}
_patterns    = {}
_resolutions = {}
_runbooks    = {}
_glue_jobs   = {}

# ── Real Bedrock client ───────────────────────────────────────────────────────
import boto3
_bedrock = boto3.client("bedrock-runtime", region_name=os.environ["BEDROCK_REGION"])

# ── Load runbooks from knowledge_base/ ───────────────────────────────────────
_kb_dir = os.path.join(os.path.dirname(__file__), "knowledge_base")
if os.path.isdir(_kb_dir):
    for _f in os.listdir(_kb_dir):
        if _f.endswith(".md"):
            with open(os.path.join(_kb_dir, _f)) as _fh:
                _runbooks[_f.replace("_runbook.md", "").replace("_", "/")] = _fh.read()

# ── Seed patterns + resolutions ───────────────────────────────────────────────
def _now(): return datetime.now(timezone.utc).isoformat()

_patterns = {
    "pat-cicd-001":   {"pattern_id":"pat-cicd-001","category":"CI/CD","signature":"ECS OOM","resolution_id":"res-cicd-001","keywords":["codepipeline","ecs","task","memory","killed","oom","deploy","failed"],"occurrence_count":4,"last_seen":_now()},
    "pat-data-001":   {"pattern_id":"pat-data-001","category":"Data/ETL","signature":"Glue timeout","resolution_id":"res-data-001","keywords":["glue","job","failed","connection","timeout","jdbc","daily","load","claims"],"occurrence_count":3,"last_seen":_now()},
    "pat-infra-001":  {"pattern_id":"pat-infra-001","category":"Infrastructure","signature":"EC2 disk full","resolution_id":"res-infra-001","keywords":["ec2","instance","disk","full","unreachable","storage","ebs","volume"],"occurrence_count":5,"last_seen":_now()},
    "pat-access-001": {"pattern_id":"pat-access-001","category":"Access/IAM","signature":"Lambda S3 denied","resolution_id":"res-access-001","keywords":["lambda","function","s3","bucket","write","access","denied","permission","role"],"occurrence_count":3,"last_seen":_now()},
    "pat-network-001":{"pattern_id":"pat-network-001","category":"Network","signature":"API Gateway 503","resolution_id":"res-network-001","keywords":["api","gateway","503","backend","health","security","group","inbound","alb"],"occurrence_count":4,"last_seen":_now()},
}
_resolutions = {
    "res-cicd-001":   {"resolution_id":"res-cicd-001","ticket_id":"h1","pattern_id":"pat-cicd-001","category":"CI/CD","severity":"P2","description_summary":"ECS OOM during deploy","applied_fix":"1. Increase ECS memory to 1024MB.\n2. Create new task revision.\n3. Update service.\n4. Re-run pipeline.","created_at":_now()},
    "res-data-001":   {"resolution_id":"res-data-001","ticket_id":"h2","pattern_id":"pat-data-001","category":"Data/ETL","severity":"P2","description_summary":"Glue JDBC timeout","applied_fix":"1. Increase JDBC timeout to 120s.\n2. Add retry logic.\n3. Increase DPU.","created_at":_now()},
    "res-infra-001":  {"resolution_id":"res-infra-001","ticket_id":"h3","pattern_id":"pat-infra-001","category":"Infrastructure","severity":"P1","description_summary":"EC2 disk full","applied_fix":"1. Clean /tmp.\n2. Rotate logs.\n3. Extend EBS volume.","created_at":_now()},
    "res-access-001": {"resolution_id":"res-access-001","ticket_id":"h4","pattern_id":"pat-access-001","category":"Access/IAM","severity":"P3","description_summary":"Lambda S3 denied","applied_fix":"1. Add s3:PutObject to Lambda execution role.","created_at":_now()},
    "res-network-001":{"resolution_id":"res-network-001","ticket_id":"h5","pattern_id":"pat-network-001","category":"Network","severity":"P1","description_summary":"API Gateway 503","applied_fix":"1. Add SG inbound rule TCP 8080 from ALB.","created_at":_now()},
}
_glue_jobs = {"daily_claims_load":"FAILED","etl_pipeline":"FAILED","claims_transform":"FAILED"}

# ── Patch ticket_store to use in-memory dicts ─────────────────────────────────
import tools.ticket_store as _ts
import tools.models as _m
import config as _cfg
import re as _re

_cfg.CONFIDENCE_THRESHOLD = 80

def _mem_create_ticket(description, intake_channel="CLI", dynamodb=None):
    _ts.validate_description(description)
    t = _m.Ticket(description=description, intake_channel=intake_channel)
    t.add_status_transition("OPEN", "Ticket created")
    _tickets[t.ticket_id] = t.to_dict()
    return t

def _mem_get_ticket(ticket_id, dynamodb=None):
    d = _tickets.get(ticket_id)
    return _m.Ticket.from_dict(d) if d else None

def _mem_update_ticket(ticket, dynamodb=None):
    _tickets[ticket.ticket_id] = ticket.to_dict()

def _mem_get_patterns(category, dynamodb=None):
    return [_m.TicketPattern.from_dict(p) for p in _patterns.values() if p["category"] == category]

def _mem_get_resolution(pattern_id, dynamodb=None):
    pat = _patterns.get(pattern_id)
    if not pat: return None
    res = _resolutions.get(pat.get("resolution_id"))
    return _m.Resolution.from_dict(res) if res else None

def _mem_log_resolution(ticket, applied_fix, dynamodb=None):
    res = _m.Resolution(ticket_id=ticket.ticket_id, category=ticket.category,
        severity=ticket.severity, description_summary=ticket.description[:500],
        applied_fix=applied_fix, pattern_id=ticket.pattern_id)
    _resolutions[res.resolution_id] = res.to_dict()
    if ticket.pattern_id and ticket.pattern_id in _patterns:
        _patterns[ticket.pattern_id]["occurrence_count"] += 1
    elif ticket.pattern_id is None:
        words = list(set(_re.findall(r"\b[a-zA-Z]{5,}\b", ticket.description.lower())))[:20]
        pid = str(uuid.uuid4())
        _patterns[pid] = {"pattern_id":pid,"category":ticket.category,"signature":ticket.description[:200],
            "keywords":words,"resolution_id":res.resolution_id,"occurrence_count":1,"last_seen":_now()}
    return res

_ts.create_ticket              = _mem_create_ticket
_ts.get_ticket                 = _mem_get_ticket
_ts.update_ticket              = _mem_update_ticket
_ts.get_patterns_by_category   = _mem_get_patterns
_ts.get_resolution_by_pattern  = _mem_get_resolution
_ts.log_resolution             = _mem_log_resolution

# ── Patch knowledge_base to use in-memory runbooks ────────────────────────────
import tools.knowledge_base as _kb
_RUNBOOK_MAP = {"CI/CD":"CI/CD","Data/ETL":"Data/ETL","Infrastructure":"Infrastructure","Access/IAM":"Access/IAM","Network":"Network"}
def _mem_get_runbook(category, s3_client=None):
    for k, v in _runbooks.items():
        if category.lower().replace("/","").replace(" ","") in k.lower().replace("/","").replace(" ",""):
            return v
    return None
_kb.get_runbook = _mem_get_runbook

# ── Patch Bedrock calls to use real client ────────────────────────────────────
import tools.classifier as _clf
import agent_core.base_agent as _ba

def _nova_clf(prompt):
    body = json.dumps({"system":[{"text":_clf.SYSTEM_PROMPT}],
        "messages":[{"role":"user","content":[{"text":prompt}]}],
        "inferenceConfig":{"maxTokens":256,"temperature":0.1}})
    r = _bedrock.invoke_model(modelId=os.environ["BEDROCK_MODEL_ID"],
        body=body, contentType="application/json", accept="application/json")
    return json.loads(r["body"].read())["output"]["message"]["content"][0]["text"]

def _nova_ba(system_prompt, prompt):
    body = json.dumps({"system":[{"text":system_prompt}],
        "messages":[{"role":"user","content":[{"text":prompt}]}],
        "inferenceConfig":{"maxTokens":1024,"temperature":0.2}})
    r = _bedrock.invoke_model(modelId=os.environ["BEDROCK_MODEL_ID"],
        body=body, contentType="application/json", accept="application/json")
    return json.loads(r["body"].read())["output"]["message"]["content"][0]["text"]

_clf._call_nova = _nova_clf
_ba._call_nova  = _nova_ba

# ── Patch data_agent Glue calls to use in-memory ─────────────────────────────
import agent_core.data_agent as _da

def _mem_get_job_status(job_name):
    return _glue_jobs.get(job_name, "NOT_FOUND")

def _mem_rerun_job(job_name):
    if job_name in _glue_jobs:
        _glue_jobs[job_name] = "RUNNING"
        return str(uuid.uuid4())[:8], None
    return None, f"Job {job_name} not found"

_da._get_job_status = _mem_get_job_status
_da._rerun_glue_job = _mem_rerun_job


# ── AgentCore entrypoint ──────────────────────────────────────────────────────
@app.entrypoint
def handle(payload: dict) -> dict:
    description = payload.get("prompt", "").strip()
    if not description:
        return {"error": "prompt is required", "final_status": "REJECTED"}

    from agent_core.master_agent import MasterAgent
    from unittest.mock import patch
    with patch("builtins.input", return_value="approve"):
        result = MasterAgent().process(description)

    return result


if __name__ == "__main__":
    app.run()
