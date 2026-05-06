# CI/CD Troubleshooting Runbook

## ECS Deployment Failures

### OOM Killed
- **Symptom:** Task stopped with reason "OutOfMemoryError" or "OOM killed"
- **Root Cause:** Container memory limit too low for application
- **Fix:**
  1. Check current memory: `aws ecs describe-task-definition --task-definition <name>`
  2. Increase memory in task definition (double current value)
  3. Register new revision and update service
- **Prevention:** Monitor with Container Insights, set memory alarm at 80%

### Health Check Failing
- **Symptom:** Service stuck in "draining" state, new tasks failing health check
- **Root Cause:** Health check path/port mismatch or app slow to start
- **Fix:**
  1. Verify health check path returns 200: `curl http://localhost:<port>/health`
  2. Increase health check grace period (startPeriod)
  3. Check target group health check settings match app config
- **Prevention:** Add startup probe, increase deregistration delay

## CodePipeline Issues

### Stage Stuck
- **Symptom:** Pipeline stage shows "InProgress" for extended time
- **Root Cause:** Approval action pending, or downstream service timeout
- **Fix:**
  1. Check execution history: `aws codepipeline get-pipeline-execution`
  2. If approval: approve or reject manually
  3. If timeout: check CloudWatch Logs for the action
- **Prevention:** Set stage timeout, add SNS notification on stuck

### Artifact Not Found
- **Symptom:** "No artifact found" error in deploy stage
- **Root Cause:** Build stage output artifact name mismatch
- **Fix:**
  1. Check buildspec.yml artifacts section
  2. Verify output artifact name matches pipeline input artifact name
  3. Check S3 artifact bucket permissions
- **Prevention:** Use consistent naming convention for artifacts

## CodeBuild Issues

### Build Timeout
- **Symptom:** Build terminated after timeout period
- **Root Cause:** Long-running tests, large dependency install, or network issues
- **Fix:**
  1. Increase timeout: `aws codebuild update-project --timeout-in-minutes 120`
  2. Add caching for dependencies
  3. Parallelize test execution
- **Prevention:** Cache layers, use smaller base images, split build phases

### Docker Build Failures
- **Symptom:** Docker build fails with layer errors or permission issues
- **Root Cause:** Dockerfile issues, ECR permissions, or disk space
- **Fix:**
  1. Check ECR login: `aws ecr get-login-password | docker login`
  2. Verify build role has ecr:GetAuthorizationToken
  3. Check compute type has enough disk (use BUILD_GENERAL1_LARGE for big images)
- **Prevention:** Multi-stage builds, .dockerignore, layer caching

## Terraform/CloudFormation

### State Lock
- **Symptom:** "Error acquiring the state lock" or timeout
- **Root Cause:** Previous apply interrupted, leaving stale lock
- **Fix:**
  1. Check lock: `aws dynamodb get-item --table-name terraform-locks --key '{"LockID":{"S":"<path>"}}'`
  2. Force unlock: `terraform force-unlock <lock-id>`
  3. Verify no other apply running
- **Prevention:** Add lock timeout detection in pipeline, auto-cleanup stale locks >30min

### Drift Detected
- **Symptom:** Plan shows unexpected changes, resources modified outside Terraform
- **Root Cause:** Manual console changes or another tool modified resources
- **Fix:**
  1. Run `terraform plan` to see drift
  2. Either import changes: `terraform import` or revert manual changes
  3. Apply to reconcile state
- **Prevention:** Enforce no-manual-changes policy, enable Config drift detection
