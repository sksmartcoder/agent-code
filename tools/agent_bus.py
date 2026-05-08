"""
Agent Message Bus — structured agent-to-agent communication.

Agents send typed messages to each other via the bus.
The bus logs every message with sender, receiver, type, and payload.
Sub-agents can request help from peer agents (e.g. DataETL asks Infra
about disk space when a Glue job fails due to storage issues).
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from tools.tracer import log

# ANSI
R="\033[0m"; B="\033[1m"; DIM="\033[2m"
CY="\033[96m"; GR="\033[92m"; YL="\033[93m"; MG="\033[95m"; BL="\033[94m"

AGENT_ICONS = {
    "MasterAgent":    "🎯",
    "CICDAgent":      "🔧",
    "DataETLAgent":   "🗄 ",
    "InfraAgent":     "🖥 ",
    "AccessIAMAgent": "🔑",
    "NetworkAgent":   "🌐",
    "Classifier":     "🤖",
    "PatternMatcher": "🔍",
    "KnowledgeBase":  "📚",
}


@dataclass
class AgentMessage:
    sender:    str
    receiver:  str
    msg_type:  str          # REQUEST | RESPONSE | NOTIFY | ESCALATE
    content:   dict
    msg_id:    str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    reply_to:  str = None   # msg_id this is replying to
    ts:        str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3])


class AgentBus:
    """
    Central message bus. Agents register handlers and send messages.
    All messages are printed and traced.
    """

    def __init__(self):
        self._handlers: dict[str, Any] = {}   # agent_name → agent instance
        self._history:  list[AgentMessage] = []

    def register(self, name: str, agent: Any):
        self._handlers[name] = agent

    def send(self, msg: AgentMessage) -> AgentMessage | None:
        """Send a message and return the response (if any)."""
        self._history.append(msg)
        self._print_message(msg)
        log(msg.sender, f"MSG_{msg.msg_type}",
            f"→ {msg.receiver}  content={str(msg.content)[:60]}", "INFO")

        receiver = self._handlers.get(msg.receiver)
        if receiver and hasattr(receiver, "on_message"):
            response = receiver.on_message(msg)
            if response:
                self._history.append(response)
                self._print_message(response)
                log(response.sender, f"MSG_{response.msg_type}",
                    f"→ {response.receiver}  content={str(response.content)[:60]}", "DONE")
            return response
        return None

    def _print_message(self, msg: AgentMessage):
        s_icon = AGENT_ICONS.get(msg.sender,   "·")
        r_icon = AGENT_ICONS.get(msg.receiver, "·")
        type_col = {
            "REQUEST":  CY, "RESPONSE": GR,
            "NOTIFY":   BL, "ESCALATE": YL,
        }.get(msg.msg_type, DIM)

        print(f"  {DIM}{msg.ts}{R}  "
              f"{s_icon} {B}{msg.sender}{R}  "
              f"{type_col}──{msg.msg_type}──▶{R}  "
              f"{r_icon} {B}{msg.receiver}{R}  "
              f"{DIM}[{msg.msg_id}]{R}")

        # Print key content fields
        for k, v in msg.content.items():
            if k not in ("ticket_id",):
                print(f"  {DIM}  {k}: {str(v)[:80]}{R}")

    def get_history(self) -> list[AgentMessage]:
        return list(self._history)

    def print_conversation(self):
        """Print the full agent conversation for demo/debug."""
        print(f"\n{MG}{'═'*60}{R}")
        print(f"{MG}  AGENT CONVERSATION LOG ({len(self._history)} messages){R}")
        print(f"{MG}{'═'*60}{R}")
        for msg in self._history:
            s_icon = AGENT_ICONS.get(msg.sender, "·")
            r_icon = AGENT_ICONS.get(msg.receiver, "·")
            print(f"  {DIM}{msg.ts}{R}  {s_icon}→{r_icon}  "
                  f"{B}{msg.sender}{R} → {B}{msg.receiver}{R}  "
                  f"[{msg.msg_type}]  {DIM}{str(msg.content)[:60]}{R}")
        print(f"{MG}{'═'*60}{R}\n")


# Global bus instance
bus = AgentBus()
