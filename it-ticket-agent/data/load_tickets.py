"""
Load synthetic tickets and patterns into DynamoDB.
Run after dynamodb_setup.py to seed the database for demo.
"""
import json
import boto3

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
tickets_table = dynamodb.Table('it_tickets')
patterns_table = dynamodb.Table('ticket_patterns')


def load_tickets():
    """Load synthetic historical tickets."""
    with open('data/synthetic_tickets.json', 'r') as f:
        tickets = json.load(f)

    with tickets_table.batch_writer() as batch:
        for ticket in tickets:
            batch.put_item(Item=ticket)

    print(f"✅ Loaded {len(tickets)} historical tickets")


def load_patterns():
    """Load known recurring patterns."""
    with open('data/synthetic_patterns.json', 'r') as f:
        patterns = json.load(f)

    with patterns_table.batch_writer() as batch:
        for pattern in patterns:
            batch.put_item(Item=pattern)

    print(f"✅ Loaded {len(patterns)} recurring patterns")


if __name__ == '__main__':
    print("🚀 Loading synthetic data into DynamoDB...")
    load_tickets()
    load_patterns()
    print("✅ Done! Ready for demo.")
