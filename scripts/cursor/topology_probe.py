#!/usr/bin/env python3
"""Read-only Cursor worker topology probe (Mode A / Mode B).

Reports git toplevel, board file identity, and whether this checkout may use
the shared local coordinator board (Mode A) or must stay queue-read-only
(Mode B). Never imports GossipBus or agent coordination helpers.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional


def _git_rev_parse(root: Path, arg: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", arg],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def probe(repo_root: Path, coordinator_ino: Optional[int] = None) -> dict[str, Any]:
    """Return cwd/toplevel/board identity and Mode A|B for *repo_root*."""
    root = Path(repo_root)
    toplevel = Path(_git_rev_parse(root, "--show-toplevel")).resolve()
    git_common_dir = _git_rev_parse(root, "--git-common-dir")

    board_path = toplevel / ".state" / "perpetua_core.db"
    board_present = board_path.is_file()
    board_dev: Optional[int] = None
    board_ino: Optional[int] = None
    board_size: Optional[int] = None
    if board_present:
        st = board_path.stat()
        board_dev = st.st_dev
        board_ino = st.st_ino
        board_size = st.st_size

    root_resolved = root.resolve()
    same_root = toplevel == root_resolved
    inode_ok = (
        coordinator_ino is not None
        and board_ino is not None
        and coordinator_ino == board_ino
    )
    mode = "A" if (board_present and inode_ok and same_root) else "B"

    return {
        "cwd": str(Path.cwd()),
        "toplevel": str(toplevel),
        "git_common_dir": git_common_dir,
        "board_present": board_present,
        "board_dev": board_dev,
        "board_ino": board_ino,
        "board_size": board_size,
        "mode": mode,
    }


def main(argv: Optional[list] = None) -> int:
    """CLI: print probe JSON for the current working directory."""
    parser = argparse.ArgumentParser(
        description="Probe git toplevel and shared board identity (Mode A|B)."
    )
    parser.add_argument(
        "--coordinator-ino",
        type=int,
        default=None,
        help="Expected board inode from the coordinator; required for Mode A.",
    )
    args = parser.parse_args(argv)
    payload = probe(Path.cwd(), coordinator_ino=args.coordinator_ino)
    json.dump(payload, sys.stdout)
    sys.stdout.write(os.linesep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
