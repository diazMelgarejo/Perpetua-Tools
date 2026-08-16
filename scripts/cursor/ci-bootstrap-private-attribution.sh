#!/usr/bin/env bash
# Self-contained CI bootstrap for gitignored attribution patterns (no orama checkout required).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOME="${HOME:-/home/ubuntu}"
OPENCLAW="${HOME}/.cursor/openclaw"
PRIVATE="${REPO_ROOT}/.cursor/private"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$OPENCLAW/private-lessons" "$PRIVATE"
chmod 700 "$OPENCLAW" "$PRIVATE" 2>/dev/null || true

PATTERNS_OPENCLAW="${OPENCLAW}/banned-attribution-patterns"
if [[ -s "$PATTERNS_OPENCLAW" && -s "${PRIVATE}/banned-attribution-patterns" ]]; then
  printf 'OK: CI bootstrap already present → %s\n' "$PATTERNS_OPENCLAW"
  exit 0
fi

if ! bash "$SCRIPT_DIR/seed-banned-attribution-patterns.sh" "$PATTERNS_OPENCLAW" 2>/dev/null; then
  # No local-only registry available (expected in CI -- registries are
  # workspace-local by design, never checked into the repo; see
  # docs/v2/47-portable-memory-local-topology-invariant.md). Fall back to a
  # placeholder so the mandatory hooks-active/attribution-guard steps below
  # can still run; they don't depend on this file's literal contents.
  #
  # Deliberately not "fail closed" here (considered and rejected 2026-08-08,
  # CodeRabbit review 4890233271): the identity/author enforcement that
  # actually matters in CI (bad_author checks via identity-policy.json) does
  # not read this file at all and is unaffected either way. The one
  # consumer that does read it (scan-tracked-banned-tokens.sh's tracked-file
  # content scan) can never be meaningful in CI regardless of this fallback
  # -- the real registry is intentionally never present there by design, so
  # failing closed would only hard-block every PR's CI without closing a
  # real gap, reintroducing the exact incident this fallback fixed.
  # Not the former placeholder value -- that was a real word common in
  # real security docs/log messages and started matching genuine tracked
  # content once scan-tracked-banned-tokens.sh could actually find ripgrep
  # to run against it. Long, synthetic, and structurally unlike anything
  # a real token or real prose would ever contain, so it can never
  # collide with tracked content while still keeping the file non-empty
  # (banned_patterns_ready() requires that). Assembled at runtime via
  # concatenation, not written as one literal, so this script's own
  # source never contains the substring the scanner would then flag.
  _placeholder_token="ci-placeholder-pattern"
  _placeholder_token+="-never-matches-real-content-7f3ae9c1"
  {
    echo "# Banned attribution tokens (one per line, case-insensitive substring match)"
    echo "$_placeholder_token"
  } >"$PATTERNS_OPENCLAW"
  chmod 600 "$PATTERNS_OPENCLAW"
  unset _placeholder_token
fi
install -m 0600 "$PATTERNS_OPENCLAW" "${PRIVATE}/banned-attribution-patterns"

printf 'OK: CI bootstrap → %s and %s\n' "$PATTERNS_OPENCLAW" "${PRIVATE}/banned-attribution-patterns"
