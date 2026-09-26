#!/usr/bin/env python3
"""Read-only Cursor worker topology probe (Mode A / Mode B).

Reports git toplevel and board file identity for a worker-local topology
classification. Mode A means the observed checkout and board match the
coordinator identity supplied to the probe; Mode B means they do not. This is
advisory only: it never grants queue-write authority. Never imports GossipBus
or agent coordination helpers.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from collections.abc import Sequence
from typing import Any


def _git_rev_parse(root: Path, arg: str) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", arg],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def probe(
    repo_root: Path,
    coordinator_ino: int | None = None,
    coordinator_dev: int | None = None,
    coordinator_size: int | None = None,
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
    board_present = board_path.is_file()
    board_dev: int | None = None
    board_ino: int | None = None
    board_size: int | None = None
    if board_present:
        st = board_path.stat()
        board_dev = st.st_dev
        board_ino = st.st_ino
        board_size = st.st_size

    same_root = toplevel == root_resolved
    identity_ok = (
        coordinator_dev is not None
        and coordinator_ino is not None
        and coordinator_size is not None
        and board_dev is not None
        and board_ino is not None
        and board_size is not None
        and coordinator_dev == board_dev
        and coordinator_ino == board_ino
        and coordinator_size == board_size
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
        # Authorization remains exclusively with the coordinator-side command.
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
        "--coordinator-ino",
        type=int,
        default=None,
        help="Expected board inode; all identity values are required for Mode A.",
    )
    parser.add_argument(
        "--coordinator-dev",
        type=int,
        default=None,
        help="Expected board device; all identity values are required for Mode A.",
    )
    parser.add_argument(
        "--coordinator-size",
        type=int,
        default=None,
        help="Expected board size; all identity values are required for Mode A.",
    )
    args = parser.parse_args(argv)
    payload = probe(
        Path.cwd(),
        coordinator_ino=args.coordinator_ino,
        coordinator_dev=args.coordinator_dev,
        coordinator_size=args.coordinator_size,
    )
    json.dump(payload, sys.stdout)
    sys.stdout.write(os.linesep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
