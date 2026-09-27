#!/usr/bin/env python3
"""Read-only Cursor worker topology probe (Mode A / Mode B).

Reports git toplevel and board file identity for a worker-local topology
classification. Mode A means the observed checkout and board match the
orchestrator identity supplied to the probe; Mode B means they do not. This is
advisory only: it never grants queue-write authority. Never imports GossipBus
or agent coordination helpers.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from collections.abc import Sequence
from typing import Any

# Local rev-parse is diagnostic. A stalled git must not block the JSON result.
_GIT_TIMEOUT_SECONDS = 5


def _git_env() -> dict[str, str]:
    """Environment for git lookups aimed at the checkout, not a parent repo.

    ``git -C`` does not override ``GIT_DIR`` or ``GIT_WORK_TREE``. Cloud agents
    and the local worker can inherit those from the MacBook Pro Orchestrator
    session, which would classify the wrong checkout.
    """
    env = os.environ.copy()
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    return env


def _git_rev_parse(root: Path, arg: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", arg],
            capture_output=True,
            text=True,
            check=False,
            timeout=_GIT_TIMEOUT_SECONDS,
            env=_git_env(),
        )
    except subprocess.TimeoutExpired:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def probe(
    repo_root: Path,
    orchestrator_ino: int | None = None,
    orchestrator_dev: int | None = None,
    orchestrator_size: int | None = None,
) -> dict[str, Any]:
    """Classify *repo_root* topology; this result is not an authority grant."""
    root = Path(repo_root)
    root_resolved = root.resolve()
    toplevel_raw = _git_rev_parse(root, "--show-toplevel")
    git_common_dir = _git_rev_parse(root, "--git-common-dir")

    if toplevel_raw is None:
        return {
            "cwd": str(root_resolved),
            "toplevel": None,
            "git_common_dir": None,
            "board_present": False,
            "board_dev": None,
            "board_ino": None,
            "board_size": None,
            "topology_match": False,
            "queue_write_authority": False,
            "mode": "B",
        }

    toplevel = Path(toplevel_raw).resolve()
    board_path = toplevel / ".state" / "perpetua_core.db"
    board_dev: int | None = None
    board_ino: int | None = None
    board_size: int | None = None
    try:
        board_stat = board_path.stat()
    except OSError:
        board_stat = None
    board_present = board_stat is not None and stat.S_ISREG(board_stat.st_mode)
    if board_present and board_stat is not None:
        board_dev = board_stat.st_dev
        board_ino = board_stat.st_ino
        board_size = board_stat.st_size

    same_root = toplevel == root_resolved
    identity_ok = (
        orchestrator_dev is not None
        and orchestrator_ino is not None
        and orchestrator_size is not None
        and board_dev is not None
        and board_ino is not None
        and board_size is not None
        and orchestrator_dev == board_dev
        and orchestrator_ino == board_ino
        and orchestrator_size == board_size
    )
    topology_match = board_present and identity_ok and same_root
    mode = "A" if topology_match else "B"

    return {
        "cwd": str(root_resolved),
        "toplevel": str(toplevel),
        "git_common_dir": git_common_dir,
        "board_present": board_present,
        "board_dev": board_dev,
        "board_ino": board_ino,
        "board_size": board_size,
        "topology_match": topology_match,
        # Authorization remains exclusively with the orchestrator-side command.
        "queue_write_authority": False,
        "mode": mode,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: print probe JSON for the current working directory."""
    parser = argparse.ArgumentParser(
        description=(
            "Classify git and board topology (Mode A|B); never grants queue-write authority."
        )
    )
    parser.add_argument(
        "--orchestrator-ino",
        type=int,
        default=None,
        help="Expected board inode; all identity values are required for Mode A.",
    )
    parser.add_argument(
        "--orchestrator-dev",
        type=int,
        default=None,
        help="Expected board device; all identity values are required for Mode A.",
    )
    parser.add_argument(
        "--orchestrator-size",
        type=int,
        default=None,
        help="Expected board size; all identity values are required for Mode A.",
    )
    args = parser.parse_args(argv)
    payload = probe(
        Path.cwd(),
        orchestrator_ino=args.orchestrator_ino,
        orchestrator_dev=args.orchestrator_dev,
        orchestrator_size=args.orchestrator_size,
    )
    json.dump(payload, sys.stdout)
    sys.stdout.write(os.linesep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
