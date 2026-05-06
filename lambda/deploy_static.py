#!/usr/bin/env python3
"""Build static HTML with Lambda URL baked in, upload to S3 with public access."""
import os, boto3

REGION = "us-west-2"
BUCKET = "amzn-hackthon-it-ticket-system"
ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(ROOT, "lambda", "function_url.txt")) as f:
    LAMBDA_URL = f.read().strip()

print(f"Lambda URL: {LAMBDA_URL}")

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IT Ticket Intelligence Agent</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',sans-serif;background:#0d1117;color:#e6edf3;min-height:100vh}}
  header{{background:linear-gradient(135deg,#1a2332,#0d1117);border-bottom:1px solid #30363d;padding:16px 32px;display:flex;align-items:center;gap:12px}}
  header h1{{font-size:1.2rem;font-weight:600;color:#58a6ff}}
  .badge{{background:#1f6feb33;color:#58a6ff;border:1px solid #1f6feb;border-radius:20px;padding:3px 10px;font-size:.75rem}}
  .aws{{background:#ff990033;color:#ff9900;border:1px solid #ff9900;border-radius:20px;padding:3px 10px;font-size:.75rem}}
  .main{{max-width:900px;margin:32px auto;padding:0 20px;display:flex;flex-direction:column;gap:20px}}
  .card{{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:24px}}
  .card h2{{font-size:.85rem;color:#8b949e;text-transform:uppercase;letter-spacing:.05em;margin-bottom:16px}}
  textarea{{width:100%;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#e6edf3;padding:12px;font-size:.95rem;resize:vertical;min-height:80px;font-family:inherit;outline:none}}
  textarea:focus{{border-color:#58a6ff}}
  .btns{{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}}
  .btn{{padding:8px 16px;border-radius:8px;border:none;cursor:pointer;font-size:.85rem;font-weight:500;transition:all .2s}}
  .btn-primary{{background:#1f6feb;color:#fff}}
  .btn-primary:hover{{background:#388bfd}}
  .btn-primary:disabled{{background:#30363d;color:#8b949e;cursor:not-allowed}}
  .btn-demo{{background:#21262d;color:#8b949e;border:1px solid #30363d;font-size:.8rem}}
  .btn-demo:hover{{background:#30363d;color:#e6edf3}}
  .flow{{display:flex;align-items:center;gap:0;margin:8px 0 20px}}
  .step{{display:flex;flex-direction:column;align-items:center;flex:1;position:relative}}
  .step:not(:last-child)::after{{content:'';position:absolute;top:20px;left:55%;width:90%;height:2px;background:#30363d;z-index:0;transition:background .5s}}
  .step.done:not(:last-child)::after{{background:#3fb950}}
  .step.active:not(:last-child)::after{{background:#58a6ff}}
  .icon{{width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.1rem;border:2px solid #30363d;background:#0d1117;z-index:1;transition:all .4s}}
  .step.active .icon{{border-color:#58a6ff;background:#1f6feb22;box-shadow:0 0 16px #58a6ff66;animation:pulse 1.2s infinite}}
  .step.done .icon{{border-color:#3fb950;background:#3fb95022}}
  .step.error .icon{{border-color:#f85149;background:#f8514922}}
  .lbl{{font-size:.7rem;color:#8b949e;margin-top:6px;text-align:center}}
  .step.active .lbl{{color:#58a6ff}}
  .step.done .lbl{{color:#3fb950}}
  @keyframes pulse{{0%,100%{{box-shadow:0 0 8px #58a6ff44}}50%{{box-shadow:0 0 20px #58a6ffaa}}}}
  .agents{{display:flex;gap:8px;margin-top:4px}}
  .agent{{flex:1;background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:8px 4px;text-align:center;font-size:.72rem;color:#8b949e;transition:all .4s}}
  .agent .ai{{font-size:1.2rem;display:block;margin-bottom:3px}}
  .agent.active{{border-color:#58a6ff;background:#1f6feb11;color:#58a6ff;box-shadow:0 0 12px #58a6ff33}}
  .agent.done{{border-color:#3fb950;background:#3fb95011;color:#3fb950}}
  .result{{display:none}}
  .result.show{{display:block}}
  .tags{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}}
  .tag{{display:inline-block;border-radius:6px;padding:4px 12px;font-size:.8rem;font-weight:600}}
  .t-cicd{{background:#1f6feb33;color:#58a6ff;border:1px solid #1f6feb}}
  .t-data{{background:#a371f733;color:#a371f7;border:1px solid #a371f7}}
  .t-infra{{background:#3fb95033;color:#3fb950;border:1px solid #3fb950}}
  .t-access{{background:#d2992233;color:#d29922;border:1px solid #d29922}}
  .t-network{{background:#f8514933;color:#f85149;border:1px solid #f85149}}
  .t-unknown{{background:#30363d;color:#8b949e;border:1px solid #30363d}}
  .t-p1{{background:#f8514933;color:#f85149;border:1px solid #f85149}}
  .t-p2{{background:#d2992233;color:#d29922;border:1px solid #d29922}}
  .t-p3{{background:#3fb95033;color:#3fb950;border:1px solid #3fb950}}
  .t-p4{{background:#1f6feb33;color:#58a6ff;border:1px solid #1f6feb}}
  .t-recurring{{background:#d2992233;color:#d29922;border:1px solid #d29922}}
  .t-new{{background:#a371f733;color:#a371f7;border:1px solid #a371f7}}
  .conf-row{{display:flex;align-items:center;gap:10px;margin:8px 0 16px}}
  .conf-bar{{height:8px;border-radius:4px;background:#30363d;flex:1;overflow:hidden}}
  .conf-fill{{height:100%;border-radius:4px;transition:width .8s ease}}
  .fix-box{{background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:14px;margin-top:12px}}
  .fix-box h3{{font-size:.8rem;color:#8b949e;margin-bottom:8px}}
  .fix-box p,.fix-steps{{font-size:.88rem;line-height:1.7;color:#e6edf3;white-space:pre-wrap}}
  .spinner{{display:inline-block;width:14px;height:14px;border:2px solid #30363d;border-top-color:#58a6ff;border-radius:50%;animation:spin .8s linear infinite;vertical-align:middle;margin-right:6px}}
  @keyframes spin{{to{{transform:rotate(360deg)}}}}
  .status-bar{{font-size:.85rem;color:#8b949e;min-height:24px;margin-top:8px}}
  .resolved{{color:#3fb950;font-weight:600}}
  .error-msg{{color:#f85149;font-size:.85rem;margin-top:8px}}
</style>
</head>
<body>
<header>
  <span style="font-size:1.4rem">🎫</span>
  <h1>IT Ticket Intelligence Agent</h1>
  <span class="badge">Strands SDK</span>
  <span class="aws">☁ Amazon Bedrock Nova</span>
</header>

<div class="main">

  <!-- Input -->
  <div class="card">
    <h2>Submit IT Support Ticket</h2>
    <textarea id="desc" placeholder="Describe the IT issue... e.g. CodePipeline deploy failed — ECS task OOM killed"></textarea>
    <div class="btns">
      <button class="btn btn-primary" id="runBtn" onclick="submitTicket()">▶ Run Agent</button>
      <button class="btn btn-demo" onclick="runDemo(0)">🔧 CI/CD OOM</button>
      <button class="btn btn-demo" onclick="runDemo(1)">🔑 IAM Denied</button>
      <button class="btn btn-demo" onclick="runDemo(2)">🗄 Glue Timeout</button>
      <button class="btn btn-demo" onclick="runDemo(3)">🖥 Disk Full</button>
      <button class="btn btn-demo" onclick="runDemo(4)">🌐 API 503</button>
    </div>
    <div class="status-bar" id="statusBar"></div>
  </div>

  <!-- Flow -->
  <div class="card">
    <h2>Agent Flow</h2>
    <div class="flow">
      <div class="step" id="s-intake"><div class="icon">📥</div><div class="lbl">Intake</div></div>
      <div class="step" id="s-classify"><div class="icon">🤖</div><div class="lbl">Classify<br><span style="font-size:.65rem;color:#8b949e">Bedrock Nova</span></div></div>
      <div class="step" id="s-pattern"><div class="icon">🔍</div><div class="lbl">Pattern<br><span style="font-size:.65rem;color:#8b949e">Match</span></div></div>
      <div class="step" id="s-subagent"><div class="icon">⚡</div><div class="lbl">Sub-Agent<br><span style="font-size:.65rem;color:#8b949e">Specialist</span></div></div>
      <div class="step" id="s-resolve"><div class="icon">✅</div><div class="lbl">Resolve</div></div>
    </div>
    <div style="font-size:.75rem;color:#8b949e;margin-bottom:8px">SPECIALIST AGENTS</div>
    <div class="agents">
      <div class="agent" id="a-cicd"><span class="ai">🔧</span>CI/CD</div>
      <div class="agent" id="a-data"><span class="ai">🗄️</span>Data/ETL</div>
      <div class="agent" id="a-infra"><span class="ai">🖥️</span>Infra</div>
      <div class="agent" id="a-access"><span class="ai">🔑</span>Access/IAM</div>
      <div class="agent" id="a-network"><span class="ai">🌐</span>Network</div>
    </div>
  </div>

  <!-- Result -->
  <div class="card result" id="resultCard">
    <h2>Result</h2>
    <div class="tags" id="tags"></div>
    <div class="conf-row" id="confRow" style="display:none">
      <span style="font-size:.75rem;color:#8b949e;width:90px">Pattern Match</span>
      <div class="conf-bar"><div class="conf-fill" id="confFill" style="width:0%"></div></div>
      <span id="confPct" style="font-size:.8rem;color:#8b949e;width:35px">0%</span>
    </div>
    <div class="fix-box"><h3>📋 Issue Summary</h3><p id="rIssue"></p></div>
    <div class="fix-box"><h3>🛠 Remediation Steps</h3><div class="fix-steps" id="rSteps"></div></div>
    <div class="fix-box" id="rResBox" style="display:none"><h3>☁ AWS Resources</h3><p id="rRes" style="font-size:.82rem;color:#58a6ff"></p></div>
  </div>

</div>

<script>
const LAMBDA = "{LAMBDA_URL}";
const DEMOS = [
  "CodePipeline deploy failed — ECS task OOM killed",
  "Lambda function can't write to S3 bucket prod-reports",
  "Glue job daily_claims_load failed with connection timeout",
  "EC2 instance i-0abc123 unreachable, disk at 98%",
  "API gateway returning 503, backend health checks failing"
];
const CAT_CLASS = {{"CI/CD":"t-cicd","Data/ETL":"t-data","Infrastructure":"t-infra","Access/IAM":"t-access","Network":"t-network","Unknown":"t-unknown"}};
const AGENT_ID  = {{"CI/CD":"a-cicd","Data/ETL":"a-data","Infrastructure":"a-infra","Access/IAM":"a-access","Network":"a-network"}};

function setStep(id, state) {{
  document.getElementById(id).className = "step " + state;
}}
function resetFlow() {{
  ["s-intake","s-classify","s-pattern","s-subagent","s-resolve"].forEach(id => document.getElementById(id).className = "step");
  Object.values(AGENT_ID).forEach(id => document.getElementById(id).className = "agent");
  document.getElementById("resultCard").classList.remove("show");
  document.getElementById("confRow").style.display = "none";
  document.getElementById("rResBox").style.display = "none";
}}
function setAgent(cat, state) {{
  const id = AGENT_ID[cat];
  if (id) document.getElementById(id).className = "agent " + state;
}}
function status(msg, cls="") {{
  const el = document.getElementById("statusBar");
  el.innerHTML = msg ? `<span class="${{cls}}">${{msg}}</span>` : "";
}}

async function runDemo(n) {{
  document.getElementById("desc").value = DEMOS[n];
  await submitTicket();
}}

async function submitTicket() {{
  const desc = document.getElementById("desc").value.trim();
  if (!desc) return;

  const btn = document.getElementById("runBtn");
  btn.disabled = true;
  resetFlow();

  // Animate through steps while waiting
  setStep("s-intake", "active");
  status('<span class="spinner"></span>Creating ticket...');
  await sleep(400);
  setStep("s-intake", "done");

  setStep("s-classify", "active");
  status('<span class="spinner"></span>Calling Amazon Bedrock Nova Lite...');
  await sleep(300);

  setStep("s-pattern", "active");

  try {{
    const res = await fetch(LAMBDA, {{
      method: "POST",
      headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify({{description: desc}})
    }});
    const data = await res.json();

    if (data.error) throw new Error(data.error);

    // Update flow based on result
    setStep("s-classify", "done");
    setStep("s-pattern", data.pattern_status === "RECURRING" ? "done" : "done");
    setStep("s-subagent", "active");
    setAgent(data.category, "active");
    status('<span class="spinner"></span>' + data.category + ' specialist agent investigating...');
    await sleep(600);
    setStep("s-subagent", "done");
    setAgent(data.category, "done");
    setStep("s-resolve", "done");
    status("✅ Ticket resolved", "resolved");

    showResult(data);
  }} catch(e) {{
    setStep("s-classify", "error");
    status("Error: " + e.message, "error-msg");
  }}

  btn.disabled = false;
}}

function showResult(d) {{
  const catClass = CAT_CLASS[d.category] || "t-unknown";
  const sevClass = "t-" + (d.severity||"p3").toLowerCase();
  const patBadge = d.pattern_status === "RECURRING"
    ? '<span class="tag t-recurring">🔄 RECURRING PATTERN</span>'
    : '<span class="tag t-new">✨ NEW ISSUE</span>';

  document.getElementById("tags").innerHTML =
    `<span class="tag ${{catClass}}">${{d.category}}</span>` +
    `<span class="tag ${{sevClass}}">${{d.severity}}</span>` + patBadge;

  if (d.pattern_confidence > 0) {{
    document.getElementById("confRow").style.display = "flex";
    const pct = d.pattern_confidence;
    const fill = document.getElementById("confFill");
    fill.style.width = pct + "%";
    fill.style.background = pct >= 80 ? "#3fb950" : pct >= 50 ? "#d29922" : "#f85149";
    document.getElementById("confPct").textContent = pct + "%";
  }}

  document.getElementById("rIssue").textContent = d.issue_summary;
  document.getElementById("rSteps").textContent = d.remediation_steps;

  if (d.aws_resources && d.aws_resources.length) {{
    document.getElementById("rResBox").style.display = "block";
    document.getElementById("rRes").textContent = d.aws_resources.join("\\n");
  }}

  document.getElementById("resultCard").classList.add("show");
}}

function sleep(ms) {{ return new Promise(r => setTimeout(r, ms)); }}

document.getElementById("desc").addEventListener("keydown", e => {{
  if (e.key === "Enter" && e.ctrlKey) submitTicket();
}});
</script>
</body>
</html>"""

# Upload to S3
s3 = boto3.client("s3", region_name=REGION)

# Enable static website hosting
s3.put_bucket_website(Bucket=BUCKET, WebsiteConfiguration={
    "IndexDocument": {"Suffix": "index.html"}
})

# Make bucket public
try:
    s3.delete_public_access_block(Bucket=BUCKET)
except: pass

try:
    import json
    s3.put_bucket_policy(Bucket=BUCKET, Policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{"Effect":"Allow","Principal":"*","Action":"s3:GetObject",
                       "Resource":f"arn:aws:s3:::{BUCKET}/*"}]
    }))
    print("✓ Bucket policy set to public")
except Exception as e:
    print(f"⚠ Bucket policy: {e}")

# Upload HTML
s3.put_object(Bucket=BUCKET, Key="index.html", Body=HTML.encode(),
              ContentType="text/html")

print(f"\n✅ Dashboard deployed!")
print(f"\n🌐 Open this URL in your browser:")
print(f"   http://{BUCKET}.s3-website-{REGION}.amazonaws.com")
print(f"\n   Share this with leaders for the demo!")
