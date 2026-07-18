"""Sanitize workstation-specific paths before they enter tracked memory.

Hermes and dream-cycle outputs embed real /Users/... or C:\\Users\\... paths.
All .agent/memory writers must call these helpers at the boundary (episodic,
lessons, candidates, queue summaries) so LINT-006 is enforced at source — not
by hand-editing derived markdown after the fact.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# The username/segment character class excludes not just `/`, whitespace,
# and quotes, but also common sentence punctuation ( ) , . ; : ! ? — a
# TAIL pattern's lookahead only requires a quote/whitespace/EOF to stop,
# so without this the greedy capture swallows trailing punctuation as if
# it were part of the path, corrupting the surrounding sentence. Confirmed
# 2026-07-08 against a lesson quoting an absolute Windows/Unix path pair
# in prose as an illustrative example: the closing paren and comma right
# after the path got silently absorbed into the "sanitized" replacement,
# leaving a run-on sentence. A real username never legitimately contains
# any of these characters, so excluding them is a pure precision gain —
# see the reproduction and full before/after in Perpetua-Tools commit
# 36cc9d18 (manual revert) and the fix commit that follows it.
_SEG      = r"[^/\\\s\"'(),.;:!?]+"
_WIN_SEG  = r"[^\\\"'(),.;:!?\s]+"
_UNIX_HOME      = re.compile(r"/Users/(" + _SEG + r")/")
_UNIX_HOME_TAIL = re.compile(r"/Users/(" + _SEG + r")(?=[\"\'\s]|$)")
_LINUX_HOME      = re.compile(r"/home/(" + _SEG + r")/")
_LINUX_HOME_TAIL = re.compile(r"/home/(" + _SEG + r")(?=[\"\'\s]|$)")
_WIN_HOME      = re.compile(r"(?i)C:\\Users\\" + _WIN_SEG + r"\\")
_WIN_HOME_TAIL = re.compile(r"(?i)C:\\Users\\" + _WIN_SEG)
# Workspace-tree doxxing: even after home→%USERPROFILE% substitution, Downloads/SKILLS.md
# layout must not persist in tracked memory (LINT-006 antipattern).
_WORKSPACE_DOXX_WIN = re.compile(
    r"(?i)%USERPROFILE%\\Downloads\\SKILLS\.md\\u?l?trathink(?:\\[^\\\"\s]*)?"
)
_WORKSPACE_DOXX_UNIX = re.compile(
    r"(?i)\$HOME/Downloads/SKILLS\.md/u?l?trathink(?:/[^\s\"']*)?"
)
_WORKSPACE_ROOT = "<workspace-root>"

REVIEW_QUEUE_DYNAMIC_MARKER = "<!-- review-queue-dynamic -->"


def _openclaw_workspace_root(start: Path | None = None) -> Path:
    """Walk upward from `start` (default: this file's location) looking for
    the OpenClaw workspace root (a directory that contains an orama-system
    checkout as a sibling). Same discovery rule as
    scripts/review/repo_hygiene.py's openclaw_workspace_root -- kept as an
    independent, minimal implementation here (not imported) since this
    module lives under .agent/memory/ and repo_hygiene.py under
    scripts/review/, in different subtrees that may be invoked from
    different working directories; duplicating this ~6-line walk is safer
    than a fragile cross-package import. Keep these two in sync if the
    discovery rule ever changes.
    """
    cur = (start or Path(__file__)).resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / "orama-system").is_dir():
            return candidate
    return cur.parents[2] if len(cur.parents) >= 3 else cur


def _private_literal_values(key: str) -> list[str]:
    """Read configured private literal values for `key` (owner_gmail,
    owner_name, forbidden_attribution) from the local-only verboten-literals
    file. Never returns anything if the file is absent -- this is by design
    a local-machine-only source, never a tracked one. Mirrors
    scripts/review/repo_hygiene.py::private_literal_values.
    """
    configured_path = os.getenv("OPENCLAW_VERBOTEN_LITERALS")
    path = Path(configured_path) if configured_path else _openclaw_workspace_root() / ".verboten-literals.local"
    if not path.is_file():
        return []
    values: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for raw in lines:
        raw = raw.split("#", 1)[0].strip()
        if not raw or "=" not in raw:
            continue
        raw_key, value = raw.split("=", 1)
        if raw_key.strip() != key:
            continue
        value = "".join(value.split())
        if value:
            values.append(value)
    return values


def sanitize_private_identity_leaks(text: str) -> str:
    """Redact configured private owner-identity / forbidden-attribution
    literals from text before it enters tracked memory.

    Symmetric with sanitize_tracked_path_leaks: this is the identity-literal
    equivalent, closing the gap that let a real email land in
    lessons.jsonl (superseded lesson_23e51efcde2f -> lesson_c3b24dc506a6)
    because learn.py only scrubbed paths, never identity literals, at
    staging time -- the leak was only caught downstream by the pre-commit
    hygiene gate, after it had already been committed once. Catching it
    HERE, at the point the text is first written into a candidate, means
    the same class of leak can no longer reach lessons.jsonl at all.
    """
    if not text:
        return text
    for key, label in (
        ("owner_gmail", "<owner Gmail identity>"),
        ("owner_name", "<owner identity>"),
        ("forbidden_attribution", "<forbidden attribution>"),
    ):
        for value in _private_literal_values(key):
            if not value:
                continue
            text = re.sub(re.escape(value), label, text, flags=re.IGNORECASE)
    return text


def sanitize_tracked_path_leaks(text: str) -> str:
    """Replace workstation home prefixes with portable anchors, and redact
    any configured private identity literals. The two scrubs are chained
    here (not left as two separate calls at each call site) so every
    existing caller of this function automatically gets identity scrubbing
    too, without needing to be updated individually.
    """
    if not text:
        return text
    text = sanitize_private_identity_leaks(text)
    text = _UNIX_HOME.sub("$HOME/", text)
    text = _UNIX_HOME_TAIL.sub("$HOME", text)  # no trailing slash — end-of-string / before whitespace
    text = _LINUX_HOME.sub("$HOME/", text)
    text = _LINUX_HOME_TAIL.sub("$HOME", text)  # same for Linux /home/user
    text = _WIN_HOME.sub(lambda _m: "%USERPROFILE%\\", text)
    text = _WIN_HOME_TAIL.sub("%USERPROFILE%", text)
    text = _WORKSPACE_DOXX_WIN.sub(_WORKSPACE_ROOT, text)
    text = _WORKSPACE_DOXX_UNIX.sub(_WORKSPACE_ROOT, text)
    return text


def sanitize_json_strings(obj):
    """Recursively sanitize string fields in JSON-serializable structures."""
    if isinstance(obj, str):
        return sanitize_tracked_path_leaks(obj)
    if isinstance(obj, dict):
        return {k: sanitize_json_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_json_strings(v) for v in obj]
    return obj
