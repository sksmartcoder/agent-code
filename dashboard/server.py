#!/usr/bin/env python3
"""
IT Ticket Agent — Web Dashboard
Real-time flow visualization using Flask + SocketIO
"""
import os, sys, json, threading, uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("AWS_DEFAULT_REGION", "us-west-2")
os.environ.setdefault("BEDROCK_REGION",     "us-west-2")
os.environ.setdefault("BEDROCK_MODEL_ID",   "us.amazon.nova-lite-v1:0")
os.environ.setdefault("CONFIDENCE_THRESHOLD", "80")
os.environ["TICKETS_TABLE"]     = "dash_it_tickets"
os.environ["PATTERNS_TABLE"]    = "dash_ticket_patterns"
os.environ["RESOLUTIONS_TABLE"] = "dash_resolutions"
os.environ["RUNBOOK_BUCKET"]    = "dash-runbooks"

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = "hackathon-demo"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ── Bootstrap (same pattern as run_local.py) ──────────────────────────────────
import boto3 as _real_boto3
_real_bedrock = _real_boto3.client("bedrock-runtime", region_name=os.environ["BEDROCK_REGION"])

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

_kb_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge_base")
if os.path.isdir(_kb_dir):
    for f in os.listdir(_kb_dir):
        if f.endswith(".md"):
            with open(os.path.join(_kb_dir, f)) as fh:
                _s3.put_object(Bucket=config.RUNBOOK_BUCKET, Key=f"runbooks/{f}", Body=fh.read())

_glue = boto3.client("glue", region_name=config.REGION)
for _job in ["daily_claims_load", "etl_pipeline", "claims_transform"]:
    try:
        _glue.create_job(Name=_job, Role="arn:aws:iam::123:role/GlueRole",
            Command={"Name":"glueetl","ScriptLocation":f"s3://mock/{_job}.py","PythonVersion":"3"})
        _glue.start_job_run(JobName=_job)
    except: pass

from tools.models import TicketPattern, Resolution
from tools.ticket_store import create_pattern

for pat, res in [
    (TicketPattern(pattern_id="pat-cicd-001",category="CI/CD",signature="ECS OOM",resolution_id="res-cicd-001",keywords=["codepipeline","ecs","task","memory","killed","oom","deploy","failed"]),
     Resolution(resolution_id="res-cicd-001",ticket_id="h1",pattern_id="pat-cicd-001",category="CI/CD",severity="P2",description_summary="ECS OOM during deploy",applied_fix="1. Increase ECS memory to 1024MB.\n2. Create new task revision.\n3. Update service.\n4. Re-run pipeline.")),
    (TicketPattern(pattern_id="pat-data-001",category="Data/ETL",signature="Glue timeout",resolution_id="res-data-001",keywords=["glue","job","failed","connection","timeout","jdbc","daily","load","claims"]),
     Resolution(resolution_id="res-data-001",ticket_id="h2",pattern_id="pat-data-001",category="Data/ETL",severity="P2",description_summary="Glue JDBC timeout",applied_fix="1. Increase JDBC timeout to 120s.\n2. Add retry logic.\n3. Increase DPU.")),
    (TicketPattern(pattern_id="pat-infra-001",category="Infrastructure",signature="EC2 disk full",resolution_id="res-infra-001",keywords=["ec2","instance","disk","full","unreachable","storage","ebs","volume"]),
     Resolution(resolution_id="res-infra-001",ticket_id="h3",pattern_id="pat-infra-001",category="Infrastructure",severity="P1",description_summary="EC2 disk full",applied_fix="1. Clean /tmp.\n2. Rotate logs.\n3. Extend EBS volume.")),
    (TicketPattern(pattern_id="pat-access-001",category="Access/IAM",signature="Lambda S3 denied",resolution_id="res-access-001",keywords=["lambda","function","s3","bucket","write","access","denied","permission","role"]),
     Resolution(resolution_id="res-access-001",ticket_id="h4",pattern_id="pat-access-001",category="Access/IAM",severity="P3",description_summary="Lambda S3 denied",applied_fix="1. Add s3:PutObject to Lambda execution role.")),
    (TicketPattern(pattern_id="pat-network-001",category="Network",signature="API Gateway 503",resolution_id="res-network-001",keywords=["api","gateway","503","backend","health","security","group","inbound","alb"]),
     Resolution(resolution_id="res-network-001",ticket_id="h5",pattern_id="pat-network-001",category="Network",severity="P1",description_summary="API Gateway 503",applied_fix="1. Add SG inbound rule TCP 8080 from ALB.")),
]:
    create_pattern(pat, _ddb)
    _ddb.Table(config.RESOLUTIONS_TABLE).put_item(Item=res.to_dict())

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

