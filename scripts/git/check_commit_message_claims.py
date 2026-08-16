#!/usr/bin/env python3
"""Verify add/register/introduce claims in a commit message against the
actual staged diff.

Catches the exact failure mode that motivated this check: writing "Added
`FOO` to bar.sh" in a commit message when the staged diff never actually
touches a line containing FOO -- e.g. editing a file's header comment while
believing (and saying) the array body itself was edited.

Heuristic, not exhaustive. It only flags a narrow, low-noise pattern: an
add/register/introduce verb within a short window of a code-symbol-looking
token (backtick-quoted, or a bare UPPER_SNAKE_CASE identifier -- the latter
because real commit messages often name constants/env-vars without
formatting them as code, which is exactly the case that first exposed this
gap). It cannot verify general prose claims; that needs real semantic
understanding this script does not have.
"""

from __future__ import annotations

import re
import subprocess
import sys

VERB_RE = r"(?:add(?:ed|s|ing)?|regist(?:er|ered|ers|ering)|introduc(?:e|ed|es|ing))"
IDENT_RE = r"[A-Za-z_][A-Za-z0-9_]{2,}"
PROXIMITY_WINDOW = 40  # chars between verb and identifier to count as "adjacent"

BACKTICK_IDENT_RE = re.compile(rf"`({IDENT_RE})`")
BARE_UPPER_IDENT_RE = re.compile(r"\b([A-Z][A-Z0-9]*(?:_[A-Z0-9]+){1,})\b")
VERB_MATCH_RE = re.compile(rf"\b{VERB_RE}\b", re.IGNORECASE)

SKIP_IDENTS = {"THE", "THIS", "THAT", "THEN", "TRUE", "FALSE", "NONE", "SELF", "TODO", "FIXME"}

GIT_REF_RE = r"[A-Za-z0-9][A-Za-z0-9._/-]{2,}"
PUSHED_TO_RE = re.compile(
    rf"\bpushed\s+to\s+(?:`({GIT_REF_RE})`|({GIT_REF_RE})(?=\s|$|[.,;:!?)]))",
    re.IGNORECASE,
)
MERGED_INTO_RE = re.compile(
    rf"\bmerged\s+into\s+(?:`({GIT_REF_RE})`|({GIT_REF_RE})(?=\s|$|[.,;:!?)]))",
    re.IGNORECASE,
)
ON_BRANCH_RE = re.compile(
    rf"\bon\s+branch\s+(?:`({GIT_REF_RE})`|({GIT_REF_RE})(?=\s|$|[.,;:!?)]))",
    re.IGNORECASE,
)


def staged_added_lines() -> str:
    proc = subprocess.run(
        ["git", "diff", "--cached", "--no-color"],
        capture_output=True,
        text=True,
        check=True,
    )
    added = []
    for line in proc.stdout.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added.append(line[1:])
    return "\n".join(added)


def commit_message_body(path: str) -> str:
    lines = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            lines.append(line)
    return "".join(lines)


def _adjacent_to_a_verb(message: str, span: tuple[int, int]) -> bool:
    start = max(0, span[0] - PROXIMITY_WINDOW)
    end = min(len(message), span[1] + PROXIMITY_WINDOW)
    window = message[start:end]
    return bool(VERB_MATCH_RE.search(window))


def find_claims(message: str) -> list[str]:
    claims: set[str] = set()
    for pattern in (BACKTICK_IDENT_RE, BARE_UPPER_IDENT_RE):
        for match in pattern.finditer(message):
            ident = match.group(1)
            if ident.upper() in SKIP_IDENTS:
                continue
            if _adjacent_to_a_verb(message, match.span()):
                claims.add(ident)
    return sorted(claims)


def _git_ref_from_match(match: re.Match[str]) -> str:
    return match.group(1) or match.group(2)


def find_git_state_claims(message: str) -> list[tuple[str, str]]:
    """Return (claim_kind, ref) pairs for git-state phrases in *message*."""
    claims: list[tuple[str, str]] = []
    for pattern, kind in (
        (PUSHED_TO_RE, "pushed"),
        (MERGED_INTO_RE, "merged"),
        (ON_BRANCH_RE, "branch"),
    ):
        for match in pattern.finditer(message):
            claims.append((kind, _git_ref_from_match(match)))
    return claims


def _git_quiet(args: list[str]) -> bool:
    proc = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def _remote_tracking_ref_exists(ref: str) -> bool:
    candidates = [f"refs/remotes/{ref}"]
    if not ref.startswith("origin/"):
        candidates.append(f"refs/remotes/origin/{ref}")
    return any(_git_quiet(["show-ref", "--verify", "--quiet", cand]) for cand in candidates)


def _ref_resolves(ref: str) -> bool:
    return _git_quiet(["rev-parse", "--verify", "--quiet", ref])


def _current_branch() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def verify_git_state_claims(claims: list[tuple[str, str]]) -> list[str]:
    """Return human-readable problems for claims that do not match git state."""
    problems: list[str] = []
    for kind, ref in claims:
        if kind == "pushed":
            if not _remote_tracking_ref_exists(ref):
                problems.append(
                    f"pushed to {ref!r}: no remote-tracking ref "
                    f"(tried refs/remotes/{ref}"
                    + (
                        f" and refs/remotes/origin/{ref}"
                        if not ref.startswith("origin/")
                        else ""
                    )
                    + ")"
                )
        elif kind == "merged":
            # A commit-msg/pre-commit hook cannot prove a future pushed/merged
            # state, and ancestry checks are explicitly unreliable after the
            # repo's history rewrites. Leave merge-state validation to
            # post-push/CI flows that can classify refs with reanchor_scan.sh.
            continue
        elif kind == "branch":
            current = _current_branch()
            if current != ref:
                problems.append(
                    f"on branch {ref!r}: current branch is {current!r}, not {ref!r}"
                )
    return problems


def check_git_state_claims(message: str) -> list[str]:
    claims = find_git_state_claims(message)
    if not claims:
        return []
    return verify_git_state_claims(claims)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: check_commit_message_claims.py <commit-msg-file>", file=sys.stderr)
        return 2
    message = commit_message_body(argv[1])

    exit_code = 0

    claims = find_claims(message)
    if claims:
        added_text = staged_added_lines()
        missing = [c for c in claims if c not in added_text]
        if missing:
            exit_code = 1
            print(
                "ERROR [identifier-claim check]: commit message claims an "
                "add/register/introduce action for a\n"
                "symbol that does not appear in any added line of the staged diff:",
                file=sys.stderr,
            )
            for ident in missing:
                print(f"  - {ident}", file=sys.stderr)
            print(
                "\nIf this is accurate (e.g. the symbol already existed and this message\n"
                "only references it, not adds it), reword to drop the add/register/\n"
                "introduce verb from next to that name. If it's a real miss, fix the\n"
                "diff before committing -- this check exists to catch exactly that.",
                file=sys.stderr,
            )

    git_problems = check_git_state_claims(message)
    if git_problems:
        exit_code = 1
        print(
            "ERROR [git-state-claim check]: commit message asserts git state "
            "that does not match the repository:",
            file=sys.stderr,
        )
        for problem in git_problems:
            print(f"  - {problem}", file=sys.stderr)
        print(
            "\nReword the message to match actual git state, or perform the "
            "push/merge/checkout before claiming it.",
            file=sys.stderr,
        )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
