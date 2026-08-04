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
PR-BODY-GUARD: open PR #${pr_number} for branch ${branch}
  ${pr_title}
  ${pr_url}

NEVER ManagePullRequest update_pr with delta-only body= — it REPLACES the entire field.

LAYER 0 — default for Cursor agents: ManagePullRequest post_comment OR gh pr comment only.

Human override for description edits (operator runs grant-pr-body-human-override.sh first):

Correct path (append-pr-body.sh):
  1. READ   gh pr view ${pr_number} --json body
  2. BACKUP .git/pr-body-backups/<repo>-pr${pr_number}-<timestamp>.md
  3. MERGE  keep original ## Summary; append ## Follow-up chronologically
  4. WRITE  bash scripts/cursor/append-pr-body.sh <owner/repo> ${pr_number} --title "..." --file follow-up.md
     then: PR_BODY_UPDATE_ACK=1 before publish-clean-branch (strict mode)

If you must use update_pr (agent-managed PR only): pass the FULL integrative merged body,
never the latest paragraph alone. Prefer append-pr-body.sh.

Lessons: lesson_3b13ab0a45d4 lesson_4a38f0e95fcf lesson_6fff093ccb00 lesson_a8f3c2e91d04
Rules: .cursor/rules/append-only-pr-body.mdc
Skill:  bin/orama-system/skills/cursor-pr-body/SKILL.md
EOF

if [[ "${PR_BODY_GUARD_STRICT:-0}" == "1" && "${PR_BODY_UPDATE_ACK:-0}" != "1" ]]; then
  echo "PR-BODY-GUARD: strict mode — set PR_BODY_UPDATE_ACK=1 after append-pr-body.sh or skip PR body update" >&2
  exit 1
fi
