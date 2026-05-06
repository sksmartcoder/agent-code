from __future__ import annotations
from datetime import datetime, timezone
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools.models import Ticket, FixSuggestion
from tools.ticket_store import update_ticket, log_resolution

SEP = "─" * 60

def present_fix_and_get_approval(ticket, fix, dynamodb=None):
    _display_fix(ticket, fix)
    ticket.add_status_transition("PENDING_APPROVAL", "Awaiting operator approval")
    update_ticket(ticket, dynamodb)
    decision = _prompt_decision()
    return _handle_approve(ticket, fix, dynamodb) if decision == "approve" else _handle_reject(ticket, dynamodb)

def _display_fix(ticket, fix):
    conf = "✓ HIGH" if fix.confidence == "HIGH" else "⚠ LOW CONFIDENCE"
    print(f"\n{SEP}\n  FIX SUGGESTION\n{SEP}")
    print(f"  Ticket ID  : {ticket.ticket_id}")
    print(f"  Category   : {ticket.category}  |  Severity: {ticket.severity}  |  Confidence: {conf}")
    print(f"{SEP}\n  Issue: {fix.issue_summary}\n\n  Fix:")
    for line in fix.remediation_steps.splitlines():
        print(f"    {line}")
    if fix.aws_resources:
        print(f"\n  AWS Resources: {', '.join(fix.aws_resources)}")
    print(SEP)

def _prompt_decision():
    while True:
        try:
            raw = input("\n  [approve / reject]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "reject"
        if raw in ("approve", "reject"):
            return raw
        print("  Please type 'approve' or 'reject'.")

def _handle_approve(ticket, fix, dynamodb):
    ticket.fix_suggestion = fix.issue_summary
    ticket.fix_confidence = fix.confidence
    ticket.resolved_at = datetime.now(timezone.utc).isoformat()
    ticket.resolved_by = "operator"
    ticket.add_status_transition("RESOLVED", "Operator approved fix")
    update_ticket(ticket, dynamodb)
    resolution = log_resolution(ticket, fix.remediation_steps, dynamodb)
    print(f"\n  ✓ Resolved. Resolution ID: {resolution.resolution_id}")
    return "RESOLVED"

def _handle_reject(ticket, dynamodb):
    try:
        reason = input("  Rejection reason: ").strip()
    except (EOFError, KeyboardInterrupt):
        reason = "No reason provided"
    ticket.rejection_reason = reason or "No reason provided"
    ticket.add_status_transition("REJECTED", f"Rejected: {ticket.rejection_reason}")
    update_ticket(ticket, dynamodb)
    print("\n  ✗ Rejected.")
    return "REJECTED"
