"""
Ticket Classifier — Categorizes and assigns severity to incoming tickets.
Uses keyword matching as a fast first-pass, with LLM fallback for ambiguous cases.
"""
import json
import boto3

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

# Keyword-based classification rules (fast path)
CATEGORY_KEYWORDS = {
    'CI/CD': [
        'pipeline', 'codepipeline', 'codebuild', 'deploy', 'deployment',
        'build', 'ecs', 'ecr', 'docker', 'container', 'rollback',
        'artifact', 'release', 'ci', 'cd', 'github actions', 'jenkins',
        'terraform apply', 'cloudformation', 'stack', 'oom killed'
    ],
    'Data/ETL': [
        'glue', 'etl', 'data', 'redshift', 'athena', 'crawler',
        'dashboard', 'tableau', 'quicksight', 'schema', 'column',
        'null', 'duplicate', 'partition', 'query', 'sql', 'dbt',
        'airflow', 'data quality', 'stale', 'refresh', 'load failed'
    ],
    'Infrastructure': [
        'ec2', 'instance', 'disk', 'ebs', 'volume', 'cpu', 'memory',
        'scaling', 'autoscaling', 'rds', 'database', 'snapshot',
        'cloudwatch', 'alarm', 'unreachable', 'down', 'capacity',
        'storage', 'iops', 'throughput'
    ],
    'Access/IAM': [
        'permission', 'denied', 'iam', 'role', 'policy', 'access',
        'assume role', 'forbidden', '403', 'unauthorized', 'sso',
        'credentials', 'kms', 'encrypt', 'decrypt', 'secret',
        'token', 'expired', 'mfa'
    ],
    'Network': [
        'security group', 'nacl', 'vpc', 'subnet', 'route', 'dns',
        'load balancer', 'alb', 'nlb', 'target group', 'health check',
        'timeout', 'connection refused', 'port', '503', '502',
        'vpn', 'peering', 'transit gateway', 'nat', 'api gateway'
    ],
    'Application': [
        'lambda', '500', '5xx', 'error', 'exception', 'crash',
        'cold start', 'timeout', 'memory', 'api', 'endpoint',
        'response time', 'latency', 'throttle', 'rate limit',
        'sqs', 'sns', 'queue', 'dead letter'
    ],
}

SEVERITY_KEYWORDS = {
    'P1': ['down', 'outage', 'production', 'critical', 'security breach',
           'data loss', 'revenue', 'all users', 'complete failure'],
    'P2': ['failed', 'broken', 'major', 'significant', 'blocking',
           'multiple users', 'high impact', 'urgent'],
    'P3': ['degraded', 'slow', 'intermittent', 'workaround',
           'some users', 'medium', 'performance'],
    'P4': ['minor', 'cosmetic', 'documentation', 'enhancement',
           'low priority', 'when possible', 'nice to have'],
}

TEAM_MAP = {
    'CI/CD': 'DevOps Engineering',
    'Data/ETL': 'Data Engineering',
    'Infrastructure': 'Cloud Operations',
    'Access/IAM': 'Security Operations',
    'Network': 'Network Engineering',
    'Application': 'Application Support',
}


def classify_by_keywords(description: str) -> dict:
    """Fast keyword-based classification."""
    desc_lower = description.lower()
    scores = {}

    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in desc_lower)
        scores[category] = score

    best_category = max(scores, key=scores.get)
    confidence = scores[best_category] / max(len(CATEGORY_KEYWORDS[best_category]) * 0.3, 1)
    confidence = min(confidence, 1.0)

    return {
        'category': best_category,
        'confidence': round(confidence, 2),
        'scores': scores,
    }


def classify_severity(description: str) -> str:
    """Determine severity from keywords."""
    desc_lower = description.lower()
    for severity, keywords in SEVERITY_KEYWORDS.items():
        if any(kw in desc_lower for kw in keywords):
            return severity
    return 'P3'  # Default to medium


def classify_with_llm(description: str) -> dict:
    """Use Bedrock LLM for ambiguous tickets where keyword matching is low confidence."""
    prompt = f"""Classify this IT support ticket. Return JSON only.

Ticket: "{description}"

Categories: CI/CD, Data/ETL, Infrastructure, Access/IAM, Network, Application
Severity: P1 (critical/production down), P2 (high/major broken), P3 (medium/degraded), P4 (low/minor)

Return:
{{"category": "<category>", "severity": "<P1-P4>", "confidence": <0.0-1.0>, "reasoning": "<1 sentence>"}}"""

    response = bedrock.invoke_model(
        modelId='anthropic.claude-3-sonnet-20240229-v1:0',
        body=json.dumps({
            'anthropic_version': 'bedrock-2023-05-31',
            'max_tokens': 200,
            'messages': [{'role': 'user', 'content': prompt}]
        })
    )
    result = json.loads(response['body'].read())
    text = result['content'][0]['text']

    # Parse JSON from response
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback if LLM doesn't return clean JSON
        return {'category': 'Application', 'severity': 'P3', 'confidence': 0.5}


def classify_ticket(description: str) -> dict:
    """
    Main classification entry point.
    Uses keywords first (fast), falls back to LLM if confidence is low.
    """
    # Fast path: keyword classification
    keyword_result = classify_by_keywords(description)
    severity = classify_severity(description)

    if keyword_result['confidence'] >= 0.5:
        return {
            'category': keyword_result['category'],
            'severity': severity,
            'confidence': keyword_result['confidence'],
            'assigned_team': TEAM_MAP[keyword_result['category']],
            'method': 'keywords',
        }

    # Slow path: LLM classification (for ambiguous tickets)
    llm_result = classify_with_llm(description)
    category = llm_result.get('category', keyword_result['category'])

    return {
        'category': category,
        'severity': llm_result.get('severity', severity),
        'confidence': llm_result.get('confidence', 0.5),
        'assigned_team': TEAM_MAP.get(category, 'Application Support'),
        'method': 'llm',
        'reasoning': llm_result.get('reasoning', ''),
    }
