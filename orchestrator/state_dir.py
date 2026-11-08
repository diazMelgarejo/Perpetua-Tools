"""Shared runtime state-directory resolution without database dependencies."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _canonical_repo_state_dir() -> Path | None:
    """Find the shared Git-worktree state directory, or None outside Git."""
    try:
        common_dir = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"], text=True, encoding="utf-8",
            stderr=subprocess.DEVNULL, timeout=5,
        ).strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    common_path = Path(common_dir).resolve()
    state_anchor = common_path.parent if common_path.name == ".git" else common_path
    return state_anchor / ".state"


def resolve_default_state_dir() -> Path:
    """Return the configured or shared runtime state directory."""
    env_dir = os.environ.get("PT_STATE_DIR", "").strip()
    if env_dir:
        return Path(env_dir)
    return _canonical_repo_state_dir() or Path(".state")
