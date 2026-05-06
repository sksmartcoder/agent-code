# Network Runbook

## Common Failure Patterns

### API Gateway 503 / Backend Unhealthy
- Symptom: API Gateway returns 503, ALB target group shows unhealthy targets
- Diagnosis: Check ALB target group health checks, security group rules between ALB and backend
- Fix: Verify SG allows inbound traffic on backend port from ALB SG, fix health check path/port

### Security Group Missing Inbound Rule
- Symptom: Connection refused or timeout to a service
- Diagnosis: Check SG inbound rules for the target port, verify source SG or CIDR
- Fix: Add inbound rule for required port (e.g., 8080) from ALB security group ID

### VPC Peering Route Missing
- Symptom: Cross-VPC traffic fails despite peering connection active
- Diagnosis: Check route tables in both VPCs for peering routes, verify CIDR ranges don't overlap
- Fix: Add route to peer VPC CIDR pointing to peering connection in both route tables

### DNS Resolution Failure
- Symptom: Service cannot resolve internal DNS names
- Diagnosis: Check Route 53 private hosted zone association with VPC, check resolver rules
- Fix: Associate private hosted zone with VPC, verify DHCP options set uses AmazonProvidedDNS

### ALB 504 Gateway Timeout
- Symptom: ALB returns 504, backend is healthy but slow
- Diagnosis: Check ALB idle timeout vs backend response time, check target response time metrics
- Fix: Increase ALB idle timeout, optimize backend response time, add caching layer

## Diagnostic Steps
1. Check ALB access logs for error patterns
2. Review VPC flow logs for rejected traffic
3. Test connectivity with VPC Reachability Analyzer
4. Check security group rules and NACLs for both source and destination

## AWS Resources Commonly Involved
- VPC, Security Groups, NACLs, ALB, API Gateway, Route 53, CloudWatch
