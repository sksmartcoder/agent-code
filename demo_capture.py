#!/usr/bin/env python3
"""
IT Ticket Agent — Technical Demo Capture
3 speed modes: slow (3min), medium (2min), fast (1min)
Shows: Lambda test, CloudWatch logs, Bedrock invocations,
       AgentCore runtime, Glue re-run, human approval loop

Usage:
    python3 demo_capture.py --speed slow    # 3 min, max narration
    python3 demo_capture.py --speed medium  # 2 min
    python3 demo_capture.py --speed fast    # 1 min, quick overview
"""
import os, sys, json, time, boto3, base64, argparse
from datetime import datetime, timezone
from pathlib import Path

# ── Args ──────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--speed", choices=["slow","medium","fast"], default="medium")
args = parser.parse_args()

SPEEDS = {
    "slow":   {"page": 8, "action": 4, "label": "SLOW (3 min — full narration)"},
    "medium": {"page": 5, "action": 2, "label": "MEDIUM (2 min — balanced)"},
    "fast":   {"page": 3, "action": 1, "label": "FAST (1 min — quick overview)"},
}
S = SPEEDS[args.speed]
PAGE_WAIT   = S["page"]
ACTION_WAIT = S["action"]

REGION   = "us-west-2"
FUNCTION = "it-ticket-agent-api"
BUCKET   = "amzn-hackthon-it-ticket-system"
AGENT_ID = "it_ticket_agent_agentcore_app-Y14wFRAyTO"
LOG_GROUP = f"/aws/lambda/{FUNCTION}"
AGENTCORE_LOG = f"/aws/bedrock-agentcore/runtimes/{AGENT_ID}-DEFAULT"

OUT_DIR = Path(f"it-ticket-agent/screenshots_{args.speed}")
OUT_DIR.mkdir(exist_ok=True)

FEDERATION_URL = "https://signin.aws.amazon.com/federation?Action=login&Issuer=workshopstudio&Destination=https://us-west-2.console.aws.amazon.com/console/home&SigninToken=bdyKNdIPwZM4k4yOlMH_4uympt7wuf1BlR1nBniopWiG-O8OjZMWidgG33iodP6FyQFgyK6yj8gxomZnG5af_U_7SK5Udh-AVg48aM5Upqj_E4AvlvF_A3qfhd_o2PV_qFqKOLOn5tGa1rysSMJFUMvSl-hVAhKOaNJ3y3tws-vy2dBK-I2gBocqLWlQxBdoBJkXVNtMCvM0qbuSHanIpLxtqW6J-0CwNnkBpi70hfGo7ZETF-iqKpOiKaywQhBShkKvhg2RT9TimN8_xOe_MbiL7m7Q5KYjEVpqAwOrRwYuJjlpayYBx49mGflLGChM89kPi077Y8XguBI9VCgwMB5dI3YG04FvMFlXbGSKpjb5etAcioW6kIFUdgTm6hYOh68WYR8HZflxH5bnxJEDFlWg0ohHS60BBOLvdKRG_JB1Zkb40dTYrRanzAznAItGIp2CsBe3priq6t1EJrvdxGAx-q3tZSeaRyN2GIRM_-7eUieQZFk8LY-jMmqhpHzBjS0XHFs2PrI9NfRZQn60CqMTlMwufzHB-G-y1gyy5495-20HQfrfaC-Hmtv1CjiqfC7OFxoTP8fLm3yTFo2gKBgckquu11RkZBmU1KaZEFXseIubBnQrFn2cB7XGhll2Xs2ot18Tkwc_tbH3USH049PQDBFMChnioCur1WzOHGewBmdDqC6Vx0rHh6Yw2bxA7itRrwuRWqTA6w20wostFTcSXFXK1agcqVRxgJW_9slPVZQzQK_-38Gei5w8YT67s9wNB0fFGfFzbmeQrwjyCx27Q-cyccyAuA7vUIWBSob1fJIG4851AOGpdHsNEI0l-ev45ysYU3hFnS8UHwckUNlH-ACNdK_W-fw0q3efrLy6Zsuf80aqjtdkw2LOpeXrLuPIFjeQ06esCuwFSCbH6_s0zoTK6xpXlRqgfRdelzE27-0FvWwqQ946qkjUuQHjxmJIxlt40osxO8nLTx4prEJE3Q-Ey007v7cZP0u5nqpy4NrU4O-wmQOnKDXwOc3aLWoMv3cARru57oZLVG2bCqdShdBtVCyDnsJ6PliZWXrmtWHXIV0T4_s63wBWfzfSZ5VI7679bH872vWTWp1EUu2yqBWcPUycZ2k17w-vr4CP_6BWzPnGOXe26W28xfb3vY0SQ088DOcL1UhxzMAZZtFSzxNT9KdewQQNQzzAmHGwJOp32i2N_JmVRxLW_pkE0H3eHNOxedn3n0u_38gkvO38w2xp_yVIYeNxFjWTgCLR-B_ILrh1aQwLOKmasi7GOtdH_JYWT5QsHucZiqRj6tWi6xUkIkS0wC_PPJ_j23qGzlQn2EDZ6nc5qJKf5-MgeWqTpFXYcv5npwmx2M1gNsy-Rrm4O7twzqxI3xcWhcYrV2QbdIApk_9WAqNJuNhFE93VzeSxto-pDexOtOpudFdP9-0QdLKcFcCDhedIrOp7OAzzrgGM5g"

