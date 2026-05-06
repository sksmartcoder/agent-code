"""
Pattern Matcher — Detects recurring issues by comparing incoming tickets
against known patterns in DynamoDB.
"""
from difflib import SequenceMatcher
from tools.ticket_store import (
    get_patterns_by_category,
    search_tickets_by_category,
    increment_pattern_occurrence,
    get_resolutions_for_pattern
)


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate text similarity between two ticket descriptions."""
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


def extract_keywords(description: str) -> list:
    """Extract key terms from a ticket description."""
    stop_words = {'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or',
                  'but', 'in', 'with', 'to', 'for', 'of', 'not', 'from', 'it',
                  'this', 'that', 'was', 'are', 'been', 'has', 'have', 'had',
                  'can', 'could', 'would', 'should', 'will', 'just', 'our'}
    words = description.lower().replace(',', '').replace('.', '').split()
    return [w for w in words if w not in stop_words and len(w) > 2]


def match_against_patterns(description: str, category: str, threshold: float = 0.6) -> dict:
    """
    Match a ticket description against known patterns.
    Returns match result with confidence score.
    """
    patterns = get_patterns_by_category(category)
    incoming_keywords = set(extract_keywords(description))

    best_match = None
    best_score = 0.0

    for pattern in patterns:
        # Keyword overlap score
        pattern_keywords = set(pattern.get('keywords', []))
        if pattern_keywords:
            keyword_overlap = len(incoming_keywords & pattern_keywords) / max(len(pattern_keywords), 1)
        else:
            keyword_overlap = 0.0

        # Text similarity score
        text_sim = calculate_similarity(description, pattern.get('description_template', ''))

        # Combined score (weighted)
        combined_score = (keyword_overlap * 0.4) + (text_sim * 0.6)

        if combined_score > best_score:
            best_score = combined_score
            best_match = pattern

    if best_match and best_score >= threshold:
        # Get proven fix for this pattern
        resolutions = get_resolutions_for_pattern(best_match['pattern_id'], limit=3)
        proven_fix = best_match.get('proven_fix', '')
        if resolutions:
            # Use most recent successful resolution
            successful = [r for r in resolutions if r.get('success', False)]
            if successful:
                proven_fix = successful[0].get('fix_applied', proven_fix)

        return {
            'is_recurring': True,
            'pattern_id': best_match['pattern_id'],
            'similarity_score': round(best_score, 3),
            'occurrences': best_match.get('occurrences', 0),
            'proven_fix': proven_fix,
            'last_seen': best_match.get('last_seen', ''),
            'success_rate': best_match.get('success_rate', 0.0),
        }

    return {
        'is_recurring': False,
        'pattern_id': None,
        'similarity_score': round(best_score, 3),
        'occurrences': 0,
        'proven_fix': None,
        'last_seen': None,
        'success_rate': 0.0,
    }


def match_against_history(description: str, category: str, threshold: float = 0.7) -> dict:
    """
    Fallback: match against raw ticket history if no pattern exists.
    Useful for detecting emerging patterns.
    """
    past_tickets = search_tickets_by_category(category, limit=20)

    best_match = None
    best_score = 0.0

    for ticket in past_tickets:
        if ticket.get('status') != 'RESOLVED':
            continue
        score = calculate_similarity(description, ticket.get('description', ''))
        if score > best_score:
            best_score = score
            best_match = ticket

    if best_match and best_score >= threshold:
        return {
            'is_recurring': True,
            'matched_ticket_id': best_match['ticket_id'],
            'similarity_score': round(best_score, 3),
            'past_resolution': best_match.get('resolution', ''),
            'source': 'ticket_history',
        }

    return {
        'is_recurring': False,
        'matched_ticket_id': None,
        'similarity_score': round(best_score, 3),
        'past_resolution': None,
        'source': 'ticket_history',
    }


def detect_recurring(description: str, category: str) -> dict:
    """
    Main entry point: check patterns first, then fall back to history.
    Returns the best match with all context needed for the agent.
    """
    # First: check known patterns
    pattern_result = match_against_patterns(description, category)
    if pattern_result['is_recurring']:
        increment_pattern_occurrence(pattern_result['pattern_id'])
        return pattern_result

    # Fallback: check raw ticket history
    history_result = match_against_history(description, category)
    return history_result
