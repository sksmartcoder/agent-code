from __future__ import annotations
import re
from typing import Optional
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from tools.models import TicketPattern

def _tokenize(text):
    return set(re.findall(r"\b[a-z]{3,}\b", text.lower()))

def compute_confidence(description, pattern):
    desc_tokens = _tokenize(description)
    pattern_tokens = set(kw.lower() for kw in pattern.keywords)
    if not desc_tokens or not pattern_tokens:
        return 0
    intersection = desc_tokens & pattern_tokens
    union = desc_tokens | pattern_tokens
    jaccard = len(intersection) / len(union)
    keyword_hit_ratio = len(intersection) / len(pattern_tokens)
    return max(0, min(100, round((jaccard * 50) + (keyword_hit_ratio * 50))))

def find_best_match(description, patterns, threshold=None):
    if threshold is None:
        threshold = config.CONFIDENCE_THRESHOLD
    if not patterns:
        return None, 0
    best_pattern, best_score = None, 0
    for pattern in patterns:
        score = compute_confidence(description, pattern)
        if score > best_score:
            best_score = score
            best_pattern = pattern
    return best_pattern, best_score

def route_ticket(description, patterns):
    best_pattern, best_score = find_best_match(description, patterns)
    if best_score >= config.CONFIDENCE_THRESHOLD and best_pattern is not None:
        return {"status": "RECURRING", "pattern": best_pattern, "confidence": best_score}
    return {"status": "NEW", "pattern": None, "confidence": best_score}
