#!/usr/bin/env bash
# Regression tests for commit-clean empty-commit guards and merge parent lineage.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
failures=0

fail() {
  echo "FAIL: $*" >&2
  failures=$((failures + 1))
}

pass() {
  echo "OK: $*"
}

run_in_repo() {
  local work="$1"
  shift
  (
    cd "$work"
    "$@"
  )
}

tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp" ${merge_tmp:+"$merge_tmp"} ${octopus_tmp:+"$octopus_tmp"}' EXIT

require_merge() {
  local repo="$1"
  local onto="$2"
  local branch="$3"
  git -C "$repo" checkout -q "$onto"
  if ! git -C "$repo" merge --no-commit --no-ff "$branch" >/dev/null 2>&1; then
    fail "merge --no-commit --no-ff ${branch} must succeed on ${onto}"
    return 1
  fi
  if [[ ! -f "$repo/.git/MERGE_HEAD" ]]; then
    fail "merge must create MERGE_HEAD for ${branch} onto ${onto}"
    return 1
  fi
}

git -C "$tmp" init -q
git -C "$tmp" config user.name "Test User"
git -C "$tmp" config user.email "codex@openai.com"
mkdir -p "$tmp/scripts/git"
for helper in commit-clean.sh verify-staged-for-commit.sh banned_attribution_lib.sh; do
  install -m 0755 "$SCRIPT_DIR/$helper" "$tmp/scripts/git/$helper"
done
printf 'base\n' >"$tmp/README.md"
git -C "$tmp" add README.md
git -C "$tmp" commit -q -m "init"

printf 'unstaged only\n' >"$tmp/README.md"

if run_in_repo "$tmp" bash "$SCRIPT_DIR/commit-clean.sh" -m "should fail unstaged" >/dev/null 2>&1; then
  fail "commit-clean must reject unstaged-only working tree"
else
  pass "blocks commit when edits are unstaged"
fi

if run_in_repo "$tmp" bash "$SCRIPT_DIR/verify-staged-for-commit.sh" >/dev/null 2>&1; then
  fail "verify-staged must reject empty index"
else
  pass "verify-staged rejects empty index"
fi

git -C "$tmp" add README.md
if ! run_in_repo "$tmp" bash "$SCRIPT_DIR/verify-staged-for-commit.sh" >/dev/null 2>&1; then
  fail "verify-staged must accept staged delta"
else
  pass "verify-staged accepts staged delta"
fi

sha="$(run_in_repo "$tmp" bash "$SCRIPT_DIR/commit-clean.sh" -m "staged commit")"
if [[ -z "$sha" ]]; then
  fail "commit-clean must return a sha for staged commit"
else
  pass "commit-clean succeeds with staged changes"
fi

if [[ "$(git -C "$tmp" rev-parse HEAD)" != "$sha" ]]; then
  fail "branch tip must advance after commit-clean"
else
  pass "branch tip advances"
fi

if ! git -C "$tmp" diff --quiet HEAD -- README.md; then
  fail "committed file must match staged content"
else
  pass "committed tree includes staged content"
fi

merge_tmp="$(mktemp -d)"
git -C "$merge_tmp" init -q
git -C "$merge_tmp" config user.name "Test User"
git -C "$merge_tmp" config user.email "codex@openai.com"
mkdir -p "$merge_tmp/scripts/git"
for helper in commit-clean.sh verify-staged-for-commit.sh banned_attribution_lib.sh; do
  install -m 0755 "$SCRIPT_DIR/$helper" "$merge_tmp/scripts/git/$helper"
done
printf 'main\n' >"$merge_tmp/README.md"
git -C "$merge_tmp" add README.md
git -C "$merge_tmp" commit -q -m "main init"
git -C "$merge_tmp" branch -M main
main_sha="$(git -C "$merge_tmp" rev-parse HEAD)"

git -C "$merge_tmp" checkout -q -b feature
printf 'feature\n' >"$merge_tmp/README.md"
git -C "$merge_tmp" add README.md
git -C "$merge_tmp" commit -q -m "feature change"
feature_sha="$(git -C "$merge_tmp" rev-parse HEAD)"

git -C "$merge_tmp" checkout -q main
if require_merge "$merge_tmp" main feature; then
printf 'merged\n' >"$merge_tmp/README.md"
git -C "$merge_tmp" add README.md

