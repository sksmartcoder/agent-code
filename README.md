# IT Ticket Intelligence Agent

AI-powered IT support triage using multi-agent orchestration on AWS. Classifies tickets, detects recurring patterns, auto-remediates (e.g. Glue job re-run), and routes to the right specialist agent — all powered by Amazon Bedrock Nova.

**Hackathon Demo URL (live now):**
```
http://amzn-hackthon-it-ticket-system.s3-website-us-west-2.amazonaws.com
```

---

## What It Does

1. You submit an IT support ticket (text description)
2. **Master Agent** classifies it by category and severity using Bedrock Nova
3. Checks if it's a **recurring pattern** (88%+ confidence match)
4. Routes to the right **specialist sub-agent** (CI/CD, Data/ETL, Infra, Access/IAM, Network)
5. Sub-agent fetches the runbook from S3 and generates a fix using AI
6. For Data/ETL tickets — **automatically re-triggers failed Glue jobs**
7. Presents the fix for operator approval → logs resolution

---

## Architecture

```
Browser / CLI
     │
     ▼
┌─────────────────────────────────────────────┐
│           MASTER AGENT                      │
│  (Strands SDK + Amazon Bedrock Nova Lite)   │
│                                             │
│  1. Validate & create ticket                │
│  2. Classify → Category + Severity          │
│  3. Pattern match (Jaccard similarity)      │
│  4. Route: RECURRING or NEW                 │
│  5. Present fix → approve / reject          │
│  6. Log resolution + update patterns        │
└──────────────┬──────────────────────────────┘
               │
    ┌──────────┼──────────────────────┐
    ▼          ▼          ▼           ▼
🔧 CI/CD   🗄 Data/ETL  🖥 Infra   🔑 Access/IAM   🌐 Network
 Agent      Agent       Agent       Agent           Agent
    │          │
    │     Auto re-run
    │     Glue jobs ──▶ AWS Glue
    │
    ▼
Amazon Bedrock Nova Lite  ←──  S3 Runbooks
(AI fix generation)
```

**AWS Services used:**
| Service | Purpose |
|---|---|
| Amazon Bedrock Nova Lite | AI classification + fix generation |
| AWS Lambda | API backend for web dashboard |
| Amazon S3 | Static web dashboard + runbook storage |
| AWS Glue (mocked) | ETL job re-run automation |
| DynamoDB (mocked) | Ticket + pattern + resolution storage |
| AgentCore Runtime | Cloud agent deployment |

---

## Project Structure

```
it-ticket-agent/
├── app.py                    # CLI entry point
├── config.py                 # Environment config
├── demo.py                   # Rich terminal demo (visual CLI)
├── run_local.py              # Interactive local runner
├── test_local.py             # Full test suite (no AWS needed)
├── agentcore_app.py          # AgentCore Runtime entrypoint
│
├── agent_core/
│   ├── master_agent.py       # Orchestrator
│   ├── base_agent.py         # Shared Strands Agent logic
│   ├── cicd_agent.py         # CI/CD specialist
│   ├── data_agent.py         # Data/ETL + Glue auto-remediation
│   ├── infra_agent.py        # Infrastructure specialist
│   ├── access_agent.py       # Access/IAM specialist
│   └── network_agent.py      # Network specialist
│
├── tools/
│   ├── models.py             # Ticket, Pattern, Resolution dataclasses
│   ├── ticket_store.py       # DynamoDB CRUD + validation
│   ├── classifier.py         # Bedrock Nova classification
│   ├── pattern_matcher.py    # Confidence scoring + routing
│   ├── knowledge_base.py     # S3 runbook fetch
│   └── notifier.py           # Approval flow
│
├── knowledge_base/           # Domain runbooks (uploaded to S3)
│   ├── cicd_runbook.md
│   ├── data_runbook.md
│   ├── infra_runbook.md
│   ├── access_runbook.md
│   └── network_runbook.md
│
├── dashboard/
│   ├── server.py             # Flask + SocketIO web dashboard
│   └── templates/index.html  # Dashboard UI
│
├── lambda/
│   ├── handler.py            # Lambda function handler
│   ├── deploy_lambda.py      # Deploy Lambda + Function URL
│   ├── deploy_static.py      # Deploy static site to S3
│   └── function_url.txt      # Lambda URL (auto-generated)
│
└── infrastructure/
    ├── template.yaml         # CloudFormation template
    └── deploy.sh             # Deploy script
```

---

## Option 1 — Web Dashboard (Recommended for Demo)

**Already live — open in any browser:**
```
http://amzn-hackthon-it-ticket-system.s3-website-us-west-2.amazonaws.com
```

Click any demo button and watch the agent flow in real time:
- Flow diagram lights up step by step
- Real Bedrock Nova AI classifies the ticket
- Confidence bar shows pattern match score
- Color-coded fix suggestion with remediation steps

