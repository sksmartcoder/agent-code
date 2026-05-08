#!/usr/bin/env python3
"""
AgentCore entrypoint — minimal cold start, all work done in handler.
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

def _now(): return datetime.now(timezone.utc).isoformat()

# Pre-seeded patterns and resolutions (no DB needed)
_PATTERNS = {
    "pat-cicd-001":   {"pattern_id":"pat-cicd-001","category":"CI/CD","resolution_id":"res-cicd-001","keywords":["codepipeline","ecs","task","memory","killed","oom","deploy","failed"],"occurrence_count":4,"last_seen":_now(),"signature":"ECS OOM"},
    "pat-data-001":   {"pattern_id":"pat-data-001","category":"Data/ETL","resolution_id":"res-data-001","keywords":["glue","job","failed","connection","timeout","jdbc","daily","load","claims"],"occurrence_count":3,"last_seen":_now(),"signature":"Glue timeout"},
    "pat-infra-001":  {"pattern_id":"pat-infra-001","category":"Infrastructure","resolution_id":"res-infra-001","keywords":["ec2","instance","disk","full","unreachable","storage","ebs","volume"],"occurrence_count":5,"last_seen":_now(),"signature":"EC2 disk full"},
    "pat-access-001": {"pattern_id":"pat-access-001","category":"Access/IAM","resolution_id":"res-access-001","keywords":["lambda","function","s3","bucket","write","access","denied","permission","role"],"occurrence_count":3,"last_seen":_now(),"signature":"Lambda S3 denied"},
    "pat-network-001":{"pattern_id":"pat-network-001","category":"Network","resolution_id":"res-network-001","keywords":["api","gateway","503","backend","health","security","group","inbound","alb"],"occurrence_count":4,"last_seen":_now(),"signature":"API Gateway 503"},
}
_RESOLUTIONS = {
    "res-cicd-001":   {"resolution_id":"res-cicd-001","ticket_id":"h1","pattern_id":"pat-cicd-001","category":"CI/CD","severity":"P2","description_summary":"ECS task OOM killed during CodePipeline deployment","applied_fix":"1. Open ECS task definition.\n2. Increase memory from 512MB to 1024MB.\n3. Create new task revision.\n4. Update ECS service.\n5. Re-run CodePipeline.","created_at":_now()},
    "res-data-001":   {"resolution_id":"res-data-001","ticket_id":"h2","pattern_id":"pat-data-001","category":"Data/ETL","severity":"P2","description_summary":"Glue job JDBC connection timeout","applied_fix":"1. Increase JDBC timeout to 120s.\n2. Add retry: maxRetries=3.\n3. Increase DPU from 2 to 4.\n4. Re-run job.","created_at":_now()},
    "res-infra-001":  {"resolution_id":"res-infra-001","ticket_id":"h3","pattern_id":"pat-infra-001","category":"Infrastructure","severity":"P1","description_summary":"EC2 instance disk full","applied_fix":"1. SSH in: sudo du -sh /* | sort -rh | head -20\n2. Clean /tmp: sudo rm -rf /tmp/*\n3. Extend EBS volume.\n4. Grow filesystem.","created_at":_now()},
    "res-access-001": {"resolution_id":"res-access-001","ticket_id":"h4","pattern_id":"pat-access-001","category":"Access/IAM","severity":"P3","description_summary":"Lambda missing S3 write permission","applied_fix":"1. Open IAM Console, find Lambda execution role.\n2. Add s3:PutObject on arn:aws:s3:::prod-reports/*\n3. Save and re-invoke Lambda.","created_at":_now()},
    "res-network-001":{"resolution_id":"res-network-001","ticket_id":"h5","pattern_id":"pat-network-001","category":"Network","severity":"P1","description_summary":"API Gateway 503 missing security group rule","applied_fix":"1. Open EC2 > Security Groups.\n2. Add inbound rule: TCP 8080 from ALB SG.\n3. Save and verify health checks.","created_at":_now()},
}
_tickets = {}

@app.entrypoint
def handle(payload: dict) -> dict:
    import boto3, json, re
    from tools.classifier import classify_ticket
    from tools.pattern_matcher import route_ticket
    from tools.models import Ticket, TicketPattern, Resolution, FixSuggestion
    from tools.ticket_store import validate_description

    description = payload.get("prompt", "").strip()
    if not description:
        return {"error": "prompt required", "final_status": "REJECTED"}

    print(json.dumps({"step":"INTAKE","status":"START","description":description[:80]}))

    validate_description(description)
    ticket = Ticket(description=description, intake_channel="AgentCore")
    ticket.add_status_transition("OPEN", "Ticket created")
    _tickets[ticket.ticket_id] = ticket.to_dict()
    print(json.dumps({"step":"INTAKE","status":"DONE","ticket_id":ticket.ticket_id}))

    # Classify
    print(json.dumps({"step":"CLASSIFY","status":"START","model":os.environ["BEDROCK_MODEL_ID"]}))
    bedrock = boto3.client("bedrock-runtime", region_name=os.environ["BEDROCK_REGION"])

    from tools.classifier import SYSTEM_PROMPT, _parse
    body = json.dumps({"system":[{"text":SYSTEM_PROMPT}],
        "messages":[{"role":"user","content":[{"text":f"Classify this IT ticket:\n\n{description}"}]}],
        "inferenceConfig":{"maxTokens":256,"temperature":0.1}})
    r = bedrock.invoke_model(modelId=os.environ["BEDROCK_MODEL_ID"],
        body=body, contentType="application/json", accept="application/json")
    clf_text = json.loads(r["body"].read())["output"]["message"]["content"][0]["text"]
    c = _parse(clf_text)

    ticket.category = c["category"]
    ticket.severity  = c["severity"]
    ticket.classification_rationale = c["rationale"]
    ticket.add_status_transition("NEW", "Classification complete")
    _tickets[ticket.ticket_id] = ticket.to_dict()
    print(json.dumps({"step":"CLASSIFY","status":"DONE","category":ticket.category,"severity":ticket.severity}))

    # Pattern match
    print(json.dumps({"step":"PATTERN_MATCH","status":"START","category":ticket.category}))
    patterns = [TicketPattern.from_dict(p) for p in _PATTERNS.values() if p["category"] == ticket.category]
    routing = route_ticket(description, patterns)
    conf = routing["confidence"]
    print(json.dumps({"step":"PATTERN_MATCH","status":"DONE","result":routing["status"],"confidence":conf}))

    # Fix
    fix = None
    if routing["status"] == "RECURRING":
        ticket.pattern_id = routing["pattern"].pattern_id
        ticket.add_status_transition("RECURRING", f"Confidence: {conf}%")
        _tickets[ticket.ticket_id] = ticket.to_dict()
        res_data = _RESOLUTIONS.get(_PATTERNS.get(ticket.pattern_id, {}).get("resolution_id"))
        if res_data:
            fix = FixSuggestion(issue_summary=res_data["description_summary"],
                remediation_steps=res_data["applied_fix"], confidence="HIGH")
            print(json.dumps({"step":"KNOWLEDGE_BASE","status":"DONE","resolution_id":res_data["resolution_id"]}))

    if fix is None:
        print(json.dumps({"step":"SUB_AGENT","status":"START","agent":ticket.category}))
        from agent_core.cicd_agent import CICDAgent
        from agent_core.data_agent import DataETLAgent
        from agent_core.infra_agent import InfraAgent
        from agent_core.access_agent import AccessIAMAgent
        from agent_core.network_agent import NetworkAgent
        import agent_core.base_agent as _ba

        def _nova(system_prompt, prompt):
            b = json.dumps({"system":[{"text":system_prompt}],
                "messages":[{"role":"user","content":[{"text":prompt}]}],
                "inferenceConfig":{"maxTokens":1024,"temperature":0.2}})
            rr = bedrock.invoke_model(modelId=os.environ["BEDROCK_MODEL_ID"],
                body=b, contentType="application/json", accept="application/json")
            return json.loads(rr["body"].read())["output"]["message"]["content"][0]["text"]
        _ba._call_nova = _nova

        agents = {"CI/CD":CICDAgent(),"Data/ETL":DataETLAgent(),
                  "Infrastructure":InfraAgent(),"Access/IAM":AccessIAMAgent(),"Network":NetworkAgent()}
        agent = agents.get(ticket.category)
        if agent:
            fix = agent.investigate(ticket.ticket_id, ticket.description,
                ticket.category, ticket.severity)
        else:
            fix = FixSuggestion(issue_summary="Unknown category.",
                remediation_steps="Escalate to on-call.", confidence="LOW_CONFIDENCE")
        print(json.dumps({"step":"SUB_AGENT","status":"DONE","confidence":fix.confidence}))

    # Resolve
    ticket.fix_suggestion = fix.issue_summary
    ticket.fix_confidence  = fix.confidence
    ticket.resolved_at     = _now()
    ticket.resolved_by     = "agentcore"
    ticket.add_status_transition("RESOLVED", "Auto-resolved by AgentCore")
    _tickets[ticket.ticket_id] = ticket.to_dict()
    print(json.dumps({"step":"RESOLVE","status":"DONE","ticket_id":ticket.ticket_id,"final_status":"RESOLVED"}))

    return {
        "ticket_id":          ticket.ticket_id,
        "category":           ticket.category,
        "severity":           ticket.severity,
        "rationale":          ticket.classification_rationale,
        "pattern_status":     routing["status"],
        "pattern_confidence": conf,
        "issue_summary":      fix.issue_summary,
        "remediation_steps":  fix.remediation_steps,
        "confidence":         fix.confidence,
        "aws_resources":      fix.aws_resources,
        "final_status":       "RESOLVED",
    }

if __name__ == "__main__":
    app.run()
