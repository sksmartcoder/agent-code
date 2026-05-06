"""
IT Ticket Intelligence Agent — Main Entry Point
Kiro CLI + Agent Core + Master Agent + DynamoDB

Usage:
  python app.py submit "CodePipeline deploy failed — ECS task OOM killed"
  python app.py list-open
  python app.py approve TKT-ABC12345
  python app.py dashboard
"""
import sys
import json
from datetime import datetime, timezone

from tools.classifier import classify_ticket
from tools.pattern_matcher import detect_recurring
from tools.ticket_store import (
    create_ticket, get_ticket, update_ticket_status,
    get_open_tickets, get_pending_approvals, store_pattern,
    store_resolution, increment_pattern_occurrence
)
from tools.knowledge_base import lookup_runbook


def process_ticket(description: str) -> dict:
    """
    Main agent flow:
    1. Classify the ticket
    2. Check for recurring patterns
    3. Generate fix suggestion
    4. Create ticket in DynamoDB
    5. Route appropriately
    """
    print(f"\n{'='*60}")
    print(f"📥 NEW TICKET RECEIVED")
    print(f"{'='*60}")
    print(f"Description: {description}")
    print(f"{'='*60}\n")

    # Step 1: Classify
    print("🔍 Step 1: Classifying ticket...")
    classification = classify_ticket(description)
    print(f"   Category:  {classification['category']}")
    print(f"   Severity:  {classification['severity']}")
    print(f"   Team:      {classification['assigned_team']}")
    print(f"   Confidence: {classification['confidence']}")
    print(f"   Method:    {classification['method']}")
    print()

    # Step 2: Check for recurring patterns
    print("🔄 Step 2: Checking for recurring patterns...")
    pattern = detect_recurring(description, classification['category'])
    print(f"   Recurring: {pattern['is_recurring']}")
    print(f"   Similarity: {pattern['similarity_score']}")
    if pattern['is_recurring']:
        print(f"   Pattern ID: {pattern.get('pattern_id', 'N/A')}")
        print(f"   Occurrences: {pattern.get('occurrences', 'N/A')}")
    print()

    # Step 3: Generate fix suggestion
    print("💡 Step 3: Generating fix suggestion...")
    if pattern['is_recurring'] and pattern.get('proven_fix'):
        suggested_fix = pattern['proven_fix']
        fix_source = "PROVEN FIX (from past resolution)"
    else:
        # Look up runbook for new issues
        runbook = lookup_runbook(classification['category'], description)
        suggested_fix = f"[Agent-generated based on runbook]\n{runbook[:500]}"
        fix_source = "NEW SUGGESTION (from runbook)"
    print(f"   Source: {fix_source}")
    print(f"   Fix: {suggested_fix[:200]}...")
    print()

    # Step 4: Create ticket in DynamoDB
    print("📝 Step 4: Creating ticket in DynamoDB...")
    ticket = create_ticket(
        description=description,
        category=classification['category'],
        severity=classification['severity'],
        assigned_team=classification['assigned_team'],
        suggested_fix=suggested_fix,
        is_recurring=pattern['is_recurring'],
        matched_ticket_id=pattern.get('pattern_id') or pattern.get('matched_ticket_id')
    )
    print(f"   Ticket ID: {ticket['ticket_id']}")
    print(f"   Status:    {ticket['status']}")
    print()

    # Step 5: Route
    print("🚀 Step 5: Routing...")
    if pattern['is_recurring']:
        print(f"   ✅ RECURRING ISSUE — Auto-fix suggested, awaiting approval")
        print(f"   → Status: PENDING_APPROVAL")
        print(f"   → Team: {classification['assigned_team']} (notified)")
    elif classification['severity'] == 'P1':
        print(f"   🚨 P1 ESCALATION — Immediate attention required")
        print(f"   → Status: ESCALATED")
        print(f"   → Team: {classification['assigned_team']} (paged)")
        update_ticket_status(ticket['ticket_id'], ticket['created_at'], 'ESCALATED')
    else:
        print(f"   📋 NEW ISSUE — Routed for human review")
        print(f"   → Status: OPEN")
        print(f"   → Team: {classification['assigned_team']}")

    print(f"\n{'='*60}")
    print(f"✅ TICKET PROCESSED: {ticket['ticket_id']}")
    print(f"{'='*60}\n")

    return ticket


