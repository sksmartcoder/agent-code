#!/usr/bin/env python3
"""
Demo Report Generator
Runs all 5 agent scenarios via Lambda, captures traces,
and generates a self-contained HTML report.

Usage:
    python3 run_demo_report.py
    # Opens demo_report.html when done
"""
import boto3, json, time, os, sys
from datetime import datetime, timezone

REGION   = "us-west-2"
FUNCTION = "it-ticket-agent-api"
OUT_FILE = os.path.join(os.path.dirname(__file__), "demo_report.html")

SCENARIOS = [
    {
        "id": "cicd",
        "agent": "CI/CD Agent",
        "icon": "🔧",
        "color": "#1a73e8",
        "description": "CodePipeline deploy failed — ECS task OOM killed",
        "expected_category": "CI/CD",
    },
    {
        "id": "data",
        "agent": "Data/ETL Agent",
        "icon": "🗄",
        "color": "#d29922",
        "description": "Glue job daily_claims_load failed with connection timeout",
        "expected_category": "Data/ETL",
    },
    {
        "id": "infra",
        "agent": "Infrastructure Agent",
        "icon": "🖥",
        "color": "#1d8348",
        "description": "EC2 instance i-0abc123 unreachable, disk at 98%",
        "expected_category": "Infrastructure",
    },
    {
        "id": "access",
        "agent": "Access/IAM Agent",
        "icon": "🔑",
        "color": "#d35400",
        "description": "Lambda function can't write to S3 bucket prod-reports",
        "expected_category": "Access/IAM",
    },
    {
        "id": "network",
        "agent": "Network Agent",
        "icon": "🌐",
        "color": "#c0392b",
        "description": "API gateway returning 503, backend health checks failing",
        "expected_category": "Network",
    },
]

SEV_COLOR = {"P1": "#c0392b", "P2": "#d29922", "P3": "#1d8348", "P4": "#1a73e8"}

def invoke_lambda(description):
    lm = boto3.client("lambda", region_name=REGION)
    payload = {
        "body": json.dumps({"description": description}),
        "requestContext": {"http": {"method": "POST"}}
    }
    start = time.time()
    r = lm.invoke(
        FunctionName=FUNCTION,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode()
    )
    elapsed = round((time.time() - start) * 1000)
    raw = r["Payload"].read()
    result = json.loads(raw)
    error = r.get("FunctionError")
    if error:
        return {"error": error, "raw": raw.decode()}, elapsed
    body = json.loads(result.get("body", "{}"))
    return body, elapsed

def run_all():
    print(f"\n{'='*60}")
    print("  IT Ticket Agent — Demo Report Generator")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")

    results = []
    for sc in SCENARIOS:
        print(f"  {sc['icon']} Running {sc['agent']}...", end="", flush=True)
        data, ms = invoke_lambda(sc["description"])
        sc["result"] = data
        sc["duration_ms"] = ms
        sc["passed"] = (
            data.get("category") == sc["expected_category"] and
            data.get("final_status") == "RESOLVED" and
            "error" not in data
        )
        status = "✓ PASS" if sc["passed"] else "✗ FAIL"
        print(f" {status}  ({ms}ms)  category={data.get('category','?')}  severity={data.get('severity','?')}")
        results.append(sc)
        time.sleep(0.5)

    passed = sum(1 for r in results if r["passed"])
    print(f"\n  Result: {passed}/{len(results)} passed")
    return results

