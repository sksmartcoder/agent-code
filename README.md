# IT Ticket Intelligence Agent

AI-powered IT support triage using multi-agent orchestration on AWS. Classifies tickets, detects recurring patterns, suggests fixes, and routes to the right team — all with a human-in-the-loop approval step.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         YOUR MACHINE / EC2                          │
│                                                                     │
│   ┌─────────────┐     ┌──────────────────────────────────────────┐ │
│   │  CLI Input  │────▶│           MASTER AGENT                   │ │
│   │  app.py     │     │  (Strands Agent SDK + Amazon Bedrock)    │ │
│   └─────────────┘     │                                          │ │
│                        │  1. Validate & create ticket             │ │
│                        │  2. Classify (Category + Severity)       │ │
│                        │  3. Pattern match vs DynamoDB history    │ │
│                        │  4. Route: RECURRING or NEW              │ │
│                        │  5. Present fix → approve / reject       │ │
│                        │  6. Log resolution + update patterns     │ │
│                        └──────────┬───────────────────────────────┘ │
│                                   │                                 │
│              ┌────────────────────┼────────────────────┐           │
│              ▼                    ▼                    ▼           │
│   ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐  │
│   │   CI/CD Agent    │ │  Data/ETL Agent  │ │   Infra Agent    │  │
│   │  (Strands SDK)   │ │  (Strands SDK)   │ │  (Strands SDK)   │  │
│   └──────────────────┘ └──────────────────┘ └──────────────────┘  │
│              ▼                    ▼                    ▼           │
│   ┌──────────────────┐ ┌──────────────────┐                        │
│   │  Access/IAM Agent│ │  Network Agent   │                        │
│   │  (Strands SDK)   │ │  (Strands SDK)   │                        │
│   └──────────────────┘ └──────────────────┘                        │
└─────────────────────────────────────────────────────────────────────┘
                    │                    │
          ┌─────────▼──────┐   ┌────────▼────────┐
          │   AWS DynamoDB  │   │     AWS S3      │
          │                 │   │                 │
          │ • it_tickets    │   │ • cicd_runbook  │
          │ • ticket_patterns│  │ • data_runbook  │
          │ • resolutions   │   │ • infra_runbook │
          └─────────────────┘   │ • access_runbook│
                                │ • network_runbook│
                                └─────────────────┘
                    │
          ┌─────────▼──────────┐
          │  Amazon Bedrock    │
          │  Claude 3 Sonnet   │
          │  (LLM backbone)    │
          └────────────────────┘
```

---

## Process Flow Diagram

```
Operator submits ticket via CLI
           │
           ▼
┌─────────────────────┐
│  Validate input     │──── empty/whitespace ──▶ REJECTED (no DB write)
└─────────┬───────────┘
          │ valid
          ▼
┌─────────────────────┐
│  Create ticket      │  UUID assigned, status = OPEN
│  Write to DynamoDB  │  Audit trail started
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Classify ticket    │  Bedrock LLM → Category + Severity
│  (Master Agent)     │  Fallback: Unknown / P3
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Pattern Match      │  Query ticket_patterns by Category
│  Confidence Score   │  Jaccard similarity on keywords
└─────────┬───────────┘
          │
     ┌────┴────┐
     │         │
confidence   confidence
  ≥ 80%       < 80%
     │         │
     ▼         ▼
┌─────────┐  ┌──────────────────────────────────────┐
│RECURRING│  │ NEW — delegate to specialist sub-agent│
│  PATH   │  │                                       │
└────┬────┘  │  CI/CD Agent    → cicd_runbook.md     │
     │       │  Data/ETL Agent → data_runbook.md     │
     │       │  Infra Agent    → infra_runbook.md    │
     │       │  Access Agent   → access_runbook.md   │
     │       │  Network Agent  → network_runbook.md  │
     │       │                                       │
     │       │  S3 runbook found?                    │
     │       │    YES → HIGH confidence fix          │
     │       │    NO  → LLM-only LOW_CONFIDENCE fix  │
     │       └──────────────────┬────────────────────┘
     │                          │
     ▼                          ▼
