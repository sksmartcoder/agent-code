# Data/ETL Runbook

## Common Failure Patterns

### Glue Job Connection Timeout
- Symptom: Glue job fails with JDBC connection timeout
- Diagnosis: Check VPC subnet routing, security group rules for database port, JDBC URL
- Fix: Increase JDBC connection timeout to 120s, add retry with exponential backoff, verify SG allows Glue → RDS traffic

### Glue Job Out of Memory
- Symptom: Glue job fails with Java heap space error
- Diagnosis: Check DPU allocation vs data volume in Glue job metrics
- Fix: Increase DPU count, enable job bookmarks to process incrementally

### RDS Connection Pool Exhausted
- Symptom: "Too many connections" error in application logs
- Diagnosis: Check RDS max_connections parameter, active connections in Performance Insights
- Fix: Implement connection pooling (RDS Proxy), reduce connection hold time

### Redshift Query Timeout
- Symptom: Long-running queries killed by WLM timeout
- Diagnosis: Check STL_WLM_QUERY for queue wait times, EXPLAIN plan for missing distribution keys
- Fix: Add sort/distribution keys, increase WLM timeout for ETL queue

### S3 Data Format Mismatch
- Symptom: Glue crawler fails or job produces empty output
- Diagnosis: Verify source data schema matches Glue catalog, check for schema drift
- Fix: Update Glue catalog, add schema validation step to pipeline

## Diagnostic Steps
1. Check Glue job run logs in CloudWatch
2. Review Glue job metrics (DPU utilization, records processed)
3. Verify VPC connectivity between Glue and data sources
4. Check RDS/Redshift slow query logs

## AWS Resources Commonly Involved
- AWS Glue, RDS, Redshift, S3, VPC, Security Groups, CloudWatch
