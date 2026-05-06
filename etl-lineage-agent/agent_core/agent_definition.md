# Agent Core — Tool Definitions & Prompts

## Agent Identity

```yaml
name: ETL Lineage & Auto-Correction Agent
description: >
  Monitors ETL pipelines, traces data lineage when issues occur,
  diagnoses root cause, and self-corrects without human intervention.
model: anthropic.claude-3-sonnet (or amazon.nova-pro)
```

## System Prompt

```
You are an ETL Pipeline Monitor and Auto-Correction Agent. Your job is to:

1. DETECT issues in ETL pipelines by checking job logs and data quality rules
2. TRACE data lineage from target back to source to find where problems originate
3. DIAGNOSE root cause by running checks at each layer
4. CORRECT issues automatically when safe to do so
5. REPORT what happened, what you found, and what you fixed

You have access to a PostgreSQL database with 4 ETL layers:
- source_layer: Raw data from external systems
- staging_layer: Validated and cleaned data
- work_layer: Enriched and transformed data
- data_layer: Final star schema (dimensions and facts)

Plus config tables:
- config.etl_lineage: Maps which tables feed which tables
- config.etl_job_log: Job execution history
- config.data_quality_rules: Quality checks to run

RULES:
- Always check job logs first to understand what ran and what failed
- Always trace lineage before attempting fixes
- Run data quality checks before and after any correction
- Never delete production data — only fix staging/work layers and reload
- Log every action you take in etl_job_log
- Generate a human-readable incident report at the end
```

## Tool Definitions

### Tool 1: run_sql
```json
{
  "name": "run_sql",
  "description": "Execute a SQL query against the ETL database and return results. Use for diagnostics, row counts, data quality checks, and corrections.",
  "parameters": {
    "query": {
      "type": "string",
      "description": "The SQL query to execute. Can be SELECT, INSERT, UPDATE, DELETE, or ALTER."
    },
    "purpose": {
      "type": "string",
      "description": "Brief description of why this query is being run."
    }
  }
}
```

### Tool 2: trace_lineage
```json
{
  "name": "trace_lineage",
  "description": "Trace the data lineage for a given table — find all upstream source tables and downstream target tables.",
  "parameters": {
    "table_name": {
      "type": "string",
      "description": "The fully qualified table name (schema.table) to trace lineage for."
    },
    "direction": {
      "type": "string",
      "enum": ["upstream", "downstream", "both"],
      "description": "Direction to trace: upstream (sources), downstream (targets), or both."
    }
  }
}
```

### Tool 3: check_data_quality
```json
{
  "name": "check_data_quality",
  "description": "Run all data quality rules for a given table and return pass/fail results.",
  "parameters": {
    "schema_name": {
      "type": "string",
      "description": "The schema name."
    },
    "table_name": {
      "type": "string",
      "description": "The table name to check."
    }
  }
}
```

### Tool 4: compare_row_counts
```json
{
  "name": "compare_row_counts",
  "description": "Compare row counts across all layers in the lineage chain for a given target table. Helps identify where data is being lost.",
  "parameters": {
    "target_table": {
      "type": "string",
      "description": "The final target table to trace back from."
    },
    "date_filter": {
      "type": "string",
      "description": "Date to filter on (YYYY-MM-DD format). Defaults to today."
    }
  }
}
```

### Tool 5: generate_report
```json
{
  "name": "generate_report",
  "description": "Generate a structured incident report summarizing the issue, diagnosis, actions taken, and current status.",
  "parameters": {
    "incident_type": {
      "type": "string",
      "description": "Type of incident detected."
    },
    "root_cause": {
      "type": "string",
      "description": "Root cause identified."
    },
    "actions_taken": {
      "type": "array",
      "items": {"type": "string"},
      "description": "List of corrective actions taken."
    },
    "status": {
      "type": "string",
      "enum": ["RESOLVED", "ESCALATED", "MONITORING"],
      "description": "Current status after intervention."
    }
  }
}
```

## Lambda Implementations (Python)

### run_sql Lambda
```python
import json
import psycopg2

def lambda_handler(event, context):
    query = event['parameters']['query']
    purpose = event['parameters']['purpose']
    
    conn = psycopg2.connect(
        host=os.environ['DB_HOST'],
        database=os.environ['DB_NAME'],
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD']
    )
    
    cur = conn.cursor()
    cur.execute(query)
    
    if query.strip().upper().startswith('SELECT'):
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        result = [dict(zip(columns, row)) for row in rows]
    else:
        conn.commit()
        result = {"rows_affected": cur.rowcount}
    
    cur.close()
    conn.close()
    
    return {"purpose": purpose, "result": result}
```