# ── Demo steps: (url, filename, title, narration) ─────────────────────────────
STEPS = [
    # 1. AWS Console home
    (FEDERATION_URL, "01_aws_console",
     "AWS Console — Logged In",
     "We are logged into the AWS Workshop account in us-west-2 (Oregon). "
     "This is the hackathon environment where our IT Ticket Intelligence Agent is deployed."),

    # 2. Lambda function
    (f"https://console.aws.amazon.com/lambda/home?region={REGION}#/functions/{FUNCTION}",
     "02_lambda_function",
     "AWS Lambda — it-ticket-agent-api",
     "The agent runs as a Lambda function. It receives IT ticket descriptions, "
     "runs the full AI pipeline (classify → pattern match → sub-agent → resolve), "
     "and returns structured results. No server to manage."),

    # 3. Lambda test tab — CI/CD scenario
    (f"https://console.aws.amazon.com/lambda/home?region={REGION}#/functions/{FUNCTION}?tab=testing",
     "03_lambda_test_cicd",
     "Lambda Test — CI/CD Agent (CodePipeline OOM)",
     "We test the CI/CD agent directly from the Lambda console. "
     "Input: 'CodePipeline deploy failed — ECS task OOM killed'. "
     "The agent classifies it as CI/CD P2, matches a RECURRING pattern at 88% confidence, "
     "and returns the proven fix instantly — no LLM call needed for recurring issues."),

    # 4. Lambda test — Glue/Data agent
    (f"https://console.aws.amazon.com/lambda/home?region={REGION}#/functions/{FUNCTION}?tab=testing",
     "04_lambda_test_glue",
     "Lambda Test — Data/ETL Agent (Glue Job Re-run)",
     "The Data/ETL agent handles Glue job failures. "
     "It detects the job name from the ticket description, checks the last run status (FAILED), "
     "and automatically re-triggers the job. The response includes [AUTO-ACTION] with the new Job Run ID. "
     "This is the auto-remediation feature — no human needed to restart the job."),

    # 5. CloudWatch logs — Lambda
    (f"https://console.aws.amazon.com/cloudwatch/home?region={REGION}#logsV2:log-groups/log-group/$252Faws$252Flambda$252F{FUNCTION}",
     "05_cloudwatch_lambda_logs",
     "CloudWatch Logs — Lambda Execution Trace",
     "Every agent step emits a structured JSON log to CloudWatch. "
     "You can see: INTAKE → CLASSIFY (Bedrock Nova called) → PATTERN_MATCH → SUB_AGENT → RESOLVE. "
     "Each log entry has a timestamp, step name, status, and key data. "
     "This is the full audit trail of every ticket processed."),

    # 6. CloudWatch logs — AgentCore
    (f"https://console.aws.amazon.com/cloudwatch/home?region={REGION}#logsV2:log-groups/log-group/$252Faws$252Fbedrock-agentcore$252Fruntimes$252F{AGENT_ID}-DEFAULT",
     "06_cloudwatch_agentcore_logs",
     "CloudWatch Logs — AgentCore Runtime Trace",
     "The AgentCore runtime also writes logs to CloudWatch. "
     "These show the agent initialization, memory operations, and execution lifecycle. "
     "This is separate from the Lambda logs — it shows the orchestration layer."),

    # 7. GenAI Observability
    (f"https://console.aws.amazon.com/cloudwatch/home?region={REGION}#gen-ai-observability/agent-core",
     "07_genai_observability",
     "GenAI Observability Dashboard — Agent Tracing",
     "The GenAI Observability dashboard shows distributed traces across all agent invocations. "
     "Each trace shows the full request flow: entry → orchestration → Bedrock model call → response. "
     "This is how you monitor agent performance and identify bottlenecks in production."),

    # 8. Bedrock model invocations
    (f"https://console.aws.amazon.com/bedrock/home?region={REGION}#/model-invocation-logging",
     "08_bedrock_invocations",
     "Amazon Bedrock — Model Invocation Logs",
     "Every call to Amazon Bedrock Nova Lite is logged here. "
     "You can see the model ID (us.amazon.nova-lite-v1:0), input tokens, output tokens, and latency. "
     "The classifier uses ~256 tokens per call. Sub-agents use ~1024 tokens. "
     "This is where you track AI usage and costs."),

    # 9. Bedrock model access
    (f"https://console.aws.amazon.com/bedrock/home?region={REGION}#/models",
     "09_bedrock_models",
     "Amazon Bedrock — Nova Lite Model Active",
     "Amazon Nova Lite is the AI backbone of this solution. "
     "It replaced Claude 3 Sonnet which was marked legacy in this account. "
     "Nova Lite is fast, cost-effective, and handles both classification and fix generation. "
     "Model access is enabled at the account level here."),

    # 10. AgentCore Runtime
    (f"https://console.aws.amazon.com/bedrock/home?region={REGION}#/agentcore/runtimes",
     "10_agentcore_runtime",
     "AgentCore Runtime — Agent Deployed and READY",
     "The agent is deployed to Amazon Bedrock AgentCore Runtime. "
     "Status: READY. This is the managed runtime that hosts our agent code. "
     "It handles scaling, memory management (STM), and provides the invocation endpoint. "
     "The agent can be invoked via CLI: agentcore invoke '{\"prompt\": \"...\"}'"),

    # 10b. AgentCore obs list (tracing)
    (f"https://console.aws.amazon.com/bedrock/home?region={REGION}#/agentcore/runtimes/{AGENT_ID}",
     "10b_agentcore_detail",
     "AgentCore Runtime — Agent Detail View",
     "Drilling into the agent runtime shows: deployment type (Direct Code Deploy), "
     "Python 3.12 runtime, execution role, network mode (PUBLIC), "
     "memory configuration (STM_ONLY, 30-day retention), and the S3 deployment package. "
     "The agent was last updated with the latest code including agent bus and tracing."),

    # 11. AgentCore Memory
    (f"https://console.aws.amazon.com/bedrock/home?region={REGION}#/agentcore/memory",
     "11_agentcore_memory",
     "AgentCore Memory — Short-Term Memory Active",
     "AgentCore Memory provides short-term memory (STM) for the agent. "
     "This allows the agent to maintain context across multiple invocations in a session. "
     "Memory ID: it_ticket_agent_agentcore_app_mem. "
     "In production, this would store ticket history and resolution patterns."),

    # 12. S3 bucket — runbooks
    (f"https://console.aws.amazon.com/s3/buckets/{BUCKET}?region={REGION}&prefix=runbooks/",
     "12_s3_runbooks",
     "S3 — Domain Runbooks (Knowledge Base)",
     "The knowledge base lives in S3. Five domain runbooks: "
     "cicd_runbook.md, data_runbook.md, infra_runbook.md, access_runbook.md, network_runbook.md. "
     "Each sub-agent fetches its runbook before calling Bedrock, giving the AI domain-specific context. "
     "This is why the fixes are accurate and actionable, not generic."),

    # 12b. S3 runbook — data
    (f"https://console.aws.amazon.com/s3/buckets/{BUCKET}?region={REGION}&prefix=runbooks/data_runbook.md",
     "12b_s3_data_runbook",
     "S3 — Data/ETL Runbook (Glue, RDS, JDBC)",
     "The Data/ETL runbook is stored in S3 and fetched by the DataETLAgent before calling Bedrock. "
     "It contains step-by-step guidance for Glue job failures, JDBC timeouts, RDS connectivity issues. "
     "The AI uses this as context to generate accurate, domain-specific fix recommendations. "
     "Without the runbook, the agent still works but with lower confidence."),

    # 12c. S3 runbook — network
    (f"https://console.aws.amazon.com/s3/buckets/{BUCKET}?region={REGION}&prefix=runbooks/network_runbook.md",
     "12c_s3_network_runbook",
     "S3 — Network Runbook (VPC, ALB, Security Groups)",
     "The Network runbook guides the NetworkAgent on VPC troubleshooting, "
     "security group rules, ALB health checks, and API Gateway 503 errors. "
     "Each of the 5 specialist agents has its own domain runbook in S3. "
     "This is the knowledge base that makes the AI fixes actionable and accurate."),

    # 13. S3 bucket — dashboard
    (f"https://console.aws.amazon.com/s3/buckets/{BUCKET}?region={REGION}",
     "13_s3_dashboard",
     "S3 — Static Web Dashboard Hosted",
     "The web dashboard is hosted as a static site on S3. "
     "No server, no EC2, no port configuration needed. "
     "The dashboard calls Lambda directly for AI processing. "
     "URL: amzn-hackthon-it-ticket-system.s3-website-us-west-2.amazonaws.com"),

    # 14a. Live demo dashboard — empty
    (f"http://{BUCKET}.s3-website-{REGION}.amazonaws.com",
     "14a_live_dashboard",
     "Live Demo Dashboard — Ready to Accept Tickets",
     "The web dashboard is hosted on S3 — no server needed. "
     "It accepts IT ticket descriptions and shows the AI agent processing them in real time. "
     "Five demo scenarios are pre-loaded covering all 5 specialist agents."),

    # 14b. Demo report showing all results
    (f"http://{BUCKET}.s3-website-{REGION}.amazonaws.com/demo_report.html",
     "14b_demo_report",
     "Demo Report — All 5 Agents Verified with Real AI",
     "This report was generated by running all 5 scenarios through the live Lambda function. "
     "Every result shows: category (CI/CD, Data/ETL, Infrastructure, Access/IAM, Network), "
     "severity (P1-P4), pattern match status, AI confidence, and the full fix suggestion. "
     "All 5 agents passed with real Amazon Bedrock Nova Lite responses."),

    # 15. Demo report
    (f"http://{BUCKET}.s3-website-{REGION}.amazonaws.com/demo_report.html",
     "15_demo_report",
     "Demo Report — All 5 Agents Verified",
     "This report shows all 5 specialist agents running successfully with real Bedrock AI. "
     "CI/CD, Data/ETL, Infrastructure, Access/IAM, and Network agents all passed. "
     "Each result shows the category, severity, pattern match confidence, "
     "AI-generated fix, and AWS resources identified."),
]