┌─────────────────────────────────────┐
│  Present fix to operator (CLI)      │
│  Ticket ID, Category, Severity,     │
│  Issue summary, Remediation steps   │
│  Status → PENDING_APPROVAL          │
└─────────────┬───────────────────────┘
              │
         ┌────┴────┐
         │         │
      approve    reject
         │         │
         ▼         ▼
   ┌──────────┐  ┌──────────────────┐
   │ RESOLVED │  │ REJECTED         │
   │          │  │ Reason captured  │
   │ Write    │  │ Status updated   │
   │ Resolution│  └──────────────────┘
   │ to DB    │
   │          │
   │ RECURRING?│
   │  YES → increment pattern count
   │  NO  → create new pattern entry
   └──────────┘
```

---

## Project Structure

```
it-ticket-agent/
├── app.py                      # CLI entry point
├── config.py                   # Env var config (table names, model ID)
├── requirements.txt
│
├── agent_core/
│   ├── master_agent.py         # Orchestrator — full triage pipeline
│   ├── base_agent.py           # Shared Strands Agent logic for sub-agents
│   ├── cicd_agent.py           # CI/CD specialist
│   ├── data_agent.py           # Data/ETL specialist
│   ├── infra_agent.py          # Infrastructure specialist
│   ├── access_agent.py         # Access/IAM specialist
│   └── network_agent.py        # Network specialist
│
├── tools/
│   ├── models.py               # Ticket, TicketPattern, Resolution dataclasses
│   ├── ticket_store.py         # DynamoDB CRUD + validation + resolution logging
│   ├── classifier.py           # Bedrock classification via Strands Agent
│   ├── pattern_matcher.py      # Confidence scoring + RECURRING/NEW routing
│   ├── knowledge_base.py       # S3 runbook fetch
│   └── notifier.py             # CLI approve/reject flow
│
├── knowledge_base/
│   ├── cicd_runbook.md
│   ├── data_runbook.md
│   ├── infra_runbook.md
│   ├── access_runbook.md
│   └── network_runbook.md
│
├── data/
│   ├── synthetic_tickets.json  # 20+ demo tickets + patterns + resolutions
│   └── load_tickets.py         # Seed DynamoDB from JSON
│
├── infrastructure/
│   ├── template.yaml           # CloudFormation: DynamoDB tables + S3 bucket
│   └── setup.py                # One-command deploy + seed
│
└── test_local.py               # Full test suite (no AWS creds needed)
```

---

## Quick Start — Local Machine (No AWS needed)

### 1. Clone / copy the project

```bash
git clone <your-repo-url>
cd it-ticket-agent
```

### 2. Install dependencies

```bash
pip install strands-agents strands-agents-tools moto[dynamodb,s3] boto3 pytest
```

### 3. Run tests locally (mock LLM + mock AWS)

```bash
python test_local.py
```

All 21 tests run with zero AWS credentials. DynamoDB and S3 are mocked via `moto`. The Strands Agent is stubbed to return canned responses.

### 4. Run with a real LLM (Anthropic — no AWS needed)

```bash
pip install 'strands-agents[anthropic]'
export USE_ANTHROPIC=true
export ANTHROPIC_API_KEY=sk-ant-...
python test_local.py
```

### 5. Run a single ticket interactively

```bash
python app.py "CodePipeline deploy failed — ECS task OOM killed"
```

---

## Quick Start — EC2 (Hackathon Sandbox)

### 1. SSH into your EC2 instance

```bash
ssh -i hackathon-key.pem ec2-user@<your-ec2-ip>
```

### 2. Copy the project

```bash
scp -i hackathon-key.pem -r it-ticket-agent/ ec2-user@<your-ec2-ip>:~/
```

Or clone directly on EC2 if you pushed to a repo.

### 3. Install dependencies

```bash
cd it-ticket-agent
pip install strands-agents strands-agents-tools boto3
```

### 4. Deploy infrastructure (CloudFormation)

```bash
python infrastructure/setup.py
```

This creates:
- DynamoDB tables: `hackathon_it_tickets`, `hackathon_ticket_patterns`, `hackathon_resolutions`
- S3 bucket for runbooks
- Uploads all 5 runbooks
- Seeds 20 synthetic tickets + patterns

### 5. Enable Bedrock model access

In the AWS console:
1. Go to **Amazon Bedrock → Model access**
2. Enable **Claude 3 Sonnet** (`anthropic.claude-3-sonnet-20240229-v1:0`)

### 6. Run the agent

```bash
python app.py "CodePipeline deploy failed — ECS task OOM killed"
```

### 7. Run tests against real AWS

```bash
python test_local.py   # still uses moto by default — safe to run anytime
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_DEFAULT_REGION` | `us-east-1` | AWS region |
| `ENVIRONMENT` | `hackathon` | Prefix for DynamoDB table names |
| `TICKETS_TABLE` | `hackathon_it_tickets` | Override table name |
| `PATTERNS_TABLE` | `hackathon_ticket_patterns` | Override table name |
| `RESOLUTIONS_TABLE` | `hackathon_resolutions` | Override table name |
| `RUNBOOK_BUCKET` | `hackathon-it-ticket-runbooks` | S3 bucket name |
| `BEDROCK_MODEL_ID` | `anthropic.claude-3-sonnet-20240229-v1:0` | Bedrock model |
| `CONFIDENCE_THRESHOLD` | `80` | Pattern match threshold (0–100) |
| `USE_ANTHROPIC` | `false` | Set `true` to use Anthropic instead of Bedrock |
| `ANTHROPIC_API_KEY` | — | Required if `USE_ANTHROPIC=true` |

---

## Demo Scenarios

Run these tickets to showcase the full agent flow:

```bash
# Scenario 1: RECURRING — CI/CD OOM (matches pattern, pulls proven fix)
python app.py "CodePipeline deploy failed — ECS task OOM killed"