# ── Ticket history for dashboard ──────────────────────────────────────────────
ticket_history = []

# ── Emit helper — sends step updates to browser ───────────────────────────────
def emit_step(run_id, step, status, detail="", category="", severity="", confidence=0):
    socketio.emit("step", {
        "run_id": run_id, "step": step, "status": status,
        "detail": detail, "category": category,
        "severity": severity, "confidence": confidence,
        "ts": datetime.now(timezone.utc).strftime("%H:%M:%S")
    })

# ── Patched MasterAgent that emits events ─────────────────────────────────────
def run_ticket_with_events(description, run_id):
    from tools.ticket_store import (create_ticket, update_ticket,
        get_patterns_by_category, get_resolution_by_pattern)
    from tools.classifier import classify_ticket
    from tools.pattern_matcher import route_ticket
    from tools.models import FixSuggestion
    from tools.notifier import log_resolution
    import tools.ticket_store as ts

    emit_step(run_id, "intake", "active", f"Creating ticket...")

    try:
        ticket = create_ticket(description, dynamodb=_ddb)
    except Exception as e:
        emit_step(run_id, "intake", "error", str(e))
        return {"error": str(e)}

    emit_step(run_id, "intake", "done", f"Ticket ID: {ticket.ticket_id[:8]}...")

    # Classify
    emit_step(run_id, "classify", "active", "Calling Amazon Bedrock Nova...")
    c = classify_ticket(description)
    ticket.category = c["category"]
    ticket.severity = c["severity"]
    ticket.classification_rationale = c["rationale"]
    ticket.add_status_transition("NEW", "Classification complete")
    update_ticket(ticket, _ddb)
    emit_step(run_id, "classify", "done", c["rationale"],
              category=ticket.category, severity=ticket.severity)

    # Pattern match
    emit_step(run_id, "pattern", "active", "Scanning known patterns...")
    patterns = get_patterns_by_category(ticket.category, _ddb)
    routing = route_ticket(description, patterns)
    conf = routing["confidence"]

    fix = None
    if routing["status"] == "RECURRING":
        pattern = routing["pattern"]
        ticket.pattern_id = pattern.pattern_id
        ticket.add_status_transition("RECURRING", f"Confidence: {conf}%")
        update_ticket(ticket, _ddb)
        emit_step(run_id, "pattern", "recurring",
                  f"Pattern match: {conf}% confidence", confidence=conf)

        emit_step(run_id, "subagent", "active", "Fetching proven fix from knowledge base...")
        resolution = get_resolution_by_pattern(pattern.pattern_id, _ddb)
        if resolution:
            fix = FixSuggestion(issue_summary=resolution.description_summary,
                remediation_steps=resolution.applied_fix, confidence="HIGH")
            emit_step(run_id, "subagent", "done", f"Proven fix found ✓", confidence=conf)
        else:
            emit_step(run_id, "subagent", "active", f"Delegating to {ticket.category} agent...")
            fix = _delegate(ticket)
            emit_step(run_id, "subagent", "done", f"{ticket.category} agent responded")
    else:
        emit_step(run_id, "pattern", "new",
                  f"New issue — best match: {conf}%", confidence=conf)
        emit_step(run_id, "subagent", "active",
                  f"Delegating to {ticket.category} specialist agent...")
        fix = _delegate(ticket)
        emit_step(run_id, "subagent", "done", f"{ticket.category} agent analysis complete")

    # Approval (auto-approve for dashboard)
    emit_step(run_id, "approval", "active", "Presenting fix to operator...")
    ticket.fix_suggestion = fix.issue_summary
    ticket.fix_confidence = fix.confidence
    ticket.resolved_at = datetime.now(timezone.utc).isoformat()
    ticket.resolved_by = "operator"
    ticket.add_status_transition("RESOLVED", "Operator approved fix")
    update_ticket(ticket, _ddb)
    ts.log_resolution(ticket, fix.remediation_steps, _ddb)
    emit_step(run_id, "approval", "resolved", "Ticket resolved ✓")

    result = {
        "ticket_id": ticket.ticket_id,
        "category": ticket.category,
        "severity": ticket.severity,
        "rationale": ticket.classification_rationale,
        "issue_summary": fix.issue_summary,
        "remediation_steps": fix.remediation_steps,
        "confidence": fix.confidence,
        "aws_resources": fix.aws_resources,
        "pattern_status": routing["status"],
        "pattern_confidence": conf,
        "final_status": "RESOLVED",
    }
    ticket_history.insert(0, result)
    if len(ticket_history) > 20:
        ticket_history.pop()
    socketio.emit("result", result)
    return result