def approve_ticket(ticket_id: str, approver: str = "human-reviewer"):
    """Approve a pending fix and resolve the ticket."""
    ticket = get_ticket(ticket_id)
    if not ticket:
        print(f"❌ Ticket {ticket_id} not found")
        return

    if ticket['status'] != 'PENDING_APPROVAL':
        print(f"⚠️  Ticket {ticket_id} is not pending approval (status: {ticket['status']})")
        return

    updated = update_ticket_status(
        ticket_id=ticket_id,
        created_at=ticket['created_at'],
        status='RESOLVED',
        resolution=ticket.get('suggested_fix', 'Approved fix applied'),
        approved_by=approver
    )

    # Store resolution for future pattern matching
    if ticket.get('matched_ticket_id') and ticket['matched_ticket_id'] != 'NONE':
        store_resolution(
            ticket_id=ticket_id,
            pattern_id=ticket['matched_ticket_id'],
            fix_applied=ticket.get('suggested_fix', ''),
            success=True
        )

    print(f"\n✅ Ticket {ticket_id} APPROVED and RESOLVED")
    print(f"   Approved by: {approver}")
    print(f"   Resolution: {ticket.get('suggested_fix', '')[:100]}...")
    print(f"   Resolved at: {updated.get('resolved_at', 'now')}")


def reject_ticket(ticket_id: str, reason: str = ""):
    """Reject a suggested fix, reopen for manual investigation."""
    ticket = get_ticket(ticket_id)
    if not ticket:
        print(f"❌ Ticket {ticket_id} not found")
        return

    updated = update_ticket_status(
        ticket_id=ticket_id,
        created_at=ticket['created_at'],
        status='OPEN',
        resolution=f"Fix rejected: {reason}"
    )
    print(f"\n❌ Ticket {ticket_id} fix REJECTED — reopened for manual investigation")
    print(f"   Reason: {reason}")


def show_dashboard():
    """Show current ticket status overview."""
    open_tickets = get_open_tickets()
    pending = get_pending_approvals()

    print(f"\n{'='*60}")
    print(f"📊 IT TICKET DASHBOARD")
    print(f"{'='*60}")
    print(f"\n🔴 OPEN TICKETS ({len(open_tickets)})")
    for t in open_tickets[:10]:
        print(f"   [{t['severity']}] {t['ticket_id']} | {t['category']} | {t['description'][:50]}...")

    print(f"\n🟡 PENDING APPROVAL ({len(pending)})")
    for t in pending[:10]:
        print(f"   [{t['severity']}] {t['ticket_id']} | {t['category']} | {t['suggested_fix'][:50]}...")

    print(f"\n{'='*60}\n")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print('  python app.py submit "ticket description"')
        print('  python app.py approve TKT-XXXXXXXX')
        print('  python app.py reject TKT-XXXXXXXX "reason"')
        print('  python app.py list-open')
        print('  python app.py list-pending')
        print('  python app.py dashboard')
        return

    command = sys.argv[1]

    if command == 'submit':
        description = sys.argv[2] if len(sys.argv) > 2 else input("Enter ticket description: ")
        process_ticket(description)
    elif command == 'approve':
        ticket_id = sys.argv[2]
        approver = sys.argv[3] if len(sys.argv) > 3 else "human-reviewer"
        approve_ticket(ticket_id, approver)
    elif command == 'reject':
        ticket_id = sys.argv[2]
        reason = sys.argv[3] if len(sys.argv) > 3 else ""
        reject_ticket(ticket_id, reason)
    elif command == 'list-open':
        tickets = get_open_tickets()
        for t in tickets:
            print(f"[{t['severity']}] {t['ticket_id']} | {t['category']} | {t['description'][:60]}")
    elif command == 'list-pending':
        tickets = get_pending_approvals()
        for t in tickets:
            print(f"[{t['severity']}] {t['ticket_id']} | {t['category']} | {t['suggested_fix'][:60]}")
    elif command == 'dashboard':
        show_dashboard()
    else:
        print(f"Unknown command: {command}")


if __name__ == '__main__':
    main()
