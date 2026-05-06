#!/usr/bin/env python3
"""
IT Ticket Agent — Rich Terminal Demo
Full visual flow with live panels, progress, and color-coded results.
"""
import os, sys, time, json
from datetime import datetime, timezone

os.environ.setdefault("AWS_DEFAULT_REGION", "us-west-2")
os.environ.setdefault("BEDROCK_REGION",     "us-west-2")
os.environ.setdefault("BEDROCK_MODEL_ID",   "us.amazon.nova-lite-v1:0")
os.environ.setdefault("CONFIDENCE_THRESHOLD", "80")
os.environ["TICKETS_TABLE"]     = "demo_it_tickets"
os.environ["PATTERNS_TABLE"]    = "demo_ticket_patterns"
os.environ["RESOLUTIONS_TABLE"] = "demo_resolutions"
os.environ["RUNBOOK_BUCKET"]    = "demo-runbooks"

sys.path.insert(0, os.path.dirname(__file__))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.columns import Columns
from rich.text import Text
from rich.rule import Rule
from rich.live import Live
from rich.layout import Layout
from rich import box
from rich.prompt import Prompt

console = Console()

# ── Bootstrap ─────────────────────────────────────────────────────────────────
import boto3 as _real_boto3
_real_bedrock = _real_boto3.client("bedrock-runtime", region_name=os.environ["BEDROCK_REGION"])

from moto import mock_aws
import boto3
_mock = mock_aws()
_mock.start()

import config
_ddb = boto3.resource("dynamodb", region_name="us-east-1")

def _make_table(name, pk, attrs, gsi):
    try:
        _ddb.create_table(TableName=name,
            KeySchema=[{"AttributeName": pk, "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": k, "AttributeType": v} for k,v in attrs],
            BillingMode="PAY_PER_REQUEST", GlobalSecondaryIndexes=gsi)
    except: pass

_make_table(config.TICKETS_TABLE, "ticket_id",
    [("ticket_id","S"),("category","S"),("status","S")],
    [{"IndexName":"category-status-index","KeySchema":[{"AttributeName":"category","KeyType":"HASH"},{"AttributeName":"status","KeyType":"RANGE"}],"Projection":{"ProjectionType":"ALL"}}])
_make_table(config.PATTERNS_TABLE, "pattern_id",
    [("pattern_id","S"),("category","S")],
    [{"IndexName":"category-index","KeySchema":[{"AttributeName":"category","KeyType":"HASH"}],"Projection":{"ProjectionType":"ALL"}}])
_make_table(config.RESOLUTIONS_TABLE, "resolution_id",
    [("resolution_id","S"),("ticket_id","S")],
    [{"IndexName":"ticket-index","KeySchema":[{"AttributeName":"ticket_id","KeyType":"HASH"}],"Projection":{"ProjectionType":"ALL"}}])

_s3 = boto3.client("s3", region_name="us-east-1")
try: _s3.create_bucket(Bucket=config.RUNBOOK_BUCKET)
except: pass

_kb_dir = os.path.join(os.path.dirname(__file__), "knowledge_base")
if os.path.isdir(_kb_dir):
    for f in os.listdir(_kb_dir):
        if f.endswith(".md"):
            with open(os.path.join(_kb_dir, f)) as fh:
                _s3.put_object(Bucket=config.RUNBOOK_BUCKET, Key=f"runbooks/{f}", Body=fh.read())

_glue = boto3.client("glue", region_name=config.REGION)
for _job in ["daily_claims_load", "etl_pipeline", "claims_transform"]:
    try:
        _glue.create_job(Name=_job, Role="arn:aws:iam::123:role/GlueRole",
            Command={"Name":"glueetl","ScriptLocation":f"s3://mock/{_job}.py","PythonVersion":"3"})
        _glue.start_job_run(JobName=_job)
    except: pass

from tools.models import TicketPattern, Resolution
from tools.ticket_store import create_pattern

