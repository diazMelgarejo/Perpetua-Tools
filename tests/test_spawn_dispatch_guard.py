"""PT shim must enforce runtime policy even with an older sibling checkout."""
from __future__ import annotations

import asyncio
import runpy
import shutil
from pathlib import Path

import pytest


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
    asyncio.run(dispatch("all", "review code", scope="chosen"))
    with pytest.raises(RuntimeError, match="already claimed"):
        asyncio.run(dispatch("codex", "review code", scope="chosen"))
    assert module["_mod"].effects == ["review code"]
