"""PT shim must enforce runtime policy even with an older sibling checkout."""
from __future__ import annotations

import asyncio
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def test_dispatch_does_not_require_async_gossip_dependency(tmp_path: Path) -> None:
    """Dispatch state resolution must work without the optional gossip driver."""
    script = tmp_path / "pt" / "scripts" / "spawn_agents.py"
    script.parent.mkdir(parents=True)
    shutil.copyfile(Path(__file__).resolve().parents[1] / "scripts" / "spawn_agents.py", script)
    code = '''
import asyncio, builtins, runpy, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name == "aiosqlite":
        raise ModuleNotFoundError("blocked aiosqlite")
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
sys.path.insert(0, sys.argv[2])
sys.path.insert(0, sys.argv[2] + "/src")
module = runpy.run_path(sys.argv[1])
asyncio.run(module["dispatch"]("unavailable", "test"))
'''
    result = subprocess.run([sys.executable, "-c", code, str(script), str(Path(__file__).resolve().parents[1])], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_old_sibling_cannot_bypass_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-exporting a pre-guard sibling's dispatch would repeat its effect."""
    pt_script = tmp_path / "pt" / "scripts" / "spawn_agents.py"
    pt_script.parent.mkdir(parents=True)
    shutil.copyfile(Path(__file__).resolve().parents[1] / "scripts" / "spawn_agents.py", pt_script)
    sibling = tmp_path / "orama-system" / "scripts" / "spawn_agents.py"
    sibling.parent.mkdir(parents=True)
    sibling.write_text(
        "effects = []\n"
        "def discover_agents(): return {}\n"
        "def print_status(): return None\n"
        "async def dispatch(agent, task, model=None):\n"
        "    effects.append(task)\n"
        "    return {'ok': True, 'output': task}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PT_STATE_DIR", str(tmp_path / "state"))
    module = runpy.run_path(str(pt_script))
    dispatch = module["dispatch"]
    assert asyncio.run(dispatch("codex", "review code"))["ok"] is True
    with pytest.raises(RuntimeError, match="already claimed"):
        asyncio.run(dispatch("codex", "review code"))
    assert module["_mod"].effects == ["review code"]
    with pytest.raises(ValueError, match="model is unavailable"):
        asyncio.run(dispatch("ollama-mac", "review code"))
    with pytest.raises(ValueError, match="Cursor"):
        asyncio.run(dispatch("cursor", "review code"))
    assert module["_mod"].effects == ["review code"]


def test_old_sibling_nested_dispatch_is_guarded_on_import(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Nested legacy dispatch must share the direct call's durable claim."""
    pt_script = tmp_path / "pt" / "scripts" / "spawn_agents.py"
    pt_script.parent.mkdir(parents=True)
    shutil.copyfile(Path(__file__).resolve().parents[1] / "scripts" / "spawn_agents.py", pt_script)
    sibling = tmp_path / "orama-system" / "scripts" / "spawn_agents.py"
    sibling.parent.mkdir(parents=True)
    sibling.write_text(
        "effects = []\n"
        "def discover_agents(): return {}\n"
        "def print_status(): return None\n"
        "async def dispatch(agent, task, model=None):\n"
        "    if agent == 'all': return await dispatch('codex', task)\n"
        "    effects.append(task)\n"
        "    return {'ok': True}\n", encoding="utf-8"
    )
    monkeypatch.setenv("PT_STATE_DIR", str(tmp_path / "state"))
    module = runpy.run_path(str(pt_script))
    dispatch = module["dispatch"]
    with pytest.raises(ValueError, match="fan-out"):
        asyncio.run(dispatch("all", "review code", scope="chosen"))
    asyncio.run(dispatch("codex", "review code", scope="chosen"))
    with pytest.raises(RuntimeError, match="already claimed"):
        asyncio.run(dispatch("codex", "review code", scope="chosen"))
    assert module["_mod"].effects == ["review code"]


def test_marked_sibling_inherits_pt_default_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Upgrading a sibling must not change the default PT claim scope."""
    pt_script = tmp_path / "pt" / "scripts" / "spawn_agents.py"
    pt_script.parent.mkdir(parents=True)
    shutil.copyfile(Path(__file__).resolve().parents[1] / "scripts" / "spawn_agents.py", pt_script)
    sibling = tmp_path / "orama-system" / "scripts" / "spawn_agents.py"
    sibling.parent.mkdir(parents=True)
    sibling.write_text(
        "from __future__ import annotations\n"
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class Agent: name: str\n"
        "PT_RUNTIME_DISPATCH_GUARD = 1\n"
        "def discover_agents(): return {}\n"
        "def print_status(): return None\n"
        "async def dispatch(agent, task, model=None, *, scope=None): return {'scope': scope}\n",
        encoding="utf-8",
    )
    module = runpy.run_path(str(pt_script))
    assert asyncio.run(module["dispatch"]("codex", "task"))["scope"] == str(pt_script.parents[1])


def test_marked_sibling_nested_dispatch_inherits_explicit_scope(tmp_path: Path) -> None:
    """A delegated fan-out must not silently revert its leaves to PT's default."""
    pt_script = tmp_path / "pt" / "scripts" / "spawn_agents.py"
    pt_script.parent.mkdir(parents=True)
    shutil.copyfile(Path(__file__).resolve().parents[1] / "scripts" / "spawn_agents.py", pt_script)
    sibling = tmp_path / "orama-system" / "scripts" / "spawn_agents.py"
    sibling.parent.mkdir(parents=True)
    sibling.write_text(
        "PT_RUNTIME_DISPATCH_GUARD = 1\n"
        "def discover_agents(): return {}\n"
        "def print_status(): return None\n"
        "async def dispatch(agent, task, model=None, *, scope=None):\n"
        "    if agent == 'all': return await dispatch('codex', task)\n"
        "    return {'scope': scope}\n",
        encoding="utf-8",
    )
    module = runpy.run_path(str(pt_script))
    module["_mod"].dispatch = module["dispatch"]
    assert asyncio.run(module["dispatch"]("all", "task", scope="chosen"))["scope"] == "chosen"


def test_legacy_fanout_cannot_bypass_leaf_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An opaque legacy fan-out must not call an unguarded private helper."""
    pt_script = tmp_path / "pt" / "scripts" / "spawn_agents.py"
    pt_script.parent.mkdir(parents=True)
    shutil.copyfile(Path(__file__).resolve().parents[1] / "scripts" / "spawn_agents.py", pt_script)
    sibling = tmp_path / "orama-system" / "scripts" / "spawn_agents.py"
    sibling.parent.mkdir(parents=True)
    sibling.write_text(
        "effects = []\n"
        "def discover_agents(): return {}\n"
        "def print_status(): return None\n"
        "async def _dispatch_codex(task): effects.append(task); return {'ok': True}\n"
        "async def dispatch(agent, task, model=None): return await _dispatch_codex(task)\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PT_STATE_DIR", str(tmp_path / "state"))
    module = runpy.run_path(str(pt_script))
    asyncio.run(module["dispatch"]("codex", "task"))
    with pytest.raises((RuntimeError, ValueError)):
        asyncio.run(module["dispatch"]("all", "task"))
    with pytest.raises(RuntimeError, match="already claimed"):
        asyncio.run(module["_mod"]._dispatch_codex("task"))
    assert module["_mod"].effects == ["task"]
