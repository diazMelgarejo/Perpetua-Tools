#!/usr/bin/env bash
# Mandatory pre-commit gate: fail unless the index has a real delta vs HEAD.
# Run AFTER git add and BEFORE commit-clean.sh.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/git/verify-staged-for-commit.sh [--amend] [--allow-empty]

Mandatory agent sequence (never skip steps):
  1. git add <paths>              # commit-clean NEVER stages for you
  2. bash scripts/git/verify-staged-for-commit.sh
  3. bash scripts/git/commit-clean.sh -m "type(scope): summary"

Fails when:
  - nothing is staged (unless --amend for message-only amend)
  - staged index would produce the same tree as HEAD (empty commit)

Options:
  --amend         Allow message-only amend (staged tree may match HEAD)
  --allow-empty   Rare escape hatch for intentional empty commits

Prints git diff --cached --stat on success.
EOF
}

allow_empty="${COMMIT_CLEAN_ALLOW_EMPTY:-0}"
amend=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --allow-empty)
      allow_empty=1
      shift
      ;;
    --amend)
      amend=1
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

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "error: not inside a git repository" >&2
  exit 1
}
cd "$repo_root"

mandatory_sequence() {
  cat >&2 <<'EOF'

MANDATORY sequence (agents — do not skip or reorder):
  1. git add <paths>              # commit-clean NEVER stages for you
  2. bash scripts/git/verify-staged-for-commit.sh
  3. bash scripts/git/commit-clean.sh -m "type(scope): summary"

Before step 3, confirm: git diff --cached --stat is non-empty.
EOF
}

head_tree=""
if git rev-parse HEAD >/dev/null 2>&1; then
  head_tree="$(git rev-parse HEAD^{tree})"
fi

if git diff --cached --quiet 2>/dev/null; then
  if [[ "$amend" -eq 1 ]]; then
    echo "verify-staged-for-commit: amend with no staged file changes (message-only)" >&2
    exit 0
  fi
  echo "error: nothing staged to commit" >&2
  mandatory_sequence
  if ! git diff --quiet 2>/dev/null; then
    echo "" >&2
    echo "Unstaged edits exist (NOT included unless you git add them):" >&2
    git status --short >&2
  fi
  exit 1
fi

index_tree="$(git write-tree)"
if [[ "$allow_empty" -eq 0 && "$amend" -eq 0 && -n "$head_tree" && "$index_tree" == "$head_tree" ]]; then
  echo "error: staged index matches HEAD tree — would create an empty commit" >&2
  echo "hint: run git add on the paths you intend to commit" >&2
  mandatory_sequence
  git diff --cached --stat >&2
  exit 1
fi

echo "verify-staged-for-commit: OK — staged changes:" >&2
git diff --cached --stat >&2
