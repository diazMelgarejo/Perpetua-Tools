#!/usr/bin/env bash
# Pre-commit glue (Perpetua-Tools side): verify this repo's generated docs/adr
# pointers are in sync with the canonical orama-system docs/v2 collection. The sync
# LOGIC is canonical in orama (scripts/git/sync-docs-v2-pointers.sh) — we only
# locate orama and delegate, never fork the script (zero-fragmentation doctrine,
# orama docs/v2/27-git-governance-zero-fragmentation.md). Skips gracefully when
# orama is not a sibling (e.g. GitHub CI), so it never blocks a clean commit.
set -euo pipefail
PT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for cand in "${ORAMA_ROOT:-}" \
            "$PT_ROOT/../../orama-system"; do
  [[ -n "$cand" && -f "$cand/scripts/git/sync-docs-v2-pointers.sh" ]] || continue
  exec bash "$cand/scripts/git/sync-docs-v2-pointers.sh" --check "$PT_ROOT"
done
echo "skip: orama-system not found as sibling (set ORAMA_ROOT to enable docs/v2 pointer sync check)" >&2
exit 0
