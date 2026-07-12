#!/usr/bin/env python3
"""Legacy compatibility entrypoint for agent coordination.

The maintained implementation lives in ``scripts.agent_coordination_core`` and
is exposed through ``scripts.agent_coordination``. Importing or executing this
legacy path now delegates to that facade, so heartbeat and queue handlers are
always the corrected implementations rather than unresolved injected globals.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts import agent_coordination as _facade

for _name, _value in vars(_facade).items():
    if not _name.startswith("__"):
        globals()[_name] = _value

main = _facade.main

if __name__ == "__main__":
    raise SystemExit(main())
