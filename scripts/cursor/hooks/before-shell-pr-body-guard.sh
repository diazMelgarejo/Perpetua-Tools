#!/usr/bin/env bash
# beforeShellExecution — Layer 0: block gh pr edit / append-pr-body; allow gh pr comment.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pr-body-backup-lib.sh
source "$SCRIPT_DIR/pr-body-backup-lib.sh"

input="$(cat)"
decision="ALLOW"
deny_msg=""

while IFS= read -r line; do
  case "$line" in
    BACKUP\|*)
      repo="${line#BACKUP|}"
      pr="${repo##*|}"
      repo="${repo%|*}"
      pr_body_backup_if_needed "$repo" "$pr" "shell-preflight"
      ;;
    DENY\|*)
      decision="DENY"
      deny_msg="${line#DENY|}"
      ;;
    DENY)
      decision="DENY"
      ;;
  esac
done < <(python3 "$SCRIPT_DIR/pr-body-guard-core.py" shell <<<"$input")

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
