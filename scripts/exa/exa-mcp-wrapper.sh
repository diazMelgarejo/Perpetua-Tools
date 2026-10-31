#!/usr/bin/env bash
# exa-mcp-wrapper.sh — singleton-aware Exa MCP stdio bridge
#
# Architecture:
#   ONE exa-mcp-daemon.py owns the real npx exa-mcp-server process.
#   Claude Desktop, orama-system, Perpetua-Tools, and Codex registrations
#   all point here.
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
LOCK_DIR="${HOME}/.openclaw/run/exa-mcp-start.lock"
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
# 4. Start daemon if not running — singleton-safe (idempotent under races)
# ---------------------------------------------------------------------------
# `flock(1)` is util-linux-only and NOT present on macOS/BSD, so mutual
# exclusion here uses the portable mkdir-is-atomic lock idiom instead.
# Only the process that wins the lock may start/restart the daemon; every
# other concurrent invocation backs off and just watches the socket come up
# — it never kills or races a competing backend.
_watch_for_daemon() {
  local waited=0
  until _daemon_alive || [[ $waited -ge 100 ]]; do
    sleep 0.1
    waited=$((waited + 1))
  done
  _daemon_alive
}

if ! _daemon_alive; then
  mkdir -p "$(dirname "$LOCK_DIR")"
  LOCK_ACQUIRED=0

  # Try to become the starter for up to ~10s, ceding to a live lock holder.
  WAITED=0
  while [[ $WAITED -lt 100 ]]; do
    if mkdir "$LOCK_DIR" 2>/dev/null; then
      echo $$ > "$LOCK_DIR/pid" 2>/dev/null || true
      LOCK_ACQUIRED=1
      break
    fi

    # Lock is held — is the holder still alive, or stale (crashed mid-start,
    # or crashed between mkdir and writing its pid file)? Either way the
    # lock dir is non-empty once a pid file is written, so reclaim must use
    # rm -rf, not rmdir — rmdir silently no-ops on a non-empty directory
    # and left unfixed, WAITED is never incremented on this path, spinning
    # forever on every restart after the first successful run.
    HOLDER_PID=$(cat "$LOCK_DIR/pid" 2>/dev/null || true)
    if [[ -z "$HOLDER_PID" ]] || ! kill -0 "$HOLDER_PID" 2>/dev/null; then
      rm -rf "$LOCK_DIR" 2>/dev/null || true
      # Defensive: count this as a waited tick even though we expect the
      # next mkdir to succeed immediately — guards against an unexpected
      # rm -rf failure (e.g. permissions) turning this into a hard spin.
      WAITED=$((WAITED + 1))
      continue
    fi

    # Live holder is (presumably) starting the daemon for us — back off,
    # watch only, never spawn a competing backend.
    if _daemon_alive; then
      break
    fi
    sleep 0.1
    WAITED=$((WAITED + 1))
  done

  if [[ "$LOCK_ACQUIRED" -eq 1 ]]; then
    # rm -rf, not rmdir: the lock dir contains a "pid" file (written above),
    # so rmdir always no-ops here — that left every successful run's lock
    # dir behind, wedging the *next* daemon restart into the reclaim loop.
    trap 'rm -rf "$LOCK_DIR" 2>/dev/null || true' EXIT
    # Re-check under the lock: another process may have finished starting it
    # in the tiny window before we acquired the lock.
    if ! _daemon_alive; then
      # Stale PID/socket cleanup — only kill a PID that is truly dead;
      # never blind-kill a live process just because the socket is missing.
      if [[ -f "$PID_PATH" ]]; then
        OLD_PID=$(cat "$PID_PATH" 2>/dev/null || true)
        if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
          kill "$OLD_PID" 2>/dev/null || true
        fi
        rm -f "$PID_PATH"
      fi
      rm -f "$SOCKET_PATH"

      # Start daemon detached
      nohup python3 "$DAEMON" </dev/null \
        >>"${HOME}/.openclaw/log/exa-mcp-daemon.log" 2>&1 &

      if ! _watch_for_daemon; then
        printf '{"jsonrpc":"2.0","error":{"code":-32000,"message":"exa-mcp-daemon failed to start — check ~/.openclaw/log/exa-mcp-daemon.log"},"id":null}\n' >&2
        exit 1
      fi
    fi
    rm -rf "$LOCK_DIR" 2>/dev/null || true
    trap - EXIT
  else
    # Never acquired the lock and the daemon still isn't up — watch once
    # more before giving up.
    if ! _watch_for_daemon; then
      printf '{"jsonrpc":"2.0","error":{"code":-32000,"message":"exa-mcp-daemon still not alive after backoff — check ~/.openclaw/log/exa-mcp-daemon.log"},"id":null}\n' >&2
      exit 1
    fi
  fi
fi

# ---------------------------------------------------------------------------
# 5. Bridge this process's stdio ↔ daemon socket (we become the wrapper)
# ---------------------------------------------------------------------------
exec python3 -c "
import socket, sys, threading

sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect('${SOCKET_PATH}')

# Use raw (unbuffered) stdin so read() returns immediately on any available
# bytes instead of blocking until the 4096-byte buffer fills up.
_raw_stdin = sys.stdin.buffer.raw

def _to_sock():
    try:
        while chunk := _raw_stdin.read(65536):
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
