# IT Ticket Intelligence Agent — Full Flow Diagram

## End-to-End Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER / BROWSER / CLI                          │
│         Submits: "Glue job daily_claims_load failed with timeout"   │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         MASTER AGENT                                 │
│                  (agent_core/master_agent.py)                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Step 1: VALIDATE & CREATE TICKET                                   │
│  ┌────────────────────────────────────────────┐                     │
│  │  ticket_id = "TKT-20260507-abc123"         │                     │
│  │  status = OPEN                             │                     │
│  │  Store in DynamoDB (it-tickets table)      │                     │
│  └────────────────────┬───────────────────────┘                     │
│                       │                                             │
│                       ▼                                             │
│  Step 2: CLASSIFY (via Amazon Bedrock Nova Lite)                    │
│  ┌────────────────────────────────────────────┐                     │
│  │  boto3 → bedrock-runtime → invoke_model()  │                     │
│  │  Input:  "Glue job daily_claims_load..."   │                     │
│  │  Output: category = "Data/ETL"             │                     │
│  │          severity = "P2"                   │                     │
│  │          rationale = "Glue job failure..." │                     │
│  └────────────────────┬───────────────────────┘                     │
│                       │                                             │
│                       ▼                                             │
│  Step 3: PATTERN MATCH (tools/pattern_matcher.py)                   │
│  ┌────────────────────────────────────────────┐                     │
│  │  Query DynamoDB (it-patterns table)        │                     │
│  │  Compare using Jaccard similarity          │                     │
│  │                                            │                     │
│  │  Result A: Match ≥ 88% → RECURRING         │                     │
│  │    → Pull proven fix from it-resolutions   │                     │
│  │    → Skip to Step 6 (present fix)          │                     │
│  │                                            │                     │
│  │  Result B: No match → NEW ISSUE            │                     │
│  │    → Continue to Step 4 (route to agent)   │                     │
│  └────────────────────┬───────────────────────┘                     │
│                       │                                             │
│                       ▼                                             │
│  Step 4: ROUTE TO SPECIALIST AGENT                                  │
│  ┌────────────────────────────────────────────┐                     │
│  │  Category → Agent mapping:                 │                     │
│  │    "CI/CD"          → CICDAgent            │                     │
│  │    "Data/ETL"       → DataETLAgent    ◄──  │                     │
│  │    "Infrastructure" → InfraAgent           │                     │
│  │    "Access/IAM"     → AccessAgent          │                     │
│  │    "Network"        → NetworkAgent         │                     │
│  │                                            │                     │
│  │  Send via Agent Message Bus (REQUEST)      │                     │
│  └────────────────────┬───────────────────────┘                     │
│                       │                                             │
└───────────────────────┼─────────────────────────────────────────────┘
                        │
                        │  Agent Message Bus
                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SPECIALIST AGENT (e.g. DataETLAgent)              │
