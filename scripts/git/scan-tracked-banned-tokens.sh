#!/usr/bin/env bash
# Fail if any gitignored banned token appears in tracked files (GitHub hygiene).
set -euo pipefail

if ! command -v rg >/dev/null 2>&1; then
  echo "ERROR: ripgrep ('rg') is required by this scanner but was not found in PATH." >&2
  echo "This scan cannot be trusted to report 'no banned tokens' without it -- install ripgrep and re-run." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=banned_attribution_lib.sh
source "$SCRIPT_DIR/banned_attribution_lib.sh"

cd "$REPO_ROOT"

if ! banned_patterns_ready "$REPO_ROOT"; then
  bash "$REPO_ROOT/scripts/cursor/sync-private-attribution-from-home.sh"
fi

# These internal bootstrap scripts legitimately reference the local-only
# .verboten-literals.local key name `forbidden_attribution`. Keep that
# structural exception line-scoped; do not exempt the entire file from banned
# value scanning.
SCAN_TRACKED_KEY_NAME_FILES=(
  scripts/cursor/write-openclaw-private-attribution.sh
  scripts/cursor/ci-bootstrap-private-attribution.sh
  scripts/cursor/seed-banned-attribution-patterns.sh
)

_is_key_name_file() {
  local rel="$1" allowed
  for allowed in "${SCAN_TRACKED_KEY_NAME_FILES[@]}"; do
    [[ "$rel" == "$allowed" ]] && return 0
  done
  return 1
}

_is_allowed_key_name_collision() {
  local rel="$1" token="$2" line="$3" token_lc
  token_lc="$(printf '%s' "$token" | tr '[:upper:]' '[:lower:]')"
  [[ "$token_lc" == "forbidden_attribution" ]] || return 1
  _is_key_name_file "$rel" || return 1
  [[ "$line" =~ list_private_literal_values[[:space:]].*[[:space:]]forbidden_attribution([[:space:]]|$) ]] && return 0
  [[ "$line" =~ (^|[^[:alnum:]_])forbidden_attribution= ]] && return 0
  return 1
}

errors=0
while IFS= read -r token; do
  [[ -n "$token" ]] || continue
  while IFS= read -r rel; do
    [[ -f "$rel" ]] || continue
    while IFS= read -r hit; do
      line="${hit#*:}"
      if _is_allowed_key_name_collision "$rel" "$token" "$line"; then
        continue
      fi
      echo "ERROR: banned token in tracked file: $rel" >&2
      errors=$((errors + 1))
      break
    done < <(rg -F -i -n -- "$token" "$rel" 2>/dev/null || true)
  done < <(git ls-files)
done < <(list_banned_pattern_tokens "$REPO_ROOT")

if [[ "$errors" -gt 0 ]]; then
  exit 1
fi
echo "OK: no banned tokens in tracked files"
