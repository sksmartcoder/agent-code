# SPEC: IT Ticket Intelligence Agent

## Document Purpose
Complete technical specification for the hackathon IT Ticket Intelligence Agent.
Share this with your team — it contains everything needed to build and demo in 2.5 days.

---

## 1. Overview

| Field | Value |
|-------|-------|
| Project | IT Ticket Intelligence Agent |
| Duration | 2.5 days |
| Environment | AWS Sandbox (EC2 instance) |
| Stack | Kiro CLI + Agent Core + Master Agent + DynamoDB + S3 + Bedrock |
| Ticket Store | DynamoDB (replaces Jira) |
| Event System | DynamoDB Streams (simulates Jira webhooks) |

---

## 2. Problem Statement

IT support tickets arrive as unstructured natural language. Current process:
1. Human reads ticket (2-5 min)
2. Human classifies and assigns severity (5 min)
3. Human routes to team (5 min)
4. Team investigates from scratch (15-45 min)
5. Fix applied, ticket closed (5-10 min)

**Total: 30-60 minutes per ticket, even for recurring issues.**

Our agent reduces recurring issues to **30 seconds** (classify → pattern match → suggest proven fix → approve).

---

## 3. Solution Architecture

### 3.1 Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Agent Runtime | EC2 + Agent Core | Runs the agent logic |
| CLI Interface | Kiro CLI | Submit/manage tickets |
| Orchestrator | Master Agent | Classifies, routes, decides |
| Specialists | Sub-Agents (5) | Domain-specific investigation |
| Ticket Store | DynamoDB | Tracks all tickets (replaces Jira) |
| Event Bus | DynamoDB Streams | Real-time ticket events |
| Knowledge Base | S3 | Runbooks for each category |
| LLM | Amazon Bedrock | Classification + fix generation |

### 3.2 Data Flow

```
1. User submits ticket (CLI/API)
2. Master Agent receives description
3. Classifier determines category + severity (keywords → LLM fallback)
4. Pattern Matcher queries DynamoDB for similar past tickets
5. Decision:
   a. RECURRING (>80% match) → pull proven fix → PENDING_APPROVAL
   b. NEW → delegate to specialist → lookup runbook → suggest fix → OPEN
   c. P1 → ESCALATE immediately regardless
6. Ticket created in DynamoDB with full context
7. DynamoDB Stream fires event (for future automation)
8. Human reviews → approves/rejects
9. Resolution stored for future pattern matching
```

---

## 4. DynamoDB Schema

### 4.1 Table: `it_tickets`

| Attribute | Type | Description |
|-----------|------|-------------|
| ticket_id (PK) | String | UUID: TKT-XXXXXXXX |
| created_at (SK) | String | ISO timestamp |
| description | String | Original ticket text |
| category | String | CI/CD, Data/ETL, Infrastructure, Access/IAM, Network, Application |
| severity | String | P1, P2, P3, P4 |
| assigned_team | String | Team name |
| status | String | OPEN, INVESTIGATING, PENDING_APPROVAL, APPROVED, RESOLVED, ESCALATED, REJECTED |
| is_recurring | Boolean | Pattern match result |
| matched_ticket_id | String | ID of matched pattern/ticket |
| suggested_fix | String | Agent's recommended fix |
| resolution | String | Actual fix applied |
| approved_by | String | Who approved |
| resolved_at | String | Resolution timestamp |

**GSIs:**
- `category-severity-index` (for routing queries)
- `status-index` (for dashboard)
- `team-index` (for team views)

**Stream:** NEW_AND_OLD_IMAGES enabled

### 4.2 Table: `ticket_patterns`

| Attribute | Type | Description |
|-----------|------|-------------|
| pattern_id (PK) | String | PAT-XXXXXXXX |
| category | String | Category this pattern belongs to |
| keywords | List | Key terms for matching |
| description_template | String | Template description for similarity |
| proven_fix | String | Fix that works for this pattern |
| occurrences | Number | How many times seen |
| last_seen | String | Last occurrence timestamp |
| success_rate | Number | Fix success rate (0.0-1.0) |

### 4.3 Table: `ticket_resolutions`

| Attribute | Type | Description |
|-----------|------|-------------|
| resolution_id (PK) | String | RES-XXXXXXXX |
| resolved_at (SK) | String | ISO timestamp |
| ticket_id | String | Which ticket this resolved |
| pattern_id | String | Which pattern this belongs to |
| fix_applied | String | What was actually done |
| success | Boolean | Did the fix work? |

---

## 5. Agent Definitions

### 5.1 Master Agent
- **Role:** Orchestrator
- **Responsibilities:** Classify, pattern match, delegate, route, manage approval
- **Tools:** create_ticket, search_ticket_history, lookup_runbook, update_ticket_status, delegate_to_specialist, approve_fix
- **Decision Logic:** See `agent_core/master_agent.md`

### 5.2 Specialist Sub-Agents
| Agent | File | Expertise |
|-------|------|-----------|
| CI/CD | `cicd_agent.md` | Pipelines, builds, deploys, ECS, Docker |
| Data/ETL | `data_agent.md` | Glue, Redshift, dashboards, data quality |
| Infrastructure | `infra_agent.md` | EC2, EBS, RDS, scaling, CloudWatch |
| Access/IAM | `access_agent.md` | Permissions, roles, policies, KMS |
| Network | `network_agent.md` | SGs, ALB, DNS, VPN, API Gateway |