# Scenario 2: NEW — Access/IAM (sub-agent investigates)
python app.py "Lambda function can't write to S3 bucket prod-reports"

# Scenario 3: RECURRING — Data/ETL timeout
python app.py "Glue job daily_claims_load failed with connection timeout"

# Scenario 4: NEW — Infrastructure P1
python app.py "EC2 instance i-0abc123 unreachable, disk at 98%"

# Scenario 5: NEW — Network P1
python app.py "API gateway returning 503, backend health checks failing"
```

---

## Team Setup (Multiple Members)

Each team member can work independently:

| Member | Focus | Files |
|--------|-------|-------|
| Dev 1 | Master Agent + classifier | `agent_core/master_agent.py`, `tools/classifier.py` |
| Dev 2 | DynamoDB tools + pattern matcher | `tools/ticket_store.py`, `tools/pattern_matcher.py` |
| Dev 3 | Sub-agents + runbooks | `agent_core/*_agent.py`, `knowledge_base/*.md` |
| All | Integration + demo | `test_local.py`, `app.py` |

Everyone runs `python test_local.py` to verify their changes without needing AWS access.

---

## How the Strands Agent SDK is Used

```python
from strands import Agent
from strands.models import BedrockModel

# Classifier — single-turn, structured JSON output
model = BedrockModel(model_id="anthropic.claude-3-sonnet-20240229-v1:0", region_name="us-east-1")
agent = Agent(model=model, system_prompt="You are an IT triage assistant...")
response = agent("Classify this ticket: CodePipeline deploy failed")
# → {"category": "CI/CD", "severity": "P2", "rationale": "..."}

# Sub-agent — domain specialist with runbook context injected into system prompt
agent = Agent(model=model, system_prompt=f"You are a CI/CD specialist.\n{runbook_content}")
response = agent(f"Ticket: {description}")
# → {"issue_summary": "...", "remediation_steps": "...", "aws_resources": [...]}
```

Each agent is stateless and single-turn. The Master Agent orchestrates the flow in Python — no Strands multi-agent framework needed, keeping the code simple and debuggable.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: strands` | `pip install strands-agents` |
| `AccessDenied` on Bedrock | Enable Claude 3 Sonnet in Bedrock console → Model access |
| `ResourceNotFoundException` on DynamoDB | Run `python infrastructure/setup.py` first |
| `NoSuchBucket` on S3 | Run `python infrastructure/setup.py` first |
| Tests fail with boto3 version error | `pip install boto3 --upgrade` |
| Pattern not matching (confidence < 80) | Check keywords in `data/synthetic_tickets.json` match ticket wording |
