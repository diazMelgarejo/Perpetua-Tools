"""tests/test_agent_coordination.py

Pure-logic tests for scripts/agent_coordination.py helpers.

These tests construct a temporary GossipBus per test and exercise the async
helper functions directly. They avoid the real .state/perpetua_core.db and do
not depend on the CLI argparse layer.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

# Ensure project root is on path for scripts/agent_coordination + orchestrator.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.agent_coordination import (
    _agents,
    _claim,
    _known_agent_ids,
    _list,
    _log,
    _phase_list,
    _phase_start,
    _register,
    _release,
    canonical_db_path,
    canonical_repo_root,
    current_worktree_label,
)
from scripts import agent_coordination_core, agent_coordination_legacy
from orchestrator.gossip_bus import GossipBus


@pytest.fixture
def make_bus(tmp_path):
    """Factory for temporary, freshly-initialised GossipBus instances."""

    async def _factory():
        db_path = str(tmp_path / "coordination_test.db")
        bus = GossipBus(db_path)
        await bus.init_db()
        return bus

    return _factory


async def test_register_then_known_agent_ids(make_bus):
    bus = await make_bus()
    await _register(bus, "kimi-t1", "cli-tool", "kimi-code", "test registration")
    ids = await _known_agent_ids(bus)
    assert "kimi-t1" in ids


async def test_claim_then_release_no_longer_open(make_bus, capsys):
    bus = await make_bus()
    await _register(bus, "agy-a1", "llm-agent", "gemini", "claim/release test")

    await _claim(bus, "agy-a1", "task/alpha", "working on it")
    await _release(bus, "agy-a1", "task/alpha")
    await _list(bus, None)

    captured = capsys.readouterr()
    assert "no open claims" in captured.out


async def test_claim_without_release_shows_open(make_bus, capsys):
    bus = await make_bus()
    await _register(bus, "kimi-t2", "cli-tool", "kimi-code", "open claim test")

    await _claim(bus, "kimi-t2", "task/beta", "notes-beta")
    await _list(bus, None)

    captured = capsys.readouterr()
    assert "OPEN  task/beta" in captured.out
    assert "kimi-t2" in captured.out
    assert "notes-beta" in captured.out


async def test_two_tasks_claimed_by_two_agents(make_bus, capsys):
    bus = await make_bus()
    await _register(bus, "agent-x", "cli-tool", "model-x", "multi claim test")
    await _register(bus, "agent-y", "llm-agent", "model-y", "multi claim test")

    await _claim(bus, "agent-x", "task/x", "notes-x")
    await _claim(bus, "agent-y", "task/y", "notes-y")
    await _list(bus, None)

    captured = capsys.readouterr()
    assert captured.out.count("OPEN") == 2
    assert "OPEN  task/x" in captured.out
    assert "OPEN  task/y" in captured.out
    assert "agent-x" in captured.out
    assert "agent-y" in captured.out


async def test_second_claim_on_same_task_wins(make_bus, capsys):
    """Last-claim-wins: a second claim without an intervening release overwrites."""
    bus = await make_bus()
    await _register(bus, "agent-first", "cli-tool", "model-a", "last wins test")
    await _register(bus, "agent-second", "llm-agent", "model-b", "last wins test")

    await _claim(bus, "agent-first", "task/shared", "first claim")
    await _claim(bus, "agent-second", "task/shared", "second claim")
    await _list(bus, None)

    captured = capsys.readouterr()
    open_lines = [line for line in captured.out.splitlines() if line.startswith("OPEN")]
    assert len(open_lines) == 1
    open_line = open_lines[0]
    assert "OPEN  task/shared" in open_line
    assert "agent-second" in open_line
    assert "second claim" in open_line
    assert "agent-first" not in open_line
    assert "first claim" not in open_line


async def test_list_task_filter_excludes_other_tasks(make_bus, capsys):
    bus = await make_bus()
    await _register(bus, "agent-f", "cli-tool", "model-f", "filter test")

    await _claim(bus, "agent-f", "task/filtered", "filtered notes")
    await _claim(bus, "agent-f", "task/other", "other notes")
    await _list(bus, "task/filtered")

    captured = capsys.readouterr()
    open_lines = [line for line in captured.out.splitlines() if line.startswith("OPEN")]
    assert len(open_lines) == 1
    assert "OPEN  task/filtered" in open_lines[0]
    assert "task/other" not in open_lines[0]


@pytest.mark.asyncio
async def test_list_survives_heartbeat_noise_beyond_tail_window(make_bus, capsys):
    """Legacy list must not drop open claims once unrelated heartbeat volume
    exceeds bus.tail()'s size-bounded window."""
    bus = await make_bus()
    await _register(bus, "claimer", "cli-tool", "model-x", "noise test")
    await _claim(bus, "claimer", "important-task", "hold this")

    for i in range(1500):
        await bus.emit(
            "heartbeat",
            {"kind": "agent_pulse", "agent_id": f"noise-{i % 10}", "seq": i},
        )

    await _list(bus, None)
    captured = capsys.readouterr()
    assert "OPEN  important-task" in captured.out
    assert "claimer" in captured.out


