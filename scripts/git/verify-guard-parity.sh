#!/usr/bin/env bash
# verify-guard-parity.sh — enforce the zero-fragmentation invariant (docs/v2/27).
#
# Checks (fail-closed):
#   1. MANIFEST — every GUARD_PARITY_REQUIRED path exists on disk in canonical repo.
#   2. SYNC BINDING — sync-attribution-guard-scripts.sh sources guard-sync-manifest.sh.
#   3. PARITY (optional) — downstream copies byte-identical to orama canonical.
#
# Canonical source is THIS repo (orama-system). Run in CI and daily-attribution-guard.
#
# Usage:
#   verify-guard-parity.sh                      # manifest + sync binding (single-repo CI)
#   verify-guard-parity.sh <repo> [<repo>...]   # + parity against each target
#   WORKSPACE_ROOT=/agent/repos verify-guard-parity.sh --workspace
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CANON="$SCRIPT_DIR"
SYNC="$SCRIPT_DIR/sync-attribution-guard-scripts.sh"
# shellcheck source=guard-sync-manifest.sh
source "$SCRIPT_DIR/guard-sync-manifest.sh"
rc=0

echo "== MANIFEST: canonical guard files exist =="
for rel in "${GUARD_PARITY_REQUIRED[@]}"; do
  if [[ -f "$CANON/$rel" ]]; then
    echo "  OK  $rel"
  else
    echo "  FAIL $rel missing from canonical scripts/git/"; rc=1
  fi
done

echo "== SYNC BINDING: sync tool uses guard-sync-manifest.sh =="
if [[ ! -f "$SYNC" ]]; then
  echo "  ERR: sync tool not found at $SYNC"; rc=1
elif grep -Eq '^[[:space:]]*(source|\.)[[:space:]]+.*guard-sync-manifest\.sh' "$SYNC"; then
  echo "  OK  sync-attribution-guard-scripts.sh sources manifest"
else
  echo "  FAIL sync tool does not source guard-sync-manifest.sh (lists would drift)"; rc=1
fi

targets=()
if [[ "${1:-}" == "--workspace" ]]; then
  for d in "${WORKSPACE_ROOT:-/agent/repos}"/*; do [[ -d "$d/.git" ]] && targets+=("$d"); done
else
  targets=("$@")
fi

if [[ ${#targets[@]} -gt 0 ]]; then
  echo "== PARITY: downstream guard copies byte-identical to canonical =="
  for repo in "${targets[@]}"; do
    canon_root="$(cd "$CANON/../.." && pwd)"
    if ! repo_root="$(cd "$repo" 2>/dev/null && pwd)"; then
      echo "  FAIL cannot access target repository: $repo"; rc=1
      continue
    fi
    [[ "$repo_root" == "$canon_root" ]] && continue
    for rel in "${GUARD_PARITY_REQUIRED[@]}"; do
      src="$CANON/$rel"
      dst="$repo/scripts/git/$rel"
      [[ -f "$src" ]] || continue
      if [[ ! -f "$dst" ]]; then
        echo "  FAIL $(basename "$repo")/$rel absent — run: bash scripts/git/sync-attribution-guard-scripts.sh $repo"; rc=1
        continue
      fi
      if cmp -s "$src" "$dst"; then
        echo "  OK   $(basename "$repo")/$rel"
      else
        echo "  FAIL $(basename "$repo")/$rel DRIFTED — re-sync: bash scripts/git/sync-attribution-guard-scripts.sh $repo"; rc=1
      fi
    done
  done
fi

[[ $rc -eq 0 ]] && echo "guard-parity: PASS" || echo "guard-parity: FAIL"
exit $rc
