#!/usr/bin/env bash
# Pre-commit glue (Perpetua-Tools side): verify this repo's generated docs/adr
# pointers are in sync with the canonical orama-system docs/v2 collection. The sync
# LOGIC is canonical in orama (scripts/git/sync-docs-v2-pointers.sh) — we only
# locate orama and delegate, never fork the script (zero-fragmentation doctrine,
# orama docs/v2/27-git-governance-zero-fragmentation.md). Skips gracefully when
# orama is not a sibling (e.g. GitHub CI), so it never blocks a clean commit.
set -euo pipefail
PT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PT_PARENT="$(dirname "$PT_ROOT")"
ORAMA_RESOLVER="$PT_ROOT/scripts/resolve_orama_root.sh"

if [[ -n "${ORAMA_ROOT:-}" ]]; then
  orama_root_abs="$(cd "$ORAMA_ROOT" 2>/dev/null && pwd)" || orama_root_abs=""
  if [[ -n "$orama_root_abs" && "${GITHUB_ACTIONS:-}" == "true" && "$(dirname "$orama_root_abs")" != "$PT_PARENT" ]]; then
    echo "skip: orama-system is not a sibling in CI: $orama_root_abs" >&2
    exit 0
  fi
fi

for cand in "${ORAMA_ROOT:-}" \
            "$(source "$ORAMA_RESOLVER" >/dev/null 2>&1 && resolve_orama_root 2>/dev/null || true)"; do
  [[ -n "$cand" ]] || continue
  cand_abs="$(cd "$cand" 2>/dev/null && pwd)" || continue

  # GitHub Actions checks out optional companion repos under $GITHUB_WORKSPACE by
  # default (for example, $PT_ROOT/orama-system), which is not the sibling layout
  # required by the zero-fragmentation pointer check. Treat those nested/non-sibling
  # CI checkouts as out of scope instead of delegating to the canonical orama check.
  if [[ "${GITHUB_ACTIONS:-}" == "true" && "$(dirname "$cand_abs")" != "$PT_PARENT" ]]; then
    echo "skip: orama-system is not a sibling in CI: $cand_abs" >&2
    continue
  fi

  [[ -f "$cand_abs/scripts/git/sync-docs-v2-pointers.sh" ]] || continue
  exec bash "$cand_abs/scripts/git/sync-docs-v2-pointers.sh" --check "$PT_ROOT"
done
echo "skip: orama-system not found as sibling (set ORAMA_ROOT to enable docs/v2 pointer sync check)" >&2
exit 0
