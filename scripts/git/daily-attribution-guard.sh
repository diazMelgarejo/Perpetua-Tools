#!/usr/bin/env bash
# Run at session start (and optionally cron): neutralize injection, scan, verify hooks.
# History rewrite + force-push never run unless ATTRIBUTION_EXPUNGE_AUTO=1 (explicit opt-in).
#
# CANONICAL, SELF-CONTAINED, IDENTICAL ACROSS ALL REPOS. Edit orama's copy, then
# `scripts/git/sync-attribution-guard-scripts.sh <target>` to redistribute. Do NOT
# replace this with a thin wrapper to another repo — that hardcodes a path and, run
# against the wrapper's own target, execs itself (infinite recursion). It scans the
# whole workspace from whichever repo invokes it, so every entrypoint is equivalent.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-/agent/repos}"
LOG="${HOME:-}/.cursor/openclaw/attribution-guard.log"

mkdir -p "${HOME:-}/.cursor/openclaw"
{
  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) daily-attribution-guard ==="
} >>"$LOG"

if [[ -x "$REPO_ROOT/scripts/cursor/install-user-git-environment.sh" ]]; then
  bash "$REPO_ROOT/scripts/cursor/install-user-git-environment.sh" >>"$LOG" 2>&1 || true
fi

if [[ -x "$SCRIPT_DIR/neutralize-cursor-coauthor-hook.sh" ]]; then
  bash "$SCRIPT_DIR/neutralize-cursor-coauthor-hook.sh" --all-agent-hooks >>"$LOG" 2>&1 || true
fi

# shellcheck source=banned_attribution_lib.sh
source "$REPO_ROOT/scripts/git/banned_attribution_lib.sh"
total_hits=0
for repo in "$WORKSPACE_ROOT"/*; do
  [[ -d "$repo/.git" ]] || continue
  bash "$SCRIPT_DIR/sync-banned-patterns-to-repo.sh" "$repo" >>"$LOG" 2>&1 || true
  if [[ -x "$repo/scripts/git/install-local-hooks.sh" ]]; then
    bash "$repo/scripts/git/install-local-hooks.sh" >>"$LOG" 2>&1 || true
  elif [[ "$repo" != "$REPO_ROOT" && -x "$REPO_ROOT/scripts/git/install-local-hooks.sh" ]]; then
    (cd "$repo" && git config --local core.hooksPath .githooks 2>/dev/null) || true
  fi
  hits=0
  h_line=""
  while IFS= read -r h; do
    while IFS= read -r line; do
      line_lc="$(printf '%s' "$line" | tr '[:upper:]' '[:lower:]')"
      case "$line_lc" in
        co-authored-by:*)
          if line_matches_banned_pattern "$line_lc" "$repo"; then
            hits=$((hits + 1))
          fi
          ;;
      esac
    done < <(git -C "$repo" log -1 --format=%B "$h" 2>/dev/null)
  done < <(git -C "$repo" rev-list --all 2>/dev/null)
  total_hits=$((total_hits + hits))
  echo "scan $(basename "$repo") hits=$hits" >>"$LOG"
done

if [[ "$total_hits" -gt 0 ]]; then
  echo "ALERT: banned co-author hits=$total_hits — run: bash $SCRIPT_DIR/expunge-all-workspace-repos.sh" >>"$LOG"
  if [[ "${ATTRIBUTION_EXPUNGE_AUTO:-}" == "1" ]]; then
    echo "ATTRIBUTION_EXPUNGE_AUTO=1 — running workspace expunge" >>"$LOG"
    bash "$SCRIPT_DIR/expunge-all-workspace-repos.sh" >>"$LOG" 2>&1
  else
    echo "expunge skipped (set ATTRIBUTION_EXPUNGE_AUTO=1 to enable automatic rewrite)" >>"$LOG"
  fi
else
  echo "scan clean — no expunge required" >>"$LOG"
fi

if [[ -x "$REPO_ROOT/scripts/git/verify-git-guards.sh" ]]; then
  bash "$REPO_ROOT/scripts/git/verify-git-guards.sh" >>"$LOG" 2>&1 || true
fi

# Zero-fragmentation enforcement (docs/v2/27): assert the canonical guard scripts
# in every workspace repo are byte-identical to orama's. Warn-only here (the daily
# guard never blocks); CI runs the same script as a hard gate. Catches a downstream
# hand-edit before it silently diverges policy.
if [[ -x "$REPO_ROOT/scripts/git/verify-guard-parity.sh" ]]; then
  if bash "$REPO_ROOT/scripts/git/verify-guard-parity.sh" --workspace >>"$LOG" 2>&1; then
    echo "guard-parity: PASS (all workspace repos byte-identical to canonical)" >>"$LOG"
  else
    echo "ALERT: guard-parity FAIL — a repo's guard scripts drifted from orama canonical." >>"$LOG"
    echo "       Re-sync: bash <orama>/scripts/git/sync-attribution-guard-scripts.sh <repo>" >>"$LOG"
  fi
fi

echo "daily-attribution-guard complete (log: $LOG)"