# ── Step 1: Pre-run all Lambda scenarios to generate fresh logs ───────────────
print(f"\n{'='*60}")
print(f"  IT Ticket Agent Demo Capture — {S['label']}")
print(f"{'='*60}")
print("\n  Pre-running all 5 scenarios to generate fresh CloudWatch logs...")

lm = boto3.client("lambda", region_name=REGION)
scenarios = [
    ("CI/CD",          "CodePipeline deploy failed — ECS task OOM killed"),
    ("Data/ETL",       "Glue job daily_claims_load failed with connection timeout"),
    ("Infrastructure", "EC2 instance i-0abc123 unreachable, disk at 98%"),
    ("Access/IAM",     "Lambda function can't write to S3 bucket prod-reports"),
    ("Network",        "API gateway returning 503, backend health checks failing"),
]
lambda_results = {}
for cat, desc in scenarios:
    try:
        r = lm.invoke(FunctionName=FUNCTION, InvocationType="RequestResponse",
            Payload=json.dumps({"body": json.dumps({"description": desc}),
                               "requestContext": {"http": {"method": "POST"}}}).encode())
        body = json.loads(json.loads(r["Payload"].read()).get("body", "{}"))
        lambda_results[cat] = body
        print(f"  ✓ {cat:15} → {body.get('category','?')} / {body.get('severity','?')} / {body.get('final_status','?')}")
    except Exception as e:
        print(f"  ✗ {cat}: {e}")
    time.sleep(0.5)

