from __future__ import annotations
from datetime import datetime, timezone
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools.models import Ticket, FixSuggestion
from tools.ticket_store import update_ticket, log_resolution

R  = "\033[0m";  B  = "\033[1m"
CY = "\033[96m"; GR = "\033[92m"; YL = "\033[93m"; RD = "\033[91m"; BL = "\033[94m"
SEP  = f"{CY}{'─' * 60}{R}"
SEP2 = f"{BL}{'─' * 60}{R}"

SEVERITY_COLOR = {"P1": RD, "P2": YL, "P3": GR, "P4": BL}

def present_fix_and_get_approval(ticket, fix, dynamodb=None):
    _display_fix(ticket, fix)
    ticket.add_status_transition("PENDING_APPROVAL", "Awaiting operator approval")
    update_ticket(ticket, dynamodb)
    decision = _prompt_decision()
    return _handle_approve(ticket, fix, dynamodb) if decision == "approve" else _handle_reject(ticket, dynamodb)

def _display_fix(ticket, fix):
    conf_str = f"{GR}{B}✓ HIGH{R}" if fix.confidence == "HIGH" else f"{YL}{B}⚠ LOW CONFIDENCE{R}"
    sev_col  = SEVERITY_COLOR.get(ticket.severity, R)
    print(f"\n{SEP2}")
    print(f"  {B}{BL}🔍  FIX SUGGESTION{R}")
    print(SEP2)
    print(f"  {B}Ticket  :{R} {ticket.ticket_id}")
    print(f"  {B}Category:{R} {ticket.category}   {B}Severity:{R} {sev_col}{B}{ticket.severity}{R}")
    print(f"  {B}Confidence:{R} {conf_str}")
    print(SEP2)
    print(f"\n  {B}📋 Issue:{R}")
    print(f"     {fix.issue_summary}")
    print(f"\n  {B}🛠  Remediation Steps:{R}")
    for line in fix.remediation_steps.splitlines():
        if line.strip():
            print(f"     {GR}›{R} {line.strip()}")
    if fix.aws_resources:
        print(f"\n  {B}☁  AWS Resources:{R}")
        for r in fix.aws_resources:
            print(f"     {BL}•{R} {r}")
    print(f"\n{SEP2}")

def _prompt_decision():
    print(f"\n  {YL}Operator action required:{R}")
    while True:
        try:
            raw = input(f"  {B}[approve / reject]{R}: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "reject"
        if raw in ("approve", "reject"):
            return raw
        print(f"  {RD}Please type 'approve' or 'reject'.{R}")

def _handle_approve(ticket, fix, dynamodb):
    ticket.fix_suggestion = fix.issue_summary
    ticket.fix_confidence = fix.confidence
    ticket.resolved_at = datetime.now(timezone.utc).isoformat()
    ticket.resolved_by = "operator"
    ticket.add_status_transition("RESOLVED", "Operator approved fix")
    update_ticket(ticket, dynamodb)
    resolution = log_resolution(ticket, fix.remediation_steps, dynamodb)
    print(f"\n  {GR}{B}✅  Approved & Resolved{R}")
    print(f"  Resolution ID: {B}{resolution.resolution_id}{R}")
    return "RESOLVED"

def _handle_reject(ticket, dynamodb):
    try:
        reason = input(f"  {RD}Rejection reason:{R} ").strip()
    except (EOFError, KeyboardInterrupt):
        reason = "No reason provided"
    ticket.rejection_reason = reason or "No reason provided"
    ticket.add_status_transition("REJECTED", f"Rejected: {ticket.rejection_reason}")
    update_ticket(ticket, dynamodb)
    print(f"\n  {RD}{B}❌  Ticket Rejected{R}")
    return "REJECTED"
