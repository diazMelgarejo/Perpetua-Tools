#!/usr/bin/env bash
# install-agentic-stack.sh — idempotent submodule sync + upgrade dry-run preview.
#
# Modelled on orama-system/scripts/install-openclaw-skills.sh:
#   1. Sync vendor/agentic-stack to pinned gitlink (no vendor/ edits)
#   2. Preview upstream .agent/ skeleton deltas (dry-run when available)
#   3. PT .agent/ remains project-owned — union-merge only after human review
#
# See orama-system/docs/v2/41-agentic-stack-gstack-gbrain-memory-blend.md
set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "$0")/../.." rev-parse --show-toplevel)"
SUBPATH="vendor/agentic-stack"
STACK="$REPO_ROOT/$SUBPATH"

echo "[agentic-stack] Syncing submodule to pinned SHA..."
git -C "$REPO_ROOT" submodule update --init --depth 1 "$SUBPATH"

if [ ! -f "$STACK/harness_manager/cli.py" ]; then
  echo "[agentic-stack] ERROR: harness_manager missing at $STACK" >&2
  exit 1
fi

export AGENTIC_STACK_ROOT="$STACK"
export PYTHONPATH="$STACK${PYTHONPATH:+:$PYTHONPATH}"

_run_doctor_fallback() {
  echo "[agentic-stack] upgrade verb unavailable at pinned SHA — running doctor"
  python3 -m harness_manager.cli doctor "$REPO_ROOT"
  echo "[agentic-stack] tip: bump vendor/agentic-stack to >= v0.16 for upgrade --dry-run"
  echo "[agentic-stack]       bash scripts/git/agentic-stack-submodule-sync.sh upgrade"
}

# Probe by attempting the real dry-run rather than `upgrade --help` -- the
# CLI's argv parsing has changed across versions (v0.18 mis-parses a bare
# --help as a positional adapter name), so a --help probe is not a reliable
# version gate. The dry-run itself is side-effect-free either way.
echo "[agentic-stack] upgrade --dry-run (no writes until you run upgrade --yes):"
_dry_run_output="$(python3 -m harness_manager.cli upgrade --dry-run "$REPO_ROOT" 2>&1)" && {
  printf '%s\n' "$_dry_run_output"
} || {
  printf '%s\n' "$_dry_run_output" | grep -qi "unrecognized\|no such\|unknown\|invalid choice" \
    && _run_doctor_fallback || printf '%s\n' "$_dry_run_output"
}

echo "[agentic-stack] BLOCK upstream Brain integration — use Gbrain via gstack (doc 41 §5)"
echo "[agentic-stack] PT .agent/ is union-merged at upgrade time; never commit into vendor/"
echo "[agentic-stack] Done."
