#!/usr/bin/env python3
"""
VibeMon Hook for Kiro IDE
Desktop App + ESP32 (USB Serial / HTTP)
Shared transport lives in vibemon_core.py (~/.vibemon/vibemon_core.py).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Locate vibemon_core.py: repo checkout first (docs/vibemon/), then the
# installed copy (~/.vibemon/).
for _core_dir in (
    Path(__file__).resolve().parent.parent.parent / "vibemon",
    Path.home() / ".vibemon",
):
    if (_core_dir / "vibemon_core.py").is_file():
        sys.path.insert(0, str(_core_dir))
        break

try:
    import vibemon_core as core
except ImportError:
    print(
        "[vibemon] vibemon_core.py not found — re-run the installer: "
        "curl -fsSL https://docs.vibemon.io/install.py | python3",
        file=sys.stderr,
    )
    sys.exit(0)

# Character configuration
CHARACTER = "kiro"

# Event to state mapping (immutable)
EVENT_STATE_MAP: dict[str, str] = {
    "agentSpawn": "start",
    "promptSubmit": "thinking",
    "userPromptSubmit": "thinking",
    "fileCreated": "working",
    "fileDeleted": "working",
    "fileEdited": "working",
    "preToolUse": "working",
    "agentStop": "done",
    "stop": "done",
}


def build_payload(
    state: str, tool: str, project: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Build payload dict for sending to monitor. Kiro has no statusline
    cache, so model/memory are not reported."""
    return {
        "state": state,
        "tool": tool,
        "project": project,
        "model": "",
        "memory": 0,
        "character": CHARACTER,
        "terminalId": core.get_terminal_id(),
    }


if __name__ == "__main__":
    # agentSpawn is the session-start event (maps to the "start" state) —
    # auto-launch is anchored to it, matching the Claude/Codex bridges'
    # SessionStart behavior. Kiro hook registrations pass the event name as
    # the first argument (argv_event_fallback).
    core.run(
        event_state_map=EVENT_STATE_MAP,
        build_payload=build_payload,
        start_event="agentSpawn",
        argv_event_fallback=True,
    )
    sys.exit(0)