**To redeploy the dashboard after code changes:**
```bash
python3 lambda/deploy_lambda.py    # redeploy Lambda backend
python3 lambda/deploy_static.py    # redeploy S3 frontend
```

---

## Option 2 — Rich Terminal Demo

Best for showing the full pipeline in a terminal:

```bash
python3 demo.py
```

Pick a scenario from the menu. Shows:
- Live step-by-step flow with spinner
- Color-coded category/severity
- Confidence bar
- Formatted fix panel with remediation steps

---

## Option 3 — Run Tests (No AWS Needed)

Zero credentials required — uses moto mocks + stubbed LLM:

```bash
python3 test_local.py
```

Expected output: **21 tests, all passing.**

To test with real Bedrock Nova (requires AWS credentials):
```bash
python3 run_local.py
```

---

## Setup for Team Members

### Prerequisites
```bash
pip install -r requirements.txt
```

### Environment (already set on the hackathon EC2)
```bash
export AWS_DEFAULT_REGION=us-west-2
export BEDROCK_REGION=us-west-2
export BEDROCK_MODEL_ID=us.amazon.nova-lite-v1:0
```

Or copy the `.env` file and load it:
```bash
source .env   # or: export $(cat .env | xargs)
```

### Run tests to verify your setup
```bash
python3 test_local.py
```

All 21 tests should pass. If they do, your environment is good.

---

## Demo Scenarios

Five pre-seeded scenarios covering all 5 agent categories:

| # | Ticket | Category | Pattern |
|---|--------|----------|---------|
| 1 | `CodePipeline deploy failed — ECS task OOM killed` | CI/CD | 🔄 RECURRING (88%) |
| 2 | `Lambda function can't write to S3 bucket prod-reports` | Access/IAM | ✨ NEW |
| 3 | `Glue job daily_claims_load failed with connection timeout` | Data/ETL | ✨ NEW + auto re-run |
| 4 | `EC2 instance i-0abc123 unreachable, disk at 98%` | Infrastructure | ✨ NEW |
| 5 | `API gateway returning 503, backend health checks failing` | Network | ✨ NEW |

**Scenario 1** is the best for showing the recurring pattern path — it matches at 88% confidence and pulls a proven fix instantly without calling the LLM sub-agent.

**Scenario 3** shows the Glue auto-remediation — the agent detects the job name, checks its status, and re-triggers it automatically.

---

## How to Test as a Team

### Individual testing (no coordination needed)
Each team member runs:
```bash
python3 test_local.py
```
This is fully isolated — uses in-memory mocks, no shared state.

### Integration testing (shared EC2)
```bash
python3 run_local.py
```
Pick a scenario, type `approve` or `reject` when prompted.

### End-to-end via web
Open the dashboard URL and click demo buttons. Each click is independent.

### Custom ticket
In the web dashboard, type any IT issue in the text box and click **Run Agent**.

Or via CLI:
```bash
python3 app.py "Your custom ticket description here"
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: strands` | `pip install strands-agents` |
| `ModuleNotFoundError: moto` | `pip install moto[dynamodb,s3]` |
| Bedrock `ResourceNotFoundException` | Model not enabled — ask organizers to enable Nova Lite in Bedrock console |
| Bedrock `AccessDenied` | Check AWS credentials: `aws sts get-caller-identity` |
| Tests fail | Run `pip install -r requirements.txt` then retry |
| Dashboard shows error | Check Lambda logs: `aws logs tail /aws/lambda/it-ticket-agent-api --since 5m` |
| Pattern confidence too low | Ticket wording doesn't match keywords — try the exact demo phrases above |

---

## Key Files to Understand the Code

| File | What to read |
|------|-------------|
| `agent_core/master_agent.py` | Full pipeline orchestration — start here |
| `tools/classifier.py` | How Bedrock Nova classifies tickets |
| `tools/pattern_matcher.py` | Jaccard similarity confidence scoring |
| `agent_core/data_agent.py` | Glue job detection + auto re-run logic |
| `agent_core/base_agent.py` | How sub-agents call Bedrock with runbook context |
| `test_local.py` | Best way to understand expected behavior |

---

## AgentCore Deployment

The agent is deployed to Amazon Bedrock AgentCore Runtime:

```
ARN: arn:aws:bedrock-agentcore:us-west-2:628875594738:runtime/it_ticket_agent_agentcore_app-Y14wFRAyTO
```

To redeploy after changes:
```bash
agentcore launch
```

To invoke via AgentCore CLI:
```bash
agentcore invoke '{"prompt": "CodePipeline deploy failed — ECS task OOM killed"}'
```

To check status:
```bash
agentcore status
```