for pat, res in [
    (TicketPattern(pattern_id="pat-cicd-001",category="CI/CD",signature="ECS OOM",resolution_id="res-cicd-001",keywords=["codepipeline","ecs","task","memory","killed","oom","deploy","failed"]),
     Resolution(resolution_id="res-cicd-001",ticket_id="h1",pattern_id="pat-cicd-001",category="CI/CD",severity="P2",description_summary="ECS OOM during deploy",applied_fix="1. Increase ECS memory to 1024MB.\n2. Create new task revision.\n3. Update service.\n4. Re-run pipeline.")),
    (TicketPattern(pattern_id="pat-data-001",category="Data/ETL",signature="Glue timeout",resolution_id="res-data-001",keywords=["glue","job","failed","connection","timeout","jdbc","daily","load","claims"]),
     Resolution(resolution_id="res-data-001",ticket_id="h2",pattern_id="pat-data-001",category="Data/ETL",severity="P2",description_summary="Glue JDBC timeout",applied_fix="1. Increase JDBC timeout to 120s.\n2. Add retry logic.\n3. Increase DPU.")),
    (TicketPattern(pattern_id="pat-infra-001",category="Infrastructure",signature="EC2 disk full",resolution_id="res-infra-001",keywords=["ec2","instance","disk","full","unreachable","storage","ebs","volume"]),
     Resolution(resolution_id="res-infra-001",ticket_id="h3",pattern_id="pat-infra-001",category="Infrastructure",severity="P1",description_summary="EC2 disk full",applied_fix="1. Clean /tmp.\n2. Rotate logs.\n3. Extend EBS volume.")),
    (TicketPattern(pattern_id="pat-access-001",category="Access/IAM",signature="Lambda S3 denied",resolution_id="res-access-001",keywords=["lambda","function","s3","bucket","write","access","denied","permission","role"]),
     Resolution(resolution_id="res-access-001",ticket_id="h4",pattern_id="pat-access-001",category="Access/IAM",severity="P3",description_summary="Lambda S3 denied",applied_fix="1. Add s3:PutObject to Lambda execution role.")),
    (TicketPattern(pattern_id="pat-network-001",category="Network",signature="API Gateway 503",resolution_id="res-network-001",keywords=["api","gateway","503","backend","health","security","group","inbound","alb"]),
     Resolution(resolution_id="res-network-001",ticket_id="h5",pattern_id="pat-network-001",category="Network",severity="P1",description_summary="API Gateway 503",applied_fix="1. Add SG inbound rule TCP 8080 from ALB.")),
]:
    create_pattern(pat, _ddb)
    _ddb.Table(config.RESOLUTIONS_TABLE).put_item(Item=res.to_dict())

import tools.classifier as _clf
import agent_core.base_agent as _ba

def _nova_clf(prompt):
    body = json.dumps({"system":[{"text":_clf.SYSTEM_PROMPT}],
        "messages":[{"role":"user","content":[{"text":prompt}]}],
        "inferenceConfig":{"maxTokens":256,"temperature":0.1}})
    r = _real_bedrock.invoke_model(modelId=os.environ["BEDROCK_MODEL_ID"],
        body=body, contentType="application/json", accept="application/json")
    return json.loads(r["body"].read())["output"]["message"]["content"][0]["text"]

def _nova_ba(system_prompt, prompt):
    body = json.dumps({"system":[{"text":system_prompt}],
        "messages":[{"role":"user","content":[{"text":prompt}]}],
        "inferenceConfig":{"maxTokens":1024,"temperature":0.2}})
    r = _real_bedrock.invoke_model(modelId=os.environ["BEDROCK_MODEL_ID"],
        body=body, contentType="application/json", accept="application/json")
    return json.loads(r["body"].read())["output"]["message"]["content"][0]["text"]

_clf._call_nova = _nova_clf
_ba._call_nova  = _nova_ba

# ── Visual helpers ─────────────────────────────────────────────────────────────

CATEGORY_STYLE = {
    "CI/CD":          ("bright_blue",   "🔧"),
    "Data/ETL":       ("bright_magenta","🗄 "),
    "Infrastructure": ("bright_green",  "🖥 "),
    "Access/IAM":     ("bright_yellow", "🔑"),
    "Network":        ("bright_red",    "🌐"),
    "Unknown":        ("white",         "❓"),
}
SEVERITY_STYLE = {
    "P1": ("bright_red",    "🔴 P1 CRITICAL"),
    "P2": ("bright_yellow", "🟡 P2 HIGH"),
    "P3": ("bright_green",  "🟢 P3 MEDIUM"),
    "P4": ("bright_blue",   "🔵 P4 LOW"),
}