def _delegate(ticket):
    from agent_core.cicd_agent import CICDAgent
    from agent_core.data_agent import DataETLAgent
    from agent_core.infra_agent import InfraAgent
    from agent_core.access_agent import AccessIAMAgent
    from agent_core.network_agent import NetworkAgent
    from tools.models import FixSuggestion
    agents = {"CI/CD": CICDAgent(), "Data/ETL": DataETLAgent(),
              "Infrastructure": InfraAgent(), "Access/IAM": AccessIAMAgent(),
              "Network": NetworkAgent()}
    agent = agents.get(ticket.category)
    if not agent:
        return FixSuggestion(issue_summary="Unknown category.",
            remediation_steps="Escalate to on-call.", confidence="LOW_CONFIDENCE")
    return agent.investigate(ticket.ticket_id, ticket.description,
        ticket.category, ticket.severity, _s3)


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/submit", methods=["POST"])
def submit():
    data = request.json
    description = data.get("description", "").strip()
    if not description:
        return jsonify({"error": "description required"}), 400
    run_id = str(uuid.uuid4())[:8]
    socketio.emit("start", {"run_id": run_id, "description": description})
    thread = threading.Thread(target=run_ticket_with_events, args=(description, run_id))
    thread.daemon = True
    thread.start()
    return jsonify({"run_id": run_id})

@app.route("/api/history")
def history():
    return jsonify(ticket_history)

@app.route("/api/demo/<int:n>", methods=["POST"])
def demo(n):
    demos = [
        "CodePipeline deploy failed — ECS task OOM killed",
        "Lambda function can't write to S3 bucket prod-reports",
        "Glue job daily_claims_load failed with connection timeout",
        "EC2 instance i-0abc123 unreachable, disk at 98%",
        "API gateway returning 503, backend health checks failing",
    ]
    if 1 <= n <= len(demos):
        description = demos[n-1]
        run_id = str(uuid.uuid4())[:8]
        socketio.emit("start", {"run_id": run_id, "description": description})
        thread = threading.Thread(target=run_ticket_with_events, args=(description, run_id))
        thread.daemon = True
        thread.start()
        return jsonify({"run_id": run_id, "description": description})
    return jsonify({"error": "invalid demo number"}), 400

if __name__ == "__main__":
    print("\n🚀 IT Ticket Agent Dashboard")
    print("   Open: http://35.88.44.159:8080\n")
    socketio.run(app, host="0.0.0.0", port=8080, debug=False)