async def test_agents_lists_registered_agent(make_bus, capsys):
    bus = await make_bus()
    await _register(bus, "agent-z", "human", "model-z", "agents list test")
    await _agents(bus)

    captured = capsys.readouterr()
    assert "agent-z" in captured.out
    assert "human" in captured.out
    assert "model-z" in captured.out


async def test_log_emits_note(make_bus, capsys):
    bus = await make_bus()
    await _log(bus, "agent-w", "hello from test")
    captured = capsys.readouterr()
    assert "logged" in captured.out

    # Verify the event is actually in the bus.
    events = await bus.tail(limit=10, event_type="heartbeat")
    note_events = [e for e in events if e["payload"].get("kind") == "agent_note"]
    assert len(note_events) == 1
    assert note_events[0]["payload"]["message"] == "hello from test"


async def test_phase_list_handles_nonnumeric_phase_names(make_bus, capsys):
    bus = await make_bus()
    await _phase_start(bus, "StateTransitionManager-Integration", None, "agent-z")
    await _phase_list(bus)

    captured = capsys.readouterr()
    assert "StateTransitionManager-Integration" in captured.out


@pytest.mark.parametrize(
    "module",
    [agent_coordination_core, agent_coordination_legacy],
)
async def test_compat_phase_list_handles_nonnumeric_phase_names(module, make_bus, capsys):
    if module is agent_coordination_legacy:
        module = importlib.reload(module)
    bus = await make_bus()
    await module._phase_start(bus, "StateTransitionManager-Integration", None, "agent-z")
    await module._phase_list(bus)

    captured = capsys.readouterr()
    assert "StateTransitionManager-Integration" in captured.out


@pytest.mark.parametrize(
    "module",
    [agent_coordination_core, agent_coordination_legacy],
)
async def test_compat_phase_list_orders_dotted_numbers_numerically(
    module, make_bus, capsys
):
    if module is agent_coordination_legacy:
        module = importlib.reload(module)
    bus = await make_bus()
    await module._phase_start(bus, "Phase-2.10", None, "agent-z")
    await module._phase_start(bus, "Phase-2.9", None, "agent-z")
    await module._phase_list(bus)

    captured = capsys.readouterr()
    listed = captured.out.splitlines()[2:]
    assert "\n".join(listed).index("Phase-2.9") < "\n".join(listed).index("Phase-2.10")


def test_canonical_repo_root_is_git_directory():
    root = canonical_repo_root()
    assert isinstance(root, Path)
    assert root.is_dir()
    assert (root / ".git").exists() or (root / ".git").is_symlink()


def test_canonical_repo_root_independent_of_pt_state_dir(monkeypatch):
    """Regression: canonical_repo_root() must derive the repo root from git
    directly, never from resolve_default_state_dir()/PT_STATE_DIR -- runtime
    state location is a configurable override; repository identity is not,
    and must never be influenced by where state happens to be pointed."""
    real_root = canonical_repo_root()
    monkeypatch.setenv("PT_STATE_DIR", "/tmp/totally-unrelated-scratch-dir")
    root_with_override = canonical_repo_root()
    assert root_with_override == real_root
    assert "totally-unrelated-scratch-dir" not in str(root_with_override)


def test_canonical_db_path_looks_sane():
    path = canonical_db_path()
    assert path.endswith(".state/perpetua_core.db")
    assert Path(path).parent.name == ".state"


def test_current_worktree_label_contains_cwd_or_branch():
    label = current_worktree_label()
    # Format: branch@cwd. Either component is enough to sanity-check.
    assert str(Path.cwd()) in label or "?" in label
