#!/usr/bin/env python3
"""Post-push/CI-only validation for "merged into <ref>" commit-message claims.

check_commit_message_claims.py runs as the local commit-msg hook and, by
design, skips "merged" claims there -- a hook running at commit time cannot
know a ref's future merged state (see its check_git_state_claims()). This
script closes that gap after the push has actually happened: it re-reads the
same claims and checks, per claimed ref, whether the branch that made the
claim now has a tree-twin in that ref's history via reanchor_scan.sh -- the
same tree-twin method the rest of this repo's git tooling uses instead of
ahead/behind counts or merge-base, both meaningless after a history rewrite.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from check_commit_message_claims import MERGED_INTO_RE, _git_ref_from_match  # noqa: E402

REANCHOR_LINE_RE = re.compile(r"^\s+(\S+)\s+(NO-TWIN|NEEDS-REANCHOR|MERGED/in-main)")


def commit_messages(repo: str, rev_range: str) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", repo, "log", "--format=%B%x00", rev_range],
        capture_output=True,
        text=True,
        check=True,
    )
    return [m for m in proc.stdout.split("\0") if m.strip()]


def merged_claims(messages: list[str]) -> set[str]:
    claims: set[str] = set()
    for message in messages:
        for match in MERGED_INTO_RE.finditer(message):
            claims.add(_git_ref_from_match(match))
    return claims


def current_branch(repo: str) -> str:
    if os.environ.get("GITHUB_EVENT_NAME") == "pull_request":
        head_ref = os.environ.get("GITHUB_HEAD_REF")
        if head_ref:
            return head_ref
    env_ref = os.environ.get("GITHUB_REF_NAME")
    if env_ref and os.environ.get("GITHUB_EVENT_NAME") != "pull_request":
        return env_ref
    proc = subprocess.run(
        ["git", "-C", repo, "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def reanchor_status_for_branch(repo: str, claimed_ref: str, branch: str) -> str | None:
    """Run reanchor_scan.sh with claimed_ref as the reference; return
    branch's status token, or None if reanchor_scan.sh couldn't resolve
    claimed_ref or didn't report on branch at all."""
    proc = subprocess.run(
        ["bash", str(SCRIPT_DIR / "reanchor_scan.sh"), repo, claimed_ref, "all"],
        capture_output=True,
        text=True,
        check=False,
    )
    for line in proc.stdout.splitlines():
        match = REANCHOR_LINE_RE.match(line)
        if not match:
            continue
        ref, token = match.group(1), match.group(2)
        short = ref[len("origin/"):] if ref.startswith("origin/") else ref
        if branch in (ref, short):
            return "MERGED" if token == "MERGED/in-main" else token
    return None


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: verify_merge_claims.py <rev-range> [repo_path]", file=sys.stderr)
        return 2
    rev_range = argv[1]
    repo = argv[2] if len(argv) > 2 else "."

    claims = merged_claims(commit_messages(repo, rev_range))
    if not claims:
        print("verify_merge_claims: no 'merged into <ref>' claims in range, nothing to check")
        return 0

    branch = current_branch(repo)
    problems: list[str] = []
    for ref in sorted(claims):
        if ref in (branch, f"origin/{branch}"):
            # "merged into <this same branch>" is a no-op claim, not checkable
            # against itself -- reanchor_scan.sh only compares OTHER refs to
            # a reference, never a ref to itself.
            continue
        token = reanchor_status_for_branch(repo, ref, branch)
        if token is None:
            problems.append(
                f"merged into {ref!r}: reanchor_scan.sh could not resolve {ref!r} or "
                f"did not report a status for branch {branch!r} against it"
            )
        elif token != "MERGED":
            problems.append(
                f"merged into {ref!r}: reanchor_scan.sh reports branch {branch!r} as "
                f"{token} against {ref!r}, not merged"
            )

    if problems:
        print(
            "ERROR [merge-claim check]: commit message(s) in this range claim a merge "
            "that reanchor_scan.sh's tree-twin scan does not confirm:",
            file=sys.stderr,
        )
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print(
            "\nEither the merge claim was premature, or the target ref named in the "
            "message is wrong. This check runs post-push/in CI, not the commit-msg "
            "hook, because a hook running at commit time cannot see future repository "
            "state -- see check_git_state_claims()'s 'merged' branch in "
            "check_commit_message_claims.py for that boundary.",
            file=sys.stderr,
        )
        return 1

    print(f"verify_merge_claims: {len(claims)} merge claim(s) for branch {branch!r} confirmed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
