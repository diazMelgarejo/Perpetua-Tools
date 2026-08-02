#!/usr/bin/env bash
# beforeSubmitPrompt — inject Layer 0 reminder so agents cannot "forget" between turns.
set -euo pipefail

input="$(cat)"
python3 - "$input" <<'PY'
import json, sys

raw = sys.argv[1]
try:
    data = json.loads(raw) if raw.strip() else {}
except json.JSONDecodeError:
    data = {}

prompt = str(data.get("prompt") or data.get("user_message") or "")
lower = prompt.lower()
triggers = (
    "update_pr", "pr body", "pull request", "managepullrequest",
    "append-pr-body", "gh pr edit", "pr description", "pr summary",
)
if not any(t in lower for t in triggers):
    print(json.dumps({"continue": True}))
    sys.exit(0)

print(json.dumps({
    "continue": True,
    "additional_context": (
        "LAYER-0 PR BODY RULE (Cursor agents): NEVER automatically change an existing "
        "PR description. Use post_comment / gh pr comment ONLY. "
        "ManagePullRequest update_pr with body=, gh pr edit, and append-pr-body.sh are "
        "BLOCKED by hooks unless the operator issued a grant via "
        "grant-pr-body-human-override.sh — then only append-pr-body.sh is allowed "
        "(no delta-only writes, no direct gh pr edit / gh api)."
    ),
}))
PY