│                  (agent_core/data_agent.py)                          │
│                  inherits from base_agent.py                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Step 4a: FETCH RUNBOOK FROM S3 (Knowledge Base)                    │
│  ┌────────────────────────────────────────────┐                     │
│  │  get_runbook("Data/ETL")                   │                     │
│  │  boto3 → S3 → get_object()                │                     │
│  │  Bucket: it-ticket-agent-kb                │                     │
│  │  Key:    runbooks/data_runbook.md          │                     │
│  │                                            │                     │
│  │  Returns:                                  │                     │
│  │    - Common Glue failure patterns          │                     │
│  │    - Connection timeout troubleshooting    │                     │
│  │    - Auto-remediation steps                │                     │
│  │    - Diagnostic procedures                 │                     │
│  └────────────────────┬───────────────────────┘                     │
│                       │                                             │
│                       ▼                                             │
│  Step 4b: BUILD AI PROMPT WITH RUNBOOK CONTEXT                      │
│  ┌────────────────────────────────────────────┐                     │
│  │  system_prompt = """                       │                     │
│  │    You are a specialist IT engineer for    │                     │
│  │    Data/ETL.                               │                     │
│  │                                            │                     │
│  │    Relevant runbook:                       │                     │
│  │    # Data/ETL Runbook                      │                     │
│  │    ## Glue Job Connection Timeout          │                     │
│  │    - Symptom: JDBC connection timeout      │                     │
│  │    - Fix: Increase timeout to 120s...      │                     │
│  │    [full runbook content - up to 3000 ch]  │                     │
│  │                                            │                     │
│  │    Respond ONLY with JSON:                 │                     │
│  │    {"issue_summary": "...",                │                     │
│  │     "remediation_steps": "...",            │                     │
│  │     "aws_resources": [...]}                │                     │
│  │  """                                       │                     │
│  │                                            │                     │
│  │  user_prompt = """                         │                     │
│  │    Ticket: TKT-20260507-abc123             │                     │
│  │    Category: Data/ETL                      │                     │
│  │    Severity: P2                            │                     │
│  │    Description: Glue job daily_claims_load │                     │
│  │    failed with connection timeout          │                     │
│  │  """                                       │                     │
│  └────────────────────┬───────────────────────┘                     │
│                       │                                             │
│                       ▼                                             │
│  Step 4c: CALL BEDROCK NOVA LITE (AI Fix Generation)                │
│  ┌────────────────────────────────────────────┐                     │
│  │  boto3 → bedrock-runtime → invoke_model() │                     │
│  │  Model: us.amazon.nova-lite-v1:0           │                     │
│  │                                            │                     │
│  │  Nova reads:                               │                     │
│  │    ✓ Domain runbook (expert knowledge)     │                     │
│  │    ✓ Ticket details (specific problem)     │                     │
│  │                                            │                     │
│  │  Nova generates SPECIFIC fix:              │                     │
│  │  {                                         │                     │
│  │    "issue_summary": "JDBC connection       │                     │
│  │      timeout due to SG blocking port 5432",│                     │
│  │    "remediation_steps":                    │                     │
│  │      "1. Check VPC subnet routing\n        │                     │
│  │       2. Verify SG allows Glue→RDS\n       │                     │
│  │       3. Increase JDBC timeout to 120s\n   │                     │
│  │       4. Add retry with exp backoff",      │                     │
│  │    "aws_resources": [                      │                     │
│  │      "glue:job:daily_claims_load",         │                     │
│  │      "rds:instance:claims-db"]             │                     │
│  │  }                                         │                     │
│  └────────────────────┬───────────────────────┘                     │
│                       │                                             │
│                       ▼                                             │
│  Step 4d: AUTO-REMEDIATION (Data/ETL Agent specific)                │
│  ┌────────────────────────────────────────────┐                     │
│  │  Detected Glue job: "daily_claims_load"    │                     │
│  │  Last run status: FAILED                   │                     │
│  │                                            │                     │
│  │  boto3 → glue → start_job_run()           │                     │
│  │  ✓ Glue job re-triggered automatically    │                     │
│  │  Job Run ID: jr_abc123xyz                  │                     │
│  └────────────────────┬───────────────────────┘                     │
│                       │                                             │
│                       ▼                                             │
│  Step 4e: AGENT-TO-AGENT (if needed)                                │
│  ┌────────────────────────────────────────────┐                     │
│  │  Storage keywords detected?                │                     │
│  │  → DataETLAgent asks InfraAgent via bus    │                     │
│  │  → InfraAgent responds with disk steps     │                     │
│  │  → Merged into final fix                   │                     │
│  └────────────────────┬───────────────────────┘                     │
│                       │                                             │
│  Return: FixSuggestion(confidence=HIGH)                             │
│          (HIGH because runbook was available)                        │
│                                                                     │
└───────────────────────┬─────────────────────────────────────────────┘
                        │
                        │  Agent Message Bus (RESPONSE)
                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      BACK TO MASTER AGENT                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Step 5: PRESENT FIX TO HUMAN                                       │
