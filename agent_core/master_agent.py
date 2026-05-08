from __future__ import annotations
import sys, os, time, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools.ticket_store import create_ticket, update_ticket, get_patterns_by_category, get_resolution_by_pattern, ValidationError
from tools.classifier import classify_ticket
from tools.pattern_matcher import route_ticket
from tools.models import FixSuggestion
from tools.notifier import present_fix_and_get_approval
from tools.tracer import start_trace, log, end_trace
from agent_core.cicd_agent import CICDAgent
from agent_core.data_agent import DataETLAgent
from agent_core.infra_agent import InfraAgent
from agent_core.access_agent import AccessIAMAgent
from agent_core.network_agent import NetworkAgent

# ── ANSI colours ──────────────────────────────────────────────────────────────
R  = "\033[0m"       # reset
B  = "\033[1m"       # bold
CY = "\033[96m"      # cyan
GR = "\033[92m"      # green
YL = "\033[93m"      # yellow
RD = "\033[91m"      # red
BL = "\033[94m"      # blue
MG = "\033[95m"      # magenta

SEP  = f"{CY}{'─' * 60}{R}"
SEP2 = f"{BL}{'─' * 60}{R}"

SEVERITY_COLOR = {"P1": RD, "P2": YL, "P3": GR, "P4": BL}
CATEGORY_ICON  = {
    "CI/CD": "🔧", "Data/ETL": "🗄️ ", "Infrastructure": "🖥️ ",
    "Access/IAM": "🔑", "Network": "🌐", "Unknown": "❓",
}

SUB_AGENTS = {
    "CI/CD": CICDAgent(), "Data/ETL": DataETLAgent(),
    "Infrastructure": InfraAgent(), "Access/IAM": AccessIAMAgent(), "Network": NetworkAgent(),
}


class _Spinner:
    """Simple CLI spinner for long-running steps."""
    def __init__(self, msg):
        self._msg = msg
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._spin, daemon=True)

    def _spin(self):
        frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
        i = 0
        while not self._stop.is_set():
            print(f"\r  {CY}{frames[i % len(frames)]}{R}  {self._msg}", end="", flush=True)
            time.sleep(0.1)
            i += 1

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._t.join()
        print("\r" + " " * (len(self._msg) + 10) + "\r", end="")


