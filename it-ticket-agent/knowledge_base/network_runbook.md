# Network Troubleshooting Runbook

## Load Balancer Issues

### ALB 503 Errors
- **Symptom:** Clients getting 503 Service Unavailable
- **Root Cause:** No healthy targets in target group
- **Fix:**
  1. Check target health: `aws elbv2 describe-target-health --target-group-arn <arn>`
  2. If unhealthy: verify health check path/port matches application
  3. Check security group allows ALB → target on health check port
  4. Increase health check grace period if app slow to start
- **Prevention:** Multiple targets across AZs, proper health check config

### ALB 502 Bad Gateway
- **Symptom:** Intermittent 502 errors
- **Root Cause:** Target closing connection before ALB, or target returning malformed response
- **Fix:**
  1. Check target keep-alive timeout > ALB idle timeout (60s default)
  2. Set application keep-alive to 65s+
  3. Check target isn't returning HTTP/0.9 or malformed headers
- **Prevention:** Set keep-alive > 60s, enable access logs for debugging

## Security Group Issues

### Connection Refused/Timeout
- **Symptom:** Cannot connect to service on expected port
- **Root Cause:** Security group missing inbound rule
- **Fix:**
  1. Identify source and destination security groups
  2. Add inbound rule: `aws ec2 authorize-security-group-ingress --group-id <sg> --protocol tcp --port <port> --source-group <source-sg>`
  3. Verify with: `aws ec2 describe-security-groups --group-ids <sg>`
- **Prevention:** Document required SG rules in IaC, use SG references not CIDR

### NACL Blocking
- **Symptom:** Connection works from some subnets but not others
- **Root Cause:** NACL deny rule or missing allow rule (NACLs are stateless)
- **Fix:**
  1. Check NACL rules: `aws ec2 describe-network-acls --filters Name=association.subnet-id,Values=<subnet>`
  2. Remember: NACLs need BOTH inbound AND outbound rules (stateless)
  3. Check ephemeral port range (1024-65535) is allowed for return traffic
- **Prevention:** Keep NACLs simple (allow all), use SGs for fine-grained control

## DNS Issues

### Resolution Failure
- **Symptom:** "Could not resolve host" or NXDOMAIN
- **Root Cause:** VPC DNS settings, missing Route 53 record, or resolver rule
- **Fix:**
  1. Check VPC DNS: `aws ec2 describe-vpc-attribute --vpc-id <vpc> --attribute enableDnsSupport`
  2. Verify record exists: `aws route53 list-resource-record-sets --hosted-zone-id <zone>`
  3. For private hosted zones: ensure VPC is associated
- **Prevention:** Enable DNS hostnames and support on VPC, test DNS after changes

## VPN/Connectivity Issues

### VPN Tunnel Down
- **Symptom:** Site-to-site VPN showing "DOWN" status
- **Root Cause:** IKE negotiation failure, DPD timeout, or customer gateway issue
- **Fix:**
  1. Check tunnel status: `aws ec2 describe-vpn-connections --vpn-connection-ids <id>`
  2. Verify customer gateway IP hasn't changed
  3. Check IKE/IPsec parameters match on both sides
  4. Increase DPD timeout if intermittent
- **Prevention:** Redundant tunnels, monitoring on tunnel status, DPD tuning

## API Gateway Issues

### 429 Too Many Requests
- **Symptom:** Clients getting throttled
- **Root Cause:** Default throttle limit (10,000 req/s account level) or usage plan limit
- **Fix:**
  1. Check usage plan limits: `aws apigateway get-usage-plans`
  2. Increase throttle: `aws apigateway update-stage --rest-api-id <id> --stage-name prod --patch-operations op=replace,path=/throttling/rateLimit,value=5000`
  3. Add caching to reduce backend calls
- **Prevention:** Set appropriate limits per client, enable caching, use CDN

### Integration Timeout
- **Symptom:** 504 Gateway Timeout from API Gateway
- **Root Cause:** Backend taking longer than 29s (API Gateway hard limit)
- **Fix:**
  1. Optimize backend response time
  2. If long-running: switch to async pattern (Step Functions + callback)
  3. Increase Lambda timeout (but can't exceed 29s for sync API GW)
- **Prevention:** Async for long operations, optimize queries, add caching
