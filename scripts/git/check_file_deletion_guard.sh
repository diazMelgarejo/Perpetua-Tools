#!/usr/bin/env bash
# check_file_deletion_guard.sh — block unreviewed whole-file removals.
#
# Usage:
#   check_file_deletion_guard.sh --staged
#   check_file_deletion_guard.sh --range <revision-range>
#
# Intentional removals require BOTH:
#   GIT_ALLOW_FILE_DELETIONS=1
#   GIT_FILE_DELETION_JUSTIFICATION='why this removal is safe'
#
# Bash 3.2 compatible: do not use mapfile/readarray or associative arrays.
set -euo pipefail

EXIT_FILE_DELETION=9

usage() {
  cat >&2 <<'EOF'
usage: scripts/git/check_file_deletion_guard.sh --staged
       scripts/git/check_file_deletion_guard.sh --range <revision-range>
EOF
}

mode=""
range=""
case "${1:-}" in
  --staged)
    [[ $# -eq 1 ]] || { usage; exit 2; }
    mode="staged"
    ;;
  --range)
    [[ $# -eq 2 ]] || { usage; exit 2; }
    mode="range"
    range="$2"
    ;;
  *)
    usage
    exit 2
    ;;
esac

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "file-deletion-guard: not inside a git repository" >&2
  exit 2
}
cd "$repo_root"

deletions="$(mktemp)"
trap 'rm -f "$deletions"' EXIT

if [[ "$mode" == "staged" ]]; then
  git diff --cached --no-renames --name-only --diff-filter=D >"$deletions"
  review_command="git diff --cached --name-status"
  restore_command="git restore --staged --worktree -- <path>"
else
  git diff --no-renames --name-only --diff-filter=D "$range" >"$deletions"
  review_command="git diff --name-status $range"
  if [[ "$range" == *".."* ]]; then
    # A genuine A..B (or A...B) range -- HEAD^ has no relationship to the
    # range's own boundaries and can point at the wrong commit entirely for
    # anything wider than a single-commit range. Use the range's own left
    # side: the file was definitely present there, for any deletion this
    # guard could have flagged within the range, even if a later commit
    # inside the range is a more precise (but not universally safe) source.
    range_start="${range%%..*}"
    restore_command="git restore --source=$range_start --staged --worktree -- <path>"
  else
    # A single ref, not a range -- the original HEAD^-relative-to-that-ref
    # assumption is well-defined here.
    restore_command="git restore --source=${range}^ --staged --worktree -- <path>"
  fi
fi

[[ -s "$deletions" ]] || exit 0

if [[ "${GIT_ALLOW_FILE_DELETIONS:-0}" == "1" && -n "${GIT_FILE_DELETION_JUSTIFICATION:-}" ]]; then
  echo "file-deletion-guard: whole-file deletion explicitly allowed: ${GIT_FILE_DELETION_JUSTIFICATION}" >&2
  exit 0
fi

echo "git scope: blocked [GIT_SCOPE_E_FILE_DELETION] (exit $EXIT_FILE_DELETION) — whole-file deletion detected" >&2
echo "  Review before committing or pushing; ordinary line removals are not blocked." >&2
while IFS= read -r path; do
  [[ -n "$path" ]] || continue
  echo "  D  $path" >&2
done <"$deletions"
echo "  Inspect: $review_command" >&2
echo "  If accidental: $restore_command" >&2
echo "  If intentional, require an auditable override:" >&2
echo "    GIT_ALLOW_FILE_DELETIONS=1 GIT_FILE_DELETION_JUSTIFICATION='why' <commit-or-push-command>" >&2
echo "  KB: bin/orama-system/skills/git-history-surgery/references/file-deletion-preflight-reference-card.md" >&2
exit "$EXIT_FILE_DELETION"
