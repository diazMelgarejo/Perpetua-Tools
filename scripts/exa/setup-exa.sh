#!/usr/bin/env bash
# setup-exa.sh — Exa.ai integration bootstrap + daemon control
#
# Usage:
#   bash setup-exa.sh --key <EXA_API_KEY>   # first-time setup
#   bash setup-exa.sh status                 # check daemon + key
#   bash setup-exa.sh stop                  # kill daemon
#   bash setup-exa.sh restart               # stop + let next use restart it

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_CFG="${HOME}/Library/Application Support/Claude/claude_desktop_config.json"
MCP_WRAPPER="${SCRIPT_DIR}/exa-mcp-wrapper.sh"
SOCKET_PATH="${HOME}/.openclaw/run/exa-mcp.sock"
PID_PATH="${HOME}/.openclaw/run/exa-mcp.pid"
LOG_PATH="${HOME}/.openclaw/log/exa-mcp-daemon.log"
# orama-system owns the EXA runtime, and this script is mirrored byte-identical
# into Perpetua-Tools, so resolve the orama-system checkout with whichever
# resolver this copy sits next to; never assume a workstation layout.
_resolve_exa_owner_root() {
  if [[ -f "$SCRIPT_DIR/resolve-orama-root.sh" ]]; then        # orama-system copy
    bash "$SCRIPT_DIR/resolve-orama-root.sh" 2>/dev/null
  elif [[ -f "$SCRIPT_DIR/../resolve_orama_root.sh" ]]; then   # Perpetua-Tools mirror
    # shellcheck source=/dev/null
    (source "$SCRIPT_DIR/../resolve_orama_root.sh" && resolve_orama_root) 2>/dev/null
  fi
}
EXA_OWNER_ROOT="$(_resolve_exa_owner_root || true)"

# Perpetua-Tools is the other repo whose .mcp.json shares this wrapper.
_resolve_pt_root() {
  local lib
  if [[ -f "$SCRIPT_DIR/../../orchestrator/fastapi_app.py" ]]; then   # Perpetua-Tools mirror
    (cd "$SCRIPT_DIR/../.." && pwd)
    return
  fi
  lib="${EXA_OWNER_ROOT:-}/bin/orama-system/skills/hermes-harness/scripts/resolve_perp_harness.sh"
  # shellcheck source=/dev/null
  [[ -f "$lib" ]] && (cd "$EXA_OWNER_ROOT" && source "$lib" && resolve_pt_root) 2>/dev/null
}
PT_ROOT="$(_resolve_pt_root || true)"
CODEX_WRAPPER_CMD=""
if [[ -n "$EXA_OWNER_ROOT" && -f "$EXA_OWNER_ROOT/scripts/exa/exa-mcp-wrapper.sh" ]]; then
  CODEX_WRAPPER_CMD="exec \"$EXA_OWNER_ROOT/scripts/exa/exa-mcp-wrapper.sh\""
fi

# A project's own .codex/config.toml [mcp_servers.exa] overrides the global
# registration in that checkout. Print each such file whose exa entry does not
# use the wrapper, so setup never reports Codex ready when it is not.
_codex_project_exa_overrides() {
  local root cfg
  for root in "$(cd "$SCRIPT_DIR/../.." && pwd)" "${EXA_OWNER_ROOT:-}"; do
    cfg="$root/.codex/config.toml"
    [[ -n "$root" && -f "$cfg" ]] || continue
    if awk '/^\[/{s=($0=="[mcp_servers.exa]")} s' "$cfg" | grep -q . &&
       ! awk '/^\[/{s=($0=="[mcp_servers.exa]")} s' "$cfg" | grep -q 'exa-mcp-wrapper.sh'; then
      echo "$cfg"
    fi
  done | sort -u
}

mkdir -p "${HOME}/.openclaw/run" "${HOME}/.openclaw/log"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_daemon_alive() {
  python3 -c "
import socket, sys
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(1)
try:
    s.connect('${SOCKET_PATH}')
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null
}

_stop_daemon() {
  if [[ -f "$PID_PATH" ]]; then
    PID=$(cat "$PID_PATH" 2>/dev/null || true)
    [[ -n "$PID" ]] && kill "$PID" 2>/dev/null && echo "Daemon (pid=$PID) stopped." || true
    rm -f "$PID_PATH"
  fi
  rm -f "$SOCKET_PATH"
}

# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------
CMD="${1:-setup}"
case "$CMD" in
  status)
    echo "=== Exa MCP Daemon ==="
    if _daemon_alive; then
      echo "  socket:  UP  ($SOCKET_PATH)"
      PID=$(cat "$PID_PATH" 2>/dev/null || echo "unknown")
      echo "  pid:     $PID"
    else
      echo "  socket:  DOWN"
    fi
    echo ""
    echo "=== API Key ==="
    KEY="${EXA_API_KEY:-}"
    if [[ -z "$KEY" ]]; then
      OC_JSON="${HOME}/.openclaw/openclaw.json"
      [[ -f "$OC_JSON" ]] && KEY=$(python3 -c "
import json,pathlib
d=json.loads(pathlib.Path('$OC_JSON').read_text())
print((d.get('env') or {}).get('EXA_API_KEY',''))
" 2>/dev/null || true)
    fi
    if [[ -z "$KEY" ]]; then
      KEY=$(security find-generic-password -s "openclaw.exa.api_key" -w 2>/dev/null || true)
    fi
    if [[ -n "$KEY" ]]; then
      echo "  key: ${KEY:0:8}…${KEY: -4}"
    else
      echo "  key: NOT SET — run: bash setup-exa.sh --key YOUR_KEY"
    fi
    echo ""
    echo "=== Codex MCP ==="
    if command -v codex >/dev/null 2>&1; then
      if codex mcp get exa 2>/dev/null | grep -q 'exa-mcp-wrapper.sh'; then
        echo "  exa:    configured via wrapper"
      else
        echo "  exa:    not configured via wrapper — run setup"
      fi
    else
      echo "  codex:  not installed"
    fi
    echo ""
    echo "=== Log (last 5 lines) ==="
    [[ -f "$LOG_PATH" ]] && tail -5 "$LOG_PATH" || echo "  (no log yet)"
    exit 0
    ;;
  stop)
    _stop_daemon
    exit 0
    ;;
  restart)
    _stop_daemon
    echo "Daemon stopped. It will restart on next use."
    exit 0
    ;;
esac

# ---------------------------------------------------------------------------
# First-time setup
# ---------------------------------------------------------------------------
API_KEY="${EXA_API_KEY:-}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --key) API_KEY="$2"; shift 2 ;;
    *) shift ;;
  esac
done

echo "[exa-setup] Starting Exa.ai integration bootstrap"

# 1. Install exa-py
echo "[exa-setup] Installing exa-py..."
pip3 install -q exa-py && echo "[exa-setup] exa-py: OK"

# 2. Get API key
if [[ -z "$API_KEY" ]]; then
  echo "[exa-setup] Enter your Exa API key (https://dashboard.exa.ai/keys):"
  read -r -s API_KEY
  echo
fi
[[ -z "$API_KEY" ]] && { echo "ERROR: No API key provided" >&2; exit 1; }

# 3a. macOS Keychain
echo "[exa-setup] Storing in macOS Keychain..."
security add-generic-password -s "openclaw.exa.api_key" -a "$(whoami)" \
  -w "$API_KEY" -U 2>/dev/null && echo "[exa-setup] Keychain: OK"

# 3b. openclaw.json
OC_JSON="${HOME}/.openclaw/openclaw.json"
if [[ -f "$OC_JSON" ]]; then
  echo "[exa-setup] Injecting into ~/.openclaw/openclaw.json..."
  python3 - <<PYEOF
import json, pathlib
path = pathlib.Path("$OC_JSON")
data = json.loads(path.read_text())
data.setdefault("env", {})["EXA_API_KEY"] = "$API_KEY"
path.write_text(json.dumps(data, indent=2))
print("[exa-setup] openclaw.json: OK")
PYEOF
fi

# 4. Wire MCP wrapper into Claude Desktop
chmod +x "$MCP_WRAPPER"
echo "[exa-setup] Registering Exa MCP server in Claude Desktop config..."
python3 - <<PYEOF
import json, pathlib, os
cfg_path = pathlib.Path("$DESKTOP_CFG")
cfg = json.loads(cfg_path.read_text())
cfg.setdefault("mcpServers", {})["exa"] = {
    "command": "bash",
    "args": [os.path.expandvars("$MCP_WRAPPER").replace(os.path.expanduser("~"), "\$HOME")],
    "env": {}
}
cfg_path.write_text(json.dumps(cfg, indent=2))
print("[exa-setup] Claude Desktop: OK (restart app to activate)")
PYEOF

# 5. Check .mcp.json in both repos. Each tracked file already resolves the
# shared wrapper portably at run time, so setup only reports and never
# rewrites a tracked file with a machine-specific path.
for REPO_PATH in "${EXA_OWNER_ROOT:-}" "${PT_ROOT:-}"; do
  [[ -n "$REPO_PATH" && -d "$REPO_PATH" ]] || continue
  MCP_FILE="${REPO_PATH}/.mcp.json"
  if python3 - "$MCP_FILE" <<'PYEOF'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
