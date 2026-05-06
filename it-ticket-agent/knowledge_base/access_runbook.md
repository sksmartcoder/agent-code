# Access/IAM Troubleshooting Runbook

## Permission Denied Errors

### S3 Access Denied
- **Symptom:** "Access Denied" when reading/writing S3 objects
- **Root Cause:** Missing IAM policy, bucket policy conflict, or KMS key policy
- **Fix:**
  1. Check IAM policy on the calling principal (role/user)
  2. Check S3 bucket policy for explicit denies
  3. If encrypted: check KMS key policy grants decrypt to the principal
  4. Check S3 Block Public Access settings
- **Minimal Policy:**
  ```json
  {
    "Effect": "Allow",
    "Action": ["s3:GetObject", "s3:PutObject"],
    "Resource": "arn:aws:s3:::<bucket>/<prefix>/*"
  }
  ```
- **Prevention:** Use IAM Access Analyzer, test with policy simulator

### AssumeRole Failed
- **Symptom:** "AccessDenied" on sts:AssumeRole
- **Root Cause:** Trust policy doesn't include the calling principal
- **Fix:**
  1. Check trust policy on target role: `aws iam get-role --role-name <role>`
  2. Add calling principal to trust policy
  3. Ensure calling principal has `sts:AssumeRole` permission
  4. Check for condition keys (ExternalId, SourceAccount)
- **Trust Policy Fix:**
  ```json
  {
    "Effect": "Allow",
    "Principal": {"AWS": "arn:aws:iam::<account>:role/<calling-role>"},
    "Action": "sts:AssumeRole",
    "Condition": {"StringEquals": {"sts:ExternalId": "<external-id>"}}
  }
  ```
- **Prevention:** Document cross-account access patterns, use ExternalId

### KMS Decrypt Denied
- **Symptom:** "AccessDeniedException" on kms:Decrypt
- **Root Cause:** KMS key policy doesn't grant decrypt to the principal
- **Fix:**
  1. Check key policy: `aws kms get-key-policy --key-id <key-id>`
  2. Add statement granting kms:Decrypt to the principal
  3. Or add via IAM policy if key policy allows it (has root account statement)
- **Key Policy Addition:**
  ```json
  {
    "Effect": "Allow",
    "Principal": {"AWS": "arn:aws:iam::<account>:role/<role>"},
    "Action": ["kms:Decrypt", "kms:DescribeKey"],
    "Resource": "*"
  }
  ```
- **Prevention:** Use key aliases, document which roles need which keys

## Lambda Permission Issues

### Lambda Can't Access Resource
- **Symptom:** Lambda returns permission error when calling AWS service
- **Root Cause:** Execution role missing required permissions
- **Fix:**
  1. Identify the action and resource from error message
  2. Add minimal policy to execution role
  3. Test with IAM Policy Simulator
- **Common Lambda Permissions:**
  - DynamoDB: `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:Query`
  - S3: `s3:GetObject`, `s3:PutObject`
  - SQS: `sqs:ReceiveMessage`, `sqs:DeleteMessage`
  - Secrets Manager: `secretsmanager:GetSecretValue`
- **Prevention:** Use SAM/CDK policy templates, least privilege from start

### Lambda VPC Access
- **Symptom:** Lambda in VPC can't reach internet or AWS services
- **Root Cause:** Missing NAT Gateway or VPC endpoints
- **Fix:**
  1. For internet: add NAT Gateway in public subnet, route from private subnet
  2. For AWS services: add VPC endpoints (S3, DynamoDB, SQS, etc.)
  3. Verify security group allows outbound traffic
- **Prevention:** Use VPC endpoints for AWS services, NAT for external

## SSO/Federation Issues

### Token Expired
- **Symptom:** "ExpiredTokenException" or "Token has expired"
- **Root Cause:** Session duration exceeded, or cached credentials stale
- **Fix:**
  1. Re-authenticate: `aws sso login --profile <profile>`
  2. Check session duration setting on role (max 12 hours)
  3. Clear credential cache: `rm -rf ~/.aws/sso/cache/*`
- **Prevention:** Increase session duration if appropriate, automate refresh