def print_header():
    console.print()
    console.print(Panel.fit(
        "[bold bright_cyan]🎫  IT Ticket Intelligence Agent[/bold bright_cyan]\n"
        "[dim]Powered by Amazon Bedrock Nova · Strands SDK · AWS[/dim]",
        border_style="bright_cyan", padding=(0, 4)
    ))

def print_flow_diagram(active_step=None, done_steps=None, category=None):
    done_steps = done_steps or []
    steps = [
        ("intake",    "📥", "Intake"),
        ("classify",  "🤖", "Classify"),
        ("pattern",   "🔍", "Pattern"),
        ("subagent",  "⚡", "Sub-Agent"),
        ("approval",  "✅", "Resolve"),
    ]
    parts = []
    for key, icon, label in steps:
        if key in done_steps:
            parts.append(f"[bold green]{icon} {label}[/bold green]")
        elif key == active_step:
            parts.append(f"[bold bright_cyan blink]{icon} {label}[/bold bright_cyan blink]")
        else:
            parts.append(f"[dim]{icon} {label}[/dim]")
        if key != "approval":
            parts.append("[dim] ──▶ [/dim]")
    console.print("  " + "".join(parts))

    # Sub-agents row
    agents = [
        ("CI/CD",          "🔧", "bright_blue"),
        ("Data/ETL",       "🗄 ", "bright_magenta"),
        ("Infrastructure", "🖥 ", "bright_green"),
        ("Access/IAM",     "🔑", "bright_yellow"),
        ("Network",        "🌐", "bright_red"),
    ]
    if active_step in ("subagent", "approval") or "subagent" in done_steps:
        agent_parts = []
        for name, icon, color in agents:
            if name == category and active_step == "subagent":
                agent_parts.append(f"[bold {color} reverse] {icon} {name} [/bold {color} reverse]")
            elif name == category and "subagent" in done_steps:
                agent_parts.append(f"[bold {color}]✓ {icon} {name}[/bold {color}]")
            else:
                agent_parts.append(f"[dim]  {icon} {name} [/dim]")
        console.print("  " + "  ".join(agent_parts))


def conf_bar(score):
    filled = round(score / 5)
    empty = 20 - filled
    color = "green" if score >= 80 else "yellow" if score >= 50 else "red"
    return f"[{color}]{'█' * filled}[/{color}][dim]{'░' * empty}[/dim] [bold]{score}%[/bold]"


