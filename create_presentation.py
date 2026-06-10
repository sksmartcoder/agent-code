#!/usr/bin/env python3
"""Generate clean executive presentation with Aflac branding."""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

# Aflac colors
AFLAC_BLUE = RGBColor(0x00, 0x3B, 0x71)
AFLAC_LIGHT = RGBColor(0x00, 0xA4, 0xE4)
BLACK = RGBColor(0x1A, 0x1A, 0x1A)
GRAY = RGBColor(0x55, 0x55, 0x55)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

LOGO_PATH = "aflac_logo.png"

prs = Presentation()
prs.slide_width = Inches(13.33)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


def add_slide():
    s = prs.slides.add_slide(BLANK)
    # White background (default)
    # Add Aflac logo footer
    s.shapes.add_picture(LOGO_PATH, Inches(5.75), Inches(6.8), height=Inches(0.5))
    return s


def title_text(s, text, y=0.4, size=28, color=AFLAC_BLUE):
    tb = s.shapes.add_textbox(Inches(0.8), Inches(y), Inches(11.5), Inches(1))
    p = tb.text_frame.paragraphs[0]
    p.text = text
    p.font.size = Pt(size)
    p.font.bold = True
    p.font.color.rgb = color


def bullets(s, items, y=1.5, size=18, color=BLACK):
    tb = s.shapes.add_textbox(Inches(1.0), Inches(y), Inches(11), Inches(5))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = item
        p.font.size = Pt(size)
        p.font.color.rgb = color
        p.space_after = Pt(14)


def subtitle(s, text, y=1.0):
    tb = s.shapes.add_textbox(Inches(0.8), Inches(y), Inches(11.5), Inches(0.6))
    p = tb.text_frame.paragraphs[0]
    p.text = text
    p.font.size = Pt(14)
    p.font.color.rgb = GRAY


# ── SLIDE 1: Title ──
s = add_slide()
tb = s.shapes.add_textbox(Inches(1), Inches(2.2), Inches(11.3), Inches(1.2))
p = tb.text_frame.paragraphs[0]
p.text = "🦆 IT Ticket Intelligence Agent"
p.font.size = Pt(40)
p.font.bold = True
p.font.color.rgb = AFLAC_BLUE
p.alignment = PP_ALIGN.CENTER

tb2 = s.shapes.add_textbox(Inches(1), Inches(3.5), Inches(11.3), Inches(0.6))
p2 = tb2.text_frame.paragraphs[0]
p2.text = "AI-Powered IT Support Triage · Auto-Resolution · Human-in-the-Loop"
p2.font.size = Pt(18)
p2.font.color.rgb = GRAY
p2.alignment = PP_ALIGN.CENTER

tb3 = s.shapes.add_textbox(Inches(1), Inches(4.5), Inches(11.3), Inches(0.6))
p3 = tb3.text_frame.paragraphs[0]
p3.text = "Aflac  ·  AWS Hackathon 2026"
p3.font.size = Pt(14)
p3.font.color.rgb = AFLAC_LIGHT
p3.alignment = PP_ALIGN.CENTER

# ── SLIDE 2: The Problem ──
s = add_slide()
title_text(s, "The Problem")
bullets(s, [
    "• Engineers spend 2–4 hours diagnosing issues already solved last week",
    "• No institutional memory — every incident starts from scratch",
    "• Tickets land with the wrong team, causing delays",
    "• No audit trail of what was tried or what worked",
    "• 80% of IT tickets are recurring patterns",
    "",
    "→ Slow resolution · Frustrated teams · Repeated mistakes",
])

# ── SLIDE 3: Our Solution ──
s = add_slide()
title_text(s, "Our Solution")
subtitle(s, "An AI agent that reads, classifies, remembers, and resolves IT tickets")
bullets(s, [
    "• Understands natural language tickets instantly",
    "• Classifies by category (CI/CD, Data, Infra, IAM, Network) and severity",
    "• Checks pattern memory — detects if issue was solved before",
    "• Routes to the right specialist AI agent automatically",
    "• Suggests proven fixes for recurring issues",
    "• Human approves every fix before it's applied",
    "• Learns from every resolution — gets smarter over time",
], y=1.6)

# ── SLIDE 4: Business Value ──
s = add_slide()
title_text(s, "Business Value")
bullets(s, [
    "⚡  Recurring issues resolved in seconds (was 30–60 min)",
    "🎯  5 specialist domains: CI/CD, Data/ETL, Infra, IAM, Network",
    "🧠  Self-learning — improves with every resolved ticket",
    "👤  Human-in-the-loop — operator approves every fix",
    "📊  Full audit trail — every decision logged and traceable",
    "🔒  Compliance ready — no auto-apply without approval",
])

