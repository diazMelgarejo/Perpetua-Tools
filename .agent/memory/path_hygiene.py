"""Sanitize workstation-specific paths before they enter tracked memory.

Hermes and dream-cycle outputs embed real /Users/... or C:\\Users\\... paths.
All .agent/memory writers must call these helpers at the boundary (episodic,
lessons, candidates, queue summaries) so LINT-006 is enforced at source — not
by hand-editing derived markdown after the fact.
"""
from __future__ import annotations

import re

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


def sanitize_tracked_path_leaks(text: str) -> str:
    """Replace workstation home prefixes with portable anchors."""
    if not text:
        return text
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
