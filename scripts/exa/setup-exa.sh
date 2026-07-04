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
ORAMA_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PT_ROOT="${HOME}/code/OpenClaw/perplexity-api/Perpetua-Tools"
DESKTOP_CFG="${HOME}/Library/Application Support/Claude/claude_desktop_config.json"
MCP_WRAPPER="${SCRIPT_DIR}/exa-mcp-wrapper.sh"
SOCKET_PATH="${HOME}/.openclaw/run/exa-mcp.sock"
PID_PATH="${HOME}/.openclaw/run/exa-mcp.pid"
LOG_PATH="${HOME}/.openclaw/log/exa-mcp-daemon.log"

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

# 5. Write .mcp.json for both repos (both point to the SAME wrapper)
for REPO_PATH in "$ORAMA_ROOT" "$PT_ROOT"; do
  if [[ -d "$REPO_PATH" ]]; then
    MCP_FILE="${REPO_PATH}/.mcp.json"
    python3 - <<PYEOF
import json, pathlib
path = pathlib.Path("$MCP_FILE")
data = json.loads(path.read_text()) if path.exists() else {}
data.setdefault("mcpServers", {})["exa"] = {
    "command": "bash",
    "args": ["\$HOME/code/OpenClaw/orama-system/scripts/exa/exa-mcp-wrapper.sh"],
    "env": {}
}
path.write_text(json.dumps(data, indent=2))
print(f"[exa-setup] {path}: OK")
PYEOF
  fi
done

# 6. Smoke-test: start daemon and verify
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
echo "[exa-setup] Done. All 3 MCP registrations point to ONE daemon:"
echo "  Claude Desktop      → bash $MCP_WRAPPER → daemon"
echo "  orama-system CLI    → bash $MCP_WRAPPER → daemon"
echo "  Perpetua-Tools CLI  → bash $MCP_WRAPPER → daemon"
echo ""
echo "Control:"
echo "  bash setup-exa.sh status   — check daemon + key"
echo "  bash setup-exa.sh stop     — kill daemon"
echo "  bash setup-exa.sh restart  — cycle daemon"
echo ""
echo "Python test:"
echo "  python3 ${SCRIPT_DIR}/exa_search.py 'orama system MCP agent'"
