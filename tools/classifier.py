from __future__ import annotations
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
    '{"category": "<CI/CD|Data/ETL|Infrastructure|Access/IAM|Network|Unknown>", "severity": "<P1|P2|P3|P4>", "rationale": "<one sentence>"}' "\n"
    "Severity: P1=production down, P2=major impact, P3=minor, P4=cosmetic\n"
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
        return _parse(str(agent(f"Classify this IT ticket:\n\n{description}")))
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
