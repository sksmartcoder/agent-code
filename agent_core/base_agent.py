from __future__ import annotations
import json, os, boto3
from strands import Agent
from strands.models import BedrockModel
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from tools.models import FixSuggestion
from tools.knowledge_base import get_runbook
from tools.tracer import log
from tools.agent_bus import bus, AgentMessage

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

def _call_nova(system_prompt: str, prompt: str) -> str:
    """Direct boto3 call for Nova models (bypasses Strands streaming issue)."""
    client = boto3.client("bedrock-runtime", region_name=config.BEDROCK_REGION)
    body = json.dumps({
        "system": [{"text": system_prompt}],
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": 1024, "temperature": 0.2},
    })
    r = client.invoke_model(
        modelId=config.BEDROCK_MODEL_ID, body=body,
        contentType="application/json", accept="application/json")
    return json.loads(r["body"].read())["output"]["message"]["content"][0]["text"]

class BaseSubAgent:
    domain = "Unknown"
    category = "Unknown"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Auto-register with bus when subclass is defined
        import sys
        if "agent_core" in sys.modules:
            pass  # registered lazily on first use

    def on_message(self, msg: AgentMessage) -> AgentMessage | None:
        """
        Handle incoming messages from other agents.
        Override in subclasses for custom inter-agent logic.
        """
        if msg.msg_type == "REQUEST":
            content = msg.content
            result = self.investigate(
                ticket_id=content.get("ticket_id", "unknown"),
                description=content.get("description", ""),
                category=content.get("category", self.category),
                severity=content.get("severity", "P3"),
            )
            return AgentMessage(
                sender=self.__class__.__name__,
                receiver=msg.sender,
                msg_type="RESPONSE",
                reply_to=msg.msg_id,
                content={
                    "issue_summary":    result.issue_summary,
                    "remediation_steps": result.remediation_steps,
                    "confidence":       result.confidence,
                    "aws_resources":    result.aws_resources,
                }
            )
        return None

    def ask_peer(self, peer_name: str, ticket_id: str,
                 description: str, category: str, severity: str) -> AgentMessage | None:
        """Send a REQUEST to a peer agent and return its RESPONSE."""
        msg = AgentMessage(
            sender=self.__class__.__name__,
            receiver=peer_name,
            msg_type="REQUEST",
            content={
                "ticket_id":   ticket_id,
                "description": description,
                "category":    category,
                "severity":    severity,
            }
        )
        return bus.send(msg)

    def notify_master(self, ticket_id: str, event: str, detail: str):
        """Send a NOTIFY to MasterAgent (e.g. escalation, extra context)."""
        bus.send(AgentMessage(
            sender=self.__class__.__name__,
            receiver="MasterAgent",
            msg_type="NOTIFY",
            content={"ticket_id": ticket_id, "event": event, "detail": detail}
        ))

    def investigate(self, ticket_id, description, category, severity, s3_client=None, bedrock_client=None):
        agent_name = self.__class__.__name__
        log(agent_name, "INVESTIGATE_START", f"ticket={ticket_id[:8]} category={category} severity={severity}", "START",
            inputs={"ticket_id": ticket_id, "category": category, "severity": severity})

        runbook = get_runbook(category, s3_client)
        has_runbook = runbook is not None
        log(agent_name, "RUNBOOK_FETCH", f"found={has_runbook} category={category}",
            "DONE" if has_runbook else "WARN")

        runbook_ctx = f"Relevant runbook:\n\n{runbook[:3000]}" if has_runbook else "No runbook available."
        system_prompt = (
            f"You are a specialist IT engineer for {self.domain}.\n"
            f"{runbook_ctx}\n"
            f"{FIX_JSON_SCHEMA}"
        )
        prompt = f"Ticket: {ticket_id}\nCategory: {category}\nSeverity: {severity}\nDescription: {description}"
        try:
            log(agent_name, "BEDROCK_INVOKE", f"model={os.environ.get('BEDROCK_MODEL_ID','nova')}", "START")
            if os.environ.get("USE_ANTHROPIC", "").lower() == "true":
                agent = Agent(model=_build_model(), system_prompt=system_prompt)
                suggestion = self._parse_fix(str(agent(prompt)))
            else:
                suggestion = self._parse_fix(_call_nova(system_prompt, prompt))
            log(agent_name, "FIX_GENERATED", f"confidence={'HIGH' if has_runbook else 'LOW'}", "DONE",
                outputs={"issue_summary": suggestion.issue_summary[:80]})
        except Exception as e:
            log(agent_name, "BEDROCK_ERROR", str(e)[:80], "ERROR")
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
