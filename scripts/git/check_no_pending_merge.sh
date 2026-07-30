#!/usr/bin/env bash
# Block push while a --no-commit merge/cherry-pick/revert is still uncommitted.
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
for head in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD; do
  if git rev-parse -q --verify "$head" >/dev/null 2>&1; then
    pending+=("$head")
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
# still pre-rebase.
if [[ -d "$(git rev-parse --git-path rebase-merge)" ]] || [[ -d "$(git rev-parse --git-path rebase-apply)" ]]; then
  pending+=("REBASE")
fi

if [[ ${#pending[@]} -gt 0 ]]; then
  echo "pre-push: blocked — uncommitted in-progress operation(s): ${pending[*]}" >&2
  echo "  A --no-commit merge/cherry-pick/revert was never finalized with 'git commit'." >&2
  echo "  The branch tip you're about to push is still the PRE-operation commit." >&2
  echo "  Run 'git commit' to finalize it, or the matching '--abort' to discard it," >&2
  echo "  then push again." >&2
  exit 1
fi

exit 0
