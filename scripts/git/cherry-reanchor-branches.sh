#!/usr/bin/env bash
# Cherry-pick patch-id-unique commits onto origin/main and force-update branch tips.
#
# Preferred post-rewrite re-anchor after a full history scrub (rebase --onto often
# conflicts on rewritten ancestry). Open PR branches should end with
# merge-base == origin/main.
#
# Usage:
#   cherry-reanchor-branches.sh [repo_path] branch [branch...]
#   cherry-reanchor-branches.sh [repo_path] --from-json actions.json [--all-needs]
#
# Env:
#   DELETE_ON_CHERRY_CONFLICT=0  never delete on failure unless --delete-on-conflict
#   SKIP_EMPTY_CHERRY=1          default on — skip empty picks and continue
#   ALLOW_LOCAL_SOURCE=1         fall back to refs/heads/<branch> when remote missing
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${1:-.}"
shift || true

DELETE_ON_CONFLICT="${DELETE_ON_CHERRY_CONFLICT:-0}"
SKIP_EMPTY="${SKIP_EMPTY_CHERRY:-1}"
ALLOW_LOCAL="${ALLOW_LOCAL_SOURCE:-1}"
FROM_JSON=""
ALL_NEEDS=0
branches=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from-json) FROM_JSON="${2:?}"; shift 2 ;;
    --all-needs) ALL_NEEDS=1; shift ;;
    --delete-on-conflict) DELETE_ON_CONFLICT=1; shift ;;
    --no-local-source) ALLOW_LOCAL=0; shift ;;
    *) branches+=("$1"); shift ;;
  esac
done

cd "$REPO"
git fetch origin --prune

# Re-check at call time: checkout origin/main removes scripts that are not on main yet.
push_git() {
  if [[ -x "$SCRIPT_DIR/history-surgery-push.sh" ]]; then
    bash "$SCRIPT_DIR/history-surgery-push.sh" "$@"
  else
    git -c core.hooksPath=/dev/null push "$@"
  fi
}

if [[ "$ALL_NEEDS" == "1" && -n "$FROM_JSON" ]]; then
  while IFS= read -r branch; do
    [[ -n "$branch" ]] && branches+=("$branch")
  done < <(
    python3 -c "import json,sys; print('\n'.join(x['branch'] for x in json.load(open(sys.argv[1]))['needs']))" \
      "$FROM_JSON"
  )
elif [[ ${#branches[@]} -eq 0 && -n "$FROM_JSON" ]]; then
  echo "ERROR: pass branch names or --all-needs with --from-json" >&2
  exit 2
fi

ok=0
deleted=0
failed=0
skipped=0

resolve_source_ref() {
  local branch="$1"
  if git show-ref --verify --quiet "refs/remotes/origin/$branch"; then
    echo "origin/$branch"
    return 0
  fi
  if [[ "$ALLOW_LOCAL" == "1" ]] \
    && git show-ref --verify --quiet "refs/heads/$branch"; then
    echo "$branch"
    return 0
  fi
  return 1
}

is_empty_cherry_pick() {
  # Mid cherry-pick with no index/worktree delta (empty patch or already in tree).
  git rev-parse --verify CHERRY_PICK_HEAD >/dev/null 2>&1 || return 1
  if git diff-index --quiet HEAD -- 2>/dev/null; then
    return 0
  fi
  git diff --cached --quiet && git diff --quiet
}

cherry_pick_commits() {
  local commits=("$@")
  local c
  for c in "${commits[@]}"; do
    if git cherry-pick "$c"; then
      echo "  OK $c"
      continue
    fi
    if [[ "$SKIP_EMPTY" == "1" ]] && is_empty_cherry_pick; then
      echo "  SKIP empty $c"
      git cherry-pick --skip
      continue
    fi
    echo "  FAIL at $c" >&2
    return 1
  done
  return 0
}

for branch in "${branches[@]}"; do
  [[ -n "$branch" ]] || continue
  source_ref=""
  if ! source_ref="$(resolve_source_ref "$branch")"; then
    echo "skip: no source ref for $branch (remote or local)" >&2
    skipped=$((skipped + 1))
    continue
  fi
  echo ">>> CHERRY-REANCHOR $branch (source=$source_ref)"
  old_sha=""
  if git show-ref --verify --quiet "refs/remotes/origin/$branch"; then
    old_sha="$(git rev-parse "origin/$branch")"
  fi
  commits=()
  while IFS= read -r commit; do
    [[ -n "$commit" ]] && commits+=("$commit")
  done < <(git cherry origin/main "$source_ref" | awk '/^\+/{print $2}')
  if [[ "${#commits[@]}" -eq 0 ]]; then
    echo "  no unique commits vs origin/main — skip (not deleting)"
    skipped=$((skipped + 1))
    continue
  fi
  work="__cherry_${branch//\//_}"
  work_dir="$(mktemp -d)"
  if ! git worktree add -B "$work" "$work_dir" origin/main >/dev/null; then
    echo "  FAIL: could not create disposable worktree for $branch" >&2
    rm -rf "$work_dir"
    failed=$((failed + 1))
    continue
  fi
  if ! (cd "$work_dir" && cherry_pick_commits "${commits[@]}"); then
    echo "  FAIL cherry-pick $branch" >&2
    git -C "$work_dir" cherry-pick --abort 2>/dev/null || true
    git worktree remove --force "$work_dir" 2>/dev/null || rm -rf "$work_dir"
    git branch -D "$work" 2>/dev/null || true
    if [[ "$DELETE_ON_CONFLICT" == "1" ]] \
      && git show-ref --verify --quiet "refs/remotes/origin/$branch"; then
      if push_git origin --delete "$branch" 2>/dev/null; then
        echo "  deleted $branch (conflict; DELETE_ON_CHERRY_CONFLICT=1)" >&2
        deleted=$((deleted + 1))
      else
        failed=$((failed + 1))
      fi
    else
      failed=$((failed + 1))
    fi
    continue
  fi
  mb="$(git -C "$work_dir" merge-base HEAD origin/main)"
  main_tip="$(git rev-parse origin/main)"
  if [[ "$mb" != "$main_tip" ]]; then
    echo "  FAIL: merge-base != origin/main after cherry-pick" >&2
    git worktree remove --force "$work_dir" 2>/dev/null || rm -rf "$work_dir"
    git branch -D "$work" 2>/dev/null || true
    failed=$((failed + 1))
    continue
  fi
  push_ok=0
  if [[ -n "$old_sha" ]]; then
    if push_git --force-with-lease="refs/heads/${branch}:${old_sha}" \
      origin "${work}:refs/heads/${branch}"; then
      push_ok=1
    else
      echo "  FAIL: lease rejected for $branch; fetch/review and retry with a fresh recorded lease" >&2
    fi
  else
    if push_git -u origin "${work}:refs/heads/${branch}"; then
      push_ok=1
    fi
  fi
  git worktree remove --force "$work_dir" 2>/dev/null || rm -rf "$work_dir"
  git branch -D "$work" 2>/dev/null || true
  if [[ "$push_ok" == "1" ]]; then
    ok=$((ok + 1))
  else
    failed=$((failed + 1))
  fi
done

echo "OK: cherry-reanchor ok=$ok deleted=$deleted failed=$failed skipped=$skipped"
exit $(( failed > 0 ? 1 : 0 ))
