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

CANON_ROOT="${GUARD_SYNC_CANON_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-$(cd "$CANON_ROOT/.." && pwd)}"
RC=0

_usage() {
  echo "usage: $0 --workspace | <target-repo-path>" >&2
  exit 2
}

_file_hash() {
  git hash-object "$1"
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

_scan_sibling() {
  local sibling_root="$1"
  local rel pair_rc=0

  [[ "$(cd "$sibling_root" && pwd)" == "$CANON_ROOT" ]] && return 0
  if ! git -C "$sibling_root" rev-parse --show-toplevel >/dev/null 2>&1; then
    return 0
  fi

  echo "== DIVERGENCE: $(basename "$sibling_root") vs canonical =="
  for rel in "${GUARD_PARITY_REQUIRED[@]}"; do
    _check_pair "$sibling_root" "$rel" || pair_rc=1
  done
  if [[ -d "$sibling_root/.githooks" ]]; then
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
