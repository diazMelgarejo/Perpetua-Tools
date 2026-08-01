#!/usr/bin/env bash
# preToolUse / beforeMCPExecution — Layer 0: never auto-mutate PR bodies (comment only).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pr-body-backup-lib.sh
source "$SCRIPT_DIR/pr-body-backup-lib.sh"

input="$(cat)"
decision="ALLOW"
deny_msg=""

guard_output=""
guard_status=0
guard_output="$(python3 "$SCRIPT_DIR/pr-body-guard-core.py" manage_pr <<<"$input" 2>&1)" || guard_status=$?

if [[ "$guard_status" -ne 0 ]]; then
  decision="DENY"
  deny_msg="PR body guard internal error (fail-closed)."
else
  while IFS= read -r line; do
    case "$line" in
      BACKUP\|*)
        repo="${line#BACKUP|}"
        pr="${repo##*|}"
        repo="${repo%|*}"
        if ! pr_body_backup_if_needed "$repo" "$pr" "mcp-preflight"; then
          decision="DENY"
          deny_msg="PR body backup failed (fail-closed)."
          break
        fi
        ;;
      DENY\|*)
        decision="DENY"
        deny_msg="${line#DENY|}"
        ;;
      DENY)
        decision="DENY"
        ;;
    esac
  done <<<"$guard_output"
fi

if [[ "$decision" == "DENY" ]]; then
  deny_msg="${deny_msg:-Layer 0: comment only — never auto-change PR body.}"
  python3 - "$deny_msg" <<'PY'
import json, sys
msg = sys.argv[1]
print(json.dumps({
    "permission": "deny",
    "agent_message": msg,
    "user_message": "Cursor agent blocked from changing PR description. Use post_comment only.",
}))
PY
  exit 0
fi

printf '%s\n' '{"permission":"allow"}'
