#!/usr/bin/env bash
# Block push while a --no-commit merge/cherry-pick/revert is still uncommitted.
#
# Exit codes (KB-indexed — see
# bin/orama-system/skills/git-history-surgery/references/pending-operation-push-guard-reference-card.md):
#   0 = GIT_PUSH_OK
#   1 = GIT_PUSH_E_PENDING_MERGE_CLEAN    (MERGE_HEAD, no unmerged paths)
#   2 = GIT_PUSH_E_PENDING_MERGE_CONFLICT (MERGE_HEAD + unmerged paths)
#   3 = GIT_PUSH_E_PENDING_CHERRY_PICK    (CHERRY_PICK_HEAD)
#   4 = GIT_PUSH_E_PENDING_REVERT         (REVERT_HEAD)
#   5 = GIT_PUSH_E_PENDING_MERGE_MSG      (MERGE_MSG only — no MERGE_HEAD)
#   6 = GIT_PUSH_E_PENDING_SQUASH         (SQUASH_MSG)
#   7 = GIT_PUSH_E_PENDING_REBASE         (rebase-merge / rebase-apply)
#   8 = GIT_PUSH_E_PENDING_AM             (git am via rebase-apply/applying)
#
# A --no-commit operation leaves MERGE_HEAD / CHERRY_PICK_HEAD / REVERT_HEAD
# set until 'git commit' finalizes it. Pushing before that silently ships the
# PRE-operation tip with zero error -- git can't push an uncommitted index,
# so there's nothing to catch this except checking these refs directly.
#
# Caught 2026-07-30 on periscope PR #39: a fully-conflict-resolved
# `git merge origin/merged --no-commit --no-ff` was never followed by
# `git commit`. The branch was pushed and a PR opened describing the merge,
# but the pushed tip was still the pre-merge commit -- the PR was empty
# relative to its own description.
set -euo pipefail

ROOT="${1:-$(git rev-parse --show-toplevel)}"
cd "$ROOT"

pending=()
has_merge=false
has_cherry=false
has_revert=false
merge_conflicted=false

_pending_has() {
  local want="$1"
  for item in "${pending[@]}"; do
    if [[ "$item" == "$want" ]]; then
      return 0
    fi
  done
  return 1
}

for head in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD; do
  if git rev-parse -q --verify "$head" >/dev/null 2>&1; then
    pending+=("$head")
    case "$head" in
      MERGE_HEAD) has_merge=true ;;
      CHERRY_PICK_HEAD) has_cherry=true ;;
      REVERT_HEAD) has_revert=true ;;
    esac
  fi
done

# A clean (no-conflict) 'cherry-pick --no-commit' sets no *_HEAD ref on git
# >=2.43 -- it uses AUTO_MERGE/MERGE_MSG instead. MERGE_MSG is always
# consumed and removed by a successful 'git commit' (fast-forward or real
# merge commit alike -- verified empirically), so its presence here is not
# a false-positive risk for normal completed work; it only lingers when a
# --no-commit operation prepared a message and nothing ever committed it.
if [[ -f "$(git rev-parse --git-path MERGE_MSG)" ]]; then
  pending+=("MERGE_MSG")
fi

# 'git merge --squash' leaves SQUASH_MSG but sets no MERGE_HEAD -- same
# silently-ships-the-pre-operation-tip risk class.
if [[ -f "$(git rev-parse --git-path SQUASH_MSG)" ]]; then
  pending+=("SQUASH_MSG")
fi

# An interactive or non-interactive rebase left uncommitted is the same
# risk class: rebase-merge/rebase-apply present means the branch tip is
# still pre-rebase. `git am` also uses rebase-apply/ internally (it's an
# am-based patch-apply session, not a rebase) -- distinguish via the
# `applying` marker file, which only exists during `git am`, never during
# an actual rebase (which uses `rebasing` instead). Reporting an am
# session as "REBASE" would point the operator at `git rebase --continue`/
# `--abort`, neither of which is the right recovery command here.
if [[ -d "$(git rev-parse --git-path rebase-merge)" ]]; then
  pending+=("REBASE")
