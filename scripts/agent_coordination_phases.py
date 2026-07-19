#!/usr/bin/env python3
"""Compatibility entrypoint for canonical phase coordination commands.

The implementation lives in orchestrator.coordination.cli. This wrapper keeps
the historical direct phase script path working while using the same GossipBus
constructor, parser, and handlers as scripts/agent_coordination.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.coordination import cli as _cli  # noqa: E402

globals().update(
    {name: getattr(_cli, name) for name in dir(_cli) if not name.startswith("__")}
)
main = _cli.main


if __name__ == "__main__":
    raise SystemExit(main())
