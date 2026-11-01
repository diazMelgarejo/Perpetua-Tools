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
# Only one process may start, restart or retire the daemon at a time. That is
# a kernel-backed advisory lock (fcntl.flock on a file): the OS releases it
# when the holder exits, even on a crash or SIGKILL, so there is no stale lock
# to reclaim and no path-based "remove the lock" step that could delete a
# competitor's. (`flock(1)` itself is util-linux-only and absent on macOS, so
# the lock is taken through python3, which this wrapper already requires.)
# The locked section is this script re-invoked with --start-daemon; the lock
# file descriptor is never inherited by it or by the daemon it spawns.
LOCK_FILE="${HOME}/.openclaw/run/exa-mcp-start.flock"
LOCK_WAIT_SECONDS=20
SELF="${SCRIPT_DIR}/$(basename "${BASH_SOURCE[0]}")"

_LOCKRUN='
import fcntl, os, subprocess, sys, time
path, wait, cmd = sys.argv[1], float(sys.argv[2]), sys.argv[3:]
fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)   # non-inheritable by default
end = time.monotonic() + wait
while True:
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        break
    except BlockingIOError:
        if time.monotonic() >= end:
            sys.exit(75)
        time.sleep(0.05)
sys.exit(subprocess.call(cmd))
'

_watch_for_daemon() {
  local waited=0
  until _daemon_alive || [[ $waited -ge 100 ]]; do
    sleep 0.1
    waited=$((waited + 1))
  done
  _daemon_alive
}

# True only for a live process whose executable is a Python interpreter and
# whose script argument is exactly this daemon file, so a recycled PID that now
# belongs to an editor, pager or any other program is never signalled.
_is_exa_daemon() {
  local pid="${1:-}" args
  [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null || return 1
  args="$(ps -p "$pid" -o args= 2>/dev/null)" || return 1
  [[ "$args" =~ ^([^[:space:]]*/)?python[0-9.]*[[:space:]]+(-[^[:space:]]+[[:space:]]+)*(.*) ]] || return 1
  local script="${BASH_REMATCH[3]}"
  [[ "$script" == "$DAEMON" || "$script" == "$DAEMON "* ]]
}

# A daemon that stopped listening may still be shutting down. Wait for it to
# exit (escalating to SIGKILL) before a replacement is started, so the old
# process can never remove the socket or PID file the new one creates.
_retire_old_daemon() {
  local pid="$1" i
  _is_exa_daemon "$pid" || return 0
  kill "$pid" 2>/dev/null || true
  for ((i = 0; i < 100; i++)); do
    _is_exa_daemon "$pid" || return 0
    sleep 0.1
  done
  kill -9 "$pid" 2>/dev/null || true
  for ((i = 0; i < 20; i++)); do
    _is_exa_daemon "$pid" || return 0
    sleep 0.1
  done
  return 1
}

# Runs only under the lock (via --start-daemon).
_start_daemon_locked() {
  # Re-check under the lock: another process may have finished starting it.
  _daemon_alive && return 0
  mkdir -p "${HOME}/.openclaw/log"
  if [[ -f "$PID_PATH" ]]; then
    local old_pid
    old_pid=$(cat "$PID_PATH" 2>/dev/null || true)
    if ! _retire_old_daemon "$old_pid"; then
      printf '{"jsonrpc":"2.0","error":{"code":-32000,"message":"previous exa-mcp-daemon (pid %s) did not exit — not starting a second one"},"id":null}\n' "$old_pid" >&2
      return 1
    fi
    rm -f "$PID_PATH"
  fi
  rm -f "$SOCKET_PATH"

  nohup python3 "$DAEMON" </dev/null \
    >>"${HOME}/.openclaw/log/exa-mcp-daemon.log" 2>&1 &

  if ! _watch_for_daemon; then
    printf '{"jsonrpc":"2.0","error":{"code":-32000,"message":"exa-mcp-daemon failed to start — check ~/.openclaw/log/exa-mcp-daemon.log"},"id":null}\n' >&2
    return 1
  fi
}

if [[ "${1:-}" == "--start-daemon" ]]; then
  _start_daemon_locked
  exit $?
fi

if ! _daemon_alive; then
  mkdir -p "$(dirname "$LOCK_FILE")"
  rc=0
  python3 -c "$_LOCKRUN" "$LOCK_FILE" "$LOCK_WAIT_SECONDS" bash "$SELF" --start-daemon || rc=$?
  if [[ $rc -eq 1 ]]; then
    exit 1   # the locked section already reported why
  elif [[ $rc -ne 0 ]] && ! _watch_for_daemon; then
    printf '{"jsonrpc":"2.0","error":{"code":-32000,"message":"exa-mcp-daemon still not alive after waiting for the start lock — check ~/.openclaw/log/exa-mcp-daemon.log"},"id":null}\n' >&2
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
