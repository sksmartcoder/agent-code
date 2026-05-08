# Hackathon Learnings — IT Ticket Intelligence Agent

Built during AWS Hackathon using Amazon Bedrock AgentCore + Strands SDK.
This document captures what worked, what didn't, and what we'd do differently.

---

## What We Built

A multi-agent IT support triage system that:
- Classifies IT tickets by category and severity using AI
- Detects recurring patterns and pulls proven fixes
- Routes new issues to specialist sub-agents (CI/CD, Data/ETL, Infra, Access/IAM, Network)
- Auto-remediates Glue job failures
- Supports agent-to-agent communication via a message bus
- Deployed to AWS Lambda + S3 (web dashboard) + AgentCore Runtime

---

## AWS Services Used

| Service | Purpose | Status |
|---|---|---|
| Amazon Bedrock Nova Lite | AI classification + fix generation | ✅ Worked great |
| AWS Lambda | API backend for web dashboard | ✅ Deployed |
| Amazon S3 | Static web dashboard + runbooks | ✅ Deployed |
| AgentCore Runtime | Cloud agent deployment | ✅ Deployed, cold start issue |
| AgentCore Memory | Short-term memory (STM) | ✅ Created |
| DynamoDB | Ticket/pattern/resolution storage | ❌ No permissions — used moto |
| AWS Glue | ETL job re-run | ❌ No permissions — used moto |
| CloudFormation | Infrastructure as code | ❌ No permissions |
| CloudWatch | Logs + GenAI Observability | ✅ Logs working |
| X-Ray | Distributed tracing | ✅ Configured |

---

## Key Technical Learnings

### 1. Amazon Bedrock Model Access
**Problem:** Claude 3 Sonnet and Claude 3.5 Haiku both returned `ResourceNotFoundException` — marked as legacy, access denied after 30 days of inactivity.

**Fix:** Switched to **Amazon Nova Lite** (`us.amazon.nova-lite-v1:0`) which was active and accessible.

**Learning:** Always check model access in Bedrock Console → Model access before building. Nova models are the current generation and more reliable for hackathons.

---

### 2. Strands SDK + Nova Model Compatibility
**Problem:** Strands `Agent` uses `ConversreStream` API internally. Nova models don't support streaming the same way Claude does — got 404 errors.

**Fix:** Bypassed Strands for LLM calls and used direct `boto3.invoke_model()` with Nova's message format:
```python
body = json.dumps({
    "system": [{"text": system_prompt}],
    "messages": [{"role": "user", "content": [{"text": prompt}]}],
    "inferenceConfig": {"maxTokens": 256, "temperature": 0.1},
})
```

**Learning:** Strands SDK works best with Claude models. For Nova, use direct boto3 calls. The Strands `@tool` decorator and agent orchestration still work — just swap the LLM call layer.

---

### 3. AgentCore Cold Start Limit
**Problem:** AgentCore Runtime has a **30-second initialization limit**. Our `agentcore_app.py` was importing moto, creating DynamoDB tables, seeding data, and uploading runbooks at startup — took 45+ seconds.

**Fix 1 (lazy init):** Moved all bootstrap code inside the first request handler call.

**Fix 2 (drop moto):** Replaced moto entirely with plain Python dicts for in-memory storage. Zero import overhead, initializes in under 1 second.

**Learning:** AgentCore cold start is strict. Keep imports minimal at module level. Any heavy initialization must be lazy or pre-warmed.

---

### 4. IAM Permissions on EC2 Instance Role
**Problem:** The workshop EC2 instance role (`simple-ec2-UbuntuDesktopInstanceRole`) had very limited permissions — no DynamoDB, no CloudFormation, no EC2 security group changes, no Glue.

**What we could do:**
- S3 read/write ✅
- Bedrock invoke ✅
- Lambda create/update ✅
- IAM role read/update ✅
- AgentCore deploy ✅

**Workarounds:**
- DynamoDB → moto in-memory mock
- Glue → moto in-memory mock
- CloudFormation → direct boto3 calls
- Security group → S3 static site (no port needed)

**Learning:** Always check IAM permissions on day 1 of a hackathon. Run `aws sts get-caller-identity` and test each service you plan to use before building.

---

### 5. Lambda Function URL Public Access
**Problem:** Lambda Function URL with `AuthType: NONE` still returned 403 Forbidden from public internet, even with correct resource policy.

**Root cause:** Account-level restriction on public Lambda Function URL invocations.

**Workaround:** Invoked Lambda via `boto3.invoke()` directly from the EC2 instance (bypasses the HTTP endpoint). The web dashboard calls Lambda this way.

**Learning:** Lambda Function URLs may be restricted at the account level in workshop environments. Test with `curl` immediately after creating the URL.

---

### 6. moto Mock vs Real AWS
**What moto does well:**
- DynamoDB CRUD — perfect replacement
- S3 get/put — works fine
- Glue job create/run — works for demo

**moto gotcha:** `mock_aws()` intercepts ALL boto3 calls including Bedrock. Must create real Bedrock client BEFORE starting the mock:
```python
real_bedrock = boto3.client("bedrock-runtime", region_name="us-west-2")
mock = mock_aws()
mock.start()
# Now patch the LLM call functions to use real_bedrock
```

**Learning:** moto is excellent for hackathon demos when you don't have real AWS permissions. Just be careful about call interception order.

---

