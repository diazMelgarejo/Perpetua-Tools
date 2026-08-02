#!/usr/bin/env bash
# beforeShellExecution — Layer 0: block gh pr edit / append-pr-body; allow gh pr comment.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pr-body-backup-lib.sh
source "$SCRIPT_DIR/pr-body-backup-lib.sh"

input="$(cat)"
pr_body_run_guard "$SCRIPT_DIR" shell shell-preflight "$input"
decision="$PR_BODY_GUARD_DECISION"
deny_msg="$PR_BODY_GUARD_DENY_MSG"

if [[ "$decision" == "DENY" ]]; then
  deny_msg="${deny_msg:-Layer 0: comment only — never auto-change PR body.}"
  python3 - "$deny_msg" <<'PY'
import json, sys
msg = sys.argv[1]
print(json.dumps({
    "permission": "deny",
    "agent_message": msg,
    "user_message": "Cursor agent blocked from changing PR description. Use gh pr comment.",
}))
PY
  exit 0
fi

printf '%s\n' '{"permission":"allow"}'
