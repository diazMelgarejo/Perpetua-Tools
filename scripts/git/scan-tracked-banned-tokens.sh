#!/usr/bin/env bash
# Fail if any gitignored banned token appears in tracked files (GitHub hygiene).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=banned_attribution_lib.sh
source "$SCRIPT_DIR/banned_attribution_lib.sh"

cd "$REPO_ROOT"

if ! banned_patterns_ready "$REPO_ROOT"; then
  bash "$REPO_ROOT/scripts/cursor/sync-private-attribution-from-home.sh"
fi

# Local-only seed/bootstrap scripts may reference runtime registries; never scan them.
SCAN_TRACKED_ALLOWLIST=(
  scripts/cursor/write-openclaw-private-attribution.sh
  scripts/cursor/ci-bootstrap-private-attribution.sh
  scripts/cursor/seed-banned-attribution-patterns.sh
)

_is_allowlisted() {
  local rel="$1" allowed
  for allowed in "${SCAN_TRACKED_ALLOWLIST[@]}"; do
    [[ "$rel" == "$allowed" ]] && return 0
  done
  return 1
}

errors=0
while IFS= read -r token; do
  [[ -n "$token" ]] || continue
  while IFS= read -r rel; do
    [[ -f "$rel" ]] || continue
    if _is_allowlisted "$rel"; then
      continue
    fi
    if rg -F -i -q "$token" "$rel" 2>/dev/null; then
      echo "ERROR: banned token in tracked file: $rel" >&2
      errors=$((errors + 1))
    fi
  done < <(git ls-files)
done < <(list_banned_pattern_tokens "$REPO_ROOT")

if [[ "$errors" -gt 0 ]]; then
  exit 1
fi
echo "OK: no banned tokens in tracked files"
