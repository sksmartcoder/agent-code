"""
DynamoDB Ticket Store — CRUD operations for the IT Ticket Agent.
This replaces Jira as the ticket management system.
"""
import boto3
import uuid
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key, Attr

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
tickets_table = dynamodb.Table('it_tickets')
patterns_table = dynamodb.Table('ticket_patterns')
resolutions_table = dynamodb.Table('ticket_resolutions')


def create_ticket(description: str, category: str, severity: str,
                  assigned_team: str, suggested_fix: str = None,
                  is_recurring: bool = False, matched_ticket_id: str = None) -> dict:
    """Create a new ticket in DynamoDB."""
    ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    item = {
        'ticket_id': ticket_id,
        'created_at': now,
        'updated_at': now,
        'description': description,
        'category': category,
        'severity': severity,
        'assigned_team': assigned_team,
        'status': 'PENDING_APPROVAL' if is_recurring else 'OPEN',
        'is_recurring': is_recurring,
        'matched_ticket_id': matched_ticket_id or 'NONE',
        'suggested_fix': suggested_fix or '',
        'resolution': '',
        'approved_by': '',
        'resolved_at': '',
        'notes': [],
    }

    tickets_table.put_item(Item=item)
    return item


def get_ticket(ticket_id: str) -> dict:
    """Get a ticket by ID."""
    response = tickets_table.query(
        KeyConditionExpression=Key('ticket_id').eq(ticket_id),
        ScanIndexForward=False,
        Limit=1
    )
    items = response.get('Items', [])
    return items[0] if items else None


def update_ticket_status(ticket_id: str, created_at: str, status: str,
                         resolution: str = None, approved_by: str = None) -> dict:
    """Update ticket status (approve, resolve, escalate)."""
    now = datetime.now(timezone.utc).isoformat()
    update_expr = "SET #s = :status, updated_at = :now"
    expr_values = {':status': status, ':now': now}
    expr_names = {'#s': 'status'}

    if resolution:
        update_expr += ", resolution = :res"
        expr_values[':res'] = resolution
    if approved_by:
        update_expr += ", approved_by = :approver"
        expr_values[':approver'] = approved_by
    if status == 'RESOLVED':
        update_expr += ", resolved_at = :resolved"
        expr_values[':resolved'] = now

    response = tickets_table.update_item(
        Key={'ticket_id': ticket_id, 'created_at': created_at},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
        ReturnValues='ALL_NEW'
    )
    return response['Attributes']


def search_tickets_by_category(category: str, limit: int = 10) -> list:
    """Search tickets by category (for pattern matching)."""
    response = tickets_table.query(
        IndexName='category-severity-index',
        KeyConditionExpression=Key('category').eq(category),
        ScanIndexForward=False,
        Limit=limit
    )
    return response.get('Items', [])


def get_open_tickets() -> list:
    """Get all open tickets."""
    response = tickets_table.query(
        IndexName='status-index',
        KeyConditionExpression=Key('status').eq('OPEN'),
        ScanIndexForward=False
    )
    return response.get('Items', [])


def get_pending_approvals() -> list:
    """Get tickets waiting for human approval."""
    response = tickets_table.query(
        IndexName='status-index',
        KeyConditionExpression=Key('status').eq('PENDING_APPROVAL'),
        ScanIndexForward=False
    )
    return response.get('Items', [])


def get_team_tickets(team: str) -> list:
    """Get tickets assigned to a specific team."""
    response = tickets_table.query(
        IndexName='team-index',
        KeyConditionExpression=Key('assigned_team').eq(team),
        ScanIndexForward=False
    )
    return response.get('Items', [])


# --- Pattern Management ---

def store_pattern(category: str, keywords: list, description_template: str,
                  proven_fix: str, occurrences: int = 1) -> dict:
    """Store a recurring pattern for future matching."""
    pattern_id = f"PAT-{uuid.uuid4().hex[:8].upper()}"
    item = {
        'pattern_id': pattern_id,
        'category': category,
        'keywords': keywords,
        'description_template': description_template,
        'proven_fix': proven_fix,
        'occurrences': occurrences,
        'last_seen': datetime.now(timezone.utc).isoformat(),
        'success_rate': 1.0,
    }
    patterns_table.put_item(Item=item)
    return item


def get_patterns_by_category(category: str) -> list:
    """Get all known patterns for a category."""
    response = patterns_table.query(
        IndexName='category-index',
        KeyConditionExpression=Key('category').eq(category)
    )
    return response.get('Items', [])


def increment_pattern_occurrence(pattern_id: str):
    """Increment occurrence count when pattern is matched again."""
    patterns_table.update_item(
        Key={'pattern_id': pattern_id},
        UpdateExpression="SET occurrences = occurrences + :inc, last_seen = :now",
        ExpressionAttributeValues={
            ':inc': 1,
            ':now': datetime.now(timezone.utc).isoformat()
        }
    )


# --- Resolution Management ---

def store_resolution(ticket_id: str, pattern_id: str, fix_applied: str,
                     success: bool = True) -> dict:
    """Store a resolution for future reference."""
    resolution_id = f"RES-{uuid.uuid4().hex[:8].upper()}"
    item = {
        'resolution_id': resolution_id,
        'resolved_at': datetime.now(timezone.utc).isoformat(),
        'ticket_id': ticket_id,
        'pattern_id': pattern_id,
        'fix_applied': fix_applied,
        'success': success,
    }
    resolutions_table.put_item(Item=item)
    return item


def get_resolutions_for_pattern(pattern_id: str, limit: int = 5) -> list:
    """Get past resolutions for a known pattern."""
    response = resolutions_table.query(
        IndexName='pattern-index',
        KeyConditionExpression=Key('pattern_id').eq(pattern_id),
        ScanIndexForward=False,
        Limit=limit
    )
    return response.get('Items', [])
