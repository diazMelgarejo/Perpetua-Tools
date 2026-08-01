#!/usr/bin/env python3
"""Central PR-body guard decisions for Cursor hooks (Layer 0 + fallback layers).

Layer 0 (default): Cursor agents NEVER mutate an existing PR description.
                  Use ManagePullRequest post_comment or gh pr comment only.

Human override: operator runs grant-pr-body-human-override.sh (interactive TTY).
                  Hooks then allow only append-pr-body.sh — never direct body writes.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GRANT_MARKER = "operator-grant-v1"
GRANT_TTL_SECONDS = 8 * 3600
ACK_PATH = Path.home() / ".cursor" / "pr-body-human-override-ack"

DENY_LAYER0_AGENT = (
    "LAYER-0 BLOCK: Cursor agents must NOT change PR descriptions automatically. "
    "Use ManagePullRequest post_comment or `gh pr comment` only. "
    "Authorized body edits require an operator grant and "
    "scripts/cursor/append-pr-body.sh only."
)

DENY_APPEND_ONLY = (
    "APPEND-ONLY BLOCK: PR body writes require READ→BACKUP→MERGE→WRITE via "
    "scripts/cursor/append-pr-body.sh with a full integrative merged body, "
    "never ManagePullRequest update_pr, gh pr edit, or gh api body mutations."
)

DENY_OVERRIDE_SCOPE = (
    "OVERRIDE SCOPE: operator grant permits append-pr-body.sh only — "
    "not ManagePullRequest update_pr, gh pr edit, or gh api body writes."
)


def _parse_grant_timestamp(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _human_override_active() -> bool:
    if not ACK_PATH.is_file():
        return False
    try:
        text = ACK_PATH.read_text(encoding="utf-8")
    except OSError:
        return False
    if GRANT_MARKER not in text:
        return False
    match = re.search(r"^issued-at=([^\s]+)", text, re.MULTILINE)
    if not match:
        return False
    issued = _parse_grant_timestamp(match.group(1))
    if issued is None:
        return False
    if issued.tzinfo is None:
        issued = issued.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - issued.astimezone(timezone.utc)).total_seconds()
    return 0 <= age <= GRANT_TTL_SECONDS


def _normalize_github_repo_slug(remote: str) -> str:
    repo = re.sub(
        r"^(?:https?://github\.com/|git@github\.com:|ssh://git@github\.com/)",
        "",
        remote.strip(),
    )
    if repo.endswith(".git"):
        repo = repo[:-4]
    return repo.strip("/")


def _parse_input(raw: str) -> dict[str, Any]:
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _tool_input(data: dict[str, Any]) -> dict[str, Any]:
    tool_input = (
        data.get("tool_input")
        or data.get("arguments")
        or data.get("input")
        or {}
    )
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except json.JSONDecodeError:
            tool_input = {}
    return tool_input if isinstance(tool_input, dict) else {}


def _manage_pr_decision(data: dict[str, Any]) -> tuple[str, str | None]:
    tool = str(data.get("tool_name") or data.get("toolName") or "")
    if "managepullrequest" not in tool.lower() and tool != "ManagePullRequest":
        return "ALLOW", None

    ti = _tool_input(data)
    action = str(ti.get("action") or "")

    if action == "post_comment":
        return "ALLOW", None

    if action == "update_pr" and "body" in ti:
        return "DENY", DENY_OVERRIDE_SCOPE

    if action == "create_pr" and ti.get("body") and ti.get("draft") is not False:
        return "ALLOW", None

    return "ALLOW", None


def _shell_segments(command_line: str) -> list[str]:
    segments = [part.strip() for part in re.split(r"\s*(?:&&|;|\|\|)\s*", command_line) if part.strip()]
    return segments or [command_line.strip()]


def _segment_denies_pr_body_write(segment: str) -> tuple[str, str | None]:
    seg = segment.strip()
    if not seg:
        return "ALLOW", None

    if re.search(r"\bgh\s+pr\s+comment\b", seg):
        return "ALLOW", None

    if "append-pr-body.sh" in seg:
        if not _human_override_active():
            return "DENY", DENY_LAYER0_AGENT
        return "ALLOW", None

    if re.search(r"\bgh\s+pr\s+edit\b", seg) and re.search(r"(?:--body\b|-b\b|--body-file\b)", seg):
        return "DENY", DENY_APPEND_ONLY

    if re.search(r"\bgh\s+api\b", seg):
        lowered = seg.lower()
        is_pr_mutation = any(
            token in lowered
            for token in ("pulls", "updatepullrequest", "pullrequestid", "pullrequest")
        )
        if is_pr_mutation and ("body" in lowered or "description" in lowered):
            return "DENY", DENY_APPEND_ONLY

    if re.search(r"\bManagePullRequest\b", seg, re.IGNORECASE) and re.search(
        r"\bupdate_pr\b", seg, re.IGNORECASE
    ) and re.search(r"\bbody\b", seg, re.IGNORECASE):
        return "DENY", DENY_OVERRIDE_SCOPE

    return "ALLOW", None


def _shell_decision(command_line: str) -> tuple[str, str | None]:
    cmd = command_line.strip()
    if not cmd:
        return "ALLOW", None

    for segment in _shell_segments(cmd):
        decision, msg = _segment_denies_pr_body_write(segment)
        if decision == "DENY":
            return decision, msg
    return "ALLOW", None


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "manage_pr"
    raw = sys.stdin.read()
    data = _parse_input(raw)

    if mode == "shell":
        command_line = str(data.get("command") or data.get("cmd") or "")
        decision, msg = _shell_decision(command_line)
        print(decision if not msg else f"{decision}|{msg}")
        return

    decision, msg = _manage_pr_decision(data)
    print(decision if not msg else f"{decision}|{msg}")


if __name__ == "__main__":
    main()
