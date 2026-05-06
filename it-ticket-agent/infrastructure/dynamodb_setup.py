"""
DynamoDB Table Setup for IT Ticket Intelligence Agent
Run this once to create all required tables in your AWS sandbox.
"""
import boto3
import time

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')


def create_tickets_table():
    """Main ticket tracking table — replaces Jira."""
    table = dynamodb.create_table(
        TableName='it_tickets',
        KeySchema=[
            {'AttributeName': 'ticket_id', 'KeyType': 'HASH'},
            {'AttributeName': 'created_at', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'ticket_id', 'AttributeType': 'S'},
            {'AttributeName': 'created_at', 'AttributeType': 'S'},
            {'AttributeName': 'category', 'AttributeType': 'S'},
            {'AttributeName': 'severity', 'AttributeType': 'S'},
            {'AttributeName': 'status', 'AttributeType': 'S'},
            {'AttributeName': 'assigned_team', 'AttributeType': 'S'},
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'category-severity-index',
                'KeySchema': [
                    {'AttributeName': 'category', 'KeyType': 'HASH'},
                    {'AttributeName': 'severity', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'},
                'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
            },
            {
                'IndexName': 'status-index',
                'KeySchema': [
                    {'AttributeName': 'status', 'KeyType': 'HASH'},
                    {'AttributeName': 'created_at', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'},
                'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
            },
            {
                'IndexName': 'team-index',
                'KeySchema': [
                    {'AttributeName': 'assigned_team', 'KeyType': 'HASH'},
                    {'AttributeName': 'created_at', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'},
                'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
            }
        ],
        ProvisionedThroughput={'ReadCapacityUnits': 10, 'WriteCapacityUnits': 10},
        StreamSpecification={
            'StreamEnabled': True,
            'StreamViewType': 'NEW_AND_OLD_IMAGES'  # Enables DynamoDB Streams (simulates Jira webhooks)
        }
    )
    table.wait_until_exists()
    print(f"✅ Created table: it_tickets (with DynamoDB Streams enabled)")
    return table


def create_patterns_table():
    """Stores known recurring patterns for matching."""
    table = dynamodb.create_table(
        TableName='ticket_patterns',
        KeySchema=[
            {'AttributeName': 'pattern_id', 'KeyType': 'HASH'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'pattern_id', 'AttributeType': 'S'},
            {'AttributeName': 'category', 'AttributeType': 'S'},
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'category-index',
                'KeySchema': [
                    {'AttributeName': 'category', 'KeyType': 'HASH'},
                ],
                'Projection': {'ProjectionType': 'ALL'},
                'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
            }
        ],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )
    table.wait_until_exists()
    print(f"✅ Created table: ticket_patterns")
    return table


def create_resolutions_table():
    """Stores proven resolutions linked to patterns."""
    table = dynamodb.create_table(
        TableName='ticket_resolutions',
        KeySchema=[
            {'AttributeName': 'resolution_id', 'KeyType': 'HASH'},
            {'AttributeName': 'resolved_at', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'resolution_id', 'AttributeType': 'S'},
            {'AttributeName': 'resolved_at', 'AttributeType': 'S'},
            {'AttributeName': 'pattern_id', 'AttributeType': 'S'},
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'pattern-index',
                'KeySchema': [
                    {'AttributeName': 'pattern_id', 'KeyType': 'HASH'},
                    {'AttributeName': 'resolved_at', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'},
                'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
            }
        ],
        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    )
    table.wait_until_exists()
    print(f"✅ Created table: ticket_resolutions")
    return table


def enable_ttl(table_name, attribute):
    """Enable TTL for auto-cleanup of old resolved tickets."""
    client = boto3.client('dynamodb', region_name='us-east-1')
    client.update_time_to_live(
        TableName=table_name,
        TimeToLiveSpecification={'Enabled': True, 'AttributeName': attribute}
    )
    print(f"✅ Enabled TTL on {table_name}.{attribute}")


if __name__ == '__main__':
    print("🚀 Setting up DynamoDB tables for IT Ticket Agent...")
    print("=" * 60)

    create_tickets_table()
    time.sleep(2)

    create_patterns_table()
    time.sleep(2)

    create_resolutions_table()
    time.sleep(2)

    enable_ttl('it_tickets', 'ttl_expiry')

    print("=" * 60)
    print("✅ All tables created successfully!")
    print("")
    print("Tables:")
    print("  • it_tickets          — Main ticket store (Streams enabled)")
    print("  • ticket_patterns     — Recurring issue patterns")
    print("  • ticket_resolutions  — Proven fixes linked to patterns")
    print("")
    print("DynamoDB Streams enabled on it_tickets for real-time event processing.")