---

## 6. Classification Logic

### 6.1 Fast Path (Keywords)
- Score each category by keyword matches in ticket description
- If confidence ≥ 0.5 → use keyword result (no LLM call needed)
- Categories: CI/CD, Data/ETL, Infrastructure, Access/IAM, Network, Application

### 6.2 Slow Path (LLM)
- If keyword confidence < 0.5 → call Bedrock for classification
- Returns: category, severity, confidence, reasoning
- Model: Claude 3 Sonnet or Amazon Nova Pro

### 6.3 Severity Rules
- P1: production down, revenue impact, security breach
- P2: major feature broken, significant user impact
- P3: degraded performance, workaround exists
- P4: minor, cosmetic, documentation

---

## 7. Pattern Matching Logic

### 7.1 Algorithm
1. Get all patterns for the classified category
2. For each pattern:
   - Calculate keyword overlap (40% weight)
   - Calculate text similarity (60% weight)
   - Combined score = weighted average
3. If best score ≥ 0.6 → RECURRING
4. Pull proven fix from pattern + most recent successful resolution

### 7.2 Fallback
- If no pattern match → search raw ticket history
- Compare against resolved tickets in same category
- If similarity ≥ 0.7 → treat as emerging pattern

### 7.3 Learning
- Every resolution stored in `ticket_resolutions`
- Successful fixes increase pattern `success_rate`
- New patterns auto-created after 2+ similar tickets resolved same way

---

## 8. Knowledge Base (S3)

### 8.1 Structure
```
s3://it-ticket-agent-kb/
└── runbooks/
    ├── cicd_runbook.md
    ├── data_runbook.md
    ├── infra_runbook.md
    ├── access_runbook.md
    └── network_runbook.md
```

### 8.2 Runbook Format
Each runbook contains:
- Issue patterns with symptoms
- Root cause explanations
- Step-by-step fixes with code/commands
- Prevention recommendations

---

## 9. API / CLI Interface

```bash
# Submit a ticket
python app.py submit "description of the issue"

# Approve a pending fix
python app.py approve TKT-XXXXXXXX [approver-name]

# Reject a fix
python app.py reject TKT-XXXXXXXX "reason"

# View open tickets
python app.py list-open

# View pending approvals
python app.py list-pending

# Dashboard view
python app.py dashboard
```

---

## 10. Setup Instructions

### 10.1 EC2 Instance
- AMI: Amazon Linux 2023
- Instance type: t3.medium (or larger)
- IAM Role: needs DynamoDB, S3, Bedrock access
- Security Group: SSH (port 22) from your IP

### 10.2 IAM Policy for EC2 Role
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:*"
      ],
      "Resource": "arn:aws:dynamodb:us-east-1:*:table/it_tickets*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:*"
      ],
      "Resource": "arn:aws:dynamodb:us-east-1:*:table/ticket_*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:*"
      ],
      "Resource": [
        "arn:aws:s3:::it-ticket-agent-kb",
        "arn:aws:s3:::it-ticket-agent-kb/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "*"
    }
  ]
}
```

### 10.3 Deployment Steps
```bash
# 1. SSH into instance
ssh -i key.pem ec2-user@<ip>

# 2. Copy project (scp or git clone)
scp -r -i key.pem it-ticket-agent/ ec2-user@<ip>:/home/ec2-user/

# 3. Install deps
cd /home/ec2-user/it-ticket-agent
pip3 install -r requirements.txt

# 4. Create infrastructure
python3 infrastructure/dynamodb_setup.py
python3 infrastructure/s3_setup.py

# 5. Load data
python3 data/load_tickets.py

# 6. Test
python3 app.py submit "Test ticket — Glue job failed with timeout"
python3 app.py dashboard
```

---

## 11. Team Task Assignment

| Person | Day 1 | Day 2 | Day 3 |
|--------|-------|-------|-------|
| Dev 1 | EC2 + DynamoDB setup + Master Agent | Sub-agents + approval flow | Integration + demo |
| Dev 2 | Classifier + Pattern Matcher | Runbooks + S3 KB + data loader | Polish + presentation |
| Dev 3 (if available) | Synthetic data + DynamoDB Streams | UI (optional Streamlit) | Backup demo + slides |

---

## 12. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Bedrock not available in sandbox | Fall back to keyword-only classification (no LLM) |
| DynamoDB throttling | Use on-demand billing mode instead of provisioned |
| Time crunch | Cut sub-agents to 3 (CI/CD, Data, Infra) instead of 5 |
| Demo fails live | Pre-record backup demo video |
| Agent Core issues | Fall back to direct Bedrock API calls |

---

## 13. Success Criteria

- [ ] Submit ticket via CLI → classified correctly
- [ ] Recurring ticket detected → proven fix suggested
- [ ] New ticket → routed to correct team with suggestion
- [ ] P1 ticket → escalated immediately
- [ ] Approve flow works → ticket resolved
- [ ] Dashboard shows open/pending/resolved
- [ ] End-to-end demo runs in under 3 minutes