print(f"\n  Waiting 10s for logs to propagate to CloudWatch...")
time.sleep(10)

# ── Step 2: Browser automation ────────────────────────────────────────────────
print(f"\n  Starting browser ({args.speed} speed — {PAGE_WAIT}s per page)...")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

opts = Options()
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--window-size=1600,900")
opts.add_argument("--disable-gpu")
opts.add_argument("--disable-software-rasterizer")
opts.add_argument("--disable-extensions")

screenshots = []

def make_driver():
    d = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    d.set_window_size(1600, 900)
    return d

def capture(driver, filename, title, narration, wait=None):
    w = wait or PAGE_WAIT
    time.sleep(w)
    path = OUT_DIR / f"{filename}.png"
    driver.save_screenshot(str(path))
    screenshots.append({"filename": filename, "title": title,
                        "narration": narration, "path": str(path)})
    print(f"  📸 [{len(screenshots):02d}] {title}")

# Navigate in batches of 5 — restart Chrome between batches to avoid crash
BATCH_SIZE = 5
print("\n  Logging into AWS Console...")
driver = make_driver()
driver.get(FEDERATION_URL)
time.sleep(10)  # wait for login

for batch_start in range(0, len(STEPS), BATCH_SIZE):
    batch = STEPS[batch_start:batch_start+BATCH_SIZE]
    if batch_start > 0:
        print(f"\n  Restarting browser for next batch...")
        try: driver.quit()
        except: pass
        driver = make_driver()
        # Re-login for each batch
        driver.get(FEDERATION_URL)
        time.sleep(8)
    for url, fname, title, narration in batch:
        try:
            driver.get(url)
            capture(driver, fname, title, narration)
        except Exception as e:
            print(f"  ⚠ Skipped {fname}: {e}")