def run_ticket(description):
    from tools.ticket_store import (create_ticket, update_ticket,
        get_patterns_by_category, get_resolution_by_pattern)
    from tools.classifier import classify_ticket
    from tools.pattern_matcher import route_ticket
    from tools.models import FixSuggestion
    import tools.ticket_store as ts

    console.print()
    console.print(Rule("[bold bright_cyan]Processing Ticket[/bold bright_cyan]", style="bright_cyan"))
    console.print(f"  [dim]Description:[/dim] [italic]{description}[/italic]")
    console.print()

    done = []

    # ── Step 1: Intake ────────────────────────────────────────────────────────
    print_flow_diagram("intake", done)
    with console.status("[bright_cyan]Creating ticket...[/bright_cyan]", spinner="dots"):
        ticket = create_ticket(description, dynamodb=_ddb)
        time.sleep(0.3)
    done.append("intake")
    console.print(f"  [green]✓[/green] Ticket created: [bold]{ticket.ticket_id[:8]}...[/bold]")
    console.print()

    # ── Step 2: Classify ──────────────────────────────────────────────────────
    print_flow_diagram("classify", done)
    with console.status("[bright_cyan]Calling Amazon Bedrock Nova Lite...[/bright_cyan]", spinner="dots"):
        c = classify_ticket(description)
    ticket.category = c["category"]
    ticket.severity  = c["severity"]
    ticket.classification_rationale = c["rationale"]
    ticket.add_status_transition("NEW", "Classification complete")
    update_ticket(ticket, _ddb)
    done.append("classify")

    cat_color, cat_icon = CATEGORY_STYLE.get(ticket.category, ("white","❓"))
    sev_color, sev_label = SEVERITY_STYLE.get(ticket.severity, ("white", ticket.severity))
    console.print(f"  [green]✓[/green] Category : [{cat_color}]{cat_icon} {ticket.category}[/{cat_color}]")
    console.print(f"  [green]✓[/green] Severity : [{sev_color}]{sev_label}[/{sev_color}]")
    console.print(f"  [green]✓[/green] Rationale: [dim]{c['rationale']}[/dim]")
    console.print()

    # ── Step 3: Pattern Match ─────────────────────────────────────────────────
    print_flow_diagram("pattern", done, ticket.category)
    with console.status("[bright_cyan]Scanning known patterns...[/bright_cyan]", spinner="dots"):
        patterns = get_patterns_by_category(ticket.category, _ddb)
        routing  = route_ticket(description, patterns)
        time.sleep(0.2)
    conf = routing["confidence"]
    done.append("pattern")

    if routing["status"] == "RECURRING":
        pattern = routing["pattern"]
        ticket.pattern_id = pattern.pattern_id
        ticket.add_status_transition("RECURRING", f"Confidence: {conf}%")
        update_ticket(ticket, _ddb)
        console.print(f"  [bold yellow]🔄 RECURRING PATTERN DETECTED[/bold yellow]")
        console.print(f"  Pattern ID : [dim]{pattern.pattern_id}[/dim]")
        console.print(f"  Confidence : {conf_bar(conf)}")
    else:
        console.print(f"  [bold magenta]✨ NEW ISSUE[/bold magenta] — no pattern match")
        console.print(f"  Best match : {conf_bar(conf)}")
    console.print()

    # ── Step 4: Sub-Agent ─────────────────────────────────────────────────────
    print_flow_diagram("subagent", done, ticket.category)
    fix = None

    if routing["status"] == "RECURRING":
        with console.status("[bright_cyan]Fetching proven fix from knowledge base...[/bright_cyan]", spinner="dots"):
            resolution = get_resolution_by_pattern(pattern.pattern_id, _ddb)
        if resolution:
            fix = FixSuggestion(issue_summary=resolution.description_summary,
                remediation_steps=resolution.applied_fix, confidence="HIGH")
            console.print(f"  [green]✓[/green] Proven fix retrieved from knowledge base")
        else:
            fix = _run_subagent(ticket)
    else:
        console.print(f"  [{cat_color}]{cat_icon} Delegating to {ticket.category} specialist agent...[/{cat_color}]")
        fix = _run_subagent(ticket)
        console.print(f"  [green]✓[/green] {ticket.category} agent analysis complete")

    done.append("subagent")
    console.print()

    # ── Step 5: Resolve ───────────────────────────────────────────────────────
    print_flow_diagram("approval", done, ticket.category)
    ticket.fix_suggestion = fix.issue_summary
    ticket.fix_confidence  = fix.confidence
    ticket.resolved_at     = datetime.now(timezone.utc).isoformat()
    ticket.resolved_by     = "operator"
    ticket.add_status_transition("RESOLVED", "Operator approved fix")
    update_ticket(ticket, _ddb)
    ts.log_resolution(ticket, fix.remediation_steps, _ddb)
    done.append("approval")
    console.print()

    # ── Result Panel ──────────────────────────────────────────────────────────
    _print_result(ticket, fix, routing)
    return ticket


def _run_subagent(ticket):
    from agent_core.cicd_agent import CICDAgent
    from agent_core.data_agent import DataETLAgent
    from agent_core.infra_agent import InfraAgent
    from agent_core.access_agent import AccessIAMAgent
    from agent_core.network_agent import NetworkAgent
    from tools.models import FixSuggestion
    agents = {"CI/CD":CICDAgent(),"Data/ETL":DataETLAgent(),
              "Infrastructure":InfraAgent(),"Access/IAM":AccessIAMAgent(),"Network":NetworkAgent()}
    agent = agents.get(ticket.category)
    if not agent:
        return FixSuggestion(issue_summary="Unknown category.",
            remediation_steps="Escalate to on-call.", confidence="LOW_CONFIDENCE")
    with console.status(f"[bright_cyan]AI sub-agent investigating...[/bright_cyan]", spinner="dots"):
        return agent.investigate(ticket.ticket_id, ticket.description,
            ticket.category, ticket.severity, _s3)


