"""
S3 Setup — Create bucket and upload runbooks for the IT Ticket Agent knowledge base.
"""
import boto3
import os

s3 = boto3.client('s3', region_name='us-east-1')
BUCKET_NAME = 'it-ticket-agent-kb'


def create_bucket():
    """Create S3 bucket for knowledge base."""
    try:
        s3.create_bucket(Bucket=BUCKET_NAME)
        print(f"✅ Created bucket: {BUCKET_NAME}")
    except s3.exceptions.BucketAlreadyOwnedByYou:
        print(f"ℹ️  Bucket already exists: {BUCKET_NAME}")
    except Exception as e:
        # For us-east-1, no LocationConstraint needed
        print(f"❌ Error: {e}")


def upload_runbooks():
    """Upload all runbook files to S3."""
    kb_dir = 'knowledge_base/'
    for filename in os.listdir(kb_dir):
        if filename.endswith('.md'):
            filepath = os.path.join(kb_dir, filename)
            key = f"runbooks/{filename}"
            s3.upload_file(filepath, BUCKET_NAME, key)
            print(f"  ✅ Uploaded: {key}")


if __name__ == '__main__':
    print("🚀 Setting up S3 knowledge base...")
    create_bucket()
    upload_runbooks()
    print("✅ Knowledge base ready!")