pre_dry_head="$(git -C "$merge_tmp" rev-parse HEAD)"
dry_out="$(run_in_repo "$merge_tmp" bash "$SCRIPT_DIR/commit-clean.sh" --dry-run -m "dry-run merge" 2>&1)"
if [[ "$(git -C "$merge_tmp" rev-parse HEAD)" != "$pre_dry_head" ]]; then
  fail "dry-run must not move branch tip"
else
  pass "dry-run leaves branch tip unchanged"
fi
if [[ ! -f "$merge_tmp/.git/MERGE_HEAD" ]]; then
  fail "dry-run must preserve MERGE_HEAD during in-progress merge"
else
  pass "dry-run preserves MERGE_HEAD"
fi
case "$dry_out" in
  *"merge in progress"*) pass "dry-run reports merge-aware parent retention" ;;
  *) fail "dry-run must mention merge in progress" ;;
esac

merge_sha="$(run_in_repo "$merge_tmp" bash "$SCRIPT_DIR/commit-clean.sh" -m "merge: feature into main")"
parent_count="$(git -C "$merge_tmp" show -s --format=%P "$merge_sha" | wc -w | tr -d ' ')"
if [[ "$parent_count" -ne 2 ]]; then
  fail "merge commit must retain two parents (got ${parent_count})"
else
  pass "merge commit retains two parents"
fi

first_parent="$(git -C "$merge_tmp" rev-parse "${merge_sha}^1")"
second_parent="$(git -C "$merge_tmp" rev-parse "${merge_sha}^2")"
if [[ "$first_parent" != "$main_sha" || "$second_parent" != "$feature_sha" ]]; then
  fail "merge parents must be main (${main_sha}) and feature (${feature_sha})"
else
  pass "merge parents match HEAD and MERGE_HEAD lineage"
fi

if [[ -f "$merge_tmp/.git/MERGE_HEAD" ]]; then
  fail "MERGE_HEAD must be cleared after commit-clean merge finalization"
else
  pass "MERGE_HEAD cleared after merge commit"
fi
fi

git -C "$merge_tmp" checkout -q -b mode-cleanup "$main_sha"
git -C "$merge_tmp" checkout -q -b feature2 "$feature_sha"
git -C "$merge_tmp" checkout -q mode-cleanup
if require_merge "$merge_tmp" mode-cleanup feature2; then
printf 'mode cleanup\n' >"$merge_tmp/README.md"
printf 'merge msg\n' >"$merge_tmp/.git/MERGE_MSG"
git -C "$merge_tmp" add README.md
run_in_repo "$merge_tmp" bash "$SCRIPT_DIR/commit-clean.sh" -m "merge: verify mode cleanup" >/dev/null
for artifact in MERGE_HEAD MERGE_MODE MERGE_MSG; do
  if [[ -f "$merge_tmp/.git/$artifact" ]]; then
    fail "$artifact must be cleared after commit-clean merge finalization"
  else
    pass "$artifact cleared after merge commit"
  fi
done
fi

git -C "$merge_tmp" checkout -q -b amend-target "$main_sha"
printf 'amend me\n' >"$merge_tmp/README.md"
git -C "$merge_tmp" add README.md
run_in_repo "$merge_tmp" bash "$SCRIPT_DIR/commit-clean.sh" -m "first" >/dev/null
printf '%s\n' "$feature_sha" >"$merge_tmp/.git/MERGE_HEAD"
printf 'amended\n' >"$merge_tmp/README.md"
git -C "$merge_tmp" add README.md
amend_sha="$(run_in_repo "$merge_tmp" bash "$SCRIPT_DIR/commit-clean.sh" --amend -m "amended")"
amend_parent_count="$(git -C "$merge_tmp" show -s --format=%P "$amend_sha" | wc -w | tr -d ' ')"
if [[ "$amend_parent_count" -ne 1 ]]; then
  fail "--amend must ignore MERGE_HEAD and keep a single parent (got ${amend_parent_count})"
else
  pass "--amend ignores MERGE_HEAD during merge state"
fi

rm -f \
  "$merge_tmp/.git/MERGE_HEAD" \
  "$merge_tmp/.git/MERGE_MODE" \
  "$merge_tmp/.git/MERGE_MSG"