def _print_result(ticket, fix, routing):
    cat_color, cat_icon = CATEGORY_STYLE.get(ticket.category, ("white","❓"))
    sev_color, sev_label = SEVERITY_STYLE.get(ticket.severity, ("white", ticket.severity))
    conf_color = "green" if fix.confidence == "HIGH" else "yellow"
    pat_badge = "[bold yellow]🔄 RECURRING[/bold yellow]" if routing["status"] == "RECURRING" else "[bold magenta]✨ NEW ISSUE[/bold magenta]"

    # Header table
    t = Table(box=box.ROUNDED, border_style="bright_cyan", show_header=False, padding=(0,1))
    t.add_column(style="dim", width=16)
    t.add_column()
    t.add_row("Ticket ID",  f"[bold]{ticket.ticket_id}[/bold]")
    t.add_row("Category",   f"[{cat_color}]{cat_icon} {ticket.category}[/{cat_color}]")
    t.add_row("Severity",   f"[{sev_color}]{sev_label}[/{sev_color}]")
    t.add_row("Pattern",    pat_badge)
    t.add_row("Confidence", conf_bar(routing["confidence"]))
    t.add_row("AI Confidence", f"[{conf_color}]{'✓ HIGH' if fix.confidence=='HIGH' else '⚠ LOW'}[/{conf_color}]")
    t.add_row("Status",     "[bold green]✅ RESOLVED[/bold green]")

    console.print(Panel(t, title="[bold bright_cyan]🎫 Ticket Result[/bold bright_cyan]",
        border_style="bright_cyan"))

    # Fix panel
    steps_text = Text()
    for line in fix.remediation_steps.splitlines():
        line = line.strip()
        if not line: continue
        if line[0].isdigit():
            steps_text.append(f"  {line}\n", style="bright_white")
        else:
            steps_text.append(f"  {line}\n", style="white")

    console.print(Panel(
        f"[bold]📋 Issue:[/bold]\n  [italic]{fix.issue_summary}[/italic]\n\n"
        f"[bold]🛠  Remediation Steps:[/bold]\n" + steps_text.plain,
        title=f"[bold {cat_color}]{cat_icon} Fix Suggestion[/bold {cat_color}]",
        border_style=cat_color
    ))

    if fix.aws_resources:
        res_text = "\n".join(f"  [bright_blue]•[/bright_blue] {r}" for r in fix.aws_resources)
        console.print(Panel(res_text, title="[bold]☁  AWS Resources[/bold]", border_style="bright_blue"))

    console.print()


# ── Main menu ─────────────────────────────────────────────────────────────────

DEMOS = [
    "CodePipeline deploy failed — ECS task OOM killed",
    "Lambda function can't write to S3 bucket prod-reports",
    "Glue job daily_claims_load failed with connection timeout",
    "EC2 instance i-0abc123 unreachable, disk at 98%",
    "API gateway returning 503, backend health checks failing",
]

def main():
    print_header()

    while True:
        console.print()
        console.print(Rule("[dim]Demo Scenarios[/dim]", style="dim"))

        table = Table(box=box.SIMPLE, show_header=False, padding=(0,1))
        table.add_column(style="bold bright_cyan", width=4)
        table.add_column(style="dim", width=14)
        table.add_column()
        table.add_row("1", "🔧 CI/CD",       DEMOS[0])
        table.add_row("2", "🔑 Access/IAM",  DEMOS[1])
        table.add_row("3", "🗄  Data/ETL",    DEMOS[2])
        table.add_row("4", "🖥  Infra",       DEMOS[3])
        table.add_row("5", "🌐 Network",      DEMOS[4])
        table.add_row("6", "✏️  Custom",       "Enter your own ticket")
        table.add_row("q", "Quit", "")
        console.print(table)

        choice = Prompt.ask("[bold bright_cyan]Select[/bold bright_cyan]",
                            choices=["1","2","3","4","5","6","q"], default="1")

        if choice == "q":
            console.print("\n[dim]Goodbye![/dim]\n")
            break
        elif choice == "6":
            desc = Prompt.ask("[bold]Enter ticket description[/bold]")
            if desc.strip():
                run_ticket(desc.strip())
        else:
            run_ticket(DEMOS[int(choice)-1])

        input("\n  [Press Enter to continue...]")
        console.clear()
        print_header()


if __name__ == "__main__":
    main()