def build_html(results):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    passed = sum(1 for r in results if r["passed"])
    total  = len(results)

    cards = ""
    for sc in results:
        d = sc.get("result", {})
        status_color = "#1d8348" if sc["passed"] else "#c0392b"
        status_label = "✓ PASSED" if sc["passed"] else "✗ FAILED"
        sev = d.get("severity", "?")
        sev_col = SEV_COLOR.get(sev, "#888")
        pat = d.get("pattern_status", "?")
        pat_col = "#1d8348" if pat == "RECURRING" else "#7d3c98"
        conf = d.get("pattern_confidence", 0)
        conf_fill = min(100, conf)
        conf_col = "#1d8348" if conf >= 80 else "#d29922" if conf >= 50 else "#c0392b"

        steps = d.get("remediation_steps", "No steps available")
        if isinstance(steps, list):
            steps = "\n".join(steps)
        steps_html = "".join(
            f'<div class="step-line">› {line.strip()}</div>'
            for line in steps.splitlines() if line.strip()
        )

        resources = d.get("aws_resources", [])
        res_html = ""
        if resources:
            res_html = '<div class="res-title">☁ AWS Resources</div>' + "".join(
                f'<div class="res-item">{r}</div>' for r in resources
            )

        trace_steps = [
            ("📥", "Intake", "Ticket created", "#1a73e8", "DONE"),
            ("🤖", "Classify", f"Bedrock Nova → {d.get('category','?')} / {sev}", "#7d3c98", "DONE"),
            ("🔍", "Pattern Match", f"{pat} · {conf}% confidence", pat_col, "DONE"),
            ("⚡", "Sub-Agent", f"{sc['agent']} investigated", sc['color'], "DONE"),
            ("✅", "Resolve", f"Status: {d.get('final_status','?')}", "#1d8348", "DONE"),
        ]
        trace_html = ""
        for icon, name, detail, col, _ in trace_steps:
            trace_html += f'''
            <div class="trace-step">
              <div class="trace-dot" style="background:{col};border-color:{col}">{icon}</div>
              <div class="trace-body">
                <span class="trace-name" style="color:{col}">{name}</span>
                <span class="trace-detail">{detail}</span>
              </div>
            </div>'''

        cards += f'''
        <div class="card" id="{sc['id']}">
          <div class="card-header" style="border-left:5px solid {sc['color']}">
            <div class="card-title">
              <span class="agent-icon">{sc['icon']}</span>
              <span class="agent-name" style="color:{sc['color']}">{sc['agent']}</span>
              <span class="status-badge" style="background:{status_color}20;color:{status_color};border:1px solid {status_color}">{status_label}</span>
              <span class="duration">{sc['duration_ms']}ms</span>
            </div>
            <div class="ticket-desc">"{sc['description']}"</div>
          </div>
          <div class="card-body">
            <div class="meta-row">
              <div class="meta-item">
                <div class="meta-label">Category</div>
                <div class="meta-value" style="color:{sc['color']}">{d.get('category','?')}</div>
              </div>
              <div class="meta-item">
                <div class="meta-label">Severity</div>
                <div class="meta-value" style="color:{sev_col}">{sev}</div>
              </div>
              <div class="meta-item">
                <div class="meta-label">Pattern</div>
                <div class="meta-value" style="color:{pat_col}">{pat}</div>
              </div>
              <div class="meta-item">
                <div class="meta-label">Confidence</div>
                <div class="conf-bar-wrap">
                  <div class="conf-bar"><div class="conf-fill" style="width:{conf_fill}%;background:{conf_col}"></div></div>
                  <span style="color:{conf_col};font-weight:700">{conf}%</span>
                </div>
              </div>
              <div class="meta-item">
                <div class="meta-label">AI Confidence</div>
                <div class="meta-value" style="color:{'#1d8348' if d.get('confidence')=='HIGH' else '#d29922'}">
                  {'✓ HIGH' if d.get('confidence')=='HIGH' else '⚠ LOW'}
                </div>
              </div>
            </div>

            <div class="two-col">
              <div class="left-col">
                <div class="section-title">🔄 Agent Trace</div>
                <div class="trace">{trace_html}</div>
              </div>
              <div class="right-col">
                <div class="section-title">📋 Issue Summary</div>
                <div class="issue-text">{d.get('issue_summary','No summary available')}</div>
                <div class="section-title" style="margin-top:12px">🛠 Remediation Steps</div>
                <div class="steps">{steps_html}</div>
                {res_html}
              </div>
            </div>
          </div>
        </div>'''

    nav_items = "".join(
        f'<a href="#{sc["id"]}" class="nav-item" style="border-left:3px solid {sc["color"]}">'
        f'{sc["icon"]} {sc["agent"]}'
        f'<span class="nav-status" style="color:{"#1d8348" if sc["passed"] else "#c0392b"}">{"✓" if sc["passed"] else "✗"}</span>'
        f'</a>'
        for sc in results
    )

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>IT Ticket Agent — Demo Report</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',Arial,sans-serif;background:#f0f2f5;color:#1a1a2e;display:flex;min-height:100vh}}
.sidebar{{width:220px;min-width:220px;background:#1a1a2e;padding:20px 0;position:sticky;top:0;height:100vh;overflow-y:auto}}
.sidebar-title{{color:#ff9900;font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;padding:0 16px 12px}}
.nav-item{{display:flex;align-items:center;justify-content:space-between;padding:10px 16px;color:#ccc;text-decoration:none;font-size:.82rem;font-weight:500;transition:background .15s;gap:6px}}
.nav-item:hover{{background:#2d3748;color:#fff}}
.nav-status{{font-size:.9rem}}
.sidebar-summary{{margin-top:20px;padding:12px 16px;border-top:1px solid #2d3748}}
.sidebar-summary .s-label{{color:#888;font-size:.72rem;text-transform:uppercase}}
.sidebar-summary .s-val{{color:#ff9900;font-size:1.4rem;font-weight:700}}
.main{{flex:1;padding:24px;overflow-y:auto}}
.page-header{{background:#1a1a2e;color:#fff;border-radius:10px;padding:20px 28px;margin-bottom:24px;display:flex;align-items:center;justify-content:space-between}}
.page-header h1{{font-size:1.3rem;color:#ff9900}}
.page-header .meta{{font-size:.8rem;color:#888;text-align:right}}
.summary-row{{display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap}}
.summary-card{{background:#fff;border-radius:8px;padding:16px 20px;flex:1;min-width:140px;box-shadow:0 1px 4px rgba(0,0,0,.08);text-align:center}}
.summary-card .sv{{font-size:2rem;font-weight:700}}
.summary-card .sl{{font-size:.75rem;color:#888;margin-top:4px}}
.card{{background:#fff;border-radius:10px;margin-bottom:20px;box-shadow:0 1px 6px rgba(0,0,0,.08);overflow:hidden}}
.card-header{{padding:16px 20px;background:#fafbfc;border-bottom:1px solid #eee}}
.card-title{{display:flex;align-items:center;gap:10px;margin-bottom:6px;flex-wrap:wrap}}
.agent-icon{{font-size:1.3rem}}
.agent-name{{font-size:1rem;font-weight:700}}
.status-badge{{border-radius:4px;padding:2px 10px;font-size:.72rem;font-weight:700}}
.duration{{color:#888;font-size:.75rem;margin-left:auto}}
.ticket-desc{{font-size:.85rem;color:#555;font-style:italic}}
.card-body{{padding:16px 20px}}
.meta-row{{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:16px;padding-bottom:16px;border-bottom:1px solid #f0f0f0}}
.meta-item{{min-width:100px}}
.meta-label{{font-size:.68rem;color:#888;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px}}
.meta-value{{font-size:.9rem;font-weight:700}}
.conf-bar-wrap{{display:flex;align-items:center;gap:8px}}
.conf-bar{{height:8px;background:#eee;border-radius:4px;width:80px;overflow:hidden}}
.conf-fill{{height:100%;border-radius:4px;transition:width .8s}}
.two-col{{display:grid;grid-template-columns:220px 1fr;gap:20px}}
.section-title{{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#888;margin-bottom:8px}}
.trace{{display:flex;flex-direction:column;gap:6px}}
.trace-step{{display:flex;align-items:flex-start;gap:8px}}
.trace-dot{{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.8rem;flex-shrink:0;border:2px solid}}
.trace-body{{display:flex;flex-direction:column}}
.trace-name{{font-size:.78rem;font-weight:700}}
.trace-detail{{font-size:.7rem;color:#888}}
.issue-text{{font-size:.85rem;color:#333;line-height:1.5;background:#f8f9fa;border-radius:6px;padding:10px;margin-bottom:8px}}
.steps{{display:flex;flex-direction:column;gap:4px}}
.step-line{{font-size:.8rem;color:#444;padding:3px 0;border-bottom:1px solid #f5f5f5;line-height:1.4}}
.res-title{{font-size:.72rem;font-weight:700;text-transform:uppercase;color:#888;margin:10px 0 4px}}
.res-item{{font-size:.72rem;color:#1a73e8;font-family:monospace;padding:2px 0}}
@media(max-width:700px){{.sidebar{{display:none}}.two-col{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="sidebar">
  <div class="sidebar-title">🎫 Agent Demo Report</div>
  {nav_items}
  <div class="sidebar-summary">
    <div class="s-label">Scenarios Passed</div>
    <div class="s-val">{passed}/{total}</div>
    <div class="s-label" style="margin-top:8px">Generated</div>
    <div style="color:#ccc;font-size:.72rem">{ts}</div>
  </div>
</div>
<div class="main">
  <div class="page-header">
    <div>
      <h1>🎫 IT Ticket Intelligence Agent</h1>
      <div style="color:#888;font-size:.82rem;margin-top:4px">Demo Execution Report · Amazon Bedrock Nova Lite · Strands SDK</div>
    </div>
    <div class="meta">
      <div style="color:#ff9900;font-size:1.2rem;font-weight:700">{passed}/{total} Passed</div>
      <div>{ts}</div>
      <div>Region: {REGION}</div>
    </div>
  </div>

  <div class="summary-row">
    <div class="summary-card">
      <div class="sv" style="color:#1d8348">{passed}</div>
      <div class="sl">Scenarios Passed</div>
    </div>
    <div class="summary-card">
      <div class="sv" style="color:#c0392b">{total-passed}</div>
      <div class="sl">Failed</div>
    </div>
    <div class="summary-card">
      <div class="sv" style="color:#1a73e8">{total}</div>
      <div class="sl">Total Agents Tested</div>
    </div>
    <div class="summary-card">
      <div class="sv" style="color:#ff9900">{round(sum(s['duration_ms'] for s in results)/len(results))}ms</div>
      <div class="sl">Avg Response Time</div>
    </div>
  </div>

  {cards}

  <div style="text-align:center;color:#888;font-size:.75rem;margin-top:20px;padding:16px">
    Generated by IT Ticket Intelligence Agent · AWS Hackathon 2026 ·
    <a href="https://github.com/sksmartcoder/agent-code" style="color:#1a73e8">GitHub</a>
  </div>
</div>
</body>
</html>'''

if __name__ == "__main__":
    print("Running all 5 agent scenarios via Lambda...")
    results = run_all()

    print("\nGenerating HTML report...")
    html = build_html(results)

    with open(OUT_FILE, "w") as f:
        f.write(html)

    print(f"\n✅ Report saved: {OUT_FILE}")
    print(f"   Open in browser: file://{os.path.abspath(OUT_FILE)}")

    # Also upload to S3
    try:
        s3 = boto3.client("s3", region_name=REGION)
        s3.put_object(
            Bucket="amzn-hackthon-it-ticket-system",
            Key="demo_report.html",
            Body=html.encode(),
            ContentType="text/html"
        )
        print(f"   S3 URL: http://amzn-hackthon-it-ticket-system.s3-website-us-west-2.amazonaws.com/demo_report.html")
    except Exception as e:
        print(f"   S3 upload skipped: {e}")
