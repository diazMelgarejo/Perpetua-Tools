#!/usr/bin/env bash
# Self-contained CI bootstrap for gitignored attribution patterns (no orama checkout required).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOME="${HOME:-/home/ubuntu}"
OPENCLAW="${HOME}/.cursor/openclaw"
PRIVATE="${REPO_ROOT}/.cursor/private"

mkdir -p "$OPENCLAW/private-lessons" "$PRIVATE"
chmod 700 "$OPENCLAW" "$PRIVATE" 2>/dev/null || true

PATTERNS_OPENCLAW="${OPENCLAW}/banned-attribution-patterns"
if [[ -s "$PATTERNS_OPENCLAW" && -s "${PRIVATE}/banned-attribution-patterns" ]]; then
  printf 'OK: CI bootstrap already present → %s\n' "$PATTERNS_OPENCLAW"
  exit 0
fi

# Never hardcode a real banned identity in this tracked script (it would
# itself trip scan-tracked-banned-tokens.sh). Source it from a CI secret env
# var first, falling back to an already-materialized local ignored file if
# one exists from a prior bootstrap on this machine. If neither is
# available (fresh checkout, no secret configured -- e.g. local dev or this
# repo's own test suite), fall back to an obviously-synthetic placeholder
# token so the bootstrap still succeeds and downstream guards still have a
# non-empty patterns file to check against, without ever embedding a real
# identity literal in tracked source.
TOKEN="${PT_BANNED_ATTRIBUTION_TOKEN:-}"
if [[ -z "$TOKEN" && -s "${PRIVATE}/banned-attribution-patterns" ]]; then
  TOKEN="$(grep -v '^#' "${PRIVATE}/banned-attribution-patterns" | head -1)"
fi
if [[ -z "$TOKEN" ]]; then
  TOKEN="unconfigured-banned-attribution-placeholder"
fi

{
  echo "# Banned attribution tokens (one per line, case-insensitive substring match)"
  printf '%s\n' "$TOKEN"
} >"$PATTERNS_OPENCLAW"
chmod 600 "$PATTERNS_OPENCLAW"
install -m 0600 "$PATTERNS_OPENCLAW" "${PRIVATE}/banned-attribution-patterns"

printf 'OK: CI bootstrap → %s and %s\n' "$PATTERNS_OPENCLAW" "${PRIVATE}/banned-attribution-patterns"
