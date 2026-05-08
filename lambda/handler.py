"""
Lambda handler — runs the IT Ticket Agent pipeline.
All steps emit structured logs visible in CloudWatch and Lambda Test console.
"""
import os, sys, json, uuid
from datetime import datetime, timezone

os.environ.setdefault("AWS_DEFAULT_REGION", "us-west-2")
os.environ.setdefault("BEDROCK_REGION",     "us-west-2")
os.environ.setdefault("BEDROCK_MODEL_ID",   "us.amazon.nova-lite-v1:0")
os.environ.setdefault("CONFIDENCE_THRESHOLD", "80")

sys.path.insert(0, "/var/task")

def _now(): return datetime.now(timezone.utc).isoformat()

def cw_log(step, status, detail="", **kwargs):
    """Emit a structured log line visible in CloudWatch."""
    entry = {"step": step, "status": status, "detail": detail,
             "ts": datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]}
    entry.update(kwargs)
    print(json.dumps(entry))

_tickets     = {}
_resolutions = {}
_patterns = {
    "pat-cicd-001":   {"pattern_id":"pat-cicd-001","category":"CI/CD","signature":"ECS OOM","resolution_id":"res-cicd-001","keywords":["codepipeline","ecs","task","memory","killed","oom","deploy","failed"],"occurrence_count":4,"last_seen":_now()},
    "pat-data-001":   {"pattern_id":"pat-data-001","category":"Data/ETL","signature":"Glue timeout","resolution_id":"res-data-001","keywords":["glue","job","failed","connection","timeout","jdbc","daily","load","claims"],"occurrence_count":3,"last_seen":_now()},
    "pat-infra-001":  {"pattern_id":"pat-infra-001","category":"Infrastructure","signature":"EC2 disk full","resolution_id":"res-infra-001","keywords":["ec2","instance","disk","full","unreachable","storage","ebs","volume"],"occurrence_count":5,"last_seen":_now()},
    "pat-access-001": {"pattern_id":"pat-access-001","category":"Access/IAM","signature":"Lambda S3 denied","resolution_id":"res-access-001","keywords":["lambda","function","s3","bucket","write","access","denied","permission","role"],"occurrence_count":3,"last_seen":_now()},
    "pat-network-001":{"pattern_id":"pat-network-001","category":"Network","signature":"API Gateway 503","resolution_id":"res-network-001","keywords":["api","gateway","503","backend","health","security","group","inbound","alb"],"occurrence_count":4,"last_seen":_now()},
}
_resolutions = {
    "res-cicd-001":   {"resolution_id":"res-cicd-001","ticket_id":"h1","pattern_id":"pat-cicd-001","category":"CI/CD","severity":"P2","description_summary":"ECS task OOM killed during CodePipeline deployment","applied_fix":"1. Open ECS task definition.\n2. Increase memory from 512MB to 1024MB.\n3. Create new task revision.\n4. Update ECS service.\n5. Re-run CodePipeline.","created_at":_now()},
    "res-data-001":   {"resolution_id":"res-data-001","ticket_id":"h2","pattern_id":"pat-data-001","category":"Data/ETL","severity":"P2","description_summary":"Glue job JDBC connection timeout on daily ETL load","applied_fix":"1. Increase JDBC connection timeout to 120s.\n2. Add retry logic: maxRetries=3, retryInterval=30s.\n3. Increase Glue DPU from 2 to 4.\n4. Re-run the job.","created_at":_now()},
    "res-infra-001":  {"resolution_id":"res-infra-001","ticket_id":"h3","pattern_id":"pat-infra-001","category":"Infrastructure","severity":"P1","description_summary":"EC2 instance disk full causing unreachability","applied_fix":"1. SSH in and run: sudo du -sh /* | sort -rh | head -20\n2. Clean temp: sudo rm -rf /tmp/*\n3. Rotate logs: sudo journalctl --vacuum-size=500M\n4. Extend EBS volume via AWS Console.\n5. Grow filesystem: sudo growpart /dev/xvda 1","created_at":_now()},
    "res-access-001": {"resolution_id":"res-access-001","ticket_id":"h4","pattern_id":"pat-access-001","category":"Access/IAM","severity":"P3","description_summary":"Lambda function missing S3 write permission","applied_fix":"1. Open IAM Console, find Lambda execution role.\n2. Add inline policy: s3:PutObject on arn:aws:s3:::prod-reports/*\n3. Save and re-invoke Lambda to verify.","created_at":_now()},
    "res-network-001":{"resolution_id":"res-network-001","ticket_id":"h5","pattern_id":"pat-network-001","category":"Network","severity":"P1","description_summary":"API Gateway 503 due to missing security group inbound rule","applied_fix":"1. Open EC2 > Security Groups.\n2. Find backend security group.\n3. Add inbound rule: TCP port 8080 from ALB Security Group ID.\n4. Save and verify ALB health checks pass.","created_at":_now()},
}

