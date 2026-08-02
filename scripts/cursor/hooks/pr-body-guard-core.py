#!/usr/bin/env python3
"""Central PR-body guard decisions for Cursor hooks (Layer 0 + fallback layers).

Layer 0 (default): Cursor agents NEVER mutate an existing PR description.
                  Use ManagePullRequest post_comment or gh pr comment only.

Human override: operator mints operator-grant-v2 (HMAC + digest binding).
                  Hooks then allow only append-pr-body.sh with matching grant.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
GRANT_LIB_PATH = SCRIPT_DIR.parent / "pr-body-grant-lib.py"

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


def _load_grant_lib():
    spec = importlib.util.spec_from_file_location("pr_body_grant_lib", GRANT_LIB_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load grant lib at {GRANT_LIB_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_grant_lib = _load_grant_lib()


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
    segments = [
        part.strip()
        for part in re.split(r"\s*(?:&&|;|\|\||\n)\s*", command_line)
        if part.strip()
    ]
    return segments or [command_line.strip()]


def _segment_inspect(segment: str) -> tuple[str, str | None, list[str]]:
    seg = segment.strip()
    if not seg:
        return "ALLOW", None, []

    if re.search(r"\bgh\s+pr\s+comment\b", seg):
        return "ALLOW", None, []

    if "append-pr-body.sh" in seg:
        parsed = _grant_lib.parse_append_segment(seg)
        if parsed is None:
            return "DENY", (
                "append-pr-body.sh requires --file or --message in the same command"
            ), []
        repo, pr, file_path, message = parsed
        ok, err = _grant_lib.verify_grant_for_append(
            repo,
            pr,
            file_path,
            message,
            consume=False,
        )
        if not ok:
            return "DENY", err or DENY_LAYER0_AGENT, []
        return "ALLOW", None, [f"BACKUP|{repo}|{pr}"]

    if re.search(r"\bgh\s+pr\s+edit\b", seg) and re.search(
        r"(?:--body\b|-b\b|--body-file\b)", seg
    ):
        return "DENY", DENY_APPEND_ONLY, []

    if re.search(r"\bgh\s+api\b", seg):
        lowered = seg.lower()
        is_pr_mutation = any(
            token in lowered
            for token in ("pulls", "updatepullrequest", "pullrequestid", "pullrequest")
        )
        if is_pr_mutation and ("body" in lowered or "description" in lowered):
            return "DENY", DENY_APPEND_ONLY, []

    if re.search(r"\bManagePullRequest\b", seg, re.IGNORECASE) and re.search(
        r"\bupdate_pr\b", seg, re.IGNORECASE
    ) and re.search(r"\bbody\b", seg, re.IGNORECASE):
        return "DENY", DENY_OVERRIDE_SCOPE, []

    return "ALLOW", None, []


def _shell_decision_lines(command_line: str) -> list[str]:
    cmd = command_line.strip()
    if not cmd:
        return ["ALLOW"]

    backup_lines: list[str] = []
    for segment in _shell_segments(cmd):
        decision, msg, backups = _segment_inspect(segment)
        if decision == "DENY":
            return [f"DENY|{msg}" if msg else "DENY"]
        backup_lines.extend(backups)

    if backup_lines:
        return [*backup_lines, "ALLOW"]
    return ["ALLOW"]


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "manage_pr"
    raw = sys.stdin.read()
    data = _parse_input(raw)

    if mode == "shell":
        for line in _shell_decision_lines(str(data.get("command") or data.get("cmd") or "")):
            print(line)
        return

    decision, msg = _manage_pr_decision(data)
    print(decision if not msg else f"{decision}|{msg}")


if __name__ == "__main__":
    main()