# Extra: Dashboard with Glue demo result
print("\n  Capturing dashboard with Glue agent result...")
try:
    driver.get(f"http://{BUCKET}.s3-website-{REGION}.amazonaws.com")
    time.sleep(4)
    # Click the Glue demo button (3rd button = index 2)
    btns = driver.find_elements(By.CLASS_NAME, "btn-demo")
    if len(btns) >= 3:
        btns[2].click()  # Glue timeout scenario
        print("  ⏳ Waiting for Glue agent result...")
        time.sleep(12)  # wait for Lambda response
        capture(driver, "14c_dashboard_glue_result",
            "Dashboard — Data/ETL Agent: Glue Job Auto-Remediation",
            "The Data/ETL agent processed the Glue job failure ticket. "
            "The flow diagram shows: Intake → Classify (Data/ETL P2) → Pattern Match (NEW) → "
            "DataETLAgent → Glue job detected → status FAILED → AUTO-RERUN triggered → RESOLVED. "
            "The fix includes [AUTO-ACTION]: Glue job re-triggered with a new Job Run ID. "
            "This is the auto-remediation feature — the agent fixed the problem without human intervention.")
    else:
        print(f"  ⚠ Only {len(btns)} buttons found")
except Exception as e:
    print(f"  ⚠ Dashboard Glue demo: {e}")

