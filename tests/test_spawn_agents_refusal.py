"""spawn_agents.py PT stub: cmd-metacharacter refusal is reported explicitly."""
from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_stub():
    """Import scripts/spawn_agents.py as a fresh module (stub branch when orama is absent)."""
    spec = importlib.util.spec_from_file_location("spawn_agents_under_test", ROOT / "scripts" / "spawn_agents.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(sys.platform != "win32", reason="Windows .cmd shim handling")
def test_dispatch_reports_refusal_not_missing_orama(monkeypatch):
    """A .cmd codex shim plus a metacharacter task yields an explicit refusal message."""
    mod = _load_stub()
    if not hasattr(mod, "_codex_argv"):
        pytest.skip("orama-system sibling present; PT stub not active")
    from utils import win_exec

    monkeypatch.setattr(win_exec, "resolve_executable", lambda name: r"C:\\bin\\codex.cmd")
    out = asyncio.run(mod.dispatch("codex", "do this & that"))
    assert out["ok"] is False
    assert out["output"] == "refused: cmd metacharacters in arguments"
    assert "orama-system not found" not in out["output"]
