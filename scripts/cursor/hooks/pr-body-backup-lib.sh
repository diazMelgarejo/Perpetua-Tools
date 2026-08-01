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
  printf '%s/pr-body-backups\n' "$(cd "$git_common_dir" && pwd)"
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
  mkdir -p "$backup_dir"
  body="$(gh pr view "$pr_number" --repo "$repo_slug" --json body --jq .body 2>/dev/null || true)"
  [[ -n "$body" ]] || return 0

  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  safe_slug="${repo_slug//\//-}"
  path="${backup_dir}/${safe_slug}-pr${pr_number}-${ts}-${reason}.md"
  printf '%s\n' "$body" >"$path"
  printf 'PR-BODY-BACKUP: %s (%s)\n' "$path" "$reason" >&2
}
