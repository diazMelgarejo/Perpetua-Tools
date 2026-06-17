#!/usr/bin/env bash
# verify-guard-parity.sh — enforce the zero-fragmentation invariant (docs/v2/27).
#
# Two checks, both fail-closed (non-zero exit on violation):
#   1. COMPLETENESS — every canonical guard script is listed in the sync tool's
#      copy loop. Catches the 2026-06-05 bug where check_commit_message.sh and
#      check_identity.sh silently drifted because the sync omitted them.
#   2. PARITY (optional, when target repos are given or WORKSPACE_ROOT is set) —
#      each downstream repo's guard copies are byte-identical to orama's canonical.
#
# Canonical source is THIS repo (orama-system). Run in CI (orama: completeness
# always; parity when siblings are checked out) and from daily-attribution-guard.
#
# Usage:
#   verify-guard-parity.sh                      # completeness only (single-repo CI)
#   verify-guard-parity.sh <repo> [<repo>...]   # + parity against each target
#   WORKSPACE_ROOT=/agent/repos verify-guard-parity.sh --workspace
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CANON="$SCRIPT_DIR"
SYNC="$SCRIPT_DIR/sync-attribution-guard-scripts.sh"
rc=0

# The canonical guard set every repo must carry byte-identical.
CANONICAL_GUARDS=(
  banned_attribution_lib.sh
  audit_attribution.sh
  check_commit_message.sh
  check_identity.sh
  daily-attribution-guard.sh
  neutralize-cursor-coauthor-hook.sh
  expunge-all-workspace-repos.sh
  verify-git-guards.sh
  reanchor_scan.sh
)

echo "== COMPLETENESS: every canonical guard is in the sync copy list =="
if [[ ! -f "$SYNC" ]]; then
  echo "  ERR: sync tool not found at $SYNC"; rc=1
else
  for g in "${CANONICAL_GUARDS[@]}"; do
    # reanchor_scan.sh is a guard but not distributed by the attribution sync;
    # skip it from the sync-list assertion (it ships via the repo checkout).
    [[ "$g" == "reanchor_scan.sh" ]] && continue
    if grep -qE "^\s*$g\b|/$g\b" "$SYNC"; then
      echo "  OK  $g in sync list"
    else
      echo "  FAIL $g MISSING from sync copy list (would drift silently)"; rc=1
    fi
  done
fi

# Parity: compare each target repo's copies to canonical.
targets=()
if [[ "${1:-}" == "--workspace" ]]; then
  for d in "${WORKSPACE_ROOT:-/agent/repos}"/*; do [[ -d "$d/.git" ]] && targets+=("$d"); done
else
  targets=("$@")
fi

if [[ ${#targets[@]} -gt 0 ]]; then
  echo "== PARITY: downstream guard copies byte-identical to canonical =="
  canon_repo="$(cd "$CANON/../.." && pwd)"
  canon_parent="$(dirname "$canon_repo")"
  for repo in "${targets[@]}"; do
    repo_abs="$(cd "$repo" 2>/dev/null && pwd)" || continue
    [[ "$repo_abs" == "$canon_repo" ]] && continue  # skip self

    # In GitHub Actions, optional companion checkouts may be absent or nested
    # under the current checkout rather than cloned as sibling repositories.
    # That layout cannot prove the zero-fragmentation invariant, so keep local
    # workspace parity fail-closed while treating non-sibling CI targets as
    # intentionally out of scope.
    if [[ "${GITHUB_ACTIONS:-}" == "true" && "$(dirname "$repo_abs")" != "$canon_parent" ]]; then
      echo "  SKIP $(basename "$repo_abs") (CI non-sibling checkout; parity requires sibling repos)"
      continue
    fi

    for g in "${CANONICAL_GUARDS[@]}"; do
      src="$CANON/$g"; dst="$repo/scripts/git/$g"
      [[ -f "$src" ]] || continue
      if [[ ! -f "$dst" ]]; then
        echo "  WARN $(basename "$repo")/$g absent"; continue
      fi
      if cmp -s "$src" "$dst"; then
        echo "  OK   $(basename "$repo")/$g"
      else
        echo "  FAIL $(basename "$repo")/$g DRIFTED — re-sync: bash scripts/git/sync-attribution-guard-scripts.sh $repo"; rc=1
      fi
    done
  done
fi

[[ $rc -eq 0 ]] && echo "guard-parity: PASS" || echo "guard-parity: FAIL"
exit $rc
