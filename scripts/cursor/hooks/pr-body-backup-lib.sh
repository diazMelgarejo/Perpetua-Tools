#!/usr/bin/env bash
# pr-body-backup-lib.sh — shared READ→BACKUP helpers for Cursor PR-body hooks.
# Source from hook scripts; do not execute directly.
set -euo pipefail

pr_body_backup_dir() {
  local git_common_dir
  if ! git_common_dir="$(git rev-parse --git-common-dir 2>/dev/null)"; then
    printf '%s\n' "${TMPDIR:-/tmp}"
    return 0
  fi
  if [[ "$git_common_dir" != /* ]]; then
    git_common_dir="$(git rev-parse --show-toplevel 2>/dev/null)/$git_common_dir"
  fi
  local resolved
  if ! resolved="$(cd "$git_common_dir" && pwd)"; then
    printf '%s\n' "${TMPDIR:-/tmp}"
    return 0
  fi
  printf '%s/pr-body-backups\n' "$resolved"
}

pr_body_backup_if_needed() {
  local repo_slug="$1"
  local pr_number="$2"
  local reason="${3:-preflight-read}"

  if ! command -v gh >/dev/null 2>&1; then
    return 0
  fi
  if [[ -z "$repo_slug" || -z "$pr_number" ]]; then
    return 0
  fi

  local backup_dir body ts safe_slug path
  backup_dir="$(pr_body_backup_dir)"
  if ! mkdir -p "$backup_dir"; then
    return 1
  fi
  if ! body="$(gh pr view "$pr_number" --repo "$repo_slug" --json body --jq .body 2>/dev/null)"; then
    return 1
  fi
  [[ -n "$body" ]] || return 0

  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  safe_slug="${repo_slug//\//-}"
  path="${backup_dir}/${safe_slug}-pr${pr_number}-${ts}-${reason}.md"
  printf '%s\n' "$body" >"$path"
  printf 'PR-BODY-BACKUP: %s (%s)\n' "$path" "$reason" >&2
}

# Run pr-body-guard-core and optional hook backup preflight.
# Sets PR_BODY_GUARD_DECISION (ALLOW|DENY) and PR_BODY_GUARD_DENY_MSG.
pr_body_run_guard() {
  local hook_dir="$1"
  local mode="$2"
  local backup_reason="$3"
  local input="$4"

  PR_BODY_GUARD_DECISION="ALLOW"
  PR_BODY_GUARD_DENY_MSG=""

  local guard_output=""
  local guard_status=0
  guard_output="$(python3 "$hook_dir/pr-body-guard-core.py" "$mode" <<<"$input" 2>&1)" || guard_status=$?

  if [[ "$guard_status" -ne 0 ]]; then
    PR_BODY_GUARD_DECISION="DENY"
    PR_BODY_GUARD_DENY_MSG="PR body guard internal error (fail-closed)."
    return 0
  fi

  while IFS= read -r line; do
    case "$line" in
      BACKUP\|*)
        local repo="${line#BACKUP|}"
        local pr="${repo##*|}"
        repo="${repo%|*}"
        if ! pr_body_backup_if_needed "$repo" "$pr" "$backup_reason"; then
          PR_BODY_GUARD_DECISION="DENY"
          PR_BODY_GUARD_DENY_MSG="PR body backup failed (fail-closed)."
          break
        fi
        ;;
      DENY\|*)
        PR_BODY_GUARD_DECISION="DENY"
        PR_BODY_GUARD_DENY_MSG="${line#DENY|}"
        ;;
      DENY)
        PR_BODY_GUARD_DECISION="DENY"
        ;;
      ALLOW)
        ;;
    esac
  done <<<"$guard_output"
}
