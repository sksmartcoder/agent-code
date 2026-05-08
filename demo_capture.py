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

FEDERATION_URL = "https://signin.aws.amazon.com/federation?Issuer=workshopstudio&Destination=https://us-west-2.console.aws.amazon.com/console/home&SigninToken=oc3-JVSXr9tbS6P_bm4_KXB7AzI0b-ADqkLKb_kxm2O-H7u7ch5tstqauJnX5BgAzIzygpWUCRPQnH7O4ruPRP993bdNCLOHQLhzK1mv5Z0Nvz7dG_el3MkiGqQ4b18VUTuXkmQsfR9-pqPEIGXAYxijLW5RW8At8EMsZA9lms4t-9tBKwNx7wLHlFPpxoJlsf091B8_pnt7wOhfUD4X9u30OUK0ntbEOJd0mpicTmpqsumX74xUEZH2Z5L-mNPm_3-oEPyHT0suO9QYO7Kf6cFYyLIV6n65MKCpi42FXLaNv7TotIJZIKYrMab30YhI1A0sTbJJFiDPm15RYGg_4oW74JIp8HZ8fDxvz0ZNKwAi64XiK_6rhDjdyFo0rk9tLfC_AJOgPTGRLRDvin2SOEjjIiKC1ikjzuPMj4w3s8hQoAas6GHjnkq5D-XzUTNHTmKl7PVgmPnbxGOm5Yf948H4-uOHhSB15wnFyBfiAITW0tpH1aIOZQ_4hO_YgKPggi0meS4prW24_uEuyjANsZpdC1hRAJJEFO32bSMuTVVpLSxRTh9vCMeQYXrkQSaMSuA1cQ98sfrPS-w-S0X6YNJobF5aYIg-e1ADr-ZcabZMgJWJg75nRjrrS-OToeyGMCmmKGEGGwbu1Ni1d8VNqUQZRNiUHQ2KIKN4nA5qRap8iruMn2pOXEmbUW-b3a6nxxCy_RVroUOS3GdyydZ87ueQmtD5-f9SX6hfd3efp94Vlmn27bRYF-vF05lfsa7eqoOSBnmCHa7z3SMcMkdgMqIFEGEVlj706GKL1x0xlrOtX9ZQHtIjLu6w2A_0OYNwgM1puT1DJJIfCjfn2UyfcSKmMI-qiewZ1vz5rNs3QwaENiQQMNM4EKLrfwsktOcLAr6I8W_mpyschI00iBBH66Ezzqc4ucHlm4VDhkT6o1idOw9ITsTC8pUzOZXMd9oQuUloBnQsPdOjdlwgdcI1Kr4IWhVxL70VBoxiJKM0RqXIR7p_tMsjcP7aF9jKaOjM8f4MVmdaqxuDMAAEZ3cXkwtxU-zOGN_D95mg2VUwWBeXXnMbdKP4pxT4sy9Mn2JiMQv9jBYzyawxfcuk0t4vreLdkoilc8ROv6aFj2w0_5J32F_SBQnHUXK6fJoZSEqn5yyKkbHELmPyKW6zqSXCMUKR0XGC30gX5_ZUTvBt4LxMcHEQTlo8nradOBTjgmAit_1khhZvg-7LRNkXjRDdBKLqpbY1sjEGqyHhYOA1HjbER36hm0M1WypkjSEnAnqn-5P1hRCO_IJpWUGuaEiuM2HgBlWarcF-rlcbshu5oBXAOfBWmG4cUVe4X7J9KYfnRDtQLjycEDg3W_03iNU4uveOSAB3xr6cWIH2Y9HlvfAU4tr1Gsa0HRWHs9HA230cm5USB8IWQP2emUI1ovB1T0i8R4VRDRcZz4yb5H5eNDAhQkCnImQ6YQ&Action=login"

