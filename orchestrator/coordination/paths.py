"""Path and worktree helpers for the coordination package."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from orchestrator.gossip_bus import (  # noqa: E402
    resolve_gossip_db_path,
)


def canonical_db_path() -> str:
    """Return the canonical GossipBus DB path for this repo."""
    return resolve_gossip_db_path()


def current_worktree_label() -> str:
    """Human-readable identifier for the calling worktree (branch + cwd)."""
    try:
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"], text=True
        ).strip()
    except (subprocess.CalledProcessError, OSError):
        # OSError covers FileNotFoundError (git not on PATH) and other
        # exec-level failures -- worktree labeling must never crash an
        # emit path just because git itself is unavailable or unexecutable.
        branch = "?"
    return f"{branch}@{Path.cwd()}"
