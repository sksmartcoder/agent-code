"""
Knowledge Base — S3 runbook lookup for the IT Ticket Agent.
Retrieves relevant troubleshooting guides based on category and keywords.
"""
import boto3
import json

s3 = boto3.client('s3', region_name='us-east-1')
BUCKET_NAME = 'it-ticket-agent-kb'
KB_PREFIX = 'runbooks/'


def lookup_runbook(category: str, issue_keywords: str) -> str:
    """
    Retrieve relevant runbook content from S3 based on category and keywords.
    Returns the runbook text for the agent to use in generating fixes.
    """
    # Map category to runbook file
    category_map = {
        'CI/CD': 'cicd_runbook.md',
        'Data/ETL': 'data_runbook.md',
        'Infrastructure': 'infra_runbook.md',
        'Access/IAM': 'access_runbook.md',
        'Network': 'network_runbook.md',
        'Application': 'application_runbook.md',
    }

    filename = category_map.get(category)
    if not filename:
        return f"No runbook found for category: {category}"

    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=f"{KB_PREFIX}{filename}")
        content = response['Body'].read().decode('utf-8')
        return content
    except s3.exceptions.NoSuchKey:
        return f"Runbook not found: {filename}"
    except Exception as e:
        return f"Error retrieving runbook: {str(e)}"


def search_runbooks(query: str) -> list:
    """
    Search across all runbooks for relevant content.
    Returns matching sections from multiple runbooks.
    """
    results = []
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=KB_PREFIX)
        for obj in response.get('Contents', []):
            key = obj['Key']
            if not key.endswith('.md'):
                continue
            file_response = s3.get_object(Bucket=BUCKET_NAME, Key=key)
            content = file_response['Body'].read().decode('utf-8')

            # Simple keyword search within runbook sections
            query_words = query.lower().split()
            sections = content.split('\n## ')
            for section in sections:
                section_lower = section.lower()
                if any(word in section_lower for word in query_words):
                    results.append({
                        'source': key.replace(KB_PREFIX, ''),
                        'content': section[:500],  # Truncate for context window
                    })
    except Exception as e:
        results.append({'source': 'error', 'content': str(e)})

    return results


def upload_runbooks(local_dir: str = 'knowledge_base/'):
    """Upload local runbook files to S3. Run once during setup."""
    import os
    for filename in os.listdir(local_dir):
        if filename.endswith('.md'):
            filepath = os.path.join(local_dir, filename)
            s3.upload_file(filepath, BUCKET_NAME, f"{KB_PREFIX}{filename}")
            print(f"  ✅ Uploaded: {filename}")
