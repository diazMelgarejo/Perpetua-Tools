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

# owner/repo slug for the explicit --repo flag and the backup path shown
# below -- derived from pr_url (already captured above) rather than an
# extra gh call. pr_url is always https://github.com/<owner>/<repo>/pull/<n>.
repo_slug="$(printf '%s\n' "$pr_url" | sed -E 's#^https://github.com/([^/]+/[^/]+)/pull/.*#\1#')"
backup_slug="${repo_slug//\//-}"

cat <<EOF
PR-BODY-GUARD (Layer 0): open PR #${pr_number} for branch ${branch}
  ${pr_title}
  ${pr_url}

LAYER 0 — COMMENT ONLY. Cursor agents must NOT change the PR description.

  DO:    ManagePullRequest post_comment  OR  gh pr comment
  NEVER: update_pr with body=, gh pr edit, append-pr-body.sh without operator grant

Human override for description edits (operator runs grant-pr-body-human-override.sh first):

Correct path — the only path (append-pr-body.sh invokes update_pr internally, after read-backup-merge):
  1. READ   gh pr view ${pr_number} --repo ${repo_slug} --json body --jq .body
  2. BACKUP .git/pr-body-backups/${backup_slug}-pr${pr_number}-<UTC timestamp>.md
  3. MERGE  keep original ## Summary; append ## Follow-up chronologically
  4. WRITE  bash scripts/cursor/append-pr-body.sh ${repo_slug} ${pr_number} --title "..." --file follow-up.md
     then: PR_BODY_UPDATE_ACK=1 before publish-clean-branch (strict mode)

NEVER call ManagePullRequest update_pr, gh pr edit, or gh api directly for PR-body
writes — not as a primary path, not as a fallback, not even with a full body.
append-pr-body.sh is the only path; the hook guard denies the others regardless.

Lessons: lesson_3b13ab0a45d4 lesson_4a38f0e95fcf lesson_6fff093ccb00 lesson_a8f3c2e91d04
Rules: .cursor/rules/append-only-pr-body.mdc
Skill:  bin/orama-system/skills/cursor-pr-body/SKILL.md
EOF

if [[ "${PR_BODY_GUARD_STRICT:-0}" == "1" && "${PR_BODY_UPDATE_ACK:-0}" != "1" ]]; then
  echo "PR-BODY-GUARD: strict mode — set PR_BODY_UPDATE_ACK=1 after append-pr-body.sh or skip PR body update" >&2
  exit 1
fi
