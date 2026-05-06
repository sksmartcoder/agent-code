# Demo Script — IT Ticket Intelligence Agent

## Pre-Demo Setup (do before presentation)
```bash
ssh -i hackathon-key.pem ec2-user@<instance-ip>
cd /home/ec2-user/it-ticket-agent
python3.11 infrastructure/dynamodb_setup.py
python3.11 infrastructure/s3_setup.py
python3.11 data/load_tickets.py
```

## Demo Flow (2-3 minutes)

### Opening (15 seconds)
"We built an AI-powered IT ticketing system that classifies, routes, and auto-fixes recurring issues — all running on AWS with DynamoDB replacing Jira."

---

### Demo 1: Recurring Issue — Auto-Fix (45 seconds)

```bash
python3.11 app.py submit "CodePipeline deploy failed — ECS task OOM killed again"
```

**What audience sees:**
- Agent classifies: CI/CD | P2 | DevOps Engineering
- Agent detects: RECURRING (matched 3 prior tickets, 100% success rate)
- Agent suggests: "Increase ECS task memory from 512MB to 1024MB"
- Status: PENDING_APPROVAL

**Then approve it:**
```bash
python3.11 app.py approve TKT-XXXXXXXX
```

**Talking point:** "This issue happened 3 times before. The agent recognized the pattern, pulled the proven fix, and it's ready to apply — just needs human approval. 30 seconds vs 30 minutes."

---

### Demo 2: New Issue — Investigate & Route (45 seconds)

```bash
python3.11 app.py submit "Lambda function can't write to S3 bucket prod-claims-output, getting AccessDenied"
```

**What audience sees:**
- Agent classifies: Access/IAM | P3 | Security Operations
- Agent detects: NEW (no prior pattern match)
- Agent investigates: looks up IAM runbook
- Agent suggests: "Add s3:PutObject to Lambda execution role, scoped to bucket/prefix"
- Status: OPEN → routed to Security Operations team

**Talking point:** "New issue — agent can't auto-fix, but it investigates, suggests a fix with the exact IAM policy, and routes to the right team. Human reviews and approves."

---

### Demo 3: P1 Escalation (30 seconds)

```bash
python3.11 app.py submit "Production API completely down, all health checks failing, customers impacted"
```

**What audience sees:**
- Agent classifies: Network | P1 | Network Engineering
- Agent: ESCALATED immediately
- Agent suggests fix but flags for immediate human attention

**Talking point:** "P1 = production down. Agent doesn't wait — it escalates immediately while still providing a suggested fix. No time wasted on triage."

---

### Demo 4: Dashboard View (15 seconds)

```bash
python3.11 app.py dashboard
```

**What audience sees:**
- Open tickets with severity and category
- Pending approvals with suggested fixes
- Team assignments

**Talking point:** "Full visibility. Any team lead can see what's open, what's pending approval, and what's been auto-resolved."

---

### Closing (15 seconds)
"Built in 2.5 days on AWS sandbox. No Jira needed — DynamoDB with Streams gives us real-time event processing. The agent learns from every resolution, so recurring issues get faster over time. Questions?"

---

## Backup: If Something Breaks During Demo

Have these pre-recorded terminal outputs ready as screenshots:
1. Successful recurring ticket flow
2. New ticket investigation
3. Dashboard view

## Key Points to Emphasize

1. **Pattern Memory** — Agent remembers past issues and their fixes
2. **Human-in-the-Loop** — Never auto-applies without approval (compliance-friendly)
3. **Multi-Agent** — Specialist sub-agents for each domain (CI/CD, Data, Infra, IAM, Network)
4. **Audit Trail** — Every decision logged in DynamoDB (financial services requirement)
5. **DynamoDB Streams** — Simulates Jira webhooks for real-time processing
6. **No External Dependencies** — Runs entirely in AWS sandbox
