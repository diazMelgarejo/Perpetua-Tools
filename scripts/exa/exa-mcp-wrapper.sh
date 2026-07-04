#!/usr/bin/env bash
# exa-mcp-wrapper.sh — singleton-aware Exa MCP stdio bridge
#
# Architecture:
#   ONE exa-mcp-daemon.py owns the real npx exa-mcp-server process.
#   ALL THREE Claude registrations (Desktop, orama, PT) point here.
#   This script: ensures daemon is up, then bridges this process's
#   stdio ↔ the daemon's Unix socket. Only one backend ever runs.
#
# Socket:  ~/.openclaw/run/exa-mcp.sock
# PID:     ~/.openclaw/run/exa-mcp.pid
# Log:     ~/.openclaw/log/exa-mcp-daemon.log

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOCKET_PATH="${HOME}/.openclaw/run/exa-mcp.sock"
PID_PATH="${HOME}/.openclaw/run/exa-mcp.pid"
DAEMON="${SCRIPT_DIR}/exa-mcp-daemon.py"

# ---------------------------------------------------------------------------
# 1. Resolve EXA_API_KEY (shared by both daemon and this bridge)
# ---------------------------------------------------------------------------
if [[ -z "${EXA_API_KEY:-}" ]]; then
  OC_JSON="${HOME}/.openclaw/openclaw.json"
  if [[ -f "$OC_JSON" ]]; then
    EXA_API_KEY=$(python3 -c "
import json, pathlib
d = json.loads(pathlib.Path('${HOME}/.openclaw/openclaw.json').read_text())
print((d.get('env') or {}).get('EXA_API_KEY', ''))
" 2>/dev/null || true)
  fi
fi

if [[ -z "${EXA_API_KEY:-}" ]]; then
  EXA_API_KEY=$(security find-generic-password -s "openclaw.exa.api_key" -w 2>/dev/null || true)
fi

if [[ -z "${EXA_API_KEY:-}" ]]; then
  printf '{"jsonrpc":"2.0","error":{"code":-32000,"message":"EXA_API_KEY not set — run setup-exa.sh"},"id":null}\n' >&2
  exit 1
fi
export EXA_API_KEY

# ---------------------------------------------------------------------------
# 2. Ensure nvm node is on PATH for npx
# ---------------------------------------------------------------------------
NVM_NODE="${HOME}/.nvm/versions/node/v22.22.2/bin"
[[ -d "$NVM_NODE" ]] && export PATH="${NVM_NODE}:${PATH}"

# ---------------------------------------------------------------------------
# 3. Check if daemon socket is alive (idempotent probe)
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

# ---------------------------------------------------------------------------
# 4. Start daemon if not running (detached, inherits EXA_API_KEY)
# ---------------------------------------------------------------------------
if ! _daemon_alive; then
  # Stale PID/socket cleanup
  rm -f "$SOCKET_PATH"
  if [[ -f "$PID_PATH" ]]; then
    OLD_PID=$(cat "$PID_PATH" 2>/dev/null || true)
    [[ -n "$OLD_PID" ]] && kill "$OLD_PID" 2>/dev/null || true
    rm -f "$PID_PATH"
  fi

  # Start daemon detached
  nohup python3 "$DAEMON" </dev/null \
    >>"${HOME}/.openclaw/log/exa-mcp-daemon.log" 2>&1 &

  # Wait up to 5 s for socket to appear
  WAITED=0
  until _daemon_alive || [[ $WAITED -ge 50 ]]; do
    sleep 0.1
    WAITED=$((WAITED + 1))
  done

  if ! _daemon_alive; then
    printf '{"jsonrpc":"2.0","error":{"code":-32000,"message":"exa-mcp-daemon failed to start — check ~/.openclaw/log/exa-mcp-daemon.log"},"id":null}\n' >&2
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# 5. Bridge this process's stdio ↔ daemon socket (we become the wrapper)
# ---------------------------------------------------------------------------
exec python3 -c "
import socket, sys, threading

sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect('${SOCKET_PATH}')

def _to_sock():
    try:
        while chunk := sys.stdin.buffer.read(4096):
            sock.sendall(chunk)
    except Exception:
        pass
    finally:
        try: sock.shutdown(socket.SHUT_WR)
        except Exception: pass

def _from_sock():
    try:
        while chunk := sock.recv(4096):
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
    except Exception:
        pass

t = threading.Thread(target=_to_sock, daemon=True)
t.start()
_from_sock()
"
