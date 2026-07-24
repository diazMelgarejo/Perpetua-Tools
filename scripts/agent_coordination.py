#!/usr/bin/env python3
"""Compatibility entrypoint for the canonical coordination CLI.

The implementation lives in orchestrator.coordination.cli. This wrapper keeps
the historical script path and import surface working without carrying a
second copy of the coordination board.
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