│  ┌────────────────────────────────────────────┐                     │
│  │  Display:                                  │                     │
│  │    Issue: JDBC timeout, SG blocking 5432   │                     │
│  │    Fix: 4 remediation steps                │                     │
│  │    Confidence: HIGH                        │                     │
│  │    Auto-action: Glue job re-triggered      │                     │
│  │                                            │                     │
│  │  [APPROVE]  or  [REJECT]                   │                     │
│  └────────────────────┬───────────────────────┘                     │
│                       │                                             │
│                       ▼                                             │
│  Step 6: HUMAN DECISION                                             │
│  ┌────────────────────────────────────────────┐                     │
│  │                                            │                     │
│  │  IF APPROVED:                              │                     │
│  │    → Save to DynamoDB (it-resolutions)     │                     │
│  │    → Update ticket status → RESOLVED       │                     │
│  │    → Add pattern to it-patterns table      │                     │
│  │    → System LEARNS for next time           │                     │
│  │                                            │                     │
│  │  IF REJECTED:                              │                     │
│  │    → Escalate to human engineer            │                     │
│  │    → Log rejection reason                  │                     │
│  │                                            │                     │
│  └────────────────────┬───────────────────────┘                     │
│                       │                                             │
└───────────────────────┼─────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     LEARNING LOOP                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Step 7: SYSTEM GETS SMARTER                                        │
│  ┌────────────────────────────────────────────┐                     │
│  │                                            │                     │
│  │  DynamoDB it-patterns:                     │                     │
│  │    + "glue job connection timeout" pattern │                     │
│  │    + keywords: [glue, timeout, jdbc, conn] │                     │
│  │                                            │                     │
│  │  DynamoDB it-resolutions:                  │                     │
│  │    + Proven fix linked to pattern          │                     │
│  │    + Steps + resources + confidence        │                     │
│  │                                            │                     │
│  │  NEXT TIME same ticket arrives:            │                     │
│  │    → Pattern match = 88%+ → RECURRING      │                     │
│  │    → Skip investigation                    │                     │
│  │    → Suggest proven fix instantly           │                     │
│  │    → Seconds instead of minutes            │                     │
│  │                                            │                     │
│  └────────────────────────────────────────────┘                     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Storage Layer Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                        STORAGE LAYER                                 │
├────────────────────┬────────────────────┬───────────────────────────┤
│                    │                    │                           │
│   DynamoDB         │   DynamoDB         │   DynamoDB               │
│   it-tickets       │   it-patterns      │   it-resolutions         │
│                    │                    │                           │
│   • ticket_id      │   • pattern_id     │   • resolution_id        │
│   • description    │   • keywords       │   • ticket_id            │
│   • category       │   • category       │   • fix_steps            │
│   • severity       │   • frequency      │   • aws_resources        │
│   • status         │   • last_seen      │   • confidence           │
│   • created_at     │   • resolution_ref │   • approved_by          │
│                    │                    │   • approved_at           │
│   Purpose:         │   Purpose:         │   Purpose:               │
│   Track lifecycle  │   Pattern memory   │   Proven fixes           │
│   OPEN → RESOLVED  │   "Seen before?"   │   "What worked?"         │
│                    │                    │                           │
├────────────────────┴────────────────────┴───────────────────────────┤
│                                                                     │
│   S3 Bucket: it-ticket-agent-kb                                     │
│                                                                     │
│   runbooks/cicd_runbook.md      ← CI/CD domain expertise           │
│   runbooks/data_runbook.md      ← Data/ETL domain expertise        │
│   runbooks/infra_runbook.md     ← Infrastructure domain expertise  │
│   runbooks/access_runbook.md    ← Access/IAM domain expertise      │
│   runbooks/network_runbook.md   ← Network domain expertise         │
│                                                                     │
│   Purpose: RAG — inject domain knowledge into AI prompts            │
│   Used when: NEW issues (no pattern match found)                    │
│   Effect: Generic AI → Specific, actionable, expert-level fix       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Technology Mapping

| Step | AWS Service | Library | Purpose |
|------|-------------|---------|---------|
| Create ticket | DynamoDB | boto3 | Store ticket record |
| Classify | Bedrock Nova Lite | boto3 | AI classification |
| Pattern match | DynamoDB | boto3 | Query known patterns |
| Fetch runbook | S3 | boto3 | Domain expertise (RAG) |
| Generate fix | Bedrock Nova Lite | boto3 | AI fix generation |
| Auto-remediate | Glue | boto3 | Re-trigger failed job |
| Save resolution | DynamoDB | boto3 | Store proven fix |
| **Sandbox mock** | All DynamoDB/S3/Glue | **moto** | Simulate without permissions |

---

## Confidence Scoring

```
Runbook available (from S3)?
    │
    ├── YES → confidence = HIGH
    │         (AI had expert context to generate fix)
    │
    └── NO  → confidence = LOW_CONFIDENCE
              (AI generated generic response)

Pattern match found (from DynamoDB)?
    │
    ├── YES (≥88%) → RECURRING → instant proven fix
    │
    └── NO         → NEW → investigate with runbook + AI
```
