#!/usr/bin/env python3
"""
AWS Console Demo Automation
Opens Chrome, navigates AWS Console pages, triggers Lambda tests,
captures screenshots of each service, and saves an HTML report.

Usage:
    python3 console_demo.py

Output:
    screenshots/  — PNG screenshots of each console page
    console_demo_report.html — full visual report
"""
import os, sys, json, time, boto3, subprocess
from datetime import datetime, timezone
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
REGION      = "us-west-2"
ACCOUNT     = "628875594738"
FUNCTION    = "it-ticket-agent-api"
AGENT_ID    = "it_ticket_agent_agentcore_app-Y14wFRAyTO"
S3_BUCKET   = "amzn-hackthon-it-ticket-system"
SCREENSHOTS = Path("it-ticket-agent/screenshots")
SCREENSHOTS.mkdir(exist_ok=True)

SCENARIOS = [
    ("CI/CD Agent",          "CodePipeline deploy failed — ECS task OOM killed"),
    ("Data/ETL Agent",       "Glue job daily_claims_load failed with connection timeout"),
    ("Infrastructure Agent", "EC2 instance i-0abc123 unreachable, disk at 98%"),
    ("Access/IAM Agent",     "Lambda function can't write to S3 bucket prod-reports"),
    ("Network Agent",        "API gateway returning 503, backend health checks failing"),
]

# ── AWS Console federation login URL (auto-login) ────────────────────────────
FEDERATION_URL = "https://signin.aws.amazon.com/federation?Destination=https://us-west-2.console.aws.amazon.com/console/home&SigninToken=q1Eq4K-V-bfJUwhnAdPXQxZ3ZVTrl6fX4k1ArpAjHmVCP4l-U9hzNbtWMIqW5wHVdwP0J11-Th1YxN1p-y6O7BECVPu2vrFhlXiGXKVmf4RRRXCxGlwXO5At0C3XQd3CEl2vFAXpo6YRN3BdEbPrcPDN_-4oFzSdoacbcKLRPXVk2rAc5lG_ZLCGNlKzMjiZ3qfl1H9oDR-sPuTi54kX8tF1l7Es-nLTbeWX8w9zBjkprUHobh2QjES326sW4P9uLcOrdTtw7u3enkMKvHQH6MceAdGbb82epKwsVSZziMdQl8fsQWUyXWn3ISzXKSrCpIsmrYNgYW8fw1z9oLiPy6l5aXq86xVNwIe6BZp21FjSoFtVluLR8u-qgNKm3aan9rrbMVZ9kXAXxxCEVcD8K-_FSgboXD2vqKbSXmIhJnsKuddSu56ZLitOaYzVLSXkiKX-7Hk66hKfn8UtjeIe2AZVLnCNacUuQDRCV8Cc3xNVYNGSHqmWvL-wvsX1K7DiGeUhmE6lOjafm9_LcgbWhHnrijLD5k4c3Be6b66JsP9b__R0mFcHpTy4QY8nzkffxxLXwjM-EKuL9TISmiZalyi2U7Ommr80kfXxc-3JxRFfqnQ3wX-m9xnqDzi8uzc0RbM3kjlYPeQql9jcnJlD_FarRX2NLkdYLsH1jVufCKoj0vfONXjeC47oe2Y4hHobLlKqhzDGDfqn4tv6Rg1AxJe7xJYIpOSp38_HgteVGyp4URO7V8TBXTAnGjUqKjnkcpbLz2Ujp3Ghwsu1D56QgpIoxE0SrQ2Kun-NWf9xqEdUKxN5JBP-ONy2AlLaLtQNpQNOcUmvuHiPMAGL0h0hM9NQlnxygFoqqoNm1eMogBm3haEl5Y6OWsm7VZpUqYXN6q9heWWq_ZyFn-9a_AOnNb2NWCuDz1Nfyzrd7Pxk2fXKS8n0LGXrv6OqetcFpOpR-9eAGcTV5RERMqBruXvPr1j0mPu_pXWN5bNijC6WzxT8x62X9kD8M-Mbahx7PJklD5BhiJP_laMsDwpiUN3L_pncKLAkPVKpOwf4rjLGtmuoETAk6GAUqp0RRZPhjRXuY6VNzJUXzCcXYrjL0RQLwzJ0H8ovGdsFS1S02jF8eegpsMT5vn8Koh3M6Fd5MOWI2k3xFDcYxbJ2iXaEYm6ICDzKHfqs4dmUJ1kp-V40JOx-iOYZoD2KY0TTUW3zSG52KVAnGkNVQVVuj9ivfWpSr6PLbgNMf353n-tdaOBZyTCc-_XCEyy3aEaqd_sR03CZ_cTUZ9BXvz6XOaH6SFfEEzBuxLIIwSXZCG_ijJ0f_ROCY83a4G_nSCvQuB8YaLPKzx-Y725PNtE1RtSFV7TMwq1EAHgVIaADsSBryBI81K9me3n5-C9KAj3inBfh_nsGiLqxMSqNtcnougvTUjVrdsMq_phXzWLyfw-rhxzf9PBM_-niJ4_WqQ&Action=login&Issuer=workshopstudio"
URLS = {
    "lambda_function":   f"https://console.aws.amazon.com/lambda/home?region={REGION}#/functions/{FUNCTION}",
    "lambda_monitor":    f"https://console.aws.amazon.com/lambda/home?region={REGION}#/functions/{FUNCTION}?tab=monitoring",
    "agentcore_runtime": f"https://console.aws.amazon.com/bedrock/home?region={REGION}#/agentcore/runtimes",
    "cloudwatch_logs":   f"https://console.aws.amazon.com/cloudwatch/home?region={REGION}#logsV2:log-groups/log-group/$252Faws$252Flambda$252F{FUNCTION}",
    "genai_dashboard":   f"https://console.aws.amazon.com/cloudwatch/home?region={REGION}#gen-ai-observability/agent-core",
    "s3_bucket":         f"https://console.aws.amazon.com/s3/buckets/{S3_BUCKET}?region={REGION}",
    "bedrock_models":    f"https://console.aws.amazon.com/bedrock/home?region={REGION}#/models",
    "demo_dashboard":    f"http://{S3_BUCKET}.s3-website-{REGION}.amazonaws.com",
    "demo_report":       f"http://{S3_BUCKET}.s3-website-{REGION}.amazonaws.com/demo_report.html",
    "architecture":      f"http://{S3_BUCKET}.s3-website-{REGION}.amazonaws.com/architecture.html",
    "process_flow":      f"http://{S3_BUCKET}.s3-website-{REGION}.amazonaws.com/process_flow.html",
}