# ── SLIDE 5: How It Works ──
s = add_slide()
title_text(s, "How It Works")
bullets(s, [
    "1.  Ticket submitted → AI reads and classifies instantly",
    "2.  Pattern memory checked → known issue? suggest proven fix",
    "3.  New issue? → specialist agent investigates",
    "4.  Agent provides remediation steps + confidence score",
    "5.  Human operator reviews and approves",
    "6.  Resolution saved → system learns for next time",
])

# ── SLIDE 6: Architecture (Technical) ──
s = add_slide()
title_text(s, "Architecture")
subtitle(s, "Technical Overview")
bullets(s, [
    "• Entry: S3 Static Dashboard → Lambda API → AgentCore Runtime",
    "",
    "• Master Agent (Strands SDK + Bedrock Nova Lite)",
    "    → Classifies ticket → Matches patterns → Routes to specialist",
    "",
    "• Specialist Sub-Agents:",
    "    CI/CD · Data/ETL · Infrastructure · Access/IAM · Network",
    "",
    "• Agent Message Bus — agents collaborate and share context",
    "",
    "• AWS Services: Bedrock, Lambda, S3, AgentCore, CloudWatch, Glue, DynamoDB",
], y=1.6, size=16)

# ── SLIDE 7: Demo Scenarios ──
s = add_slide()
title_text(s, "Live Demo Scenarios")
bullets(s, [
    "🔧  CI/CD — Pipeline failed, ECS OOM → RECURRING, 88% match, fix in seconds",
    "🗄  Data/ETL — Glue job timeout → NEW, auto Glue job re-trigger",
    "🖥  Infrastructure — EC2 unreachable, disk 98% → NEW, P1 Critical",
    "🔑  Access/IAM — Lambda can't write to S3 → Permission fix suggested",
    "🌐  Network — API Gateway 503, health checks failing → SG fix",
])

# ── SLIDE 8: Key Learnings ──
s = add_slide()
title_text(s, "Key Learnings")
bullets(s, [
    "What worked well:",
    "  • Amazon Nova Lite — fast, accurate, no legacy issues",
    "  • S3 static site + Lambda — zero config, shareable URL instantly",
    "  • Agent Message Bus — clean tracing of agent interactions",
    "",
    "Challenges overcome:",
    "  • Switched from Claude (legacy) to Nova on day 1",
    "  • AgentCore 30s cold start — optimized with in-memory patterns",
    "  • Lambda Function URL restrictions — used S3 static hosting",
], size=16)

# ── SLIDE 9: What's Next ──
s = add_slide()
title_text(s, "What's Next")
subtitle(s, "Roadmap to production")
bullets(s, [
    "• Real DynamoDB — persistent ticket history and pattern learning",
    "• Slack / Email alerts — notify on-call for P1 tickets",
    "• Analytics dashboard — track MTTR, patterns, agent performance",
    "• Real Glue integration — actual ETL auto-remediation",
    "• API Gateway — integrate with ServiceNow, Jira, PagerDuty",
], y=1.6)

# ── SLIDE 10: Thank You ──
s = add_slide()
tb = s.shapes.add_textbox(Inches(1), Inches(2.5), Inches(11.3), Inches(1))
p = tb.text_frame.paragraphs[0]
p.text = "🦆 Thank You"
p.font.size = Pt(36)
p.font.bold = True
p.font.color.rgb = AFLAC_BLUE
p.alignment = PP_ALIGN.CENTER

tb2 = s.shapes.add_textbox(Inches(1), Inches(3.8), Inches(11.3), Inches(2))
tf = tb2.text_frame
tf.word_wrap = True
lines = [
    "Dashboard: http://amzn-hackthon-it-ticket-system.s3-website-us-west-2.amazonaws.com",
    "GitHub: https://github.com/sksmartcoder/agent-code",
    "",
    "Built with: Amazon Bedrock · Strands SDK · AgentCore · Lambda · S3",
]
for i, line in enumerate(lines):
    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    p.text = line
    p.font.size = Pt(14)
    p.font.color.rgb = GRAY
    p.alignment = PP_ALIGN.CENTER

# ── Save ──
OUT = "IT_Ticket_Agent_Presentation_Aflac.pptx"
prs.save(OUT)
print(f"✅ Saved: {OUT}")
print(f"   Slides: {len(prs.slides)}")
