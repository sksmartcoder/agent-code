# Infrastructure Runbook

## Common Failure Patterns

### EC2 Disk Full
- Symptom: EC2 instance unreachable or application errors, disk at 95%+
- Diagnosis: SSH in, run `df -h` and `du -sh /*` to find large directories
- Fix: Extend EBS volume via console (no downtime), clean /tmp, rotate logs, archive old data

### EC2 Instance Unreachable
- Symptom: SSH timeout, health checks failing, instance shows running in console
- Diagnosis: Check VPC security group inbound rules, NACL, instance status checks
- Fix: Verify SG allows SSH (port 22) from your IP, check system/instance status checks

### EKS Node Not Ready
- Symptom: kubectl shows node in NotReady state
- Diagnosis: Check node kubelet logs, disk pressure, memory pressure conditions
- Fix: Drain and terminate unhealthy node, let ASG replace it

### Auto Scaling Group Capacity Issue
- Symptom: ASG not launching new instances, desired capacity not met
- Diagnosis: Check ASG activity history for launch failures, verify AMI exists, check AZ capacity
- Fix: Update launch template with valid AMI, adjust AZ preferences

### EBS Volume Performance Degradation
- Symptom: High disk I/O latency, application slowness
- Diagnosis: Check CloudWatch EBS metrics (VolumeQueueLength, BurstBalance)
- Fix: Upgrade to gp3, increase IOPS provisioning, move to io2 for critical workloads

## Diagnostic Steps
1. Check EC2 instance status checks in console
2. Review CloudWatch metrics: CPU, disk, network
3. Check VPC flow logs for connectivity issues
4. Review Auto Scaling activity history

## AWS Resources Commonly Involved
- EC2, EBS, EKS, Auto Scaling, VPC, CloudWatch, Systems Manager
