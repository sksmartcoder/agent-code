# IT Ticket Intelligence Agent — Hackathon Project

## Pitch
An AI-powered IT ticketing system that reads incoming support tickets, classifies them, detects recurring patterns, auto-suggests fixes, routes to the correct team, and learns from resolutions — all running on AWS sandbox with DynamoDB as the ticket store (no Jira needed).

## Problem Statement
IT tickets arrive as unstructured text. Humans manually read, classify, assign severity, route to teams, and troubleshoot. This is slow, error-prone, and repetitive. Recurring issues get re-investigated from scratch every time.

**Our agent resolves recurring issues in seconds and provides intelligent triage for new ones.**

## Tech Stack
| Component | AWS Service |
|-----------|-------------|
| Agent Runtime | EC2 + Agent Core (Kiro CLI) |
| Orchestration | Master Agent (multi-agent) |
| Ticket Store | DynamoDB (replaces Jira) |
| Knowledge Base | S3 (runbooks, past resolutions) |
| LLM Backbone | Amazon Bedrock (Claude/Nova) |
| Event Triggers | DynamoDB Streams (simulate Jira webhooks) |
| Notifications | SNS (optional, for routing alerts) |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        TICKET INTAKE                             │
│   CLI / API / DynamoDB Stream Event                             │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MASTER AGENT (Orchestrator)                    │
│                                                                   │
│  1. Parse ticket description                                      │
│  2. Classify category + severity                                  │
│  3. Query DynamoDB for recurring patterns                         │
│  4. Delegate to specialist sub-agent                              │
│  5. Generate fix suggestion                                       │
│  6. Route to team OR auto-fix (with approval)                     │
│  7. Log resolution back to DynamoDB                               │
└────────┬──────────┬──────────┬──────────┬──────────┬────────────┘
         │          │          │          │          │
         ▼          ▼          ▼          ▼          ▼
┌────────────┐┌──────────┐┌────────┐┌────────┐┌──────────┐
│  CI/CD     ││  Data/   ││ Infra  ││ Access ││ Network  │
│  Agent     ││  ETL     ││ Agent  ││ /IAM   ││ Agent    │
│            ││  Agent   ││        ││ Agent  ││          │
└────────────┘└──────────┘└────────┘└────────┘└──────────┘
         │          │          │          │          │
         └──────────┴──────────┴──────────┴──────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DynamoDB Tables                              │
│                                                                   │
│  it_tickets        │  ticket_patterns    │  resolutions           │
│  (active tickets)  │  (recurring issues) │  (knowledge base)      │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Decision Flow

```
Ticket arrives
    │
    ├── Classify: [CI/CD | Data | Infra | Access | Network | App]
    ├── Severity: [P1 | P2 | P3 | P4]
    │
    ├── Is this RECURRING? (pattern match against DynamoDB history)
    │   │
    │   ├── YES (confidence > 80%)
    │   │   ├── Pull proven fix from resolutions table
    │   │   ├── Apply fix automatically
    │   │   └── Status: PENDING_APPROVAL → Human approves → RESOLVED
    │   │
    │   └── NO (new issue)
    │       ├── Delegate to specialist sub-agent
    │       ├── Sub-agent investigates (runbook lookup, diagnostics)
    │       ├── Generate suggested fix
    │       ├── Route to correct team
    │       └── Status: OPEN → Human reviews → RESOLVED
    │
    └── Log everything to DynamoDB (audit trail)
```

## Demo Scenarios

### Scenario 1: Recurring CI/CD Issue
```
Input:  "CodePipeline deploy failed — ECS task OOM killed"
Agent:  Category: CI/CD | Severity: P2 | RECURRING (matched 3 prior tickets)
Fix:    "Increase ECS task memory from 512MB to 1024MB in task definition"
Action: Auto-apply pending approval
```

### Scenario 2: New Access Issue
```
Input:  "Lambda function can't write to S3 bucket prod-reports"
Agent:  Category: Access/IAM | Severity: P3 | NEW
Fix:    "Add s3:PutObject permission to Lambda execution role for arn:aws:s3:::prod-reports/*"
Action: Route to IAM team, suggest policy JSON
```

### Scenario 3: Data Pipeline Issue
```
Input:  "Glue job daily_claims_load failed with connection timeout"
Agent:  Category: Data/ETL | Severity: P2 | RECURRING (timeout pattern)
Fix:    "Increase JDBC connection timeout to 120s, add retry with backoff"
Action: Auto-apply pending approval
```

