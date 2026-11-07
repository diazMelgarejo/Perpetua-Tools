#!/usr/bin/env python3
"""
spawn_agents.py (PT mirror) — Parallel-agent dispatch.

This is a thin re-export shim so Perpetua-Tools scripts can launch agents
the same way as orama-system scripts.

The canonical implementation lives in orama-system/scripts/spawn_agents.py.
PT scripts/tests that need to dispatch agents should import from this module
(or call it from the CLI) — it delegates to the orama copy via sys.path if
orama-system is a sibling repo, otherwise it runs a self-contained version.

Usage (same as orama version):
    python scripts/spawn_agents.py --status
    python scripts/spawn_agents.py --task "review X" --agent codex
"""

from __future__ import annotations
import os
import sys
import contextvars
from pathlib import Path

_HERE = Path(__file__).resolve()
_PT_ROOT = _HERE.parents[1]
_ORAMA_SIBLING = _PT_ROOT.parent / "orama-system"
_ORAMA_SPAWN = _ORAMA_SIBLING / "scripts" / "spawn_agents.py"

if _ORAMA_SPAWN.exists():
    # Delegate: run orama's authoritative copy
    import importlib.util
    _spec = importlib.util.spec_from_file_location("spawn_agents", _ORAMA_SPAWN)
    assert _spec and _spec.loader
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    # Re-export public API
    discover_agents = _mod.discover_agents  # type: ignore[attr-defined]
    _sibling_dispatch = _mod.dispatch
    if getattr(_mod, "PT_RUNTIME_DISPATCH_GUARD", None) == 1:
        dispatch = _mod.dispatch  # type: ignore[attr-defined]
    else:
        _legacy_scope = contextvars.ContextVar("legacy_dispatch_scope", default=None)
        async def dispatch(agent: str, task: str, model: str | None = None, *, scope: str | None = None) -> dict:
            """Guard older sibling implementations that predate PT runtime enforcement."""
            for path in (_PT_ROOT, _PT_ROOT / "src"):
                if str(path) not in sys.path:
                    sys.path.insert(0, str(path))
            from orchestrator.dispatch_guard import DispatchGuard, DispatchRequest
            from orchestrator.gossip_bus import resolve_default_state_dir

            provider = agent.lower().strip()
            if provider in {"codex", "gemini", "gemini-review", "cursor"} and model is not None:
                raise ValueError("CLI model override is not supported by this worker")
            effective_scope = scope or _legacy_scope.get() or str(_PT_ROOT)
            request = DispatchRequest(effective_scope, provider, model or "provider-default", "spawn-agent", task)
            token = _legacy_scope.set(effective_scope)
            try:
                return await DispatchGuard(resolve_default_state_dir()).execute(request, lambda: _sibling_dispatch(agent, task, model))
            finally:
                _legacy_scope.reset(token)
        _mod.dispatch = dispatch
    print_status = _mod.print_status  # type: ignore[attr-defined]
    if __name__ == "__main__":
        # Older sibling main() calls its own unguarded dispatch symbol.
        _mod.dispatch = dispatch
        _mod.main()
else:
    # Fallback: self-contained stub (orama not present — typical in CI)
    import asyncio, argparse, json, shutil, subprocess, time
    from typing import Any, Dict, Optional

    def _codex_argv(*args: str) -> Optional[list]:
        """Return ``[codex_path, *args]`` or ``None`` when codex is unavailable.

        Windows: PATH-only absolute resolution via ``utils.win_exec`` (never the
        cwd, never a bare name) plus the ``.cmd`` metacharacter refusal in
        ``safe_argv``; an unresolvable binary returns ``None`` while a
        metacharacter refusal raises ``CmdArgumentRefused`` (see ``dispatch``).
        Elsewhere: ``shutil.which`` with the Homebrew fallback, as before.
        """
        if sys.platform == "win32":
            sys.path.insert(0, str(_PT_ROOT / "src"))
            from utils.win_exec import CmdArgumentRefused, WinExecError, resolve_executable, safe_argv
            try:
                return safe_argv(resolve_executable("codex"), args)
            except CmdArgumentRefused:
                raise  # dispatch reports an explicit refusal, not "not found"
            except WinExecError:
                return None
        codex_bin = shutil.which("codex") or "/opt/homebrew/bin/codex"
        return [codex_bin, *args] if os.path.exists(codex_bin) else None

    def discover_agents():  # type: ignore[override]
        """Implement discover agents."""
        from dataclasses import dataclass

        @dataclass
        class _AI:
            """Helper type ``_AI``."""
            name: str; kind: str; available: bool = False; version: str = ""; detail: str = ""

        argv = _codex_argv("--version")
        ok = argv is not None and subprocess.run(argv, capture_output=True, timeout=4).returncode == 0
        return {"codex": _AI("Codex", "cli", ok, detail=argv[0] if argv else "codex")}

    async def dispatch(agent: str, task: str, model: Optional[str] = None, *, scope: Optional[str] = None) -> Dict[str, Any]:
        """Delegate pre-effect authorization and durable identity to PT."""
        if agent.lower().strip() == "codex" and model is not None:
            raise ValueError("CLI model override is not supported by this worker")
        for path in (_PT_ROOT, _PT_ROOT / "src"):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        from orchestrator.dispatch_guard import DispatchGuard, DispatchRequest
        from orchestrator.gossip_bus import resolve_default_state_dir

        request = DispatchRequest(scope or str(_PT_ROOT), agent, model or "provider-default", "spawn-agent", task)
        return await DispatchGuard(resolve_default_state_dir()).execute(
            request, lambda: _dispatch_unchecked(agent, task, model)
        )

    async def _dispatch_unchecked(agent: str, task: str, model: Optional[str] = None) -> Dict[str, Any]:
        """Implement dispatch."""
        try:
            argv = _codex_argv("--full-auto", task) if agent == "codex" else None
        except ValueError:  # win_exec.CmdArgumentRefused (a WinExecError/ValueError)
            return {"ok": False, "output": "refused: cmd metacharacters in arguments"}
        if argv is not None:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                stdin=asyncio.subprocess.DEVNULL,  # prevent stdin inheritance hang when backgrounded
                cwd=str(_PT_ROOT),
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=300)
            return {"ok": proc.returncode == 0, "output": stdout.decode("utf-8", errors="replace"), "elapsed": 0}
        return {"ok": False, "output": f"orama-system not found at {_ORAMA_SIBLING}; only 'codex' is available in PT standalone mode."}

    def print_status():
        """Implement print status."""
        agents = discover_agents()
        for k, ag in agents.items():
            print(f"  {'✓' if ag.available else '✗'}  {ag.name}  {ag.detail}")

    if __name__ == "__main__":
        import argparse as _ap
        p = _ap.ArgumentParser()
        p.add_argument("--task", "-t")
        p.add_argument("--agent", "-a", default="codex")
        p.add_argument("--status", "-s", action="store_true")
        p.add_argument("--json", dest="json_output", action="store_true")
        args = p.parse_args()
        if args.status:
            print_status()
        elif args.task:
            result = asyncio.run(dispatch(args.agent, args.task))
            if args.json_output:
                print(json.dumps(result, indent=2))
            else:
                print(result.get("output", ""))
            sys.exit(0 if result.get("ok") else 1)
