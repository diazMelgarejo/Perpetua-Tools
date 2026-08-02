#!/usr/bin/env bash
# remind-pr-body-append-only.sh — print mandatory PR body workflow when an open PR exists.
#
# Call after commit, before push (especially from publish-clean-branch.sh).
# Set PR_BODY_GUARD_STRICT=1 to exit 1 unless PR_BODY_UPDATE_ACK=1.
set -euo pipefail

branch="${1:-$(git branch --show-current)}"

if ! command -v gh >/dev/null 2>&1; then
  exit 0
fi

read -r pr_number pr_url pr_title < <(
  gh pr list --head "$branch" --json number,url,title --limit 1 --jq \
    'if length==0 then "" else "\(.[0].number) \(.[0].url) \(.[0].title)" end' 2>/dev/null || echo ""
)

if [[ -z "$pr_number" ]]; then
  exit 0
fi

cat <<EOF
PR-BODY-GUARD (Layer 0): open PR #${pr_number} for branch ${branch}
  ${pr_title}
  ${pr_url}

LAYER 0 — COMMENT ONLY. Cursor agents must NOT change the PR description.

  DO:    ManagePullRequest post_comment  OR  gh pr comment
  NEVER: update_pr with body=, gh pr edit, append-pr-body.sh (hooks block these)

Human override only (operator runs grant-pr-body-human-override.sh, then append-pr-body):
  bash scripts/cursor/append-pr-body.sh <owner/repo> ${pr_number} --title "..." --file follow-up.md

Rules: .cursor/rules/pr-body-comment-only.mdc
Skill:  bin/orama-system/skills/cursor-pr-body/SKILL.md
EOF

if [[ "${PR_BODY_GUARD_STRICT:-0}" == "1" && "${PR_BODY_UPDATE_ACK:-0}" != "1" ]]; then
  echo "PR-BODY-GUARD: strict mode — set PR_BODY_UPDATE_ACK=1 after append-pr-body.sh or skip PR body update" >&2
  exit 1
fi