# ── Demo steps — logical story flow ─────────────────────────────────────────
# Story: Ticket submitted → AI classifies → AgentCore routes → specialist agent fixes → verified
STEPS = [

    # ── ACT 1: THE DEMO — Show it working ────────────────────────────────────

    # 1. Live dashboard — the entry point
    (f"http://{BUCKET}.s3-website-{REGION}.amazonaws.com",
     "01_dashboard_home",
     "Live Demo — IT Ticket Intelligence Agent",
     "This is the live web dashboard hosted on Amazon S3. "
     "Anyone can open this URL and submit an IT support ticket. "
     "No login, no server, no port configuration. "
     "We will now submit a real ticket and watch the AI agent process it."),

    # 2. Dashboard — CI/CD result (recurring pattern — most impressive)
    (f"http://{BUCKET}.s3-website-{REGION}.amazonaws.com",
     "02_dashboard_cicd",
     "Demo — CI/CD Agent: Recurring Pattern at 88% Confidence",
     "We submitted: 'CodePipeline deploy failed — ECS task OOM killed'. "
     "The AI classified it as CI/CD P2 in under 1 second. "
     "Pattern matching found this is a RECURRING issue — seen 4 times before — at 88% confidence. "
     "The proven fix was retrieved instantly from the knowledge base. No LLM call needed. "
     "This is the self-learning capability — the system gets faster with every resolved ticket."),

    # 3. Demo report — all 5 agents verified
    (f"http://{BUCKET}.s3-website-{REGION}.amazonaws.com/demo_report.html",
     "03_demo_report",
     "All 5 Specialist Agents Verified — Real AI Responses",
     "This report shows all 5 specialist agents running with real Amazon Bedrock Nova AI. "
     "CI/CD Agent, Data/ETL Agent, Infrastructure Agent, Access/IAM Agent, Network Agent — all passed. "
     "Each result includes: category, severity, pattern match confidence, AI-generated fix, AWS resources. "
     "5 out of 5 resolved. Average response time under 3 seconds."),

    # ── ACT 2: THE CORE SERVICE — AgentCore ──────────────────────────────────

    # 4. AgentCore Runtime — the main service
    (f"https://console.aws.amazon.com/bedrock/home?region={REGION}#/agentcore/runtimes",
     "04_agentcore_list",
     "Amazon Bedrock AgentCore — Runtime Registry",
     "This is Amazon Bedrock AgentCore — the managed runtime for deploying AI agents. "
     "Our agent 'it_ticket_agent_agentcore_app' is listed here with status READY. "
     "AgentCore handles: agent deployment, scaling, memory management, and observability. "
     "This is what makes this a production-grade agent, not just a script."),

    # 5. AgentCore Runtime detail — invocation metrics
    (f"https://console.aws.amazon.com/bedrock/home?region={REGION}#/agentcore/runtimes/{AGENT_ID}",
     "05_agentcore_detail",
     "AgentCore Runtime — Live Invocation Metrics",
     "The runtime detail shows real metrics from our agent invocations. "
     "Runtime invocations: 6 successful calls. Error rate: 0%. "
     "Three versions deployed — we can roll back to any version instantly. "
     "The agent runs on Python 3.12, deployed as a 32MB direct code package. "
     "This is the orchestration layer — it receives tickets and routes them to specialist agents."),

    # 6. AgentCore Memory
    (f"https://console.aws.amazon.com/bedrock/home?region={REGION}#/agentcore/memory",
     "06_agentcore_memory",
     "AgentCore Memory — Short-Term Memory Active",
     "AgentCore Memory gives the agent persistent context across sessions. "
     "Memory ID: it_ticket_agent_agentcore_app_mem. Mode: STM (Short-Term Memory). "
     "In production, this stores ticket history, resolution patterns, and operator preferences. "
     "The agent remembers what it has seen before — enabling the recurring pattern detection."),

    # ── ACT 3: THE AI BRAIN — Bedrock ────────────────────────────────────────

    # 7. Bedrock model — Nova Lite
    (f"https://console.aws.amazon.com/bedrock/home?region={REGION}#/models",
     "07_bedrock_models",
     "Amazon Bedrock — Nova Lite: The AI Brain",
     "Amazon Nova Lite (us.amazon.nova-lite-v1:0) is the AI model powering every decision. "
     "It classifies tickets into 5 categories and 4 severity levels in under 1 second. "
     "It generates domain-specific fix recommendations using runbook context. "
     "Nova Lite was chosen over Claude 3 Sonnet — faster, more cost-effective, and active in this account."),

    # ── ACT 4: THE KNOWLEDGE BASE — S3 ───────────────────────────────────────

    # 8. S3 runbooks — all 5
    (f"https://console.aws.amazon.com/s3/buckets/{BUCKET}?region={REGION}&prefix=runbooks/",
     "08_s3_runbooks",
     "S3 Knowledge Base — 5 Domain Runbooks",
     "The knowledge base lives in S3. Five domain runbooks — one per specialist agent. "
     "cicd_runbook.md, data_runbook.md, infra_runbook.md, access_runbook.md, network_runbook.md. "
     "Each sub-agent fetches its runbook before calling Bedrock, giving the AI domain-specific context. "
     "This is why the fixes are accurate and actionable — not generic AI responses."),

    # 9. S3 data runbook content
    (f"https://console.aws.amazon.com/s3/buckets/{BUCKET}?region={REGION}&prefix=runbooks/data_runbook.md",
     "09_s3_data_runbook",
     "Data/ETL Runbook — Glue, RDS, JDBC Guidance",
     "The Data/ETL runbook contains step-by-step guidance for: "
     "Glue job JDBC timeouts, RDS connectivity issues, ETL pipeline failures. "
     "When the DataETLAgent investigates a Glue failure, it reads this runbook first, "
     "then calls Bedrock Nova with the runbook as context. "
     "The result: a fix that references the actual Glue configuration parameters."),

    # ── ACT 5: THE INFRASTRUCTURE — Lambda + Logs ────────────────────────────

    # 10. Lambda — brief
    (f"https://console.aws.amazon.com/lambda/home?region={REGION}#/functions/{FUNCTION}",
     "10_lambda",
     "AWS Lambda — API Layer for Web Dashboard",
     "The Lambda function is the API layer connecting the web dashboard to the agent pipeline. "
     "It receives ticket descriptions, runs the full AI pipeline, and returns structured results. "
     "Function: it-ticket-agent-api. Runtime: Python 3.12. Timeout: 120s. Memory: 512MB. "
     "This is separate from AgentCore — Lambda handles the web dashboard, AgentCore handles direct invocations."),

    # 11. CloudWatch logs — agent trace
    (f"https://console.aws.amazon.com/cloudwatch/home?region={REGION}#logsV2:log-groups/log-group/$252Faws$252Flambda$252F{FUNCTION}",
     "11_cloudwatch_logs",
     "CloudWatch Logs — Full Agent Execution Trace",
     "Every agent step emits a structured JSON log. "
     "INTAKE → CLASSIFY (Bedrock Nova: category=CI/CD severity=P2) → "
     "PATTERN_MATCH (RECURRING 88%) → KNOWLEDGE_BASE (proven fix) → RESOLVE. "
     "This is the audit trail — every AI decision is logged with timestamp and data. "
     "In production, these logs feed into dashboards and alerting."),

    # 12. GenAI Observability
    (f"https://console.aws.amazon.com/cloudwatch/home?region={REGION}#gen-ai-observability/agent-core",
     "12_genai_observability",
     "GenAI Observability — Agent Performance Dashboard",
     "The GenAI Observability dashboard provides distributed tracing across all agent invocations. "
     "This is where you monitor: response latency, model token usage, error rates, and agent health. "
     "In production, this is how the operations team monitors the AI agent 24/7."),

    # ── ACT 6: THE RESULT ─────────────────────────────────────────────────────

    # 13. Dashboard — Glue auto-remediation (the unique feature)
    (f"http://{BUCKET}.s3-website-{REGION}.amazonaws.com",
     "13_dashboard_glue",
     "Unique Feature — Glue Job Auto-Remediation",
     "This is what makes this agent unique. "
     "When a Glue job failure ticket is submitted, the DataETLAgent: "
     "1. Detects the job name from the ticket description. "
     "2. Checks the last run status (FAILED). "
     "3. Automatically re-triggers the job. "
     "The fix includes [AUTO-ACTION]: Glue job re-triggered with Job Run ID. "
     "No human needed to restart the job — the agent does it automatically."),

    # 14. AgentCore — invoke via CLI (show it's a real deployed agent)
    (f"https://console.aws.amazon.com/bedrock/home?region={REGION}#/agentcore/runtimes/{AGENT_ID}",
     "14_agentcore_final",
     "AgentCore — Production-Ready Deployed Agent",
     "To summarize: this is a fully deployed AI agent on Amazon Bedrock AgentCore. "
     "It can be invoked via: agentcore invoke, REST API, or web dashboard. "
     "It classifies tickets, detects patterns, routes to specialist agents, "
     "auto-remediates issues, and logs every decision. "
     "Built in one hackathon session using Strands SDK + Amazon Bedrock Nova Lite."),
]

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
opts.add_argument("--window-size=1920,1080")
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