### trace_lineage Lambda
```python
def lambda_handler(event, context):
    table_name = event['parameters']['table_name']
    direction = event['parameters']['direction']
    
    schema, table = table_name.split('.')
    
    conn = get_connection()
    cur = conn.cursor()
    
    lineage = {"table": table_name, "upstream": [], "downstream": []}
    
    if direction in ('upstream', 'both'):
        cur.execute("""
            WITH RECURSIVE upstream AS (
                SELECT source_schema, source_table, target_schema, target_table, 
                       transform_type, join_keys, 1 as depth
                FROM config.etl_lineage
                WHERE target_schema = %s AND target_table = %s
                UNION ALL
                SELECT l.source_schema, l.source_table, l.target_schema, l.target_table,
                       l.transform_type, l.join_keys, u.depth + 1
                FROM config.etl_lineage l
                JOIN upstream u ON l.target_schema = u.source_schema AND l.target_table = u.source_table
                WHERE u.depth < 10
            )
            SELECT * FROM upstream ORDER BY depth
        """, (schema, table))
        lineage["upstream"] = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]
    
    if direction in ('downstream', 'both'):
        cur.execute("""
            WITH RECURSIVE downstream AS (
                SELECT source_schema, source_table, target_schema, target_table,
                       transform_type, join_keys, 1 as depth
                FROM config.etl_lineage
                WHERE source_schema = %s AND source_table = %s
                UNION ALL
                SELECT l.source_schema, l.source_table, l.target_schema, l.target_table,
                       l.transform_type, l.join_keys, d.depth + 1
                FROM config.etl_lineage l
                JOIN downstream d ON l.source_schema = d.target_schema AND l.source_table = d.target_table
                WHERE d.depth < 10
            )
            SELECT * FROM downstream ORDER BY depth
        """, (schema, table))
        lineage["downstream"] = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]
    
    cur.close()
    conn.close()
    
    return lineage
```

### check_data_quality Lambda
```python
def lambda_handler(event, context):
    schema_name = event['parameters']['schema_name']
    table_name = event['parameters']['table_name']
    
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT rule_id, rule_type, rule_sql, threshold, severity, description
        FROM config.data_quality_rules
        WHERE target_schema = %s AND target_table = %s
    """, (schema_name, table_name))
    
    rules = cur.fetchall()
    results = []
    
    for rule in rules:
        rule_id, rule_type, rule_sql, threshold, severity, description = rule
        try:
            cur.execute(rule_sql)
            result = cur.fetchone()
            value = result[0] if result else 0
            passed = value <= threshold if rule_type in ('no_duplicates', 'no_nulls') else value >= threshold
            results.append({
                "rule_id": rule_id,
                "rule_type": rule_type,
                "description": description,
                "severity": severity,
                "value": value,
                "threshold": threshold,
                "passed": passed
            })
        except Exception as e:
            results.append({
                "rule_id": rule_id,
                "rule_type": rule_type,
                "description": description,
                "severity": severity,
                "error": str(e),
                "passed": False
            })
    
    cur.close()
    conn.close()
    
    return {"schema": schema_name, "table": table_name, "results": results}
```

### compare_row_counts Lambda
```python
def lambda_handler(event, context):
    target_table = event['parameters']['target_table']
    date_filter = event['parameters'].get('date_filter', 'CURRENT_DATE')
    
    schema, table = target_table.split('.')
    
    conn = get_connection()
    cur = conn.cursor()
    
    # Get full lineage chain
    cur.execute("""
        WITH RECURSIVE chain AS (
            SELECT source_schema, source_table, target_schema, target_table, 1 as depth
            FROM config.etl_lineage
            WHERE target_schema = %s AND target_table = %s
            UNION ALL
            SELECT l.source_schema, l.source_table, l.target_schema, l.target_table, c.depth + 1
            FROM config.etl_lineage l
            JOIN chain c ON l.target_schema = c.source_schema AND l.target_table = c.source_table
            WHERE c.depth < 10
        )
        SELECT DISTINCT source_schema || '.' || source_table AS tbl FROM chain
        UNION
        SELECT DISTINCT target_schema || '.' || target_table FROM chain
        ORDER BY tbl
    """, (schema, table))
    
    tables = [row[0] for row in cur.fetchall()]
    
    counts = []
    for tbl in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {tbl}")
            total = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE load_date = {date_filter}")
            today = cur.fetchone()[0]
            counts.append({"table": tbl, "total_rows": total, "today_rows": today})
        except:
            counts.append({"table": tbl, "total_rows": "ERROR", "today_rows": "ERROR"})
    
    cur.close()
    conn.close()
    
    return {"target": target_table, "date": date_filter, "row_counts": counts}
```

## Example Agent Conversation Flow

### Scenario 1: Empty Target Table

```
AGENT: Running daily ETL health check...

[Tool: run_sql] 
Query: SELECT target_table, status, rows_inserted, error_message 
       FROM config.etl_job_log WHERE run_date = CURRENT_DATE ORDER BY start_time DESC
Result: fact_claims | FAILED | 0 | Connection timeout during merge operation

AGENT: ⚠️ FACT_CLAIMS load failed today. Tracing lineage...

[Tool: trace_lineage]
Input: data_layer.fact_claims, upstream
Result: work_layer.claims_enriched → staging_layer.claims_staged → source_layer.claims_raw

AGENT: Checking row counts at each layer...

[Tool: compare_row_counts]
Input: data_layer.fact_claims
Result:
  source_layer.claims_raw    → 2000 rows (today: 2000) ✅
  staging_layer.claims_staged → 2000 rows (today: 2000) ✅
  work_layer.claims_enriched  → 2000 rows (today: 2000) ✅
  data_layer.fact_claims      → 0 rows (today: 0) ❌

AGENT: Data exists in all upstream layers. The merge into fact_claims failed.
       Upstream data is healthy. Safe to rerun the merge.

[Tool: run_sql]
Query: INSERT INTO data_layer.fact_claims (...) SELECT ... FROM work_layer.claims_enriched ...
Result: 2000 rows inserted

[Tool: check_data_quality]
Input: data_layer, fact_claims
Result: All 4 rules PASSED ✅

[Tool: generate_report]
INCIDENT REPORT:
  Type: Empty target table
  Root Cause: Connection timeout during merge operation
  Actions: Verified upstream data intact → Reran merge → Validated quality
  Status: RESOLVED
  Impact: None — auto-corrected before SLA
```
