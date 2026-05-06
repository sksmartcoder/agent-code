#!/bin/bash
# EC2 User Data — Bootstrap script for IT Ticket Agent
# Use this when launching the EC2 instance in AWS sandbox

set -e

echo "=== IT Ticket Agent — EC2 Bootstrap ==="

# Update system
yum update -y

# Install Python 3.11+
yum install -y python3.11 python3.11-pip git

# Create project directory
mkdir -p /home/ec2-user/it-ticket-agent
cd /home/ec2-user/it-ticket-agent

# Install Python dependencies
cat > requirements.txt << 'EOF'
boto3>=1.34.0
botocore>=1.34.0
EOF

pip3.11 install -r requirements.txt

# Set permissions
chown -R ec2-user:ec2-user /home/ec2-user/it-ticket-agent

echo "=== Bootstrap complete ==="
echo "Next steps:"
echo "  1. Copy project files to /home/ec2-user/it-ticket-agent/"
echo "  2. Run: python3.11 infrastructure/dynamodb_setup.py"
echo "  3. Run: python3.11 infrastructure/s3_setup.py"
echo "  4. Run: python3.11 data/load_tickets.py"
echo "  5. Run: python3.11 app.py submit 'your ticket here'"
