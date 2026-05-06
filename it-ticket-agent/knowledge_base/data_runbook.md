# Data/ETL Troubleshooting Runbook

## AWS Glue Job Failures

### Connection Timeout
- **Symptom:** Job fails with "Connection timed out" or JDBC timeout
- **Root Cause:** Network latency, Redshift under load, or security group blocking
- **Fix:**
  1. Increase timeout: `connection_options = {"connectionTimeout": "120"}`
  2. Add retry: `retry_count=3, retry_delay=exponential`
  3. Check VPC security group allows Glue ENI → Redshift port
  4. Check Redshift WLM queue concurrency
- **Prevention:** Dedicated WLM queue for ETL, connection health monitoring

### Schema Mismatch
- **Symptom:** "Column not found" or "Type mismatch" errors
- **Root Cause:** Upstream source added/removed/changed columns
- **Fix:**
  1. Run crawler to update catalog: `aws glue start-crawler --name <crawler>`
  2. Enable schema evolution: `ResolveChoice.apply(frame, choice="make_cols")`
  3. Update ApplyMapping to include new columns
- **Prevention:** Schema change detection alert, upstream contract validation

### Out of Memory
- **Symptom:** "Container killed due to memory" or executor OOM
- **Root Cause:** Data volume spike or inefficient transformations
- **Fix:**
  1. Increase DPU: `--number-of-workers 10 --worker-type G.2X`
  2. Add partitioning to reduce per-executor data
  3. Use pushdown predicates to filter at source
- **Prevention:** Monitor data volume trends, auto-scale DPU based on input size

## Data Quality Issues

### Duplicate Records
- **Symptom:** Row count higher than expected, duplicate keys in target
- **Root Cause:** Missing dedup step, incorrect merge key, or reprocessed data
- **Fix:**
  1. Identify duplicates: `SELECT key, COUNT(*) FROM table GROUP BY key HAVING COUNT(*) > 1`
  2. Add dedup in staging: `ROW_NUMBER() OVER (PARTITION BY key ORDER BY load_date DESC)`
  3. Clean target: delete duplicates keeping latest
- **Prevention:** Add DQ rule for uniqueness, idempotent loads with merge/upsert

### Null Values in Key Columns
- **Symptom:** Downstream joins failing, missing data in reports
- **Root Cause:** Source sending nulls in required fields
- **Fix:**
  1. Add null check in transform: `Filter.apply(frame, f=lambda x: x["key"] is not None)`
  2. Route nulls to error table for investigation
  3. Alert upstream data owner
- **Prevention:** NOT NULL constraint in staging, DQ rule with alerting

### Row Count Drop
- **Symptom:** Target table has significantly fewer rows than expected
- **Root Cause:** Partial source file, filter too aggressive, or failed partition
- **Fix:**
  1. Compare counts at each layer: source → staging → target
  2. Check source file completeness (row count header/trailer)
  3. Verify WHERE clauses haven't excluded valid data
- **Prevention:** Row count reconciliation check, alert on >10% variance

## Dashboard/Reporting Issues

### Stale Data
- **Symptom:** Dashboard showing yesterday's data or old timestamps
- **Root Cause:** Extract schedule runs before ETL completes
- **Fix:**
  1. Check ETL completion time vs extract schedule
  2. Adjust extract to run after ETL SLA (e.g., 7:30 AM if ETL SLA is 7 AM)
  3. Or trigger extract on ETL completion event
- **Prevention:** Event-driven refresh, add freshness indicator to dashboard

### Missing Partitions
- **Symptom:** Query returns no data for recent dates
- **Root Cause:** Crawler didn't detect new partitions, or partition projection misconfigured
- **Fix:**
  1. Run MSCK REPAIR TABLE: `MSCK REPAIR TABLE database.table`
  2. Or add partition manually: `ALTER TABLE ADD PARTITION (date='2025-06-25')`
  3. Check crawler schedule and exclusion patterns
- **Prevention:** Partition projection (no crawler needed), or event-triggered crawler
