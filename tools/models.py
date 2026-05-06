from __future__ import annotations
import json, uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

VALID_CATEGORIES = {"CI/CD", "Data/ETL", "Infrastructure", "Access/IAM", "Network", "Unknown"}
VALID_SEVERITIES = {"P1", "P2", "P3", "P4"}

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

@dataclass
class Ticket:
    description: str
    ticket_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    category: str = "Unknown"
    severity: str = "P3"
    status: str = "OPEN"
    pattern_id: Optional[str] = None
    fix_suggestion: Optional[str] = None
    fix_confidence: Optional[str] = None
    classification_rationale: Optional[str] = None
    intake_channel: str = "CLI"
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    status_history: list = field(default_factory=list)

    def add_status_transition(self, new_status, note=""):
        self.status_history.append({"from": self.status, "to": new_status, "timestamp": _now_iso(), "note": note})
        self.status = new_status
        self.updated_at = _now_iso()

    def to_dict(self): return asdict(self)
    def to_json(self): return json.dumps(self.to_dict(), indent=2, default=str)

    @classmethod
    def from_dict(cls, data):
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

@dataclass
class TicketPattern:
    category: str
    signature: str
    keywords: list
    resolution_id: str
    pattern_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurrence_count: int = 1
    last_seen: str = field(default_factory=_now_iso)

    def to_dict(self): return asdict(self)
    def to_json(self): return json.dumps(self.to_dict(), indent=2, default=str)

    @classmethod
    def from_dict(cls, data):
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

@dataclass
class Resolution:
    ticket_id: str
    category: str
    severity: str
    description_summary: str
    applied_fix: str
    resolution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pattern_id: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self): return asdict(self)
    def to_json(self): return json.dumps(self.to_dict(), indent=2, default=str)

    @classmethod
    def from_dict(cls, data):
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

@dataclass
class FixSuggestion:
    issue_summary: str
    remediation_steps: str
    confidence: str
    aws_resources: list = field(default_factory=list)

    def to_dict(self): return asdict(self)