class MasterAgent:
    def __init__(self, dynamodb=None, bedrock_client=None, s3_client=None):
        self.dynamodb = dynamodb
        self.bedrock_client = bedrock_client
        self.s3_client = s3_client

    def process(self, description):
        print(f"\n{SEP}")
        print(f"  {B}{CY}🎫  IT TICKET INTELLIGENCE AGENT{R}")
        print(f"  {BL}Powered by Amazon Bedrock + Strands{R}")
        print(SEP)

        # ── Step 1: Intake ────────────────────────────────────────────────────
        print(f"\n  {B}[1/5]{R} Creating ticket...")
        try:
            ticket = create_ticket(description, dynamodb=self.dynamodb)
        except ValidationError as e:
            print(f"  {RD}✗ {e}{R}")
            return {"ticket_id": None, "final_status": "REJECTED", "error": str(e)}
        start_trace(ticket.ticket_id, description)
        log("MasterAgent", "TICKET_CREATED", f"id={ticket.ticket_id[:8]}", "DONE",
            outputs={"ticket_id": ticket.ticket_id})
        print(f"  {GR}✓{R} Ticket ID: {B}{ticket.ticket_id}{R}")

        # ── Step 2: Classify ──────────────────────────────────────────────────
        print(f"\n  {B}[2/5]{R} Classifying with AI...")
        log("Classifier", "BEDROCK_INVOKE", "model=nova-lite", "START",
            inputs={"description": description[:80]})
        with _Spinner("Calling Amazon Bedrock Nova..."):
            c = classify_ticket(description, self.bedrock_client)

        ticket.category = c["category"]
        ticket.severity = c["severity"]
        ticket.classification_rationale = c["rationale"]
        ticket.add_status_transition("NEW", "Classification complete")
        update_ticket(ticket, self.dynamodb)
        log("Classifier", "CLASSIFIED", f"category={ticket.category} severity={ticket.severity}", "DONE",
            outputs={"category": ticket.category, "severity": ticket.severity, "rationale": c["rationale"]})

        sev_col = SEVERITY_COLOR.get(ticket.severity, R)
        icon = CATEGORY_ICON.get(ticket.category, "")
        print(f"  {GR}✓{R} Category : {B}{icon} {ticket.category}{R}")
        print(f"  {GR}✓{R} Severity : {sev_col}{B}{ticket.severity}{R}")
        print(f"  {GR}✓{R} Rationale: {ticket.classification_rationale}")

        # ── Step 3: Pattern Match ─────────────────────────────────────────────
        print(f"\n  {B}[3/5]{R} Checking for recurring patterns...")
        log("PatternMatcher", "SCAN_PATTERNS", f"category={ticket.category}", "START")
        patterns = get_patterns_by_category(ticket.category, self.dynamodb)
        routing = route_ticket(description, patterns)
        log("PatternMatcher", "MATCH_RESULT",
            f"status={routing['status']} confidence={routing['confidence']}%", "DONE",
            outputs={"status": routing["status"], "confidence": routing["confidence"]})

        if routing["status"] == "RECURRING":
            pattern = routing["pattern"]
            conf = routing["confidence"]
            bar = _conf_bar(conf)
            print(f"  {GR}✓ RECURRING PATTERN DETECTED{R}")
            print(f"    Pattern   : {B}{pattern.pattern_id}{R}")
            print(f"    Confidence: {bar} {B}{conf}%{R}")
            ticket.pattern_id = pattern.pattern_id
            ticket.add_status_transition("RECURRING", f"Confidence: {conf}%")
            update_ticket(ticket, self.dynamodb)

            print(f"\n  {B}[4/5]{R} Fetching proven fix from knowledge base...")
            log("KnowledgeBase", "FETCH_RESOLUTION", f"pattern={pattern.pattern_id[:8]}", "START")
            resolution = get_resolution_by_pattern(pattern.pattern_id, self.dynamodb)
            if resolution:
                fix = FixSuggestion(
                    issue_summary=resolution.description_summary,
                    remediation_steps=resolution.applied_fix,
                    confidence="HIGH")
                log("KnowledgeBase", "RESOLUTION_FOUND", f"id={resolution.resolution_id[:8]}", "DONE")
                print(f"  {GR}✓{R} Resolution found: {B}{resolution.resolution_id}{R}")
            else:
                log("KnowledgeBase", "NO_RESOLUTION", "falling back to sub-agent", "WARN")
                fix = self._delegate(ticket)
        else:
            conf = routing["confidence"]
            bar = _conf_bar(conf)
            print(f"  {YL}⚡ NEW ISSUE{R} — no pattern match")
            print(f"    Best confidence: {bar} {conf}%")
            print(f"\n  {B}[4/5]{R} Delegating to {B}{icon} {ticket.category}{R} sub-agent...")
            log("MasterAgent", "DELEGATE_TO_SUBAGENT", f"agent={ticket.category}", "START")
            with _Spinner(f"AI sub-agent investigating..."):
                fix = self._delegate(ticket)
            log("MasterAgent", "SUBAGENT_COMPLETE", f"confidence={fix.confidence}", "DONE",
                outputs={"issue_summary": fix.issue_summary[:80]})
            print(f"  {GR}✓{R} Sub-agent analysis complete")

        # ── Step 5: Approval ──────────────────────────────────────────────────
        print(f"\n  {B}[5/5]{R} Operator review required...")
        log("MasterAgent", "AWAITING_APPROVAL", "status=PENDING_APPROVAL", "INFO")
        final_status = present_fix_and_get_approval(ticket, fix, self.dynamodb)
        log("MasterAgent", "APPROVAL_DECISION", f"status={final_status}", "DONE")
        end_trace(final_status, ticket.ticket_id)

        _print_final(ticket.ticket_id, final_status)
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


def _conf_bar(score: int) -> str:
    filled = round(score / 10)
    color = GR if score >= 80 else YL if score >= 50 else RD
    return f"{color}{'█' * filled}{'░' * (10 - filled)}{R}"


def _print_final(ticket_id, status):
    print(f"\n{SEP}")
    if status == "RESOLVED":
        print(f"  {GR}{B}✅  TICKET RESOLVED{R}")
    elif status == "REJECTED":
        print(f"  {RD}{B}❌  TICKET REJECTED{R}")
    else:
        print(f"  {YL}{B}⚠  STATUS: {status}{R}")
    print(f"  Ticket ID: {B}{ticket_id}{R}")
    print(SEP)
