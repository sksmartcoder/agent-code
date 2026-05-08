#!/usr/bin/env python3
"""Generate PowerPoint presentation for IT Ticket Intelligence Agent."""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
import pptx.oxml.ns as nsmap
from lxml import etree

# ── Colours ───────────────────────────────────────────────────────────────────
DARK_BG    = RGBColor(0x0d, 0x11, 0x17)
CARD_BG    = RGBColor(0x16, 0x1b, 0x22)
BLUE       = RGBColor(0x58, 0xa6, 0xff)
GREEN      = RGBColor(0x3f, 0xb9, 0x50)
YELLOW     = RGBColor(0xd2, 0x99, 0x22)
RED        = RGBColor(0xf8, 0x51, 0x49)
PURPLE     = RGBColor(0xa3, 0x71, 0xf7)
ORANGE     = RGBColor(0xff, 0x99, 0x00)
WHITE      = RGBColor(0xe6, 0xed, 0xf3)
GRAY       = RGBColor(0x8b, 0x94, 0x9e)
BORDER     = RGBColor(0x30, 0x36, 0x3d)

prs = Presentation()
prs.slide_width  = Inches(13.33)
prs.slide_height = Inches(7.5)

BLANK = prs.slide_layouts[6]  # blank layout

# ── Helpers ───────────────────────────────────────────────────────────────────
def slide():
    s = prs.slides.add_slide(BLANK)
    bg = s.background.fill
    bg.solid()
    bg.fore_color.rgb = DARK_BG
    return s

def box(s, x, y, w, h, fill=None, border=None, radius=0):
    shape = s.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.line.color.rgb = border or BORDER
    shape.line.width = Pt(1)
    if fill:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    else:
        shape.fill.background()
    return shape

def txt(s, text, x, y, w, h, size=18, bold=False, color=None, align=PP_ALIGN.LEFT, wrap=True):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color or WHITE
    return tb

def heading(s, text, subtitle=None):
    txt(s, text, 0.4, 0.25, 12.5, 0.7, size=32, bold=True, color=BLUE, align=PP_ALIGN.CENTER)
    if subtitle:
        txt(s, subtitle, 0.4, 0.9, 12.5, 0.4, size=14, color=GRAY, align=PP_ALIGN.CENTER)

def divider(s, y=1.25):
    line = s.shapes.add_shape(1, Inches(0.4), Inches(y), Inches(12.5), Inches(0.02))
    line.fill.solid()
    line.fill.fore_color.rgb = BORDER
    line.line.fill.background()

def badge(s, text, x, y, color=BLUE, bg=None):
    b = box(s, x, y, len(text)*0.11+0.2, 0.28, fill=bg or CARD_BG, border=color)
    txt(s, text, x+0.05, y+0.02, len(text)*0.11+0.1, 0.24, size=9, color=color, align=PP_ALIGN.CENTER)

def card(s, x, y, w, h, title, body, icon="", title_color=BLUE, border_color=None):
    b = box(s, x, y, w, h, fill=CARD_BG, border=border_color or BORDER)
    if icon:
        txt(s, icon, x+0.1, y+0.1, 0.5, 0.4, size=20, align=PP_ALIGN.CENTER)
        txt(s, title, x+0.55, y+0.12, w-0.7, 0.35, size=11, bold=True, color=title_color)
        txt(s, body, x+0.1, y+0.5, w-0.2, h-0.6, size=9, color=GRAY)
    else:
        txt(s, title, x+0.15, y+0.12, w-0.3, 0.35, size=11, bold=True, color=title_color)
        txt(s, body, x+0.15, y+0.5, w-0.3, h-0.6, size=9, color=GRAY)

def arrow(s, x, y, w=0.4):
    txt(s, "▶", x, y, w, 0.3, size=12, color=BLUE, align=PP_ALIGN.CENTER)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 1 — TITLE
# ═══════════════════════════════════════════════════════════════════════════════
s = slide()
txt(s, "🎫", 5.9, 1.2, 1.5, 1.2, size=60, align=PP_ALIGN.CENTER)
txt(s, "IT Ticket Intelligence Agent", 1, 2.4, 11.3, 1.0,
    size=36, bold=True, color=BLUE, align=PP_ALIGN.CENTER)
txt(s, "AI-Powered IT Support Triage · Multi-Agent System · Amazon Bedrock",
    1, 3.4, 11.3, 0.5, size=16, color=GRAY, align=PP_ALIGN.CENTER)

