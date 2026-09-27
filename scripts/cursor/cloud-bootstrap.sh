#!/usr/bin/env bash
# Cursor Cloud Agent install hook (see .cursor/environment.json).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

printf '>>> [cloud-bootstrap] Perpetua-Tools %s\n' "$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

export PERPETUA_TOOLS_PATH="${PERPETUA_TOOLS_PATH:-$REPO_ROOT}"
export REPO_ROOT="$REPO_ROOT"
# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/resolve_orama_root.sh" >/dev/null 2>&1 || true
discard_stale_orama_env_overrides 2>/dev/null || true
ORAMA_SYSTEM_PATH="$(resolve_orama_root 2>/dev/null || true)"
export ORAMA_SYSTEM_PATH

# Invoke with bash + -f, not -x: git mode 100644 still runs (Cloud Agent
# start used to skip the attribution seeder and then fail verify-git-guards).
if [[ -f scripts/cursor/ci-bootstrap-private-attribution.sh ]]; then
  bash scripts/cursor/ci-bootstrap-private-attribution.sh
fi

if [[ -f scripts/cursor/install-user-git-environment.sh ]]; then
  bash scripts/cursor/install-user-git-environment.sh
fi

if [[ -f scripts/git/neutralize-cursor-coauthor-hook.sh ]]; then
  bash scripts/git/neutralize-cursor-coauthor-hook.sh --all-agent-hooks
fi

# Do not run daily-attribution-guard here: it scans full history and may rewrite repos.
# verify-git-guards + neutralize hooks are sufficient for cloud VM bootstrap.

git config --local user.name "cyre" 2>/dev/null || true
git config --local user.email "Lawrence@cyre.me" 2>/dev/null || true

if [[ -f scripts/git/install-local-hooks.sh ]]; then
  bash scripts/git/install-local-hooks.sh
fi

if [[ -f scripts/git/verify-git-guards.sh ]]; then
  bash scripts/git/verify-git-guards.sh
fi

if [[ -f scripts/git/scan-tracked-banned-tokens.sh ]]; then
  bash scripts/git/scan-tracked-banned-tokens.sh
fi

# Truthful status-only helper (I2): no network call, no pulse, no relay cosmetics.
if [[ -f scripts/cursor/remote-coordination.sh ]]; then
  bash scripts/cursor/remote-coordination.sh status || true
fi

printf '>>> [cloud-bootstrap] complete\n'
