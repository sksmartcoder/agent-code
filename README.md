# IT Ticket Intelligence Agent

AI-powered IT support triage using multi-agent orchestration on AWS. Classifies tickets, detects recurring patterns, auto-remediates (e.g. Glue job re-run), and routes to the right specialist agent — all powered by Amazon Bedrock Nova Lite + Strands SDK + AgentCore Runtime.

**Built at AWS Hackathon 2026 — May 6-8, us-west-2 (Oregon)**

---

## Live Demo Assets

| Asset | URL |
|---|---|
| 🌐 Web Dashboard | http://amzn-hackthon-it-ticket-system.s3-website-us-west-2.amazonaws.com |
| 📊 Demo Report (5/5 agents) | .../demo_report.html |
| 🎞 Slideshow (14 slides) | .../demo_slow.html |
| 📐 Architecture Diagram | .../architecture.html |
| 🔄 Process Flow | .../process_flow.html |
| 💻 GitHub | https://github.com/sksmartcoder/agent-code |

---

## What It Does

1. Submit an IT support ticket (text description)
2. **Master Agent** classifies it by category and severity using Bedrock Nova Lite
3. Checks if it's a **recurring pattern** (88%+ confidence match via Jaccard similarity)
4. Routes to the right **specialist sub-agent** (CI/CD, Data/ETL, Infra, Access/IAM, Network)
5. Sub-agent fetches the domain runbook from S3 and generates a fix using AI
6. For Data/ETL tickets — **automatically re-triggers failed Glue jobs**
7. Presents the fix for operator approval → logs resolution → learns for next time

---

## AWS Services Used

| Service | Purpose | Status |
|---|---|---|
| Amazon Bedrock Nova Lite | AI classification + fix generation | ✅ Live |
| AgentCore Runtime | Managed agent deployment + memory | ✅ Deployed |
| AgentCore Memory (STM) | Short-term memory across sessions | ✅ Active |
| AWS Lambda | API backend for web dashboard | ✅ Live |
| Amazon S3 | Static dashboard + 5 domain runbooks | ✅ Live |
| CloudWatch | Agent execution logs + GenAI observability | ✅ Live |
| DynamoDB | Ticket/pattern/resolution storage | ⚠ moto mock (no permissions) |
| AWS Glue | ETL job re-run automation | ⚠ moto mock (no permissions) |

---

## Strands SDK Usage