# Extra: CloudWatch log detail
print("\n  Capturing CloudWatch log detail...")
try:
    driver.get(f"https://console.aws.amazon.com/cloudwatch/home?region={REGION}#logsV2:log-groups/log-group/$252Faws$252Flambda$252F{FUNCTION}")
    time.sleep(PAGE_WAIT)
    try:
        streams = driver.find_elements(By.XPATH, "//a[contains(@href,'log-stream')]")
        if streams:
            streams[0].click()
            time.sleep(ACTION_WAIT + 2)
            capture(driver, "16_cloudwatch_log_detail", "CloudWatch — Agent Step-by-Step Trace",
                "Inside the log stream you can see each agent step as a JSON entry: "
                "INTAKE (ticket created), CLASSIFY (Bedrock Nova called, category=Data/ETL, severity=P2), "
                "PATTERN_MATCH (status=NEW, confidence=53%), SUB_AGENT (DataETLAgent investigating), "
                "GLUE_RERUN_SUCCESS (job re-triggered, run_id=01), RESOLVE (ticket resolved). "
                "This is the complete audit trail of the AI decision-making process.")
    except Exception as e:
        print(f"  ⚠ Could not drill into log stream: {e}")
except Exception as e:
    print(f"  ⚠ CloudWatch detail: {e}")

try: driver.quit()
except: pass
print(f"\n  ✅ {len(screenshots)} screenshots saved to {OUT_DIR}/")

# ── Step 3: Build HTML slideshow report ───────────────────────────────────────
print("\n  Building HTML slideshow report...")

