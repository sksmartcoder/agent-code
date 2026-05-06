# Access/IAM Runbook

## Common Failure Patterns

### Lambda Cannot Write to S3
- Symptom: Lambda function returns AccessDenied when writing to S3
- Diagnosis: Check Lambda execution role policies, S3 bucket policy, KMS key policy if encrypted
- Fix: Add s3:PutObject (and s3:GetObject if needed) to Lambda execution role for the specific bucket ARN

### EC2 Cannot Access AWS Services
- Symptom: EC2 application gets AccessDenied calling AWS APIs
- Diagnosis: Check instance profile attached to EC2, verify role has required permissions
- Fix: Attach correct IAM role as instance profile, add missing service permissions

### Cross-Account Access Denied
- Symptom: Role assumption fails across accounts
- Diagnosis: Check trust policy on target role, verify source account/role ARN in trust policy
- Fix: Update trust policy to include source principal, ensure sts:AssumeRole is allowed

### S3 Bucket Policy Conflict
- Symptom: Access denied despite IAM policy allowing access
- Diagnosis: Check S3 bucket policy for explicit Deny statements, check SCPs
- Fix: Remove conflicting Deny in bucket policy, or add explicit Allow that overrides

### Secrets Manager Access Denied
- Symptom: Application cannot retrieve secret
- Diagnosis: Check IAM policy for secretsmanager:GetSecretValue, check resource ARN pattern
- Fix: Add secretsmanager:GetSecretValue for the specific secret ARN to the role

## Diagnostic Steps
1. Use IAM Policy Simulator to test permissions
2. Check CloudTrail for AccessDenied events
3. Review effective permissions with `aws iam simulate-principal-policy`
4. Check for SCPs in AWS Organizations that may block access

## AWS Resources Commonly Involved
- IAM, S3, Lambda, EC2, Secrets Manager, KMS, CloudTrail, AWS Organizations