### 7. Multi-Agent Architecture with Strands
**What we implemented:**
- Master Agent orchestrates the pipeline
- 5 specialist sub-agents (CI/CD, Data/ETL, Infra, Access/IAM, Network)
- Agent Message Bus for structured agent-to-agent communication
- DataETLAgent consults InfraAgent when storage keywords detected

**Strands `@tool` decorator:** Works well for wrapping functions as agent tools. The master agent can call tools in sequence.

**Learning:** For a hackathon, a simple Python orchestrator calling sub-agents directly is faster to build and debug than full Strands multi-agent. Add the message bus layer after the core pipeline works.

---

### 8. Pattern Matching Algorithm
Used Jaccard similarity on keyword sets:
```
score = (jaccard * 50) + (keyword_hit_ratio * 50)
```

**What worked:** CI/CD OOM pattern matched at 88% consistently.

**What didn't:** Short keywords like "ECS", "RDS", "VPC", "IAM" (3 chars) were filtered out by the 3-char minimum tokenizer. This hurt pattern matching for some categories.

**Fix:** Lower the minimum token length to 2 chars, or add a keyword whitelist for AWS service names.

---

### 9. AgentCore Observability
**What's available:**
- CloudWatch Logs: `/aws/bedrock-agentcore/runtimes/<agent-id>-DEFAULT`
- X-Ray tracing: configured automatically by `agentcore deploy`
- GenAI Observability Dashboard: CloudWatch → GenAI Observability

**Tracing in console showed "Not enabled"** — this is the CloudWatch Transaction Search feature, separate from X-Ray. It requires `logs:CreateLogGroup` on vendedlogs which was blocked by the instance role.

**Learning:** AgentCore observability has multiple layers. X-Ray works without extra permissions. CloudWatch Transaction Search needs additional IAM grants.

---

### 10. Static Web Dashboard on S3
**What worked perfectly:**
- S3 static website hosting — zero server needed
- Lambda Function URL as API backend (from EC2, not public internet)
- No port configuration, no security groups, publicly accessible

**Learning:** For hackathon demos, S3 static site + Lambda is the fastest path to a shareable URL. No EC2 ports, no Docker, no server management.

---

## What We'd Do Differently

1. **Check model access on day 1** — 30 minutes lost switching from Claude to Nova
2. **Test Lambda Function URL publicly immediately** — discovered the 403 issue late
3. **Use real DynamoDB from the start** — ask organizers for permissions upfront
4. **Pre-warm AgentCore** — invoke it once before the demo to avoid cold start
5. **Add a `--mock` flag to app.py** — easier switching between real and mock AWS
6. **Seed more diverse patterns** — the pattern matcher needs more keyword coverage for short AWS service names

---

## Architecture Decisions That Paid Off

- **Dependency injection** (`dynamodb=None`, `s3_client=None`) — made switching between real and mock trivial
- **Strands for LLM abstraction** — easy to swap models
- **Agent Message Bus** — clean separation, easy to trace agent interactions
- **Structured tracer** — timestamped JSONL log made debugging fast
- **S3 runbooks** — domain knowledge separate from code, easy to update

---

## Demo Tips for Future Hackathons

- Run scenario 1 (CI/CD OOM) first — it hits the recurring pattern at 88% and resolves instantly. Most impressive for non-technical audiences.
- Run scenario 3 (Glue timeout) second — shows the auto-remediation story.
- Have the architecture diagram open in a second tab.
- Pre-invoke the Lambda before the demo to warm it up.
- Show CloudWatch logs during the demo — real-time log streaming looks impressive.

---

## Useful Commands

```bash
# Check what AWS services you can access
aws sts get-caller-identity
aws bedrock list-foundation-models --region us-west-2 --query "modelSummaries[?contains(modelId,'nova')].modelId"

# Run all tests (no AWS needed)
python3 test_local.py

# Visual terminal demo
python3 demo.py

# Redeploy Lambda
python3 lambda/deploy_lambda.py

# Redeploy AgentCore
agentcore deploy

# Check AgentCore status
agentcore status

# View CloudWatch logs
aws logs tail /aws/bedrock-agentcore/runtimes/it_ticket_agent_agentcore_app-Y14wFRAyTO-DEFAULT --since 1h

# Invoke all 5 scenarios to generate traces
python3 -c "
import boto3, json
lm = boto3.client('lambda', region_name='us-west-2')
for desc in [
    'CodePipeline deploy failed ECS task OOM killed',
    'Glue job daily_claims_load failed with connection timeout',
    'API gateway returning 503 backend health checks failing',
    'Lambda function cant write to S3 bucket prod-reports',
    'EC2 instance unreachable disk at 98 percent',
]:
    r = lm.invoke(FunctionName='it-ticket-agent-api', InvocationType='RequestResponse',
        Payload=json.dumps({'body': json.dumps({'description': desc}), 'requestContext': {'http': {'method': 'POST'}}}))
    b = json.loads(json.loads(r['Payload'].read()).get('body','{}'))
    print(b.get('category'), b.get('severity'), b.get('final_status'))
"
```

---

## Resources

- Strands SDK docs: https://strandsagents.com
- AgentCore docs: https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html
- Nova model guide: https://docs.aws.amazon.com/bedrock/latest/userguide/titan-models.html
- moto docs: https://docs.getmoto.org
- GitHub repo: https://github.com/sksmartcoder/agent-code