slides_html = ""
for i, sc in enumerate(screenshots):
    try:
        with open(sc["path"], "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        img_tag = f'<img src="data:image/png;base64,{b64}" style="width:100%;border-radius:6px;border:1px solid #ddd">'
    except Exception:
        img_tag = '<div style="background:#eee;height:400px;display:flex;align-items:center;justify-content:center;color:#888">Screenshot not available</div>'

    slides_html += f"""
    <div class="slide" id="slide-{i}" {"style='display:block'" if i==0 else "style='display:none'"}>
      <div class="slide-header">
        <span class="slide-num">{i+1} / {len(screenshots)}</span>
        <span class="slide-title">{sc['title']}</span>
        <span class="speed-badge">{S['label']}</span>
      </div>
      <div class="slide-img">{img_tag}</div>
      <div class="slide-narration">
        <span class="nar-icon">🎙</span>
        <span class="nar-text">{sc['narration']}</span>
      </div>
    </div>"""

ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>IT Ticket Agent — Technical Demo ({args.speed.upper()})</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',Arial,sans-serif;background:#1a1a2e;color:#e6edf3;min-height:100vh}}
.top-bar{{background:#232f3e;padding:12px 24px;display:flex;align-items:center;justify-content:space-between;border-bottom:2px solid #ff9900}}
.top-bar h1{{color:#ff9900;font-size:1.1rem;font-weight:700}}
.top-bar .meta{{color:#aaa;font-size:.8rem}}
.container{{max-width:1200px;margin:0 auto;padding:20px}}
.slide{{background:#161b22;border-radius:10px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,.4)}}
.slide-header{{background:#232f3e;padding:12px 20px;display:flex;align-items:center;gap:16px}}
.slide-num{{color:#ff9900;font-weight:700;font-size:.9rem;min-width:60px}}
.slide-title{{color:#fff;font-weight:600;font-size:1rem;flex:1}}
.speed-badge{{background:#ff990033;color:#ff9900;border:1px solid #ff9900;border-radius:4px;padding:2px 8px;font-size:.72rem;font-weight:700}}
.slide-img{{padding:12px;background:#0d1117}}
.slide-narration{{padding:14px 20px;background:#1f2937;border-top:1px solid #30363d;display:flex;gap:12px;align-items:flex-start}}
.nar-icon{{font-size:1.2rem;flex-shrink:0;margin-top:2px}}
.nar-text{{font-size:.88rem;color:#d1d5db;line-height:1.6}}
.controls{{display:flex;align-items:center;justify-content:center;gap:16px;padding:20px 0}}
.btn{{background:#ff9900;color:#232f3e;border:none;border-radius:8px;padding:10px 28px;font-size:.95rem;font-weight:700;cursor:pointer;transition:all .2s}}
.btn:hover{{background:#e68900}}
.btn-sec{{background:#30363d;color:#e6edf3}}
.btn-sec:hover{{background:#3d4451}}
.progress{{display:flex;gap:4px;flex-wrap:wrap;justify-content:center;padding:0 0 16px}}
.prog-dot{{width:10px;height:10px;border-radius:50%;background:#30363d;cursor:pointer;transition:all .2s}}
.prog-dot.active{{background:#ff9900;transform:scale(1.3)}}
.prog-dot.done{{background:#3fb950}}
.counter{{color:#8b949e;font-size:.85rem;text-align:center;padding-bottom:8px}}
.kbd{{background:#30363d;border-radius:4px;padding:2px 6px;font-size:.75rem;color:#aaa}}
</style>
</head>
<body>
<div class="top-bar">
  <h1>🎫 IT Ticket Intelligence Agent — Technical Demo</h1>
  <div class="meta">{ts} · {len(screenshots)} slides · {S['label']}</div>
</div>
<div class="container">
  <div class="controls" style="padding-top:16px">
    <button class="btn btn-sec" onclick="prev()">◀ Prev</button>
    <button class="btn" onclick="next()">Next ▶</button>
    <button class="btn btn-sec" onclick="toggleAuto()" id="autoBtn">▶ Auto Play</button>
  </div>
  <div class="counter" id="counter">Slide 1 of {len(screenshots)} · Use arrow keys or buttons</div>
  <div class="progress" id="progress">
    {''.join(f'<div class="prog-dot{" active" if i==0 else ""}" onclick="goTo({i})" title="{sc["title"]}"></div>' for i,sc in enumerate(screenshots))}
  </div>
  {slides_html}
  <div class="controls">
    <button class="btn btn-sec" onclick="prev()">◀ Prev</button>
    <button class="btn" onclick="next()">Next ▶</button>
  </div>
</div>
<script>
let cur = 0, total = {len(screenshots)}, autoTimer = null;
const autoDelay = {PAGE_WAIT * 1000};

function show(n) {{
  document.querySelectorAll('.slide').forEach((s,i) => s.style.display = i===n?'block':'none');
  document.querySelectorAll('.prog-dot').forEach((d,i) => {{
    d.className = 'prog-dot' + (i===n?' active':i<n?' done':'');
  }});
  document.getElementById('counter').textContent = `Slide ${{n+1}} of ${{total}} · ${{document.querySelectorAll('.slide-title')[n]?.textContent||''}}`;
  cur = n;
}}
function next() {{ if(cur < total-1) show(cur+1); else stopAuto(); }}
function prev() {{ if(cur > 0) show(cur-1); }}
function goTo(n) {{ show(n); }}
function toggleAuto() {{
  if(autoTimer) {{ stopAuto(); }}
  else {{
    autoTimer = setInterval(() => {{ if(cur < total-1) show(cur+1); else stopAuto(); }}, autoDelay);
    document.getElementById('autoBtn').textContent = '⏸ Pause';
  }}
}}
function stopAuto() {{
  clearInterval(autoTimer); autoTimer = null;
  document.getElementById('autoBtn').textContent = '▶ Auto Play';
}}
document.addEventListener('keydown', e => {{
  if(e.key==='ArrowRight'||e.key===' ') next();
  if(e.key==='ArrowLeft') prev();
}});
</script>
</body>
</html>"""

out_file = f"it-ticket-agent/demo_{args.speed}.html"
with open(out_file, "w") as f:
    f.write(html)
print(f"  ✅ Slideshow saved: {out_file}")

# Upload to S3
try:
    s3 = boto3.client("s3", region_name=REGION)
    s3.put_object(Bucket=BUCKET, Key=f"demo_{args.speed}.html",
                  Body=html.encode(), ContentType="text/html")
    print(f"  ✅ S3: http://{BUCKET}.s3-website-{REGION}.amazonaws.com/demo_{args.speed}.html")
except Exception as e:
    print(f"  ⚠ S3: {e}")

print(f"\n{'='*60}")
print(f"  DONE — {len(screenshots)} slides captured")
print(f"  Open: file://{os.path.abspath(out_file)}")
print(f"{'='*60}\n")
