#!/usr/bin/env bash
# check-guard-sync-divergence.sh — fail-closed anti-clobber guard for guard sync.
#
# Before sync-attribution-guard-scripts.sh overwrites downstream copies, verify
# every workspace sibling's manifest paths are either:
#   • byte-identical to canonical HEAD, or
#   • lagging a blob that already exists in canonical git history (safe upgrade).
#
# Abort (HITL) when a sibling carries mutations absent from canonical history —
# promote sibling → orama canonical first, then sync downstream.
#
# Usage:
#   check-guard-sync-divergence.sh --workspace
#   check-guard-sync-divergence.sh <target-repo-path>
#
# Exit: 0 safe | 1 divergence (GUARD_SYNC_E_DIVERGENCE) | 2 usage error
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=guard-sync-manifest.sh
source "$SCRIPT_DIR/guard-sync-manifest.sh"
# shellcheck source=resolve_sibling_git_repo.sh
source "$SCRIPT_DIR/resolve_sibling_git_repo.sh"

# Git hooks export repository-local GIT_* variables. This checker deliberately
# runs git against other repositories, so retaining the hook's GIT_DIR can
# rebind every `git -C <sibling>` call to the pushing checkout. Clear Git's
# documented local environment set before resolving or comparing siblings.
while IFS= read -r git_local_env; do
  unset "$git_local_env"
done < <(git rev-parse --local-env-vars)

# Canonical-root resolution: never self-nominate as canonical just because
# this script happens to be invoked from a given checkout (see ECC push-gate
# analysis 2026-08-14 § Canonical-Root Mismatch — a downstream checkout
# self-labeled canonical while also telling the operator to promote its own
# changes to the real canonical, an internally inconsistent result).
#
#   1. GUARD_SYNC_CANON_ROOT explicitly set  -> honor it (existing contract).
#   2. This checkout carries the orama-system marker itself -> it genuinely
#      IS canonical; self-as-canonical is correct here, not a self-nomination.
#   3. Otherwise (a downstream checkout, e.g. Perpetua-Tools or AlphaClaw)
#      -> auto-resolve the real orama-system sibling via the same generic
#      marker-based crawl this repo family already uses elsewhere (parent
#      dir, then mother dir, depth 2 each — covers a repo nested one level
#      deeper than expected, e.g. Perpetua-Tools under perplexity-api/).
#      Self-contained here (no dependency on a downstream-repo-specific
#      resolver script) so this file behaves correctly in every repo it
#      gets synced into, not just Perpetua-Tools. If no unambiguous sibling
#      is found, fail with an actionable configuration error — never fall
#      back to self.
_SELF_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
_ORAMA_MARKER="bin/orama-system/SKILL.md"

if [[ -n "${GUARD_SYNC_CANON_ROOT:-}" ]]; then
  CANON_ROOT="$GUARD_SYNC_CANON_ROOT"
elif sibling_repo_is_git_root "$_SELF_ROOT" "$_ORAMA_MARKER"; then
  CANON_ROOT="$_SELF_ROOT"
else
  _parent_dir="$(cd "$_SELF_ROOT/.." && pwd)"
  _mother_dir="$(cd "$_SELF_ROOT/../.." && pwd)"
  sibling_repo_reset_candidates
  sibling_repo_crawl_collect "$_parent_dir" "$_ORAMA_MARKER" 2
  if [[ "$_mother_dir" != "$_parent_dir" ]]; then
    sibling_repo_crawl_collect "$_mother_dir" "$_ORAMA_MARKER" 2
  fi
  if ! CANON_ROOT="$(sibling_repo_finalize "orama-system")"; then
    echo "check-guard-sync-divergence: this checkout ($_SELF_ROOT) is not the orama-system canonical repo, and no unambiguous orama-system sibling was found nearby." >&2
    echo "  Set GUARD_SYNC_CANON_ROOT=<path-to-orama-system> explicitly and retry." >&2
    exit 2
  fi
fi

WORKSPACE_ROOT="${WORKSPACE_ROOT:-$(cd "$CANON_ROOT/.." && pwd)}"
RC=0

_usage() {
  echo "usage: $0 --workspace | <target-repo-path>" >&2
  exit 2
}

_file_hash() {
  git hash-object "$1"
}

