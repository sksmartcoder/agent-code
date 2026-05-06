# Infrastructure Troubleshooting Runbook

## EC2 Issues

### Instance Unreachable
- **Symptom:** Cannot SSH, health check failing, status check failed
- **Root Cause:** Hardware failure, OS crash, or network misconfiguration
- **Fix:**
  1. Check status: `aws ec2 describe-instance-status --instance-ids <id>`
  2. If system status failed: stop and start (migrates to new host)
  3. If instance status failed: check OS logs via console screenshot
  4. Verify security group and route table
- **Prevention:** Auto-recovery alarm, multi-AZ deployment, ASG

### High CPU
- **Symptom:** CloudWatch CPU alarm firing, application slow
- **Root Cause:** Runaway process, traffic spike, or undersized instance
- **Fix:**
  1. Identify process: `top -bn1 | head -20`
  2. If legitimate load: scale up instance type or scale out (ASG)
  3. If runaway: kill process, investigate root cause
- **Prevention:** Right-size with Compute Optimizer, ASG with CPU target tracking

## EBS/Storage Issues

### Disk Full
- **Symptom:** "No space left on device", application errors, writes failing
- **Root Cause:** Log accumulation, temp files, or undersized volume
- **Fix:**
  1. Find large files: `du -sh /var/log/* | sort -rh | head -10`
  2. Clean: `find /var/log -name "*.gz" -mtime +7 -delete`
  3. Extend volume: `aws ec2 modify-volume --volume-id <id> --size <new-size>`
  4. Grow filesystem: `growpart /dev/xvda 1 && resize2fs /dev/xvda1`
- **Prevention:** Logrotate, CloudWatch disk alarm at 80%, auto-extend Lambda

### IOPS Throttling
- **Symptom:** High latency on disk operations, VolumeQueueLength > 1
- **Root Cause:** gp2/gp3 IOPS limit reached during burst
- **Fix:**
  1. Check metrics: VolumeReadOps, VolumeWriteOps, BurstBalance
  2. Upgrade to gp3 with provisioned IOPS
  3. Or move to io2 for consistent performance
- **Prevention:** Monitor BurstBalance, provision IOPS for predictable workloads

## RDS/Database Issues

### Connections Exhausted
- **Symptom:** "too many connections" error, new connections refused
- **Root Cause:** Connection leak, missing pooling, or undersized instance
- **Fix:**
  1. Check current: `SELECT count(*) FROM pg_stat_activity`
  2. Kill idle connections: `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle' AND query_start < now() - interval '1 hour'`
  3. Add connection pooler (PgBouncer/RDS Proxy)
  4. Scale up instance for higher max_connections
- **Prevention:** RDS Proxy, connection pool in application, idle timeout

### Storage Full
- **Symptom:** "Storage full" event, writes failing
- **Root Cause:** Data growth, WAL accumulation, or failed vacuum
- **Fix:**
  1. Enable storage autoscaling: `aws rds modify-db-instance --max-allocated-storage 200`
  2. Run vacuum: `VACUUM FULL` (requires maintenance window)
  3. Delete old data or archive to S3
- **Prevention:** Storage autoscaling, data retention policy, monitoring

## Auto Scaling Issues

### Launch Failure
- **Symptom:** ASG desired > running, launch failures in activity history
- **Root Cause:** AMI not found, subnet full, instance type unavailable
- **Fix:**
  1. Check activity: `aws autoscaling describe-scaling-activities`
  2. If AMI: update launch template with valid AMI
  3. If capacity: add more subnets/AZs or use mixed instance types
  4. If permissions: check instance profile and launch template role
- **Prevention:** Multi-AZ, mixed instance policy, AMI lifecycle management