The agent uses [Strands Agents SDK](https://strandsagents.com) for LLM orchestration:

```python
from strands import Agent, tool
from strands.models import BedrockModel

# Classifier — single-turn structured JSON output
model = BedrockModel(
    model_id="us.amazon.nova-lite-v1:0",
    region_name="us-west-2",
    temperature=0.1,
    max_tokens=256,
)
agent = Agent(model=model, system_prompt="You are an IT triage assistant...")
response = agent("Classify this ticket: CodePipeline deploy failed")
# → {"category": "CI/CD", "severity": "P2", "rationale": "..."}
```

**Note:** Strands streaming is incompatible with Nova models. We use direct `boto3.invoke_model()` for Nova calls and Strands for orchestration structure.

---

## AgentCore Runtime

The agent is deployed to Amazon Bedrock AgentCore Runtime:

```
Name: it_ticket_agent_agentcore_app
ARN:  arn:aws:bedrock-agentcore:us-west-2:628875594738:runtime/it_ticket_agent_agentcore_app-Y14wFRAyTO
Status: READY
Versions: 5 (latest = minimal 32MB package, no moto)
Memory: STM_ONLY (it_ticket_agent_agentcore_app_mem-MUuxuh3Oi0)
```

**Invoke via CLI:**
```bash
agentcore invoke '{"prompt": "CodePipeline deploy failed — ECS task OOM killed"}'
```

**Redeploy:**
```bash
agentcore deploy
```

**Check status:**
```bash
agentcore status
```

**Key learning:** AgentCore has a 30-second cold start limit. The package must be minimal — no moto, no heavy test dependencies. We reduced from 51MB → 32MB by using a minimal `requirements.txt` (bedrock-agentcore + strands-agents + boto3 only).

---

## Agent-to-Agent Communication

Agents communicate via a structured **Agent Message Bus** (`tools/agent_bus.py`):

```
MasterAgent ──REQUEST──▶ DataETLAgent
DataETLAgent ──NOTIFY──▶ InfraAgent   (when storage keywords detected)
InfraAgent ──RESPONSE──▶ DataETLAgent (disk remediation steps)
DataETLAgent ──RESPONSE──▶ MasterAgent
```

Every message is logged with sender, receiver, type, and payload.

---

## Architecture

```
Browser / CLI / AgentCore invoke
          │
          ▼
┌─────────────────────────────────────────────┐
│           MASTER AGENT                      │
│  Strands SDK + Amazon Bedrock Nova Lite     │
│  1. Validate & create ticket                │
│  2. Classify → Category + Severity          │
│  3. Pattern match (Jaccard similarity)      │
│  4. Route: RECURRING → KB | NEW → Agent    │
│  5. Present fix → approve / reject          │
│  6. Log resolution + update patterns        │
└──────────────┬──────────────────────────────┘
               │  Agent Message Bus
    ┌──────────┼──────────────────────┐
    ▼          ▼          ▼           ▼
🔧 CI/CD   🗄 Data/ETL  🖥 Infra   🔑 IAM   🌐 Network
               │
          Auto re-run ──▶ AWS Glue
               │
    Amazon Bedrock Nova Lite ←── S3 Runbooks
```

---

## Project Structure

```
it-ticket-agent/
├── app.py                    # CLI entry point
├── config.py                 # Environment config
├── demo.py                   # Rich terminal demo
├── run_local.py              # Interactive local runner (real Bedrock)
├── test_local.py             # 21 unit tests (no AWS needed)
├── test_agents.py            # Agent routing tests
├── agentcore_app.py          # AgentCore Runtime entrypoint (minimal)
├── run_demo_report.py        # Generate HTML demo report via Lambda
├── demo_capture.py           # Browser automation for screenshots
├── demo_slow.html            # 14-slide demo slideshow
├── create_presentation.py    # Generate PowerPoint presentation
├── IT_Ticket_Agent_Presentation.pptx
├── architecture.html         # Architecture diagram
├── process_flow.html         # Process flow (simple + technical views)
├── LEARNINGS.md              # Hackathon learnings
├── TESTING_GUIDE.md          # Team testing instructions
├── requirements.txt          # Full dependencies
├── requirements_agentcore.txt # Minimal deps for AgentCore
│
├── agent_core/
│   ├── master_agent.py       # Orchestrator + tracer + agent bus
│   ├── base_agent.py         # Shared Strands Agent logic + tracing
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
│   ├── pattern_matcher.py    # Jaccard similarity confidence scoring
│   ├── knowledge_base.py     # S3 runbook fetch
│   ├── notifier.py           # Approval flow
│   ├── tracer.py             # Structured agent tracing (JSONL)
│   └── agent_bus.py          # Agent-to-agent message bus
│
├── knowledge_base/           # Domain runbooks (in S3)
│   ├── cicd_runbook.md
│   ├── data_runbook.md
│   ├── infra_runbook.md
│   ├── access_runbook.md
│   └── network_runbook.md
│
├── lambda/
│   ├── handler.py            # Lambda handler with CloudWatch logging
│   ├── deploy_lambda.py      # Deploy Lambda
│   └── deploy_static.py      # Deploy S3 dashboard
│
├── screenshots_slow/         # 35 demo screenshots
└── it-ticket-agent-complete.zip  # Full project zip for redistribution
```

---

## Quick Start — New AWS Account

```bash
# 1. Clone
git clone https://github.com/sksmartcoder/agent-code.git
cd agent-code/it-ticket-agent

# 2. Install
pip install -r requirements.txt

# 3. Verify (no AWS needed)
python3 test_local.py
# Expected: 21 tests, OK

# 4. Set environment
export AWS_DEFAULT_REGION=us-west-2
export BEDROCK_REGION=us-west-2
export BEDROCK_MODEL_ID=us.amazon.nova-lite-v1:0

# 5. Enable Bedrock model access in AWS Console
# → Bedrock → Model access → Enable Nova Lite

# 6. Deploy Lambda + dashboard
python3 lambda/deploy_lambda.py
python3 lambda/deploy_static.py

# 7. Deploy to AgentCore
pip install bedrock-agentcore-starter-toolkit
agentcore configure --entrypoint agentcore_app.py --non-interactive
agentcore deploy

# 8. Run demo
python3 run_local.py
```

---

## Demo Scenarios

| # | Ticket | Category | Pattern | Special |
|---|--------|----------|---------|---------|
| 1 | `CodePipeline deploy failed — ECS task OOM killed` | CI/CD | 🔄 RECURRING 88% | Proven fix from KB |
| 2 | `Lambda function can't write to S3 bucket prod-reports` | Access/IAM | ✨ NEW | IAM agent |
| 3 | `Glue job daily_claims_load failed with connection timeout` | Data/ETL | ✨ NEW | **Auto Glue re-run** |
| 4 | `EC2 instance i-0abc123 unreachable, disk at 98%` | Infrastructure | ✨ NEW | P1 critical |
| 5 | `API gateway returning 503, backend health checks failing` | Network | ✨ NEW | Network agent |

---

## Key Learnings

See `LEARNINGS.md` for full details. Summary:

- **Nova Lite** replaced Claude 3 Sonnet (legacy/access denied in workshop account)
- **Strands streaming** incompatible with Nova — used direct boto3 calls
- **AgentCore cold start** 30s limit — dropped moto, used Python dicts, reduced package 51MB→32MB
- **Lambda Function URL** 403 from public internet — account-level restriction
- **moto** excellent for DynamoDB/S3/Glue mocking when no real permissions
- **S3 static site + Lambda** = fastest path to shareable demo URL

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: strands` | `pip install strands-agents` |
| `ModuleNotFoundError: moto` | `pip install "moto[dynamodb,s3]"` |
| Bedrock `ResourceNotFoundException` | Enable Nova Lite in Bedrock Console → Model access |
| AgentCore cold start timeout | Use `requirements_agentcore.txt` (minimal deps) |
| Tests fail | `pip install -r requirements.txt` then retry |
| Dashboard blank | Check Lambda logs: `aws logs tail /aws/lambda/it-ticket-agent-api --since 5m` |

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
