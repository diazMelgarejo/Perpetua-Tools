#!/usr/bin/env bash
# Apply mandatory git hooks to Perpetua-Tools + sibling repos (Cursor session + manual).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DISABLE="$SCRIPT_DIR/disable-cursor-commit-attribution.sh"
INSTALL="$SCRIPT_DIR/install-local-hooks.sh"
SYNC="$SCRIPT_DIR/sync-attribution-guard-scripts.sh"

OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/openclaw-v1}"

resolve_git_repo() {
  local r="$1"
  [[ -n "$r" ]] || return 1
  [[ "$r" == *'${'* ]] && return 1
  [[ -d "$r/.git" ]] || return 1
  local abs
  abs="$(cd "$r" && pwd)" || return 1
  printf '%s' "$abs"
}

raw_candidates=(
  "$PT_ROOT"
  "${PERPETUA_TOOLS_PATH:-$PT_ROOT}"
  "${PERPETUA_TOOLS_ROOT:-$PT_ROOT}"
  "${ORAMA_SYSTEM_PATH:-$OPENCLAW_HOME/orama-system}"
  "${ALPHACLAW_INSTALL_DIR:-$OPENCLAW_HOME/AlphaClaw}"
  "/agent/repos/Perpetua-Tools"
  "/agent/repos/orama-system"
  "/agent/repos/AlphaClaw"
  "/agent/repos/periscope"
)

if [[ -d /agent/repos ]]; then
  for d in /agent/repos/*; do
    raw_candidates+=("$d")
  done
fi

declare -A seen=()
unique=()
for r in "${raw_candidates[@]}"; do
  resolved="$(resolve_git_repo "$r" 2>/dev/null || true)"
  [[ -n "$resolved" ]] || continue
  if [[ -n "${seen[$resolved]+x}" ]]; then
    continue
  fi
  seen[$resolved]=1
  unique+=("$resolved")
done

# Drop nested checkouts (e.g. <repo>/~/openclaw-v1/AlphaClaw) so a bad
# literal-tilde OPENCLAW_HOME cannot fan out sync into junk trees.
filtered=()
for r in "${unique[@]}"; do
  nested=0
  for other in "${unique[@]}"; do
    [[ "$r" == "$other" ]] && continue
    case "$r" in
      "$other"/*)
        nested=1
        break
        ;;
    esac
  done
  if ((nested)); then
    echo "warn: skipping nested git checkout inside workspace sibling: $r" >&2
    continue
  fi
  filtered+=("$r")
done
unique=("${filtered[@]}")

if [[ -x "$SYNC" ]]; then
  sync_failures=0
  for r in "${unique[@]}"; do
    [[ "$r" == "$PT_ROOT" ]] && continue
    [[ "$(basename "$r")" == "periscope" ]] && continue
    if ! bash "$SYNC" "$r"; then
      echo "error: sync failed: $r" >&2
      sync_failures=$((sync_failures + 1))
    fi
  done
  if ((sync_failures > 0)); then
    echo "error: attribution guard sync failed for $sync_failures repo(s)" >&2
    # Cloud boot (explicit GUARD_SYNC_ON_DIRTY=skip): prefer a working agent over hard failure.
    if [[ "${GUARD_SYNC_ON_DIRTY:-fail}" == "skip" ]]; then
      echo "warn: continuing despite sync failures (cloud soft mode)" >&2
    else
      exit 1
    fi
  fi
fi

for r in "${unique[@]}"; do
  [[ "$(basename "$r")" == "periscope" ]] && continue
  bash "$DISABLE" "$r"
  if [[ -x "$INSTALL" && -x "$r/scripts/git/ensure_hooks_installed.sh" ]]; then
    bash "$INSTALL" "$r" || echo "warn: install-local-hooks failed: $r" >&2
  elif [[ -x "$DISABLE" ]]; then
    :
  fi
  git -C "$r" config --local user.name "cyre" 2>/dev/null || true
  git -C "$r" config --local user.email "Lawrence@cyre.me" 2>/dev/null || true
done

echo "OK: mandatory hooks applied for ${#unique[@]} repo(s)"
