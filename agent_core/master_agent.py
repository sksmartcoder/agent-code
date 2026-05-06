from __future__ import annotations
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
        print(f"\n{SEP}\n  IT TICKET INTELLIGENCE AGENT\n{SEP}")
        print("\n[1/5] Creating ticket...")
        try:
            ticket = create_ticket(description, dynamodb=self.dynamodb)
        except ValidationError as e:
            print(f"  ✗ {e}")
            return {"ticket_id": None, "final_status": "REJECTED", "error": str(e)}
        print(f"  Ticket ID: {ticket.ticket_id}")

        print("\n[2/5] Classifying ticket...")
        c = classify_ticket(description, self.bedrock_client)
        ticket.category = c["category"]
        ticket.severity = c["severity"]
        ticket.classification_rationale = c["rationale"]
        ticket.add_status_transition("NEW", "Classification complete")
        update_ticket(ticket, self.dynamodb)
        print(f"  Category: {ticket.category}  |  Severity: {ticket.severity}")
        print(f"  Rationale: {ticket.classification_rationale}")

        print("\n[3/5] Checking for recurring patterns...")
        patterns = get_patterns_by_category(ticket.category, self.dynamodb)
        routing = route_ticket(description, patterns)

        if routing["status"] == "RECURRING":
            pattern = routing["pattern"]
            conf = routing["confidence"]
            print(f"  Match: Pattern {pattern.pattern_id} (confidence: {conf}%)")
            ticket.pattern_id = pattern.pattern_id
            ticket.add_status_transition("RECURRING", f"Confidence: {conf}%")
            update_ticket(ticket, self.dynamodb)
            print("\n[4/5] Fetching proven fix...")
            resolution = get_resolution_by_pattern(pattern.pattern_id, self.dynamodb)
            if resolution:
                fix = FixSuggestion(
                    issue_summary=resolution.description_summary,
                    remediation_steps=resolution.applied_fix,
                    confidence="HIGH")
            else:
                fix = self._delegate(ticket)
        else:
            print(f"  No match (best: {routing['confidence']}%). Delegating...")
            print(f"\n[4/5] {ticket.category} sub-agent investigating...")
            fix = self._delegate(ticket)

        print("\n[5/5] Awaiting approval...")
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