exa = json.loads(path.read_text()).get("mcpServers", {}).get("exa", {}) if path.exists() else {}
sys.exit(0 if "exa-mcp-wrapper.sh" in " ".join([exa.get("command", "")] + exa.get("args", [])) else 1)
PYEOF
  then
    echo "[exa-setup] ${MCP_FILE}: OK (uses the shared wrapper)"
  else
    echo "[exa-setup] WARNING: ${MCP_FILE} has no exa entry using exa-mcp-wrapper.sh; restore it from the repository" >&2
  fi
done
[[ -n "${PT_ROOT:-}" ]] || echo "[exa-setup] Perpetua-Tools checkout not found; skipped its .mcp.json check"

# 6. Wire Codex CLI global MCP to the same wrapper when Codex is present.
# Codex's HTTP MCP registration cannot resolve the OpenClaw Keychain/openclaw.json
# secret path by itself. The stdio wrapper is the authenticated, shared path.
if command -v codex >/dev/null 2>&1 && [[ -z "$CODEX_WRAPPER_CMD" ]]; then
  echo "[exa-setup] WARNING: cannot locate the orama-system checkout that owns the EXA wrapper;" >&2
  echo "  set ORAMA_SYSTEM_ROOT and re-run to register Codex. Skipping Codex MCP registration." >&2
elif command -v codex >/dev/null 2>&1; then
  echo "[exa-setup] Registering Exa MCP server in Codex global config..."
  codex mcp remove exa >/dev/null 2>&1 || true
  if codex mcp add exa -- bash -c "$CODEX_WRAPPER_CMD" >/dev/null; then
    CODEX_OVERRIDES="$(_codex_project_exa_overrides)"
    if [[ -z "$CODEX_OVERRIDES" ]]; then
      echo "[exa-setup] Codex CLI: OK (restart Codex sessions to activate tools)"
    else
      echo "[exa-setup] Codex CLI: global registration OK, but these project configs define their own exa server," >&2
      echo "  which overrides the wrapper when Codex runs in that checkout (point them at the wrapper to switch):" >&2
      echo "$CODEX_OVERRIDES" | sed 's/^/    /' >&2
    fi
  else
    echo "[exa-setup] WARNING: Codex MCP registration failed; run manually:" >&2
    echo "  codex mcp add exa -- bash -c '$CODEX_WRAPPER_CMD'" >&2
  fi
else
  echo "[exa-setup] Codex CLI not found; skipping Codex MCP registration"
fi

# 7. Smoke-test: start daemon and verify
echo "[exa-setup] Starting daemon for smoke test..."
export EXA_API_KEY="$API_KEY"
NVM_NODE="${HOME}/.nvm/versions/node/v22.22.2/bin"
[[ -d "$NVM_NODE" ]] && export PATH="${NVM_NODE}:${PATH}"
nohup python3 "${SCRIPT_DIR}/exa-mcp-daemon.py" </dev/null \
  >>"$LOG_PATH" 2>&1 &

WAITED=0
until _daemon_alive || [[ $WAITED -ge 50 ]]; do
  sleep 0.1; WAITED=$((WAITED + 1))
done

if _daemon_alive; then
  PID=$(cat "$PID_PATH" 2>/dev/null || echo "?")
  echo "[exa-setup] Daemon: UP (pid=$PID, socket=$SOCKET_PATH)"
else
  echo "[exa-setup] WARNING: daemon did not start. Check $LOG_PATH"
fi

echo ""
echo "[exa-setup] Done. MCP registrations point to ONE daemon:"
echo "  Claude Desktop      → bash $MCP_WRAPPER → daemon"
echo "  orama-system CLI    → bash $MCP_WRAPPER → daemon"
echo "  Perpetua-Tools CLI  → bash $MCP_WRAPPER → daemon"
echo "  Codex CLI           → bash $MCP_WRAPPER → daemon"
echo ""
echo "Control:"
echo "  bash setup-exa.sh status   — check daemon + key"
echo "  bash setup-exa.sh stop     — kill daemon"
echo "  bash setup-exa.sh restart  — cycle daemon"
echo ""
echo "Python test:"
echo "  python3 ${SCRIPT_DIR}/exa_search.py 'orama system MCP agent'"
echo ""
echo "MCP smoke test:"
echo "  codex mcp get exa"
echo "  codex mcp list"
