"""
Agent Tracer — structured trace log for every agent step.
Prints to console AND writes to /tmp/agent_trace.jsonl for inspection.
"""
from __future__ import annotations
import json, time, os
from datetime import datetime, timezone

R="\033[0m"; B="\033[1m"; DIM="\033[2m"
CY="\033[96m"; GR="\033[92m"; YL="\033[93m"; RD="\033[91m"; BL="\033[94m"; MG="\033[95m"

TRACE_FILE = "/tmp/agent_trace.jsonl"

AGENT_COLORS = {
    "MasterAgent":   CY,
    "Classifier":    BL,
    "PatternMatcher":MG,
    "DataETLAgent":  YL,
    "CICDAgent":     BL,
    "InfraAgent":    GR,
    "AccessIAMAgent":YL,
    "NetworkAgent":  RD,
    "GlueRemediation":GR,
    "KnowledgeBase": MG,
}

_trace_id = None
_step_times = {}

def start_trace(ticket_id: str, description: str):
    global _trace_id
    _trace_id = ticket_id[:8]
    _step_times.clear()
    _write({"event": "TRACE_START", "ticket_id": ticket_id,
            "description": description[:100]})
    print(f"\n  {DIM}{'─'*56}{R}")
    print(f"  {DIM}TRACE ID: {_trace_id}  |  {_ts()}{R}")
    print(f"  {DIM}{'─'*56}{R}")

def log(agent: str, action: str, detail: str = "", status: str = "INFO",
        inputs: dict = None, outputs: dict = None):
    color = AGENT_COLORS.get(agent, CY)
    status_sym = {"INFO":"·","START":"▶","DONE":"✓","ERROR":"✗","WARN":"⚠"}.get(status, "·")
    status_col = {"DONE":GR,"ERROR":RD,"WARN":YL,"START":CY}.get(status, DIM)

    ts = _ts()
    key = f"{agent}:{action}"

    if status == "START":
        _step_times[key] = time.time()
        elapsed = ""
    elif key in _step_times:
        elapsed = f"  {DIM}+{(time.time()-_step_times[key])*1000:.0f}ms{R}"
    else:
        elapsed = ""

    print(f"  {DIM}{ts}{R}  {color}{B}[{agent}]{R}  "
          f"{status_col}{status_sym} {action}{R}"
          f"{('  ' + DIM + detail + R) if detail else ''}{elapsed}")

    _write({"ts": ts, "agent": agent, "action": action, "status": status,
            "detail": detail, "inputs": inputs, "outputs": outputs})

def end_trace(final_status: str, ticket_id: str):
    color = GR if final_status == "RESOLVED" else RD
    print(f"  {DIM}{'─'*56}{R}")
    print(f"  {color}{B}TRACE END → {final_status}{R}  "
          f"{DIM}ticket:{ticket_id[:8]}  log:{TRACE_FILE}{R}")
    print(f"  {DIM}{'─'*56}{R}")
    _write({"event": "TRACE_END", "final_status": final_status, "ticket_id": ticket_id})

def _ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]

def _write(data: dict):
    try:
        with open(TRACE_FILE, "a") as f:
            f.write(json.dumps({**data, "_trace_id": _trace_id}) + "\n")
    except Exception:
        pass

def print_trace_log():
    """Print the full trace log — call after a run to inspect."""
    if not os.path.exists(TRACE_FILE):
        print("No trace log found.")
        return
    print(f"\n{CY}{'═'*60}{R}")
    print(f"{CY}  FULL TRACE LOG — {TRACE_FILE}{R}")
    print(f"{CY}{'═'*60}{R}")
    with open(TRACE_FILE) as f:
        for line in f:
            try:
                d = json.loads(line)
                agent = d.get("agent","")
                color = AGENT_COLORS.get(agent, DIM)
                print(f"  {DIM}{d.get('ts','')}{R}  {color}[{agent}]{R}  "
                      f"{d.get('action','')}  {DIM}{d.get('detail','')}{R}")
            except Exception:
                pass
    print(f"{CY}{'═'*60}{R}\n")
