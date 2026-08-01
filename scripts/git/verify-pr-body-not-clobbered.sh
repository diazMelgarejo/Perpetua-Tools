#!/usr/bin/env bash
# verify-pr-body-not-clobbered.sh — Layer 6: fail if open PR bodies lack ## Summary.
#
# Detects the common clobber pattern: agent replaced entire PR body with only a
# remediation delta, erasing the original Summary and CodeRabbit tail.
#
# Usage:
#   verify-pr-body-not-clobbered.sh [owner/repo] [pr-number]
#   verify-pr-body-not-clobbered.sh                    # all open PRs in current repo
#   verify-pr-body-not-clobbered.sh owner/repo         # all open PRs in repo
#   verify-pr-body-not-clobbered.sh owner/repo 314     # single PR
#
# Exit codes:
#   0 — all checked PRs contain ## Summary (or no open PRs)
#   1 — one or more PR bodies missing ## Summary
#   2 — usage / gh unavailable
set -euo pipefail

if ! command -v gh >/dev/null 2>&1; then
  echo "skip: gh not available" >&2
  exit 0
fi

repo="${1:-}"
pr_number="${2:-}"

if [[ -z "$repo" ]]; then
  if ! repo="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)"; then
    echo "error: cannot resolve repo; pass owner/repo" >&2
    exit 2
  fi
fi

check_pr() {
  local num="$1"
  local body title
  body="$(gh pr view "$num" --repo "$repo" --json body -q .body 2>/dev/null || true)"
  title="$(gh pr view "$num" --repo "$repo" --json title -q .title 2>/dev/null || true)"

  if [[ -z "$body" ]]; then
    echo "FAIL PR #${num}: empty body (${title})"
    return 1
  fi

  if grep -qE '^##[[:space:]]+Summary' <<<"$body"; then
    echo "OK  PR #${num}: ## Summary present"
    return 0
  fi

  # Alternate acceptable headers agents sometimes use
  if grep -qE '^#[[:space:]]+Summary' <<<"$body"; then
    echo "OK  PR #${num}: # Summary present"
    return 0
  fi

  echo "FAIL PR #${num}: missing ## Summary — likely delta-only body clobber (${title})"
  echo "      Recovery: .git/pr-body-backups/ + append-pr-body.sh (see lesson_6fff093ccb00)" >&2
  return 1
}

rc=0

if [[ -n "$pr_number" ]]; then
  check_pr "$pr_number" || rc=1
else
  mapfile -t open_prs < <(gh pr list --repo "$repo" --state open --json number -q '.[].number' 2>/dev/null || true)
  if [[ ${#open_prs[@]} -eq 0 ]]; then
    echo "OK  no open PRs in ${repo}"
    exit 0
  fi
  for num in "${open_prs[@]}"; do
    check_pr "$num" || rc=1
  done
fi

exit "$rc"