# Extra: Dashboard interactions — CI/CD then Glue
print("\n  Capturing dashboard with CI/CD result (slide 02)...")
try:
    driver.get(f"http://{BUCKET}.s3-website-{REGION}.amazonaws.com")
    time.sleep(4)
    btns = driver.find_elements(By.CLASS_NAME, "btn-demo")
    if btns:
        btns[0].click()  # CI/CD OOM scenario
        print("  ⏳ Waiting for CI/CD result...")
        time.sleep(12)
        # Update slide 02 screenshot
        path = OUT_DIR / "02_dashboard_cicd.png"
        driver.save_screenshot(str(path))
        # Update the screenshot in our list
        for sc in screenshots:
            if sc["filename"] == "02_dashboard_cicd":
                sc["path"] = str(path)
                break
        print("  📸 Updated: CI/CD result on dashboard")
except Exception as e:
    print(f"  ⚠ Dashboard CI/CD: {e}")

print("\n  Capturing dashboard with Glue result (slide 13)...")
try:
    driver.get(f"http://{BUCKET}.s3-website-{REGION}.amazonaws.com")
    time.sleep(4)
    btns = driver.find_elements(By.CLASS_NAME, "btn-demo")
    if len(btns) >= 3:
        btns[2].click()  # Glue timeout scenario
        print("  ⏳ Waiting for Glue result...")
        time.sleep(12)
        path = OUT_DIR / "13_dashboard_glue.png"
        driver.save_screenshot(str(path))
        for sc in screenshots:
            if sc["filename"] == "13_dashboard_glue":
                sc["path"] = str(path)
                break
        print("  📸 Updated: Glue result on dashboard")
except Exception as e:
    print(f"  ⚠ Dashboard Glue: {e}")

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
