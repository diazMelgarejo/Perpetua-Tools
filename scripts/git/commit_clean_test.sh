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
trap 'rm -rf "$tmp"' EXIT

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
git -C "$merge_tmp" merge --no-commit --no-ff feature >/dev/null 2>&1 || true
printf 'merged\n' >"$merge_tmp/README.md"
git -C "$merge_tmp" add README.md

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
