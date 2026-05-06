from __future__ import annotations
import re, boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime, timezone
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from tools.models import Ticket, TicketPattern, Resolution

class ValidationError(ValueError):
    pass

def validate_description(description):
    if not description or not description.strip():
        raise ValidationError("Ticket description must not be empty or whitespace-only.")

def _get_table(table_name, dynamodb=None):
    if dynamodb is None:
        dynamodb = boto3.resource("dynamodb", region_name=config.REGION)
    return dynamodb.Table(table_name)

def create_ticket(description, intake_channel="CLI", dynamodb=None):
    validate_description(description)
    ticket = Ticket(description=description, intake_channel=intake_channel)
    ticket.add_status_transition("OPEN", "Ticket created")
    _get_table(config.TICKETS_TABLE, dynamodb).put_item(Item=ticket.to_dict())
    return ticket

def get_ticket(ticket_id, dynamodb=None):
    r = _get_table(config.TICKETS_TABLE, dynamodb).get_item(Key={"ticket_id": ticket_id})
    item = r.get("Item")
    return Ticket.from_dict(item) if item else None

def update_ticket(ticket, dynamodb=None):
    _get_table(config.TICKETS_TABLE, dynamodb).put_item(Item=ticket.to_dict())

def list_tickets_by_category(category, status=None, dynamodb=None):
    table = _get_table(config.TICKETS_TABLE, dynamodb)
    if status:
        r = table.query(IndexName="category-status-index",
            KeyConditionExpression=Key("category").eq(category) & Key("status").eq(status))
    else:
        r = table.query(IndexName="category-status-index",
            KeyConditionExpression=Key("category").eq(category))
    return [Ticket.from_dict(i) for i in r.get("Items", [])]

def get_patterns_by_category(category, dynamodb=None):
    r = _get_table(config.PATTERNS_TABLE, dynamodb).query(
        IndexName="category-index",
        KeyConditionExpression=Key("category").eq(category))
    return [TicketPattern.from_dict(i) for i in r.get("Items", [])]

def create_pattern(pattern, dynamodb=None):
    _get_table(config.PATTERNS_TABLE, dynamodb).put_item(Item=pattern.to_dict())

def increment_pattern_occurrence(pattern_id, dynamodb=None):
    _get_table(config.PATTERNS_TABLE, dynamodb).update_item(
        Key={"pattern_id": pattern_id},
        UpdateExpression="SET occurrence_count = occurrence_count + :inc, last_seen = :ts",
        ExpressionAttributeValues={":inc": 1, ":ts": datetime.now(timezone.utc).isoformat()},
    )

def create_resolution(resolution, dynamodb=None):
    _get_table(config.RESOLUTIONS_TABLE, dynamodb).put_item(Item=resolution.to_dict())

def get_resolution_by_pattern(pattern_id, dynamodb=None):
    r = _get_table(config.PATTERNS_TABLE, dynamodb).get_item(Key={"pattern_id": pattern_id})
    item = r.get("Item")
    if not item:
        return None
    res_id = item.get("resolution_id")
    if not res_id:
        return None
    r2 = _get_table(config.RESOLUTIONS_TABLE, dynamodb).get_item(Key={"resolution_id": res_id})
    item2 = r2.get("Item")
    return Resolution.from_dict(item2) if item2 else None

def log_resolution(ticket, applied_fix, dynamodb=None):
    resolution = Resolution(
        ticket_id=ticket.ticket_id, category=ticket.category, severity=ticket.severity,
        description_summary=ticket.description[:500], applied_fix=applied_fix,
        pattern_id=ticket.pattern_id,
    )
    create_resolution(resolution, dynamodb)
    if ticket.status == "RECURRING" and ticket.pattern_id:
        increment_pattern_occurrence(ticket.pattern_id, dynamodb)
    elif ticket.status in ("NEW", "PENDING_APPROVAL", "APPROVED"):
        words = list(set(re.findall(r"\b[a-zA-Z]{5,}\b", ticket.description.lower())))[:20]
        create_pattern(TicketPattern(
            category=ticket.category, signature=ticket.description[:200],
            keywords=words, resolution_id=resolution.resolution_id), dynamodb)
    return resolution
