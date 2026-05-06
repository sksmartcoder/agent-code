# ETL Lineage & Auto-Correction Agent — Hackathon Project

## Pitch
An agentic AI system that monitors ETL pipelines, automatically traces data lineage when issues occur, diagnoses root cause, and self-corrects — all without human intervention.

## Problem Statement
ETL breaks at 3 AM. Someone gets paged. They spend an hour tracing through 4 data layers to find the root cause. They fix it manually. They write an incident report. This happens every week.

**Our agent does it in 30 seconds.**

## Architecture
```
Alert: "FACT_CLAIMS has 0 rows"
    │
    ▼
ORCHESTRATOR AGENT (Amazon Bedrock)
    │
    ├── LINEAGE AGENT → Traces: Source → Staging → Work → Final
    │
    ├── DIAGNOSIS AGENT → Checks row counts at each hop
    │                     Finds: "Staging has duplicates"
    │
    ├── CORRECTION AGENT → Deduplicates → Reruns merge → Validates
    │
    └── REPORT AGENT → "Root cause: duplicate keys. Auto-fixed. SLA met."
```

## Tech Stack
- Amazon Bedrock (Agent Core)
- AWS Lambda (tool implementations)
- Amazon RDS PostgreSQL (synthetic ETL database)
- Amazon S3 (source files, reports)

## Demo Scenarios
1. Empty target table → trace → rerun staging → reload
2. Duplicate keys → dedup → rerun merge → validate
3. Row count drop → trace → identify partial source → restore
4. Late data → detect → retry → notify
5. Schema change → detect mismatch → alter table → reload

## Project Structure
```
hackathon/etl-lineage-agent/
├── synthetic_db/       # Database setup scripts
├── agent_core/         # Agent definitions, prompts, tools
├── scenarios/          # 5 failure scenarios with inject/fix
├── docs/               # Presentation, architecture diagrams
└── README.md           # This file
```