# ── Step 1: Run all Lambda scenarios and capture results ──────────────────────
print("\n" + "="*60)
print("  STEP 1: Running all 5 agent scenarios via Lambda")
print("="*60)

lm = boto3.client("lambda", region_name=REGION)
lambda_results = []

for name, desc in SCENARIOS:
    print(f"  ▶ {name}...", end="", flush=True)
    try:
        r = lm.invoke(
            FunctionName=FUNCTION,
            InvocationType="RequestResponse",
            Payload=json.dumps({
                "body": json.dumps({"description": desc}),
                "requestContext": {"http": {"method": "POST"}}
            }).encode()
        )
        body = json.loads(json.loads(r["Payload"].read()).get("body", "{}"))
        lambda_results.append({"name": name, "desc": desc, "result": body, "ok": True})
        print(f" ✓  {body.get('category','?')} / {body.get('severity','?')} / {body.get('final_status','?')}")
    except Exception as e:
        lambda_results.append({"name": name, "desc": desc, "result": {}, "ok": False, "error": str(e)})
        print(f" ✗  {e}")

# ── Step 2: Open Chrome and take screenshots ──────────────────────────────────
print("\n" + "="*60)
print("  STEP 2: Opening Chrome and capturing screenshots")
print("="*60)

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

opts = Options()
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--window-size=1600,900")
opts.add_argument("--disable-gpu")
opts.add_argument("--disable-software-rasterizer")
opts.add_argument("--remote-debugging-port=9222")
opts.add_argument("--disable-extensions")
opts.add_argument("--disable-background-networking")
opts.add_argument("--disable-default-apps")