for i, (label, color) in enumerate([
    ("Strands SDK", BLUE), ("Amazon Bedrock Nova", ORANGE),
    ("AWS Lambda", ORANGE), ("AgentCore Runtime", PURPLE)
]):
    bx = 2.5 + i * 2.1
    badge(s, label, bx, 4.1, color)

txt(s, "AWS Hackathon 2026  ·  Team Presentation",
    1, 6.5, 11.3, 0.5, size=12, color=GRAY, align=PP_ALIGN.CENTER)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 2 — THE PROBLEM (Non-technical)
# ═══════════════════════════════════════════════════════════════════════════════
s = slide()
heading(s, "The Problem We Solved")
divider(s)

txt(s, "Every day, IT teams waste hours on tickets that have already been solved before.",
    0.5, 1.4, 12.3, 0.5, size=16, color=WHITE, align=PP_ALIGN.CENTER)

problems = [
    ("⏱", "Hours wasted", "Engineers spend 2-4 hours diagnosing issues that were solved last week"),
    ("🔁", "Same problems, again", "No institutional memory — every incident starts from scratch"),
    ("🎯", "Wrong team", "Tickets land with the wrong team, causing delays and frustration"),
    ("📋", "No audit trail", "No record of what was tried, what worked, or why"),
]
for i, (icon, title, body) in enumerate(problems):
    col = i % 2
    row = i // 2
    card(s, 0.5 + col*6.4, 2.1 + row*2.1, 6.1, 1.9,
         title, body, icon, title_color=YELLOW, border_color=YELLOW)

txt(s, "Result: Slow resolution · Frustrated engineers · Repeated mistakes · No learning",
    0.5, 6.5, 12.3, 0.5, size=12, color=RED, align=PP_ALIGN.CENTER)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 3 — OUR SOLUTION (Non-technical)
# ═══════════════════════════════════════════════════════════════════════════════
s = slide()
heading(s, "Our Solution", "An AI agent that triages, routes, and resolves IT tickets automatically")
divider(s)

steps = [
    ("📝", "Ticket Submitted", "Engineer reports an IT issue in plain English", BLUE),
    ("🤖", "AI Understands", "Bedrock AI reads and classifies the problem instantly", PURPLE),
    ("🔍", "Checks Memory", "Has this happened before? Pulls proven fix if yes", YELLOW),
    ("⚡", "Expert Takes Over", "Right specialist AI agent investigates the issue", GREEN),
    ("👤", "Human Approves", "Operator reviews and approves the fix", ORANGE),
    ("✅", "Resolved & Learned", "Fixed and remembered for next time", GREEN),
]

