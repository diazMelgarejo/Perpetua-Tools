#!/usr/bin/env bash
# Create a commit without running git commit hooks (avoids Cursor co-author injection).
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/git/commit-clean.sh -m "message" [--amend] [--allow-empty] [--dry-run]

MANDATORY sequence (agents — never skip or reorder):
  1. git add <paths>              # this script NEVER stages for you
  2. bash scripts/git/verify-staged-for-commit.sh
  3. bash scripts/git/commit-clean.sh -m "type(scope): summary"

Unstaged edits are preserved but are NOT included in the commit.
Uses git commit-tree so Cursor commit-msg hooks never run.

During an in-progress merge (MERGE_HEAD present), parent lineage is preserved
automatically: HEAD is the first parent and every SHA listed in MERGE_HEAD is
added as an additional parent (two-parent merges and N-way octopus merges).

Options:
  --amend         Replace HEAD (parent becomes HEAD^)
  --allow-empty   Allow intentional empty commits (rare)
  --dry-run       Verify and print summary; do not update the branch

Environment overrides: GIT_AUTHOR_NAME, GIT_AUTHOR_EMAIL, COMMIT_CLEAN_ALLOW_EMPTY=1
EOF
}

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "error: not inside a git repository" >&2
  exit 1
}
cd "$repo_root"
SCRIPT_DIR="$repo_root/scripts/git"
# shellcheck source=banned_attribution_lib.sh
source "$SCRIPT_DIR/banned_attribution_lib.sh"

message=""
amend=0
allow_empty="${COMMIT_CLEAN_ALLOW_EMPTY:-0}"
dry_run=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -m)
      message="${2:-}"
      shift 2
      ;;
    --amend)
      amend=1
      shift
      ;;
    --allow-empty)
      allow_empty=1
      shift
      ;;
    --dry-run)
      dry_run=1
      shift
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

[[ -n "$message" ]] || {
  echo "error: -m message is required" >&2
  usage
  exit 1
}

author_name="${GIT_AUTHOR_NAME:-$(git config user.name)}"
author_email="${GIT_AUTHOR_EMAIL:-$(git config user.email)}"
[[ -n "$author_name" && -n "$author_email" ]] || {
  echo "error: configure user.name and user.email or set GIT_AUTHOR_*" >&2
  exit 1
}
author_email_lc="$(printf '%s' "$author_email" | tr '[:upper:]' '[:lower:]')"
author_domain_ok() {
  local email_lc="$1"
  local domain="${email_lc#*@}"
  [[ -z "$domain" || "$domain" == "$email_lc" ]] && return 1
  case "$domain" in
    openai.com|*.openai.com|anthropic.com|*.anthropic.com|cursor.com|*.cursor.com|cursor.sh|*.cursor.sh|google.com|*.google.com|google.dev|*.google.dev|github.com|*.github.com|microsoft.com|*.microsoft.com|azure.com|*.azure.com|perplexity.ai|*.perplexity.ai|x.ai|*.x.ai)
      return 0
      ;;
  esac
  return 1
}
case "$author_email_lc" in
  diazmelgarejo@gmail.com|lawrence@cyre.me|codex@openai.com)
    ;;
  *)
    if ! private_owner_email_ok "$author_email_lc" "$repo_root" && ! author_domain_ok "$author_email_lc"; then
      echo "error: commit author email must be one of the approved owner emails, codex@openai.com, or a well-known AI/vendor domain" >&2
      exit 1
    fi
    ;;
esac

verify_args=()
[[ "$allow_empty" -eq 1 ]] && verify_args+=(--allow-empty)
[[ "$amend" -eq 1 ]] && verify_args+=(--amend)
if [[ ${#verify_args[@]} -gt 0 ]]; then
  bash "$SCRIPT_DIR/verify-staged-for-commit.sh" "${verify_args[@]}"
else
  bash "$SCRIPT_DIR/verify-staged-for-commit.sh"
fi

tree="$(git write-tree)"

merge_head_path="$(git rev-parse --git-path MERGE_HEAD)"
in_merge=0
if [[ "$amend" -eq 0 && -f "$merge_head_path" ]]; then
  in_merge=1
fi

parents=()
if [[ "$amend" -eq 1 ]]; then
  parents+=("$(git rev-parse HEAD^)")
elif git rev-parse HEAD >/dev/null 2>&1; then
  parents+=("$(git rev-parse HEAD)")
fi

if [[ "$in_merge" -eq 1 ]]; then
  while IFS= read -r merge_parent || [[ -n "$merge_parent" ]]; do
    merge_parent="${merge_parent%%#*}"
    merge_parent="${merge_parent//[[:space:]]/}"
    [[ -n "$merge_parent" ]] || continue
    parents+=("$merge_parent")
  done <"$merge_head_path"
fi

if [[ "$dry_run" -eq 1 ]]; then
  echo "commit-clean: dry-run — would create commit on tree ${tree}" >&2
  if ((${#parents[@]} > 0)); then
    echo "commit-clean: dry-run — parents ${parents[*]}" >&2
  fi
  if [[ "$in_merge" -eq 1 ]]; then
    echo "commit-clean: dry-run — merge in progress; MERGE_HEAD parents retained" >&2
  fi
  printf '%s\n' "$message"
  exit 0
fi

commit_tree_args=("$tree")
for parent_sha in "${parents[@]}"; do
  commit_tree_args+=(-p "$parent_sha")
done

if ((${#commit_tree_args[@]} > 1)); then
  new_sha="$(
    printf '%s\n' "$message" |
      GIT_AUTHOR_NAME="$author_name" GIT_AUTHOR_EMAIL="$author_email" \
      git commit-tree "${commit_tree_args[@]}" -F -
  )"
else
  new_sha="$(
    printf '%s\n' "$message" |
      GIT_AUTHOR_NAME="$author_name" GIT_AUTHOR_EMAIL="$author_email" \
      git commit-tree "$tree" -F -
  )"
fi

branch="$(git symbolic-ref --short HEAD 2>/dev/null || true)"
if [[ -n "$branch" ]]; then
  git update-ref "refs/heads/${branch}" "$new_sha"
else
  git update-ref HEAD "$new_sha"
fi

if [[ "$in_merge" -eq 1 ]]; then
  rm -f \
    "$merge_head_path" \
    "$(git rev-parse --git-path MERGE_MODE)" \
    "$(git rev-parse --git-path MERGE_MSG)"
fi

echo "$new_sha"