_git_common_dir() {
  local root="$1" common

  common="$(git -C "$root" rev-parse --git-common-dir 2>/dev/null)" || return 1
  if [[ "$common" != /* ]]; then
    common="$root/$common"
  fi
  cd "$common" 2>/dev/null && pwd -P
}

# Return 0 when $want_hash appears as <prefix>/$rel at any commit in $repo.
_blob_in_repo_history() {
  local repo="$1" rel="$2" want="$3" prefix="${4:-scripts/git}"
  local gitrel="$prefix/$rel" sha got

  [[ -n "$want" ]] || return 1
  while IFS= read -r sha; do
    [[ -z "$sha" ]] && continue
    got="$(git -C "$repo" show "$sha:$gitrel" 2>/dev/null | git hash-object --stdin)" || continue
    [[ "$got" == "$want" ]] && return 0
  done < <(git -C "$repo" log --all --format=%H -- "$gitrel" 2>/dev/null || true)
  return 1
}

_check_pair() {
  local sibling_root="$1" rel="$2" prefix="${3:-scripts/git}"
  local canon_f="$CANON_ROOT/$prefix/$rel"
  local sib_f="$sibling_root/$prefix/$rel"
  local canon_hash sib_hash

  [[ -f "$canon_f" ]] || return 0
  [[ -f "$sib_f" ]] || return 0

  if cmp -s "$canon_f" "$sib_f"; then
    echo "  OK   $(basename "$sibling_root")/$prefix/$rel (byte-identical)"
    return 0
  fi

  canon_hash="$(_file_hash "$canon_f")"
  sib_hash="$(_file_hash "$sib_f")"

  if _blob_in_repo_history "$CANON_ROOT" "$rel" "$sib_hash" "$prefix"; then
    echo "  OK   $(basename "$sibling_root")/$prefix/$rel (lags canonical history — safe to upgrade)"
    return 0
  fi

  if _blob_in_repo_history "$sibling_root" "$rel" "$canon_hash" "$prefix"; then
    echo "  FAIL $(basename "$sibling_root")/$prefix/$rel — canonical lags sibling (promote sibling → orama first)"
  else
    echo "  FAIL $(basename "$sibling_root")/$prefix/$rel — sibling mutations absent from canonical history"
  fi
  return 1
}

_repo_uses_githooks() {
  local root="$1" hooks_path hooks_abs expected_abs
  if [[ -f "$root/.githooks/.guard-sync-opt-in" ]]; then
    return 0
  fi
  hooks_path="$(git -C "$root" config --path --get core.hooksPath 2>/dev/null || true)"
  [[ -n "$hooks_path" ]] || return 1
  if [[ "$hooks_path" == /* ]]; then
    hooks_abs="$(cd "$hooks_path" 2>/dev/null && pwd -P)" || return 1
  else
    hooks_abs="$(cd "$root/$hooks_path" 2>/dev/null && pwd -P)" || return 1
  fi
  expected_abs="$(cd "$root/.githooks" 2>/dev/null && pwd -P)" || return 1
  [[ "$hooks_abs" == "$expected_abs" ]]
}

_scan_sibling() {
  local sibling_root="$1" canon_common sibling_common
  local rel pair_rc=0

  [[ "$(cd "$sibling_root" && pwd)" == "$CANON_ROOT" ]] && return 0
  if ! git -C "$sibling_root" rev-parse --show-toplevel >/dev/null 2>&1; then
    return 0
  fi

  # Linked worktrees of the canonical repository are alternate checkouts of
  # the same guard authority, not downstream mirror targets. Sync never
  # overwrites them, so a pre-merge worktree must not block syncing a real
  # downstream repository. Independent repositories still take the strict
  # per-file history check below.
  canon_common="$(_git_common_dir "$CANON_ROOT")" || return 1
  sibling_common="$(_git_common_dir "$sibling_root")" || return 1
  if [[ "$sibling_common" == "$canon_common" ]]; then
    echo "== DIVERGENCE: $(basename "$sibling_root") shares canonical git history; skipped =="
    return 0
  fi

  echo "== DIVERGENCE: $(basename "$sibling_root") vs canonical =="
  for rel in "${GUARD_PARITY_REQUIRED[@]}"; do
    _check_pair "$sibling_root" "$rel" || pair_rc=1
  done
  if _repo_uses_githooks "$sibling_root"; then
    for rel in "${GUARD_SYNC_GITHOOKS[@]}"; do
      _check_pair "$sibling_root" "$rel" ".githooks" || pair_rc=1
    done
  fi
  return "$pair_rc"
}

_collect_targets() {
  TARGETS=()
  if [[ "${1:-}" == "--workspace" ]]; then
    # Depth-2 crawl, not a flat one-level glob: a sibling repo nested one
    # level deeper than expected (e.g. Perpetua-Tools under
    # perplexity-api/Perpetua-Tools) is otherwise silently skipped, giving
    # false confidence that guard scripts are in sync everywhere when a
    # whole repo was never checked. Explicit-path mode (below) is
    # unaffected and remains the reliable fallback for any layout.
    # shellcheck source=resolve_sibling_git_repo.sh
    source "$SCRIPT_DIR/resolve_sibling_git_repo.sh"
    sibling_repo_reset_candidates
    sibling_repo_crawl_collect "$WORKSPACE_ROOT" "" 2
    if ((${#_sibling_repo_candidates[@]} > 0)); then
      local cand
      for cand in "${_sibling_repo_candidates[@]}"; do
        # Match the old behavior: children of WORKSPACE_ROOT, never the
        # workspace root itself even if it happens to be a git repo.
        [[ "$cand" == "$WORKSPACE_ROOT" ]] && continue
        TARGETS+=("$cand")
      done
    fi
    return 0
  fi
  if [[ -n "${1:-}" ]]; then
    local root
    root="$(git -C "$1" rev-parse --show-toplevel 2>/dev/null)" || {
      echo "error: not a git repository: $1" >&2
      exit 2
    }
    TARGETS=("$root")
    return 0
  fi
  _usage
}

[[ $# -eq 1 ]] || _usage
_collect_targets "$@"

echo "== GUARD SYNC DIVERGENCE (canonical=$(basename "$CANON_ROOT")) =="
for repo in "${TARGETS[@]}"; do
  _scan_sibling "$repo" || RC=1
done

if [[ $RC -ne 0 ]]; then
  echo >&2
  echo "guard-sync-divergence: FAIL (GUARD_SYNC_E_DIVERGENCE)" >&2
  echo "  HITL: commit sibling improvements, promote them to orama canonical," >&2
  echo "        then run sync-attribution-guard-scripts.sh downstream." >&2
  echo "  Do NOT sync until canonical absorbs the advanced sibling mutations." >&2
  echo "  Skill: bin/orama-system/skills/guard-sync-divergence-guard/SKILL.md" >&2
  exit 1
fi

echo "guard-sync-divergence: PASS"
exit 0
