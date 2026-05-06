#!/bin/bash
# Deploy IT Ticket Agent backing resources to AWS
# Usage: bash infrastructure/deploy.sh [region] [environment]
set -e

REGION="${1:-us-east-1}"
ENVIRONMENT="${2:-hackathon}"
STACK_NAME="it-ticket-agent"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE="$SCRIPT_DIR/template.yaml"
RUNBOOKS_DIR="$SCRIPT_DIR/../knowledge_base"
DATA_DIR="$SCRIPT_DIR/../data"

# ── Pre-flight checks ─────────────────────────────────────────────────────────
if ! command -v aws &>/dev/null; then
  echo "ERROR: AWS CLI not found. Install it first: https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html"
  exit 1
fi

if ! aws sts get-caller-identity &>/dev/null; then
  echo "ERROR: No valid AWS credentials. Run 'aws configure' or attach an IAM role to this EC2 instance."
  exit 1
fi

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
BUCKET_NAME="${ENVIRONMENT}-it-ticket-runbooks-${ACCOUNT}"

echo "=== Deploying IT Ticket Agent ==="
echo "Account     : $ACCOUNT"
echo "Region      : $REGION"
echo "Environment : $ENVIRONMENT"
echo "Stack       : $STACK_NAME"
echo ""

# ── 1. Deploy CloudFormation stack ───────────────────────────────────────────
echo "[1/4] Deploying CloudFormation stack..."
aws cloudformation deploy \
  --template-file "$TEMPLATE" \
  --stack-name "$STACK_NAME" \
  --parameter-overrides EnvironmentName="$ENVIRONMENT" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION" \
  --no-fail-on-empty-changeset

echo "  Stack deployed."

# ── 2. Upload runbooks to S3 ─────────────────────────────────────────────────
echo ""
echo "[2/4] Uploading runbooks to s3://$BUCKET_NAME/runbooks/"
for f in "$RUNBOOKS_DIR"/*.md; do
  fname=$(basename "$f")
  aws s3 cp "$f" "s3://$BUCKET_NAME/runbooks/$fname" --region "$REGION"
  echo "  uploaded $fname"
done

# ── 3. Load synthetic demo data ───────────────────────────────────────────────
echo ""
echo "[3/4] Loading synthetic tickets and patterns into DynamoDB..."
TICKETS_TABLE="${ENVIRONMENT}_it_tickets" \
PATTERNS_TABLE="${ENVIRONMENT}_ticket_patterns" \
RESOLUTIONS_TABLE="${ENVIRONMENT}_resolutions" \
AWS_DEFAULT_REGION="$REGION" \
python3 "$DATA_DIR/load_tickets.py"

# ── 4. Print stack outputs and env vars ───────────────────────────────────────
echo ""
echo "[4/4] Stack outputs:"
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs" \
  --output table

echo ""
echo "=== Setup complete. Run these exports before using app.py ==="
echo ""
echo "export AWS_DEFAULT_REGION=$REGION"
echo "export BEDROCK_REGION=$REGION"
echo "export ENVIRONMENT=$ENVIRONMENT"
echo "export TICKETS_TABLE=${ENVIRONMENT}_it_tickets"
echo "export PATTERNS_TABLE=${ENVIRONMENT}_ticket_patterns"
echo "export RESOLUTIONS_TABLE=${ENVIRONMENT}_resolutions"
echo "export RUNBOOK_BUCKET=$BUCKET_NAME"
echo "export BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0"
echo ""
echo "Then run: python3 app.py \"CodePipeline deploy failed — ECS task OOM killed\""