import re as _re
import boto3

# ── Patch ticket_store to use in-memory ───────────────────────────────────────
import tools.ticket_store as _ts
import tools.models as _m
import config as _cfg
_cfg.CONFIDENCE_THRESHOLD = 80

def _create_ticket(description, intake_channel="API", dynamodb=None):
    _ts.validate_description(description)
    t = _m.Ticket(description=description, intake_channel=intake_channel)
    t.add_status_transition("OPEN", "Ticket created")
    _tickets[t.ticket_id] = t.to_dict()
    return t

def _get_ticket(ticket_id, dynamodb=None):
    d = _tickets.get(ticket_id)
    return _m.Ticket.from_dict(d) if d else None

def _update_ticket(ticket, dynamodb=None):
    _tickets[ticket.ticket_id] = ticket.to_dict()

def _get_patterns(category, dynamodb=None):
    return [_m.TicketPattern.from_dict(p) for p in _patterns.values() if p["category"] == category]

def _get_resolution(pattern_id, dynamodb=None):
    pat = _patterns.get(pattern_id)
    if not pat: return None
    res = _resolutions.get(pat.get("resolution_id"))
    return _m.Resolution.from_dict(res) if res else None

def _log_resolution(ticket, applied_fix, dynamodb=None):
    res = _m.Resolution(ticket_id=ticket.ticket_id, category=ticket.category,
        severity=ticket.severity, description_summary=ticket.description[:500],
        applied_fix=applied_fix, pattern_id=ticket.pattern_id)
    _resolutions[res.resolution_id] = res.to_dict()
    return res

_ts.create_ticket             = _create_ticket
_ts.get_ticket                = _get_ticket
_ts.update_ticket             = _update_ticket
_ts.get_patterns_by_category  = _get_patterns
_ts.get_resolution_by_pattern = _get_resolution
_ts.log_resolution            = _log_resolution

# ── Patch knowledge_base ──────────────────────────────────────────────────────
import tools.knowledge_base as _kb
def _get_runbook(category, s3_client=None):
    return None  # no runbook in Lambda — uses AI expertise only
_kb.get_runbook = _get_runbook

# ── Patch Bedrock calls ───────────────────────────────────────────────────────
import tools.classifier as _clf
import agent_core.base_agent as _ba

_bedrock = boto3.client("bedrock-runtime", region_name=os.environ["BEDROCK_REGION"])

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

