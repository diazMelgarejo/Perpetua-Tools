#!/usr/bin/env python3
"""Thin pointer: read the shared LM Link state (canonical watcher lives in
orama-system ``scripts/lm_link_watch.py``; both repos listen to one state file).
Exit 0 mode=linked, 1 degraded/solo, 2 down/missing — usable as a dispatch gate.
"""
import json
import sys
from pathlib import Path

STATE = Path.home() / ".openclaw" / "state" / "lm_link.json"

try:
    state = json.loads(STATE.read_text(encoding="utf-8"))
except Exception:
    print(json.dumps({"mode": "down", "error": "state file missing — run orama lm_link_watch"}))
    sys.exit(2)

print(json.dumps(state, indent=2, sort_keys=True))
sys.exit({"linked": 0}.get(state.get("mode"), 2 if state.get("mode") == "down" else 1))
