#!/usr/bin/env python3
"""Bootstrap AlphaClaw gateway for Perplexity-Tools (idempotent)."""

from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
from pathlib import Path

import httpx

ALPHACLAW_PORT = 18789
ALPHACLAW_URL = f"http://127.0.0.1:{ALPHACLAW_PORT}"
INSTALL_DIR = Path.cwd()


def _installed() -> bool:
    return shutil.which("alphaclaw") is not None or (INSTALL_DIR / "node_modules" / "@chrysb" / "alphaclaw").exists()


async def _health(url: str = ALPHACLAW_URL) -> bool:
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            resp = await client.get(f"{url}/health")
            return resp.status_code < 400
    except Exception:
        return False


def _run(cmd: list[str]) -> bool:
    proc = subprocess.run(cmd, cwd=INSTALL_DIR)
    return proc.returncode == 0


def _start_gateway() -> subprocess.Popen[str]:
    return subprocess.Popen(
        ["npx", "alphaclaw", "start"],
        cwd=INSTALL_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


async def _wait_for_gateway(url: str = ALPHACLAW_URL, timeout: int = 30) -> bool:
    bar_width = 38
    print(f"\n  [alphaclaw] Waiting for gateway at {url}…")
    for elapsed in range(timeout + 1):
        filled = int(bar_width * elapsed / timeout)
        bar = "█" * filled + "░" * (bar_width - filled)
        pct = int(100 * elapsed / timeout)
        left = timeout - elapsed
        print(f"\r  [alphaclaw] [{bar}] {pct:3d}%  ({left:2d}s)  ", end="", flush=True)
        if await _health(url):
            print(f"\r  [alphaclaw] [{'█' * bar_width}] 100%  ✓ ready          ")
            return True
        if elapsed < timeout:
            await asyncio.sleep(1)
    print(f"\r  [alphaclaw] [{'░' * bar_width}] timed out after {timeout}s           ")
    return False


async def bootstrap(force: bool = False) -> int:
    if not force and await _health():
        print("✓ AlphaClaw already running")
        return 0

    if not _installed():
        print("→ Installing @chrysb/alphaclaw")
        if not _run(["npm", "install", "@chrysb/alphaclaw@latest"]):
            print("✗ AlphaClaw install failed")
            return 1
    else:
        print("✓ AlphaClaw already installed")

    if not await _health():
        print("→ Starting AlphaClaw gateway")
        _start_gateway()

    ok = await _wait_for_gateway()
    return 0 if ok else 2


async def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap AlphaClaw gateway")
    parser.add_argument("--bootstrap", action="store_true", help="run full bootstrap")
    parser.add_argument("--force", action="store_true", help="force reinstall/restart")
    args = parser.parse_args()

    if args.bootstrap:
        return await bootstrap(force=args.force)

    print("Nothing to do. Use --bootstrap")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