# ── Main handler ──────────────────────────────────────────────────────────────
def lambda_handler(event, context):
    # CORS headers for S3 static site
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }

    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return {"statusCode": 200, "headers": headers, "body": ""}

    try:
        body = json.loads(event.get("body", "{}"))
        description = body.get("description", "").strip()

        if not description:
            return {"statusCode": 400, "headers": headers,
                    "body": json.dumps({"error": "description required"})}

        from tools.classifier import classify_ticket
        from tools.pattern_matcher import route_ticket
        from tools.models import FixSuggestion

        # Step 1: Create ticket
        cw_log("INTAKE", "START", "Creating ticket", description=description[:80])
        ticket = _create_ticket(description)
        cw_log("INTAKE", "DONE", "Ticket created", ticket_id=ticket.ticket_id)

        # Step 2: Classify
        cw_log("CLASSIFY", "START", "Calling Amazon Bedrock Nova Lite",
               model=os.environ["BEDROCK_MODEL_ID"])
        c = classify_ticket(description)
        ticket.category = c["category"]
        ticket.severity  = c["severity"]
        ticket.classification_rationale = c["rationale"]
        ticket.add_status_transition("NEW", "Classification complete")
        _update_ticket(ticket)
        cw_log("CLASSIFY", "DONE", "Classification complete",
               category=ticket.category, severity=ticket.severity,
               rationale=c["rationale"])

        # Step 3: Pattern match
        cw_log("PATTERN_MATCH", "START", f"Scanning patterns for category={ticket.category}")
        patterns = _get_patterns(ticket.category)
        routing  = route_ticket(description, patterns)
        conf = routing["confidence"]
        cw_log("PATTERN_MATCH", "DONE",
               f"Result={routing['status']} confidence={conf}%",
               status=routing["status"], confidence=conf)

        # Step 4: Fix
        fix = None
        if routing["status"] == "RECURRING":
            ticket.pattern_id = routing["pattern"].pattern_id
            ticket.add_status_transition("RECURRING", f"Confidence: {conf}%")
            _update_ticket(ticket)
            cw_log("KNOWLEDGE_BASE", "START", "Fetching proven fix",
                   pattern_id=routing["pattern"].pattern_id)
            resolution = _get_resolution(routing["pattern"].pattern_id)
            if resolution:
                fix = FixSuggestion(issue_summary=resolution.description_summary,
                    remediation_steps=resolution.applied_fix, confidence="HIGH")
                cw_log("KNOWLEDGE_BASE", "DONE", "Proven fix retrieved",
                       resolution_id=resolution.resolution_id)

        if fix is None:
            cw_log("SUB_AGENT", "START",
                   f"Delegating to {ticket.category} specialist agent",
                   agent=ticket.category)
            from agent_core.cicd_agent import CICDAgent
            from agent_core.data_agent import DataETLAgent
            from agent_core.infra_agent import InfraAgent
            from agent_core.access_agent import AccessIAMAgent
            from agent_core.network_agent import NetworkAgent
            agents = {"CI/CD":CICDAgent(),"Data/ETL":DataETLAgent(),
                      "Infrastructure":InfraAgent(),"Access/IAM":AccessIAMAgent(),
                      "Network":NetworkAgent()}
            agent = agents.get(ticket.category)
            if agent:
                fix = agent.investigate(ticket.ticket_id, ticket.description,
                    ticket.category, ticket.severity)
                cw_log("SUB_AGENT", "DONE",
                       f"{ticket.category} agent analysis complete",
                       agent=ticket.category, confidence=fix.confidence,
                       issue_summary=fix.issue_summary[:80])
            else:
                fix = FixSuggestion(issue_summary="Unknown category — manual review required.",
                    remediation_steps="Escalate to on-call engineer.", confidence="LOW_CONFIDENCE")
                cw_log("SUB_AGENT", "WARN", "Unknown category — no agent found")

        # Step 5: Resolve
        cw_log("RESOLVE", "START", "Logging resolution")
        ticket.fix_suggestion = fix.issue_summary
        ticket.fix_confidence  = fix.confidence
        ticket.resolved_at     = _now()
        ticket.resolved_by     = "auto"
        ticket.add_status_transition("RESOLVED", "Auto-resolved")
        _update_ticket(ticket)
        _log_resolution(ticket, fix.remediation_steps)
        cw_log("RESOLVE", "DONE", "Ticket resolved",
               ticket_id=ticket.ticket_id, final_status="RESOLVED",
               category=ticket.category, severity=ticket.severity)

        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "ticket_id":        ticket.ticket_id,
                "category":         ticket.category,
                "severity":         ticket.severity,
                "rationale":        ticket.classification_rationale,
                "pattern_status":   routing["status"],
                "pattern_confidence": conf,
                "issue_summary":    fix.issue_summary,
                "remediation_steps": fix.remediation_steps,
                "aws_resources":    fix.aws_resources,
                "confidence":       fix.confidence,
                "final_status":     "RESOLVED",
            })
        }

    except Exception as e:
        import traceback
        return {"statusCode": 500, "headers": headers,
                "body": json.dumps({"error": str(e), "trace": traceback.format_exc()[-500:]})}
