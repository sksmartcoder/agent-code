# CI/CD Runbook

## Common Failure Patterns

### ECS Task OOM (Out of Memory)
- Symptom: ECS task killed, exit code 137, OOM in CloudWatch logs
- Diagnosis: Check task definition memory limit vs actual usage in CloudWatch Container Insights
- Fix: Increase task memory in task definition (e.g., 512MB → 1024MB), redeploy service

### CodePipeline Stage Failure
- Symptom: Pipeline stuck at Build or Deploy stage, red status
- Diagnosis: Check CodeBuild logs for compile errors or test failures
- Fix: Review build spec, fix failing tests, re-run pipeline

### ECR Image Pull Failure
- Symptom: ECS task fails to start, "CannotPullContainerError"
- Diagnosis: Verify image tag exists in ECR, check ECS task role has ecr:GetAuthorizationToken
- Fix: Push correct image tag, add ECR pull permissions to task execution role

### CodeBuild Timeout
- Symptom: Build times out after default 60 minutes
- Diagnosis: Check build duration trend in CodeBuild metrics
- Fix: Increase build timeout in project settings, optimize build steps

### Deployment Rollback Loop
- Symptom: ECS service repeatedly rolling back deployments
- Diagnosis: Check health check path, target group health, container startup logs
- Fix: Fix health check endpoint, increase health check grace period

## Diagnostic Steps
1. Open CloudWatch Logs for the failing service/pipeline
2. Check ECS service events in the console
3. Review CodeBuild build logs for the last failed execution
4. Verify IAM permissions on task execution role

## AWS Resources Commonly Involved
- CodePipeline, CodeBuild, ECS, ECR, CloudWatch Logs, IAM
