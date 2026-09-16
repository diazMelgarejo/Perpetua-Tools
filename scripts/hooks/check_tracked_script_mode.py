#!/usr/bin/env python3
"""Fail if Cursor bootstrap shell scripts are not git mode 100755.

Cloud Agents invoke these via cloud-bootstrap.sh. A 100644 git mode makes
``[[ -x ... ]]`` skip the seeder, so verify-git-guards then fails the VM
start script. This gate reads the index (what the next commit would store),
not the working-tree chmod bits.

Exit 1 lists every failing path.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(
    subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip()
)

# scripts/git paths cloud-bootstrap invokes; cursor/*.sh is enumerated from git.
BOOTSTRAP_GIT_SCRIPTS = (
    "scripts/git/neutralize-cursor-coauthor-hook.sh",
    "scripts/git/install-local-hooks.sh",
    "scripts/git/verify-git-guards.sh",
    "scripts/git/scan-tracked-banned-tokens.sh",
)

INVOKE_RE = re.compile(
    r"""\[\[\s+-(?:x|f)\s+(?:\$ROOT/)?(?P<path>scripts/(?:cursor|git)/[A-Za-z0-9._/-]+\.sh)"""
)


def index_mode(path: str) -> str | None:
    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-s", "--", path],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if not out:
        return None
    return out.split()[0]


def tracked_cursor_shell_scripts() -> list[str]:
    out = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "-z", "--", "scripts/cursor"],
        text=True,
    )
    return sorted(
        p for p in out.split("\0") if p.endswith(".sh")
    )


def invoked_from_cloud_bootstrap() -> list[str]:
    text = (ROOT / "scripts" / "cursor" / "cloud-bootstrap.sh").read_text(
        encoding="utf-8"
    )
    return sorted(set(INVOKE_RE.findall(text)))


def required_executable_paths() -> list[str]:
    paths = set(tracked_cursor_shell_scripts())
    paths.update(BOOTSTRAP_GIT_SCRIPTS)
    paths.update(invoked_from_cloud_bootstrap())
    return sorted(paths)


def main() -> int:
    problems: list[str] = []
    for path in required_executable_paths():
        mode = index_mode(path)
        if mode is None:
            problems.append(f"{path}: missing from the git index")
        elif mode != "100755":
            problems.append(
                f"{path}: git mode {mode} (need 100755; "
                f"git update-index --chmod=+x -- {path})"
            )
    for problem in problems:
        print(f"SCRIPT-MODE: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
