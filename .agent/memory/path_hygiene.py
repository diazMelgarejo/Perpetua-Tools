"""Sanitize workstation-specific paths before they enter tracked memory.

Hermes and dream-cycle outputs embed real /Users/... or C:\\Users\\... paths.
All .agent/memory writers must call these helpers at the boundary (episodic,
lessons, candidates, queue summaries) so LINT-006 is enforced at source — not
by hand-editing derived markdown after the fact.
"""
from __future__ import annotations

import re

_UNIX_HOME      = re.compile(r"/Users/([^/\s\"]+)/")
_UNIX_HOME_TAIL = re.compile(r"/Users/([^/\s\"]+)(?=[\"\'\s]|$)")
_LINUX_HOME      = re.compile(r"/home/([^/\s\"]+)/")
_LINUX_HOME_TAIL = re.compile(r"/home/([^/\s\"]+)(?=[\"\'\s]|$)")
_WIN_HOME      = re.compile(r"(?i)C:\\Users\\[^\\]+\\")
_WIN_HOME_TAIL = re.compile(r"(?i)C:\\Users\\[^\\\"\s]+")
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
