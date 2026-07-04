#!/usr/bin/env python3
"""
exa-mcp-daemon.py — singleton Exa MCP multiplexer

One backend (npx exa-mcp-server) handles all three Claude registrations.
Clients (Claude Desktop, orama, PT) connect via Unix socket; daemon
routes JSON-RPC through the shared backend with per-client ID remapping.

Socket:  ~/.openclaw/run/exa-mcp.sock
PID:     ~/.openclaw/run/exa-mcp.pid
Log:     ~/.openclaw/log/exa-mcp-daemon.log

Protocol notes:
- Request IDs are mangled to "{client_id}:{original_id}" on the wire to
  the backend so responses can be routed back to the right client.
- initialize responses are cached after the first client; subsequent
  clients receive the cached capabilities without re-hitting the backend.
- Server-originated notifications (no id) are broadcast to all clients.
- tools/list responses are cached after the first call; subsequent
  clients receive the cache without extra backend round-trips.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
import signal
import subprocess
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
RUN_DIR = pathlib.Path.home() / ".openclaw" / "run"
LOG_DIR = pathlib.Path.home() / ".openclaw" / "log"
SOCKET_PATH = RUN_DIR / "exa-mcp.sock"
PID_PATH = RUN_DIR / "exa-mcp.pid"
LOG_PATH = LOG_DIR / "exa-mcp-daemon.log"

# Prefer nvm node; fall back to PATH
_NVM_NODE = pathlib.Path.home() / ".nvm" / "versions" / "node" / "v22.22.2" / "bin" / "npx"
NPX = str(_NVM_NODE) if _NVM_NODE.exists() else "npx"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("exa-mcp-daemon")


# ---------------------------------------------------------------------------
# Daemon core
# ---------------------------------------------------------------------------
class ExaMuxDaemon:
    def __init__(self) -> None:
        self.proc: asyncio.subprocess.Process | None = None
        self.clients: dict[int, asyncio.Queue] = {}
        self._next_client_id = 0
        self._cached_caps: dict | None = None      # initialize result
        self._cached_tools: dict | None = None     # tools/list result
        self._backend_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Backend lifecycle
    # ------------------------------------------------------------------
    async def _start_backend(self) -> None:
        env = os.environ.copy()
        self.proc = await asyncio.create_subprocess_exec(
            NPX, "-y", "exa-mcp-server",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        log.info("backend started (pid=%d)", self.proc.pid)
        asyncio.create_task(self._read_backend())
        asyncio.create_task(self._drain_stderr())

    async def _drain_stderr(self) -> None:
        assert self.proc and self.proc.stderr
        while True:
            line = await self.proc.stderr.readline()
            if not line:
                break
            log.debug("backend stderr: %s", line.decode(errors="replace").rstrip())

    async def _read_backend(self) -> None:
        """Route backend stdout lines to the right client queue."""
        assert self.proc and self.proc.stdout
        while True:
            line = await self.proc.stdout.readline()
            if not line:
                log.warning("backend stdout closed — daemon exiting")
                asyncio.get_event_loop().stop()
                return
            raw = line.strip()
            if not raw:
                continue
            try:
                msg: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("non-JSON from backend: %s", raw[:200])
                continue

            msg_id = msg.get("id")

            if msg_id is None:
                # Notification — broadcast
                for q in list(self.clients.values()):
                    await q.put(msg)
                continue

            # Response — demux by mangled ID
            if isinstance(msg_id, str) and ":" in msg_id:
                client_str, orig_id_str = msg_id.split(":", 1)
                try:
                    client_id = int(client_str)
                    orig_id: Any = int(orig_id_str) if orig_id_str.lstrip("-").isdigit() else orig_id_str
                except ValueError:
                    log.warning("cannot demux id=%s", msg_id)
                    continue
                msg["id"] = orig_id

                # Cache capabilities from initialize response
                if isinstance(msg.get("result"), dict) and "capabilities" in msg["result"]:
                    self._cached_caps = msg["result"]
                    log.info("capabilities cached from first initialize")

                # Cache tools/list
                if isinstance(msg.get("result"), dict) and "tools" in msg["result"]:
                    self._cached_tools = msg["result"]
                    log.info("tools/list cached (%d tools)", len(self._cached_tools.get("tools", [])))

                q = self.clients.get(client_id)
                if q:
                    await q.put(msg)
                else:
                    log.debug("no client %d for response id=%s", client_id, orig_id)
            else:
                log.warning("unexpected backend id format: %s", msg_id)

    # ------------------------------------------------------------------
    # Client handler (one per Unix socket connection)
    # ------------------------------------------------------------------
    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        client_id = self._next_client_id
        self._next_client_id += 1
        outgoing: asyncio.Queue = asyncio.Queue()
        self.clients[client_id] = outgoing
        log.info("client %d connected (total=%d)", client_id, len(self.clients))

        async def _send_loop() -> None:
            while True:
                msg = await outgoing.get()
                writer.write(json.dumps(msg).encode() + b"\n")
                await writer.drain()

        send_task = asyncio.create_task(_send_loop())
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                raw = line.strip()
                if not raw:
                    continue
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                orig_id = msg.get("id")
                method = msg.get("method", "")

                # ---- Short-circuit: initialize from cached caps --------
                if method == "initialize" and self._cached_caps and orig_id is not None:
                    await outgoing.put({
                        "jsonrpc": "2.0",
                        "id": orig_id,
                        "result": self._cached_caps,
                    })
                    log.debug("client %d: served initialize from cache", client_id)
                    continue

                # ---- Short-circuit: tools/list from cache ---------------
                if method == "tools/list" and self._cached_tools and orig_id is not None:
                    await outgoing.put({
                        "jsonrpc": "2.0",
                        "id": orig_id,
                        "result": self._cached_tools,
                    })
                    log.debug("client %d: served tools/list from cache", client_id)
                    continue

                # ---- Forward to backend with mangled ID -----------------
                if orig_id is not None:
                    msg["id"] = f"{client_id}:{orig_id}"

                assert self.proc and self.proc.stdin
                async with self._backend_lock:
                    self.proc.stdin.write(json.dumps(msg).encode() + b"\n")
                    await self.proc.stdin.drain()

        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        finally:
            send_task.cancel()
            self.clients.pop(client_id, None)
            writer.close()
            log.info("client %d disconnected (total=%d)", client_id, len(self.clients))

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    async def run(self) -> None:
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        SOCKET_PATH.unlink(missing_ok=True)

        await self._start_backend()

        server = await asyncio.start_unix_server(self.handle_client, path=str(SOCKET_PATH))
        SOCKET_PATH.chmod(0o600)
        PID_PATH.write_text(str(os.getpid()))
        log.info("daemon ready at %s (pid=%d)", SOCKET_PATH, os.getpid())

        def _shutdown(*_: Any) -> None:
            log.info("shutdown signal received")
            server.close()
            if self.proc:
                self.proc.terminate()
            SOCKET_PATH.unlink(missing_ok=True)
            PID_PATH.unlink(missing_ok=True)

        for sig in (signal.SIGTERM, signal.SIGINT):
            asyncio.get_event_loop().add_signal_handler(sig, _shutdown)

        async with server:
            await server.serve_forever()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(ExaMuxDaemon().run())