elif [[ -f "$(git rev-parse --git-path rebase-apply/applying)" ]]; then
  pending+=("AM")
elif [[ -d "$(git rev-parse --git-path rebase-apply)" ]]; then
  pending+=("REBASE")
fi

if [[ ${#pending[@]} -eq 0 ]]; then
  exit 0
fi

if [[ "$has_merge" == true ]]; then
  if git diff --name-only --diff-filter=U | grep -q .; then
    merge_conflicted=true
  fi
fi

exit_code=1
symbol="GIT_PUSH_E_PENDING_MERGE_CLEAN"
if [[ "$merge_conflicted" == true ]]; then
  exit_code=2
  symbol="GIT_PUSH_E_PENDING_MERGE_CONFLICT"
elif [[ "$has_merge" == true ]]; then
  exit_code=1
  symbol="GIT_PUSH_E_PENDING_MERGE_CLEAN"
elif [[ "$has_cherry" == true ]]; then
  exit_code=3
  symbol="GIT_PUSH_E_PENDING_CHERRY_PICK"
elif [[ "$has_revert" == true ]]; then
  exit_code=4
  symbol="GIT_PUSH_E_PENDING_REVERT"
elif _pending_has AM; then
  exit_code=8
  symbol="GIT_PUSH_E_PENDING_AM"
elif _pending_has REBASE; then
  exit_code=7
  symbol="GIT_PUSH_E_PENDING_REBASE"
elif _pending_has SQUASH_MSG; then
  exit_code=6
  symbol="GIT_PUSH_E_PENDING_SQUASH"
elif _pending_has MERGE_MSG; then
  exit_code=5
  symbol="GIT_PUSH_E_PENDING_MERGE_MSG"
fi

hex_code=$(printf "0x%08X" "$exit_code")

echo "pre-push: blocked [$symbol] (exit $exit_code, $hex_code) — uncommitted in-progress operation(s): ${pending[*]}" >&2

for head in "${pending[@]}"; do
  case "$head" in
    MERGE_HEAD)
      if [[ "$merge_conflicted" == true ]]; then
        echo "  MERGE_HEAD: resolve and stage conflicts, then run 'git commit' to finalize the merge, or 'git merge --abort'." >&2
      else
        echo "  MERGE_HEAD: staged merge ready — run 'git commit' to finalize, or 'git merge --abort'." >&2
      fi
      ;;
    CHERRY_PICK_HEAD)
      echo "  CHERRY_PICK_HEAD: run 'git cherry-pick --continue' after resolving, or 'git cherry-pick --abort'." >&2
      ;;
    REVERT_HEAD)
      echo "  REVERT_HEAD: run 'git revert --continue' after resolving, or 'git revert --abort'." >&2
      ;;
    MERGE_MSG)
      echo "  MERGE_MSG: a --no-commit operation left a prepared message — run 'git commit' to finalize or abort the operation." >&2
      ;;
    SQUASH_MSG)
      echo "  SQUASH_MSG: a squash merge was prepared but not committed — run 'git commit' to finalize or discard the squash." >&2
      ;;
    REBASE)
      echo "  REBASE: an in-progress rebase is unfinished — run 'git rebase --continue' or 'git rebase --abort'." >&2
      ;;
    AM)
      echo "  AM: an in-progress 'git am' patch-apply session is unfinished — run 'git am --continue' or 'git am --abort'." >&2
      ;;
  esac
done

echo "  The branch tip you're about to push is still the PRE-operation commit." >&2
echo "  Finalize or abort the operation above, then push again." >&2
echo "  KB: bin/orama-system/skills/git-history-surgery/references/pending-operation-push-guard-reference-card.md" >&2

exit "$exit_code"