### Scenario 4: Infrastructure Issue
```
Input:  "EC2 instance i-0abc123 unreachable, disk at 98%"
Agent:  Category: Infrastructure | Severity: P1 | NEW
Fix:    "Extend EBS volume, clean /tmp and old logs. Immediate action required."
Action: Route to Infra team with P1 escalation
```

### Scenario 5: Network Issue
```
Input:  "API gateway returning 503, backend health checks failing"
Agent:  Category: Network | Severity: P1 | NEW
Fix:    "Security group sg-xyz missing inbound rule for port 8080 from ALB"
Action: Route to Network team with P1 escalation + suggested SG rule
```

## Sprint Plan (2.5 Days)

| Time | Owner | Task |
|------|-------|------|
| Day 1 AM | All | EC2 setup, Kiro CLI install, Agent Core config, DynamoDB tables created |
| Day 1 PM | Dev 1 | Master Agent: classify + severity + route logic |
| Day 1 PM | Dev 2 | DynamoDB CRUD tools + synthetic ticket data loaded |
| Day 2 AM | Dev 1 | Sub-agents (CI/CD, Data, Infra) + S3 runbooks |
| Day 2 AM | Dev 2 | Pattern matching (recurring detection) + resolution lookup |
| Day 2 PM | Dev 1 | Approval flow + auto-fix logic |
| Day 2 PM | Dev 2 | DynamoDB Streams event trigger (simulate real-time) |
| Day 3 AM | All | End-to-end integration, edge cases, error handling |
| Day 3 PM | All | Demo polish + presentation + backup recording |

## Evaluation Criteria Alignment

| Criteria (25%) | How We Score |
|----------------|-------------|
| **Innovation** | Multi-agent orchestration + recurring pattern memory + auto-remediation with human-in-loop |
| **Technical Execution** | Agent Core on EC2, Kiro CLI, DynamoDB Streams, S3 KB, Bedrock, tool chaining |
| **Business Value** | Reduces MTTR by 80% for recurring issues, ensures audit trail, compliance-friendly |
| **Presentation** | Live demo: submit ticket → watch agent classify → investigate → fix → approve in real-time |

## Project Structure
```
it-ticket-agent/
├── agent_core/
│   ├── master_agent.md          # Master agent definition + system prompt
│   ├── cicd_agent.md            # CI/CD specialist sub-agent
│   ├── data_agent.md            # Data/ETL specialist sub-agent
│   ├── infra_agent.md           # Infrastructure specialist sub-agent
│   ├── access_agent.md          # IAM/Access specialist sub-agent
│   └── network_agent.md         # Network specialist sub-agent
├── tools/
│   ├── ticket_store.py          # DynamoDB CRUD operations
│   ├── pattern_matcher.py       # Recurring issue detection
│   ├── knowledge_base.py        # S3 runbook lookup
│   ├── classifier.py            # Ticket classification logic
│   └── notifier.py              # Team routing + notifications
├── knowledge_base/
│   ├── cicd_runbook.md          # CI/CD troubleshooting guide
│   ├── data_runbook.md          # Data/ETL troubleshooting guide
│   ├── infra_runbook.md         # Infrastructure troubleshooting guide
│   ├── access_runbook.md        # IAM/Access troubleshooting guide
│   └── network_runbook.md       # Network troubleshooting guide
├── data/
│   └── synthetic_tickets.json   # 50+ historical tickets for pattern matching
├── infrastructure/
│   ├── dynamodb_setup.py        # Create DynamoDB tables + GSIs
│   ├── s3_setup.py              # Create S3 bucket + upload runbooks
│   └── ec2_userdata.sh          # EC2 bootstrap script
├── docs/
│   ├── SPEC.md                  # This spec document
│   ├── PRESENTATION.md          # Slide content
│   └── DEMO_SCRIPT.md           # Step-by-step demo guide
├── app.py                       # Main entry point
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## Quick Start (for team members)

```bash
# 1. SSH into EC2 instance
ssh -i hackathon-key.pem ec2-user@<instance-ip>

# 2. Clone/copy project
cd /home/ec2-user/it-ticket-agent

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up infrastructure
python infrastructure/dynamodb_setup.py
python infrastructure/s3_setup.py

# 5. Load synthetic data
python data/load_tickets.py

# 6. Run the agent
python app.py
```