for i, (icon, title, body, color) in enumerate(steps):
    x = 0.4 + (i % 3) * 4.2
    y = 1.5 + (i // 3) * 2.3
    b = box(s, x, y, 3.9, 2.0, fill=CARD_BG, border=color)
    txt(s, icon, x+0.15, y+0.15, 0.6, 0.5, size=22)
    txt(s, f"{i+1}. {title}", x+0.75, y+0.18, 3.0, 0.4, size=12, bold=True, color=color)
    txt(s, body, x+0.15, y+0.65, 3.6, 1.1, size=10, color=GRAY)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 4 — BUSINESS VALUE
# ═══════════════════════════════════════════════════════════════════════════════
s = slide()
heading(s, "Business Value")
divider(s)

metrics = [
    ("⚡", "Seconds", "Recurring issues resolved", GREEN),
    ("🎯", "5 Domains", "Specialist agents: CI/CD, Data, Infra, IAM, Network", BLUE),
    ("🧠", "Self-Learning", "Gets smarter with every resolved ticket", PURPLE),
    ("👤", "Human Control", "Operator approves every fix before it's applied", ORANGE),
    ("🔄", "Auto-Remediation", "Glue jobs restarted automatically", YELLOW),
    ("📊", "Full Audit Trail", "Every decision logged and traceable", GREEN),
]

for i, (icon, metric, desc, color) in enumerate(metrics):
    col = i % 3
    row = i // 2
    x = 0.4 + col * 4.2
    y = 1.5 + row * 2.2
    b = box(s, x, y, 3.9, 2.0, fill=CARD_BG, border=color)
    txt(s, icon, x+1.5, y+0.15, 0.9, 0.5, size=24, align=PP_ALIGN.CENTER)
    txt(s, metric, x+0.15, y+0.7, 3.6, 0.4, size=14, bold=True, color=color, align=PP_ALIGN.CENTER)
    txt(s, desc, x+0.15, y+1.1, 3.6, 0.7, size=9, color=GRAY, align=PP_ALIGN.CENTER)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 5 — DEMO SCENARIOS
# ═══════════════════════════════════════════════════════════════════════════════
s = slide()
heading(s, "Live Demo Scenarios")
divider(s)

scenarios = [
    ("🔧", "CI/CD Pipeline", "CodePipeline deploy failed — ECS task OOM killed",
     "RECURRING · 88% match · Proven fix in seconds", BLUE),
    ("🗄", "Data/ETL", "Glue job daily_claims_load failed with connection timeout",
     "NEW · Data agent + auto Glue job re-trigger", YELLOW),
    ("🖥", "Infrastructure", "EC2 instance unreachable, disk at 98%",
     "NEW · Infra agent · P1 Critical", GREEN),
    ("🔑", "Access/IAM", "Lambda function can't write to S3 bucket",
     "NEW · IAM agent · Permission fix", YELLOW),
    ("🌐", "Network", "API gateway returning 503, health checks failing",
     "NEW · Network agent · Security group fix", RED),
]

for i, (icon, category, ticket, result, color) in enumerate(scenarios):
    y = 1.5 + i * 1.05
    b = box(s, 0.4, y, 12.5, 0.95, fill=CARD_BG, border=color)
    txt(s, icon, 0.5, y+0.2, 0.5, 0.5, size=18)
    txt(s, category, 1.1, y+0.08, 1.8, 0.35, size=11, bold=True, color=color)
    txt(s, ticket, 1.1, y+0.48, 6.5, 0.35, size=10, color=GRAY)
    txt(s, result, 8.0, y+0.25, 4.7, 0.4, size=10, color=WHITE, align=PP_ALIGN.RIGHT)

txt(s, "Dashboard: http://amzn-hackthon-it-ticket-system.s3-website-us-west-2.amazonaws.com",
    0.4, 6.8, 12.5, 0.35, size=9, color=BLUE, align=PP_ALIGN.CENTER)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 6 — ARCHITECTURE (Technical)
# ═══════════════════════════════════════════════════════════════════════════════
s = slide()
heading(s, "System Architecture", "Technical Overview")
divider(s)

# Entry points
txt(s, "ENTRY POINTS", 0.4, 1.4, 3, 0.25, size=8, color=GRAY)
for i, (icon, name, sub) in enumerate([
    ("🌐", "S3 Dashboard", "Static HTML"),
    ("λ", "Lambda API", "Function URL"),
    ("☁", "AgentCore", "Runtime"),
]):
    x = 0.4 + i * 1.55
    b = box(s, x, 1.65, 1.4, 0.7, fill=CARD_BG, border=BLUE)
    txt(s, f"{icon} {name}", x+0.05, 1.72, 1.3, 0.25, size=8, bold=True, color=BLUE)
    txt(s, sub, x+0.05, 1.97, 1.3, 0.2, size=7, color=GRAY)

arrow(s, 5.0, 1.9, 0.5)

# Master Agent
b = box(s, 5.5, 1.55, 3.2, 0.85, fill=CARD_BG, border=BLUE)
txt(s, "🎯 Master Agent", 5.6, 1.62, 3.0, 0.3, size=11, bold=True, color=BLUE)
txt(s, "Strands SDK · Bedrock Nova Lite\nClassify → Pattern → Route → Approve", 5.6, 1.92, 3.0, 0.4, size=8, color=GRAY)

arrow(s, 8.75, 1.9, 0.4)

# AgentCore
b = box(s, 9.2, 1.55, 2.0, 0.85, fill=CARD_BG, border=PURPLE)
txt(s, "☁ AgentCore", 9.3, 1.62, 1.8, 0.3, size=10, bold=True, color=PURPLE)
txt(s, "Runtime · STM Memory\nObservability", 9.3, 1.92, 1.8, 0.4, size=8, color=GRAY)

# Agent Bus
txt(s, "AGENT MESSAGE BUS  ──  REQUEST · RESPONSE · NOTIFY", 0.4, 2.6, 12.5, 0.3, size=9, color=PURPLE, align=PP_ALIGN.CENTER)
b = box(s, 0.4, 2.85, 12.5, 0.08, fill=PURPLE, border=PURPLE)

# Sub-agents
agents = [
    ("🔧", "CICDAgent", "CodePipeline\nECS · OOM", BLUE),
    ("🗄", "DataETLAgent", "Glue · RDS\nAuto re-run ⚡", YELLOW),
    ("🖥", "InfraAgent", "EC2 · EBS\nDisk · CPU", GREEN),
    ("🔑", "AccessIAMAgent", "Lambda · S3\nRoles", YELLOW),
    ("🌐", "NetworkAgent", "VPC · ALB\nAPI GW 503", RED),
]
for i, (icon, name, desc, color) in enumerate(agents):
    x = 0.4 + i * 2.5
    b = box(s, x, 3.0, 2.3, 1.1, fill=CARD_BG, border=color)
    txt(s, icon, x+0.1, 3.05, 0.4, 0.4, size=16)
    txt(s, name, x+0.5, 3.08, 1.7, 0.3, size=9, bold=True, color=color)
    txt(s, desc, x+0.1, 3.45, 2.1, 0.55, size=8, color=GRAY)

# AWS Services
txt(s, "AWS SERVICES", 0.4, 4.25, 3, 0.25, size=8, color=GRAY)
services = [
    ("🧠", "Bedrock Nova", "LIVE", GREEN),
    ("🪣", "S3", "LIVE", GREEN),
    ("λ", "Lambda", "LIVE", GREEN),
    ("☁", "AgentCore", "READY", GREEN),
    ("🗃", "DynamoDB", "moto", YELLOW),
    ("🔄", "Glue", "moto", YELLOW),
    ("📊", "CloudWatch", "LIVE", GREEN),
]
for i, (icon, name, status, color) in enumerate(services):
    x = 0.4 + i * 1.78
    b = box(s, x, 4.5, 1.65, 0.75, fill=CARD_BG, border=color)
    txt(s, f"{icon} {name}", x+0.05, 4.55, 1.55, 0.28, size=8, bold=True, color=color)
    txt(s, status, x+0.05, 4.83, 1.55, 0.25, size=8, color=color, align=PP_ALIGN.CENTER)

# Observability
txt(s, "OBSERVABILITY: Agent Tracer → Agent Bus Log → CloudWatch Logs → GenAI Dashboard",
    0.4, 5.45, 12.5, 0.3, size=9, color=GREEN, align=PP_ALIGN.CENTER)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 7 — AGENT-TO-AGENT INTERACTION (Technical)
# ═══════════════════════════════════════════════════════════════════════════════
s = slide()
heading(s, "Agent-to-Agent Communication", "How specialist agents collaborate via the Message Bus")
divider(s)

txt(s, "Example: Glue job timeout with storage issue detected",
    0.4, 1.4, 12.5, 0.3, size=12, color=YELLOW, align=PP_ALIGN.CENTER)

messages = [
    ("🎯 MasterAgent", "──REQUEST──▶", "🗄 DataETLAgent",
     "ticket_id · description · category=Data/ETL · severity=P2", BLUE),
    ("🗄 DataETLAgent", "──NOTIFY──▶", "🖥 InfraAgent",
     "storage keywords detected → consulting peer agent for disk analysis", YELLOW),
    ("🖥 InfraAgent", "──RESPONSE──▶", "🗄 DataETLAgent",
     "disk remediation steps: clean /tmp, extend EBS volume", GREEN),
    ("🗄 DataETLAgent", "──ACTION──▶", "AWS Glue",
     "start_job_run(JobName='daily_claims_load') → Job Run ID: 01", ORANGE),
    ("🗄 DataETLAgent", "──RESPONSE──▶", "🎯 MasterAgent",
     "issue_summary · remediation_steps (merged) · confidence=HIGH · glue_run_id=01", GREEN),
    ("🎯 MasterAgent", "──APPROVAL──▶", "👤 Operator",
     "Fix presented → operator types 'approve' → RESOLVED", ORANGE),
]

for i, (sender, arrow_txt, receiver, content, color) in enumerate(messages):
    y = 1.85 + i * 0.82
    b = box(s, 0.4, y, 12.5, 0.72, fill=CARD_BG, border=color)
    txt(s, sender,     0.55, y+0.08, 2.2, 0.28, size=10, bold=True, color=BLUE)
    txt(s, arrow_txt,  2.8,  y+0.08, 1.6, 0.28, size=9,  color=color, align=PP_ALIGN.CENTER)
    txt(s, receiver,   4.45, y+0.08, 2.2, 0.28, size=10, bold=True, color=GREEN)
    txt(s, content,    0.55, y+0.38, 12.0, 0.25, size=8, color=GRAY)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 8 — KEY LEARNINGS
# ═══════════════════════════════════════════════════════════════════════════════
s = slide()
heading(s, "Key Learnings from the Hackathon")
divider(s)

learnings = [
    ("✅", "What Worked Well", [
        "Amazon Nova Lite — fast, accurate, no legacy issues",
        "S3 static site + Lambda — zero port config, shareable URL instantly",
        "Dependency injection — trivial to swap real vs mock AWS",
        "Agent Message Bus — clean tracing of agent interactions",
        "moto mock — full DynamoDB/S3/Glue without permissions",
    ], GREEN),
    ("⚠", "Challenges Hit", [
        "Claude models marked legacy — switched to Nova on day 1",
        "Strands SDK streaming incompatible with Nova — used direct boto3",
        "AgentCore 30s cold start limit — dropped moto, used Python dicts",
        "Lambda Function URL 403 — account-level restriction",
        "No DynamoDB/CloudFormation permissions on EC2 role",
    ], YELLOW),
]

for col, (icon, title, points, color) in enumerate(learnings):
    x = 0.4 + col * 6.4
    b = box(s, x, 1.4, 6.1, 5.7, fill=CARD_BG, border=color)
    txt(s, f"{icon}  {title}", x+0.2, 1.5, 5.7, 0.4, size=13, bold=True, color=color)
    for j, point in enumerate(points):
        txt(s, f"• {point}", x+0.2, 2.05 + j*0.9, 5.7, 0.75, size=10, color=GRAY)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 9 — WHAT'S NEXT
# ═══════════════════════════════════════════════════════════════════════════════
s = slide()
heading(s, "What's Next", "Roadmap to production")
divider(s)

next_steps = [
    ("🗃", "Real DynamoDB", "Replace moto with real DynamoDB tables for persistent ticket history and pattern learning across sessions", BLUE),
    ("🔐", "IAM Permissions", "Grant DynamoDB, Glue, and CloudFormation permissions to enable full AWS integration", YELLOW),
    ("📧", "Slack / Email Alerts", "Notify on-call engineers automatically when P1 tickets are created", PURPLE),
    ("📈", "Analytics Dashboard", "Track resolution times, recurring patterns, and agent performance over time", GREEN),
    ("🔄", "Real Glue Integration", "Connect to actual AWS Glue jobs for real ETL auto-remediation", ORANGE),
    ("🌐", "API Gateway", "Expose the agent as a REST API for integration with ServiceNow, Jira, PagerDuty", RED),
]

for i, (icon, title, desc, color) in enumerate(next_steps):
    col = i % 2
    row = i // 2
    x = 0.4 + col * 6.4
    y = 1.5 + row * 1.85
    b = box(s, x, y, 6.1, 1.7, fill=CARD_BG, border=color)
    txt(s, icon, x+0.15, y+0.15, 0.5, 0.5, size=20)
    txt(s, title, x+0.7, y+0.18, 5.2, 0.35, size=12, bold=True, color=color)
    txt(s, desc, x+0.15, y+0.65, 5.8, 0.85, size=9, color=GRAY)

# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 10 — CLOSING
# ═══════════════════════════════════════════════════════════════════════════════
s = slide()
txt(s, "🎫", 5.9, 1.0, 1.5, 1.2, size=60, align=PP_ALIGN.CENTER)
txt(s, "IT Ticket Intelligence Agent", 1, 2.2, 11.3, 0.8,
    size=32, bold=True, color=BLUE, align=PP_ALIGN.CENTER)
txt(s, "Built in one hackathon session · Powered by AWS", 1, 3.0, 11.3, 0.4,
    size=14, color=GRAY, align=PP_ALIGN.CENTER)

links = [
    ("🌐 Live Dashboard", "http://amzn-hackthon-it-ticket-system.s3-website-us-west-2.amazonaws.com"),
    ("📐 Architecture", "...amazonaws.com/architecture.html"),
    ("🔄 Process Flow", "...amazonaws.com/process_flow.html"),
    ("💻 GitHub", "https://github.com/sksmartcoder/agent-code"),
]
for i, (label, url) in enumerate(links):
    x = 1.0 + (i % 2) * 5.6
    y = 3.8 + (i // 2) * 0.9
    b = box(s, x, y, 5.3, 0.7, fill=CARD_BG, border=BLUE)
    txt(s, label, x+0.15, y+0.08, 2.0, 0.3, size=10, bold=True, color=BLUE)
    txt(s, url, x+0.15, y+0.38, 5.0, 0.25, size=8, color=GRAY)

txt(s, "Thank you", 1, 5.9, 11.3, 0.5, size=20, bold=True, color=WHITE, align=PP_ALIGN.CENTER)

# ── Save ──────────────────────────────────────────────────────────────────────
OUT = "it-ticket-agent/IT_Ticket_Agent_Presentation.pptx"
prs.save(OUT)
print(f"✅ Saved: {OUT}")
print(f"   Slides: {len(prs.slides)}")
