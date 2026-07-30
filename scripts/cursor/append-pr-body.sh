#!/usr/bin/env bash
# Append-only PR body updates — NEVER replace the original Summary.
# Canonical: orama-system/scripts/cursor/append-pr-body.sh
#
# ManagePullRequest update_pr and gh pr edit REPLACE the entire body field.
# Agents must READ → backup → merge append-only → write full merged body.
set -euo pipefail

readonly CURSOR_BODY_END='<!-- CURSOR_AGENT_PR_BODY_END -->'
readonly CODERABBIT_MARKER='<!-- This is an auto-generated comment: release notes by coderabbit.ai -->'

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

count_substring() {
  local haystack="$1"
  local needle="$2"
  local count=0
  local rest="$haystack"
  while [[ "$rest" == *"$needle"* ]]; do
    count=$((count + 1))
    rest="${rest#*"$needle"}"
  done
  printf '%s' "$count"
}

normalize_follow_up_title() {
  local raw="${1:-}"
  local rest="$raw"
  if [[ "$rest" == Follow-up:* ]]; then
    rest="${rest#Follow-up:}"
  elif [[ "$rest" == Follow-up\ * ]]; then
    rest="${rest#Follow-up }"
  elif [[ "$rest" == Follow-up* ]]; then
    rest="${rest#Follow-up}"
  fi
  rest="${rest#"${rest%%[![:space:]]*}"}"
  printf 'Follow-up: %s' "$rest"
}

resolve_git_backup_dir() {
  local git_common_dir
  if ! git_common_dir="$(git rev-parse --git-common-dir 2>/dev/null)"; then
    echo "error: must run inside a git repository" >&2
    return 1
  fi
  if [[ "$git_common_dir" != /* ]]; then
    git_common_dir="$(git rev-parse --show-toplevel)/$git_common_dir"
  fi
  printf '%s/pr-body-backups' "$(cd "$git_common_dir" && pwd)"
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

if [[ -n "$append_file" && -n "$append_message" ]]; then
  echo "error: provide --file or --message, not both" >&2
  exit 1
fi

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

append_block=""
if [[ -n "$append_file" ]]; then
  append_block="$(cat "$append_file")"
else
  append_block="$append_message"
fi

if [[ "$append_block" == *"$CURSOR_BODY_END"* || "$append_block" == *"$CODERABBIT_MARKER"* ]]; then
  echo "error: append content must not contain reserved PR body delimiters" >&2
  exit 1
fi

backup_dir="$(resolve_git_backup_dir)"
mkdir -p "$backup_dir"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
safe_slug="${repo_slug//\//-}"
backup_path="$(mktemp "${backup_dir}/${safe_slug}-pr${pr_number}-${ts}.XXXXXX")"

current_body="$(gh pr view "$pr_number" --repo "$repo_slug" --json body --jq .body)"
printf '%s\n' "$current_body" >"$backup_path"
echo "backup: $backup_path"

cursor_delim_count="$(count_substring "$current_body" "$CURSOR_BODY_END")"
coderabbit_delim_count="$(count_substring "$current_body" "$CODERABBIT_MARKER")"
if ((cursor_delim_count > 1)); then
  echo "error: PR body contains $cursor_delim_count CURSOR_AGENT_PR_BODY_END markers; manual repair required" >&2
  exit 1
fi
if ((coderabbit_delim_count > 1)); then
  echo "error: PR body contains $coderabbit_delim_count CodeRabbit markers; manual repair required" >&2
  exit 1
fi

if [[ -z "$title" ]]; then
  title="$(normalize_follow_up_title "Follow-up ($(date -u +%Y-%m-%d))")"
else
  title="$(normalize_follow_up_title "$title")"
fi

follow_up=$(
  cat <<EOF

## ${title}

${append_block}
EOF
)

merged="$current_body"
if [[ "$merged" == *"$CURSOR_BODY_END"* ]]; then
  merged="${merged/"$CURSOR_BODY_END"/${follow_up}
$CURSOR_BODY_END}"
elif [[ "$merged" == *"$CODERABBIT_MARKER"* ]]; then
  merged="${merged/"$CODERABBIT_MARKER"/${follow_up}

$CODERABBIT_MARKER}"
else
  merged="${merged}${follow_up}"
fi

remote_body="$(gh pr view "$pr_number" --repo "$repo_slug" --json body --jq .body)"
if [[ "$remote_body" != "$current_body" ]]; then
  echo "error: PR body changed since initial read; aborting to avoid overwrite" >&2
  echo "hint: review concurrent edits and re-run append-pr-body.sh" >&2
  exit 1
fi

out="$(mktemp)"
trap 'rm -f "$out"' EXIT
printf '%s\n' "$merged" >"$out"
gh pr edit "$pr_number" --repo "$repo_slug" --body-file "$out"

echo "updated: https://github.com/${repo_slug}/pull/${pr_number}"
