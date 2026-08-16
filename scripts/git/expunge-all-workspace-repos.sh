#!/usr/bin/env bash
# Expunge banned Co-authored-by trailers from every repo under a workspace root, then force-push all branches.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-/agent/repos}"
EXPUNGE="$SCRIPT_DIR/expunge-banned-attribution-history.sh"
SYNC="$SCRIPT_DIR/sync-banned-patterns-to-repo.sh"
PUSH_ALL="${PUSH_ALL:-1}"

HOME="${HOME:-/home/ubuntu}"
export HOME PERPETUA_TOOLS_GUARD="$PT_ROOT"

if [[ -x "${ORAMA_SYSTEM_PATH:-}/scripts/cursor/write-openclaw-private-attribution.sh" ]]; then
  bash "${ORAMA_SYSTEM_PATH}/scripts/cursor/write-openclaw-private-attribution.sh"
elif [[ -x /agent/repos/orama-system/scripts/cursor/write-openclaw-private-attribution.sh ]]; then
  bash /agent/repos/orama-system/scripts/cursor/write-openclaw-private-attribution.sh
fi

if [[ -x "$PT_ROOT/scripts/git/neutralize-cursor-coauthor-hook.sh" ]]; then
  bash "$PT_ROOT/scripts/git/neutralize-cursor-coauthor-hook.sh" --all-agent-hooks
fi

scan_repo_hits() {
  local repo="$1"
  # shellcheck source=banned_attribution_lib.sh
  source "$PT_ROOT/scripts/git/banned_attribution_lib.sh"
  local hits=0 h ae_lc an_lc ce_lc cn_lc body_lc
  while IFS= read -r h; do
    ae_lc="$(git -C "$repo" log -1 --format=%ae "$h" | tr '[:upper:]' '[:lower:]')"
    an_lc="$(git -C "$repo" log -1 --format=%an "$h" | tr '[:upper:]' '[:lower:]')"
    ce_lc="$(git -C "$repo" log -1 --format=%ce "$h" | tr '[:upper:]' '[:lower:]')"
    cn_lc="$(git -C "$repo" log -1 --format=%cn "$h" | tr '[:upper:]' '[:lower:]')"
    body_lc="$(git -C "$repo" log -1 --format=%B "$h" | tr '[:upper:]' '[:lower:]')"
    metadata_contains_scrub_target "$ae_lc" "$an_lc" "$ce_lc" "$cn_lc" "$body_lc" "$repo" \
      && hits=$((hits + 1))
  done < <(git -C "$repo" rev-list --all 2>/dev/null)
  printf '%s' "$hits"
}

force_push_repo() {
  local repo="$1"
  git -C "$repo" remote get-url origin >/dev/null 2>&1 || return 0
  local hs_git=(git -C "$repo" -c core.hooksPath=/dev/null)
  if [[ -x "$SCRIPT_DIR/history-surgery-git.sh" ]]; then
    hs_git=("$SCRIPT_DIR/history-surgery-git.sh" -C "$repo")
  fi
  local branch old_sha failed=0
  while IFS= read -r branch; do
    [[ -n "$branch" ]] || continue
    old_sha=""
    if git -C "$repo" show-ref --verify --quiet "refs/remotes/origin/$branch"; then
      old_sha="$(git -C "$repo" rev-parse "origin/$branch")"
    fi
    if [[ -n "$old_sha" ]]; then
      "${hs_git[@]}" push --force-with-lease="refs/heads/${branch}:${old_sha}" \
        origin "${branch}:${branch}" || {
        echo "warn: lease push failed ${branch} in $(basename "$repo"); fetch/review and retry" >&2
        failed=$((failed + 1))
      }
    else
      "${hs_git[@]}" push -u origin "${branch}:${branch}" || {
        echo "warn: push failed new branch ${branch} in $(basename "$repo")" >&2
        failed=$((failed + 1))
      }
    fi
  done < <(git -C "$repo" for-each-ref refs/heads --format='%(refname:short)')
  return $(( failed > 0 ? 1 : 0 ))
}

expunge_repo() {
  local repo="$1"
  local name
  name="$(basename "$repo")"
  [[ -d "${repo}/.git" ]] || return 0
  local stashed=0 cleanup_hooks=0

  cleanup_expunge_repo() {
    local cleanup_failed=0
    if [[ "$stashed" == "1" ]]; then
      git -C "$repo" -c core.hooksPath=/dev/null stash pop >/dev/null 2>&1 || cleanup_failed=1
      stashed=0
      cleanup_hooks=1
    fi
    if [[ "$cleanup_hooks" == "1" && -x "$repo/scripts/git/install-local-hooks.sh" ]]; then
      bash "$repo/scripts/git/install-local-hooks.sh" >/dev/null 2>&1 || cleanup_failed=1
      cleanup_hooks=0
    fi
    unset HISTORY_SURGERY_ACTIVE
    return "$cleanup_failed"
  }

  trap 'status=$?; trap - RETURN; cleanup_status=0; cleanup_expunge_repo || cleanup_status=$?; if [[ $status -ne 0 ]]; then return $status; fi; return $cleanup_status' RETURN

  echo ">>> [$name] fetch"
  git -C "$repo" fetch origin --prune 2>/dev/null || true

  bash "$SYNC" "$repo"

  local before after
  before="$(scan_repo_hits "$repo")"
  echo ">>> [$name] banned metadata hits before expunge: $before"
  if [[ "$before" -eq 0 ]]; then
    echo ">>> [$name] clean — skip history rewrite and force-push"
    return 0
  fi

  echo ">>> [$name] filter-branch (all refs)"
  if ! git -C "$repo" diff-index --quiet HEAD -- 2>/dev/null \
    || ! git -C "$repo" diff-index --quiet --cached HEAD -- 2>/dev/null; then
    if git -C "$repo" stash push -u -m "attribution-expunge-autostash" >/dev/null 2>&1; then
      stashed=1
    fi
  fi
  bash "$EXPUNGE" "$repo"
  cleanup_expunge_repo

  after="$(scan_repo_hits "$repo")"
  echo ">>> [$name] banned metadata hits after expunge: $after"
  if [[ "$after" -ne 0 ]]; then
    echo "ERROR: [$name] still has banned attribution metadata after expunge" >&2
    return 1
  fi

  if [[ "$PUSH_ALL" == "1" ]]; then
    echo ">>> [$name] force-push all local branches (hooks off — history surgery)"
    export HISTORY_SURGERY_ACTIVE=1
    cleanup_hooks=1
    local push_status=0
    force_push_repo "$repo" || push_status=$?
    cleanup_expunge_repo
    if [[ "$push_status" -ne 0 ]]; then
      echo "ERROR: [$name] force-push had failures" >&2
      return 1
    fi
  fi
  echo ">>> [$name] OK"
}

shopt -s nullglob
repos=("$WORKSPACE_ROOT"/*)
if [[ ! -d "$WORKSPACE_ROOT" ]]; then
  echo "ERROR: workspace root not found: $WORKSPACE_ROOT" >&2
  exit 1
fi

failed=0
for repo in "${repos[@]}"; do
  [[ -d "$repo/.git" ]] || continue
  expunge_repo "$repo" || failed=$((failed + 1))
done

if [[ "$failed" -gt 0 ]]; then
  echo "expunge-all-workspace-repos: $failed repo(s) failed" >&2
  exit 1
fi
echo "OK: workspace expunge complete (${#repos[@]} roots scanned)"