git -C "$merge_tmp" checkout -q -b preserve-unstaged "$main_sha"
if require_merge "$merge_tmp" preserve-unstaged feature2; then
printf 'staged merge\n' >"$merge_tmp/README.md"
printf 'leave unstaged\n' >"$merge_tmp/UNSTAGED.txt"
git -C "$merge_tmp" add README.md
run_in_repo "$merge_tmp" bash "$SCRIPT_DIR/commit-clean.sh" -m "merge: preserve unstaged" >/dev/null
if [[ ! -f "$merge_tmp/UNSTAGED.txt" ]]; then
  fail "unstaged file must survive commit-clean merge commit"
elif git -C "$merge_tmp" ls-files --error-unmatch UNSTAGED.txt >/dev/null 2>&1; then
  fail "commit-clean must not stage unstaged files during merge commit"
else
  pass "unstaged untracked file preserved across merge commit-clean"
fi
if [[ "$(cat "$merge_tmp/UNSTAGED.txt")" != "leave unstaged" ]]; then
  fail "unstaged file contents must remain intact"
else
  pass "unstaged file contents intact"
fi
fi

single_parent_count="$(git -C "$tmp" show -s --format=%P "$sha" | wc -w | tr -d ' ')"
if [[ "$single_parent_count" -ne 1 ]]; then
  fail "non-merge commit must have exactly one parent (got ${single_parent_count})"
else
  pass "non-merge commit retains single parent"
fi

octopus_tmp="$(mktemp -d)"
git -C "$octopus_tmp" init -q
git -C "$octopus_tmp" config user.name "Test User"
git -C "$octopus_tmp" config user.email "codex@openai.com"
mkdir -p "$octopus_tmp/scripts/git"
for helper in commit-clean.sh verify-staged-for-commit.sh banned_attribution_lib.sh; do
  install -m 0755 "$SCRIPT_DIR/$helper" "$octopus_tmp/scripts/git/$helper"
done
printf 'base\n' >"$octopus_tmp/README.md"
git -C "$octopus_tmp" add README.md
git -C "$octopus_tmp" commit -q -m "base"
git -C "$octopus_tmp" branch -M main
octopus_main="$(git -C "$octopus_tmp" rev-parse HEAD)"

git -C "$octopus_tmp" checkout -q -b branch-a
printf 'a\n' >"$octopus_tmp/a.txt"
git -C "$octopus_tmp" add a.txt
git -C "$octopus_tmp" commit -q -m "branch a"
branch_a="$(git -C "$octopus_tmp" rev-parse HEAD)"

git -C "$octopus_tmp" checkout -q -b branch-b
printf 'b\n' >"$octopus_tmp/b.txt"
git -C "$octopus_tmp" add b.txt
git -C "$octopus_tmp" commit -q -m "branch b"
branch_b="$(git -C "$octopus_tmp" rev-parse HEAD)"

git -C "$octopus_tmp" checkout -q main
printf 'ab\n' >"$octopus_tmp/a.txt"
printf 'ab\n' >"$octopus_tmp/b.txt"
git -C "$octopus_tmp" add a.txt b.txt
{
  printf '%s\n' "$branch_a"
  printf '%s\n' "$branch_b"
} >"$octopus_tmp/.git/MERGE_HEAD"

octopus_sha="$(run_in_repo "$octopus_tmp" bash "$SCRIPT_DIR/commit-clean.sh" -m "merge: octopus")"
octopus_parent_count="$(git -C "$octopus_tmp" show -s --format=%P "$octopus_sha" | wc -w | tr -d ' ')"
if [[ "$octopus_parent_count" -ne 3 ]]; then
  fail "octopus merge commit must retain three parents (got ${octopus_parent_count})"
else
  pass "octopus merge retains three parents"
fi

if [[ "$(git -C "$octopus_tmp" rev-parse "${octopus_sha}^1")" != "$octopus_main" ]]; then
  fail "octopus first parent must be pre-merge HEAD"
else
  pass "octopus first parent is HEAD"
fi

if [[ "$failures" -gt 0 ]]; then
  echo "commit_clean_test: $failures failure(s)" >&2
  exit 1
fi

echo "commit_clean_test: all checks passed"
