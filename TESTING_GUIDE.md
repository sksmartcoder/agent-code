# IT Ticket Agent — Installation & Testing Guide

For team members installing on their own EC2 instance.

---

## Step 1 — Get the Code

Open a terminal on your EC2 instance and run:

```bash
git clone https://github.com/sksmartcoder/agent-code.git
cd agent-code/it-ticket-agent
```

---

## Step 2 — Install Dependencies

```bash
pip3 install -r requirements.txt
```

If `pip3` is not found:
```bash
sudo apt update && sudo apt install python3-pip -y
pip3 install -r requirements.txt
```

---

## Step 3 — Verify AWS Access

```bash
aws sts get-caller-identity
```

You should see your account ID and role. If you get an error, your EC2 instance role does not have AWS access — ask the organizers to attach the correct IAM role.

---

## Step 4 — Set Environment Variables

```bash
export AWS_DEFAULT_REGION=us-west-2
export BEDROCK_REGION=us-west-2
export BEDROCK_MODEL_ID=us.amazon.nova-lite-v1:0
```

Or load from the `.env` file:
```bash
export $(cat .env | grep -v '#' | xargs)
```

---

## Step 5 — Run the Test Suite

```bash
python3 test_local.py
```

Expected:
```
Ran 21 tests in ~2s
OK
```

This uses mocked AWS — no real credentials needed. If all 21 pass, your setup is correct.

---

## Step 6 — Run the Visual Demo

```bash
python3 demo.py
```

Pick a number from the menu and press Enter. The agent will run the full pipeline with real Bedrock Nova AI.

---

## Test Cases to Run

Run each of these and verify the expected result.

### CI/CD Pipeline Error
```bash
python3 app.py "CodePipeline deploy failed — ECS task OOM killed"
```
Expected: Category `CI/CD`, Severity `P2`, Pattern `RECURRING` at ~88% confidence, fix pulled from knowledge base.

---

### Network Error
```bash
python3 app.py "API gateway returning 503, backend health checks failing"
```
Expected: Category `Network`, Severity `P1`, Network specialist agent kicks off, fix mentions security group inbound rule.

---

### Data/ETL with Glue Auto-Remediation
```bash
python3 app.py "Glue job daily_claims_load failed with connection timeout"
```
Expected: Category `Data/ETL`, Glue job detected, auto re-run attempted, fix includes `[AUTO-ACTION]`.

---

### Access/IAM Error
```bash
python3 app.py "Lambda function can't write to S3 bucket prod-reports"
```
Expected: Category `Access/IAM`, Severity `P3`, fix mentions `s3:PutObject` policy.

---

### Infrastructure P1
```bash
python3 app.py "EC2 instance i-0abc123 unreachable, disk at 98%"
```
Expected: Category `Infrastructure`, Severity `P1` (red/critical), fix mentions EBS volume extension.

---

## Verify in AWS Console

### Bedrock was called
1. AWS Console → Amazon Bedrock → us-west-2
2. Left menu → **Model invocations**
3. You should see recent calls to `us.amazon.nova-lite-v1:0` after running the agent

### Lambda execution logs
1. AWS Console → Lambda → `it-ticket-agent-api`
2. Monitor tab → **View CloudWatch logs**
3. Each web dashboard run creates a new log entry with `ticket_id`, `category`, `final_status`

### AgentCore Runtime
1. AWS Console → Amazon Bedrock → AgentCore → **Runtime**
2. Look for `it_ticket_agent_agentcore_app` — status should be `READY`

### S3 Runbooks
1. AWS Console → S3 → `amzn-hackthon-it-ticket-system`
2. Open `runbooks/` folder
3. Should contain 5 `.md` files (one per agent category)

### Web Dashboard (no install needed)
Open in any browser:
```
http://amzn-hackthon-it-ticket-system.s3-website-us-west-2.amazonaws.com
```

---

## How to Know Which Agent Ran

In the terminal output, look for:

```
[4/5] Delegating to 🔧 CI/CD sub-agent...
```
or
```
[4/5] Fetching proven fix from knowledge base...   ← recurring pattern, no sub-agent needed
```

Each category has its own specialist:
- `🔧 CI/CD` — pipeline, ECS, CodeBuild issues
- `🗄 Data/ETL` — Glue, RDS, JDBC issues
- `🖥 Infrastructure` — EC2, EBS, disk issues
- `🔑 Access/IAM` — Lambda roles, S3 permissions
- `🌐 Network` — VPC, ALB, API Gateway issues

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: strands` | `pip3 install strands-agents` |
| `ModuleNotFoundError: moto` | `pip3 install "moto[dynamodb,s3]"` |
| `aws: command not found` | `sudo apt install awscli -y` |
| Bedrock returns `ResourceNotFoundException` | Model not enabled — ask organizers to enable Nova Lite in Bedrock console → Model access |
| Classification returns `Unknown` | Bedrock call failed — check `aws sts get-caller-identity` |
| `python3: command not found` | `sudo apt install python3 -y` |
| Tests fail with import error | `pip3 install -r requirements.txt` then retry |

---

## Quick Reference

| Task | Command |
|---|---|
| Run all tests | `python3 test_local.py` |
| Visual demo menu | `python3 demo.py` |
| Single ticket | `python3 app.py "your ticket description"` |
| Interactive runner | `python3 run_local.py` |
| Web dashboard | http://amzn-hackthon-it-ticket-system.s3-website-us-west-2.amazonaws.com |
