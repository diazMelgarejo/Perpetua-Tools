#!/usr/bin/env python3
"""Reject byte rewrites of the tracked episodic JSONL at a pinned Git boundary."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any

LOG_PATH = ".agent/memory/episodic/AGENT_LEARNINGS.jsonl"


class IntegrityError(ValueError):
    """A missing object, changed prefix, or invalid record blocks publication."""


def git_bytes(repo: Path, *args: str) -> bytes:
    """Run Git without a shell and fail closed without printing memory content."""
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=False
    )
    if result.returncode:
        raise IntegrityError("Git object/ref lookup failed; fetch the exact revisions")
    return result.stdout


def resolve_commit(repo: Path, revision: str) -> str:
    """Resolve an option-safe commit identity once before reading its tree."""
    return git_bytes(
        repo, "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}"
    ).decode("ascii").strip()


def committed_log(repo: Path, commit: str, *, required: bool) -> bytes:
    """Read a regular non-executable blob, allowing an absent initial base only."""
    entry = git_bytes(repo, "ls-tree", "-z", commit, "--", LOG_PATH)
    if not entry:
        if required:
            raise IntegrityError("head memory file is missing")
        return b""
    metadata, path = entry.rstrip(b"\0").split(b"\t", 1)
    mode, kind, oid = metadata.split()
    if path != LOG_PATH.encode() or kind != b"blob" or mode != b"100644":
        raise IntegrityError("memory must be a regular blob with mode 100644")
    return git_bytes(repo, "cat-file", "blob", oid.decode("ascii"))


def working_log(repo: Path) -> bytes:
    """Read bytes directly, rejecting symlinks and executable worktree files."""
    path = repo / LOG_PATH
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise IntegrityError("worktree memory file is missing") from exc
    if not stat.S_ISREG(mode):
        raise IntegrityError("memory must be a regular file")
    if mode & 0o111:
        raise IntegrityError("memory file mode must not be executable")
    return path.read_bytes()


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate JSON keys rather than silently keeping the last value."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    """Reject nonstandard JSON constants such as NaN and Infinity."""
    raise ValueError("non-finite constant")


def record_count(data: bytes, *, historical: bool = False) -> int:
    """Validate complete object records without normalizing any source bytes."""
    if not data:
        return 0
    if not data.endswith(b"\n"):
        raise IntegrityError("record stream lacks its final LF")
    rows = data[:-1].split(b"\n")
    for number, raw in enumerate(rows, 1):
        try:
            # Historical records are preserved under their existing schema.
            # New records additionally reject ambiguous duplicate/non-finite fields.
            options: dict[str, Any] = {} if historical else {
                "object_pairs_hook": unique_object, "parse_constant": reject_constant
            }
            value = json.loads(raw.decode("utf-8"), **options)
            if not isinstance(value, dict):
                raise ValueError("not an object")
        except (UnicodeError, ValueError, RecursionError) as exc:
            raise IntegrityError(f"invalid record at relative line {number}") from exc
    return len(rows)


def verify(base: bytes, head: bytes) -> dict[str, int | str]:
    """Require the base bytes as an exact prefix before validating new records."""
    if not head.startswith(base):
        offset = next(
            (i for i, (old, new) in enumerate(zip(base, head)) if old != new),
            min(len(base), len(head)),
        )
        line = base[:offset].count(b"\n") + 1
        raise IntegrityError(f"historical byte prefix changed at line {line}")
    base_records = record_count(base, historical=True)
    appended_records = record_count(head[len(base):])
    return {
        "base_records": base_records,
        "appended_records": appended_records,
        "head_records": base_records + appended_records,
        "base_bytes": len(base),
        "head_bytes": len(head),
        "base_sha256": hashlib.sha256(base).hexdigest(),
        "head_sha256": hashlib.sha256(head).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    """Check explicit immutable revisions or a deliberately selected worktree."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--base", required=True)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--head")
    target.add_argument("--worktree", action="store_true")
    args = parser.parse_args(argv)
    try:
        base_sha = resolve_commit(args.repo, args.base)
        base = committed_log(args.repo, base_sha, required=False)
        if args.worktree:
            head_sha = "worktree"
            head = working_log(args.repo)
        else:
            head_sha = resolve_commit(args.repo, args.head)
            head = committed_log(args.repo, head_sha, required=True)
        report = verify(base, head)
        report.update(base_commit=base_sha, head_commit=head_sha)
        print(json.dumps(report, sort_keys=True))
    except (IntegrityError, OSError, UnicodeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
