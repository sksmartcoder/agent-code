from __future__ import annotations
import json, os
from strands import Agent
from strands.models import BedrockModel
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from tools.models import FixSuggestion
from tools.knowledge_base import get_runbook

FIX_JSON_SCHEMA = (
    "Respond ONLY with JSON: "
    '{"issue_summary":"<root cause>","remediation_steps":"<numbered steps>","aws_resources":["<ARNs>"]}'
)

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
        runbook_ctx = f"Relevant runbook:\n\n{runbook[:3000]}" if has_runbook else "No runbook available."
        system_prompt = (
            f"You are a specialist IT engineer for {self.domain}.\n"
            f"{runbook_ctx}\n"
            f"{FIX_JSON_SCHEMA}"
        )
        prompt = f"Ticket: {ticket_id}\nCategory: {category}\nSeverity: {severity}\nDescription: {description}"
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
