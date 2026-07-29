#!/usr/bin/env bash
# Append-only PR body updates — NEVER replace the original Summary.
# Canonical: orama-system/scripts/cursor/append-pr-body.sh
#
# ManagePullRequest update_pr and gh pr edit REPLACE the entire body field.
# Agents must READ → backup → merge append-only → write full merged body.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/cursor/append-pr-body.sh <owner/repo> <pr-number> --file <append.md>
  scripts/cursor/append-pr-body.sh <owner/repo> <pr-number> --message "markdown"
  scripts/cursor/append-pr-body.sh <owner/repo> <pr-number> --title "Follow-up title" --file <append.md>

Mandatory workflow:
  1. Fetch current body (gh pr view --json body)
  2. Save timestamped backup (.git/pr-body-backups/<repo>-pr<N>-<ts>.md)
  3. Insert new ## Follow-up block before CURSOR_AGENT_PR_BODY_END or CodeRabbit section
  4. gh pr edit --body-file (full merged body — integrative, not delta-only)

Never pass body= with only the latest paragraph to ManagePullRequest update_pr.
EOF
}

repo_slug="${1:-}"
pr_number="${2:-}"
shift 2 || true

title=""
append_file=""
append_message=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --title)
      title="${2:-}"
      shift 2
      ;;
    --file)
      append_file="${2:-}"
      shift 2
      ;;
    --message)
      append_message="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

[[ -n "$repo_slug" && -n "$pr_number" ]] || {
  usage
  exit 1
}

if [[ -z "$append_file" && -z "$append_message" ]]; then
  echo "error: provide --file or --message" >&2
  exit 1
fi

if [[ -n "$append_file" && ! -f "$append_file" ]]; then
  echo "error: append file not found: $append_file" >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "error: gh CLI required" >&2
  exit 1
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
backup_dir="$repo_root/.git/pr-body-backups"
mkdir -p "$backup_dir"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
safe_slug="${repo_slug//\//-}"
backup_path="$backup_dir/${safe_slug}-pr${pr_number}-${ts}.md"

current_body="$(gh pr view "$pr_number" --repo "$repo_slug" --json body --jq .body)"
printf '%s\n' "$current_body" >"$backup_path"
echo "backup: $backup_path"

append_block=""
if [[ -n "$append_file" ]]; then
  append_block="$(cat "$append_file")"
else
  append_block="$append_message"
fi

if [[ -z "$title" ]]; then
  title="Follow-up ($(date -u +%Y-%m-%d))"
fi

follow_up=$(
  cat <<EOF

## ${title}

${append_block}
EOF
)

merged="$current_body"
if [[ "$merged" == *"<!-- CURSOR_AGENT_PR_BODY_END -->"* ]]; then
  merged="${merged//<!-- CURSOR_AGENT_PR_BODY_END -->/${follow_up}
<!-- CURSOR_AGENT_PR_BODY_END -->}"
elif [[ "$merged" == *"<!-- This is an auto-generated comment: release notes by coderabbit.ai -->"* ]]; then
  merged="${merged//<!-- This is an auto-generated comment: release notes by coderabbit.ai -->/${follow_up}

<!-- This is an auto-generated comment: release notes by coderabbit.ai -->}"
else
  merged="${merged}${follow_up}"
fi

out="$(mktemp)"
printf '%s\n' "$merged" >"$out"
gh pr edit "$pr_number" --repo "$repo_slug" --body-file "$out"
rm -f "$out"

echo "updated: https://github.com/${repo_slug}/pull/${pr_number}"