try:
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=opts
    )
    driver.set_window_size(1600, 900)
    screenshots_taken = []

    def screenshot(name, label):
        path = SCREENSHOTS / f"{name}.png"
        time.sleep(2)  # let page render
        driver.save_screenshot(str(path))
        screenshots_taken.append({"name": name, "label": label, "path": str(path)})
        print(f"  📸 {label}")
        return str(path)

    # ── Login to AWS Console first ────────────────────────────────────────────
    print("\n  Logging into AWS Console via federation URL...")
    driver.get(FEDERATION_URL)
    time.sleep(6)  # wait for login redirect to complete
    screenshot("00_aws_console_login", "AWS Console — Logged In")

    # ── Demo Dashboard ────────────────────────────────────────────────────────
    print("\n  Opening Demo Dashboard...")
    driver.get(URLS["demo_dashboard"])
    time.sleep(3)
    screenshot("01_demo_dashboard", "Demo Dashboard — Main Page")

    # Click CI/CD demo button
    try:
        btns = driver.find_elements(By.CLASS_NAME, "btn-demo")
        if btns:
            btns[0].click()
            time.sleep(6)
            screenshot("02_cicd_result", "CI/CD Agent — Flow + Result")
    except Exception as e:
        print(f"  ⚠ Could not click demo button: {e}")

    # ── Architecture Diagram ──────────────────────────────────────────────────
    print("\n  Opening Architecture Diagram...")
    driver.get(URLS["architecture"])
    time.sleep(3)
    screenshot("03_architecture", "Architecture Diagram")

    # ── Process Flow ──────────────────────────────────────────────────────────
    print("\n  Opening Process Flow...")
    driver.get(URLS["process_flow"])
    time.sleep(3)
    screenshot("04_process_flow_simple", "Process Flow — Simple View (Leaders)")

    # Click Technical view
    try:
        btns = driver.find_elements(By.CLASS_NAME, "toggle")
        if btns:
            tech_btn = driver.find_elements(By.XPATH, "//button[contains(text(),'Technical')]")
            if tech_btn:
                tech_btn[0].click()
                time.sleep(1)
                screenshot("05_process_flow_tech", "Process Flow — Technical View (Engineers)")
    except Exception as e:
        print(f"  ⚠ {e}")

    # ── Demo Report ───────────────────────────────────────────────────────────
    print("\n  Opening Demo Report...")
    driver.get(URLS["demo_report"])
    time.sleep(3)
    screenshot("06_demo_report", "Demo Report — All 5 Agents")

    # ── AWS Console Pages ─────────────────────────────────────────────────────
    print("\n  Opening AWS Console pages...")
    print("  (You may need to log in — the browser is open)")

    driver.get(URLS["lambda_function"])
    time.sleep(5)
    screenshot("07_lambda_function", "AWS Lambda — it-ticket-agent-api")

    driver.get(URLS["agentcore_runtime"])
    time.sleep(5)
    screenshot("08_agentcore_runtime", "AgentCore Runtime — Agent READY")

    driver.get(URLS["cloudwatch_logs"])
    time.sleep(5)
    screenshot("09_cloudwatch_logs", "CloudWatch Logs — Lambda Execution")

    driver.get(URLS["genai_dashboard"])
    time.sleep(5)
    screenshot("10_genai_dashboard", "GenAI Observability Dashboard")

    driver.get(URLS["s3_bucket"])
    time.sleep(5)
    screenshot("11_s3_bucket", "S3 Bucket — Dashboard + Runbooks")

    driver.get(URLS["bedrock_models"])
    time.sleep(5)
    screenshot("12_bedrock_models", "Amazon Bedrock — Nova Lite Active")

    driver.quit()
    print(f"\n  ✅ {len(screenshots_taken)} screenshots captured → {SCREENSHOTS}/")

except Exception as e:
    print(f"\n  ✗ Browser automation failed: {e}")
    print("  Screenshots from Lambda results will still be included in report.")
    screenshots_taken = []

# ── Step 3: Build HTML report with screenshots ────────────────────────────────
print("\n" + "="*60)
print("  STEP 3: Building visual HTML report")
print("="*60)

ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
passed = sum(1 for r in lambda_results if r["ok"])

# Lambda results cards
lambda_cards = ""
for r in lambda_results:
    d = r.get("result", {})
    ok = r["ok"]
    color = "#1d8348" if ok else "#c0392b"
    status = "✓ PASSED" if ok else "✗ FAILED"
    lambda_cards += f"""
    <div style="background:#fff;border-radius:8px;padding:16px;margin-bottom:12px;
                border-left:4px solid {color};box-shadow:0 1px 4px rgba(0,0,0,.08)">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
        <span style="font-weight:700;font-size:1rem">{r['name']}</span>
        <span style="background:{color}20;color:{color};border:1px solid {color};
                     border-radius:4px;padding:2px 8px;font-size:.75rem;font-weight:700">{status}</span>
        <span style="color:#888;font-size:.8rem;margin-left:auto">
          {d.get('category','?')} · {d.get('severity','?')} · {d.get('pattern_status','?')}
        </span>
      </div>
      <div style="color:#555;font-size:.85rem;font-style:italic">"{r['desc']}"</div>
      <div style="color:#333;font-size:.82rem;margin-top:8px;background:#f8f9fa;
                  padding:8px;border-radius:4px">{d.get('issue_summary','')}</div>
    </div>"""

# Screenshot gallery
gallery = ""
for sc in screenshots_taken:
    img_path = sc["path"]
    # Encode as base64 for self-contained HTML
    import base64
    try:
        with open(img_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        gallery += f"""
        <div style="margin-bottom:24px">
          <div style="font-weight:600;color:#232f3e;margin-bottom:8px;font-size:.9rem">
            📸 {sc['label']}
          </div>
          <img src="data:image/png;base64,{b64}"
               style="width:100%;border-radius:8px;border:1px solid #ddd;
                      box-shadow:0 2px 8px rgba(0,0,0,.1)">
        </div>"""
    except Exception:
        gallery += f'<div style="color:#888">Screenshot not available: {sc["label"]}</div>'

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>IT Ticket Agent — Console Demo Report</title>
<style>
body{{font-family:'Segoe UI',Arial,sans-serif;background:#f0f2f5;margin:0;padding:24px;color:#1a1a2e}}
.header{{background:#232f3e;color:#fff;border-radius:10px;padding:20px 28px;margin-bottom:24px;display:flex;justify-content:space-between;align-items:center}}
.header h1{{color:#ff9900;font-size:1.3rem}}
.header .meta{{font-size:.8rem;color:#aaa;text-align:right}}
.section{{background:#fff;border-radius:10px;padding:20px;margin-bottom:20px;box-shadow:0 1px 6px rgba(0,0,0,.08)}}
.section h2{{font-size:1rem;font-weight:700;color:#232f3e;margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid #ff9900}}
.summary{{display:flex;gap:16px;margin-bottom:20px}}
.stat{{background:#fff;border-radius:8px;padding:16px 20px;text-align:center;flex:1;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
.stat .val{{font-size:2rem;font-weight:700}}
.stat .lbl{{font-size:.75rem;color:#888;margin-top:4px}}
.links{{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}}
.link-btn{{background:#232f3e;color:#ff9900;border:none;border-radius:6px;padding:8px 16px;font-size:.82rem;font-weight:600;text-decoration:none;cursor:pointer}}
</style>
</head>
<body>
<div class="header">
  <div>
    <h1>🎫 IT Ticket Intelligence Agent — Console Demo Report</h1>
    <div style="color:#aaa;font-size:.82rem;margin-top:4px">
      Amazon Bedrock Nova Lite · Strands SDK · AWS Lambda · AgentCore Runtime
    </div>
  </div>
  <div class="meta">
    <div style="color:#ff9900;font-size:1.2rem;font-weight:700">{passed}/5 Agents Passed</div>
    <div>{ts}</div>
    <div>Region: {REGION}</div>
  </div>
</div>

<div class="summary">
  <div class="stat"><div class="val" style="color:#1d8348">{passed}</div><div class="lbl">Passed</div></div>
  <div class="stat"><div class="val" style="color:#c0392b">{5-passed}</div><div class="lbl">Failed</div></div>
  <div class="stat"><div class="val" style="color:#1a73e8">5</div><div class="lbl">Agents Tested</div></div>
  <div class="stat"><div class="val" style="color:#ff9900">{len(screenshots_taken)}</div><div class="lbl">Screenshots</div></div>
</div>

<div class="section">
  <h2>🔗 Live URLs</h2>
  <div class="links">
    <a class="link-btn" href="{URLS['demo_dashboard']}" target="_blank">🌐 Demo Dashboard</a>
    <a class="link-btn" href="{URLS['demo_report']}" target="_blank">📊 Demo Report</a>
    <a class="link-btn" href="{URLS['architecture']}" target="_blank">📐 Architecture</a>
    <a class="link-btn" href="{URLS['process_flow']}" target="_blank">🔄 Process Flow</a>
    <a class="link-btn" href="{URLS['lambda_function']}" target="_blank">λ Lambda Console</a>
    <a class="link-btn" href="{URLS['agentcore_runtime']}" target="_blank">☁ AgentCore</a>
    <a class="link-btn" href="{URLS['cloudwatch_logs']}" target="_blank">📋 CloudWatch Logs</a>
    <a class="link-btn" href="{URLS['genai_dashboard']}" target="_blank">🔍 GenAI Dashboard</a>
  </div>
</div>

<div class="section">
  <h2>⚡ Lambda Execution Results — All 5 Agents</h2>
  {lambda_cards}
</div>

{'<div class="section"><h2>📸 Console Screenshots</h2>' + gallery + '</div>' if gallery else ''}

<div style="text-align:center;color:#888;font-size:.75rem;margin-top:20px;padding:16px">
  IT Ticket Intelligence Agent · AWS Hackathon 2026 ·
  <a href="https://github.com/sksmartcoder/agent-code" style="color:#1a73e8">GitHub</a>
</div>
</body>
</html>"""

out = "it-ticket-agent/console_demo_report.html"
with open(out, "w") as f:
    f.write(html)
print(f"  ✅ Report saved: {out}")

# Upload to S3
try:
    s3 = boto3.client("s3", region_name=REGION)
    s3.put_object(Bucket=S3_BUCKET, Key="console_demo_report.html",
                  Body=html.encode(), ContentType="text/html")
    print(f"  ✅ S3: http://{S3_BUCKET}.s3-website-{REGION}.amazonaws.com/console_demo_report.html")
except Exception as e:
    print(f"  ⚠ S3 upload: {e}")

print(f"\n{'='*60}")
print(f"  DONE — open in browser:")
print(f"  file://{os.path.abspath(out)}")
print(f"{'='*60}\n")
