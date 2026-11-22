"""Characterization tests for PT's manual v1 stale-claim cleanup (closure C2).

These tests cover the historical entry points and the L-1r hold: heartbeat
silence is not proof a worker stopped. PT remains manual; no cleanup is
scheduled or automated here.

Reference: docs/coordination/manual-cleanup-characterization-2026-11-06.md.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import aiosqlite
import pytest

import orchestrator.heartbeat_monitor as heartbeat_monitor
import orchestrator.coordination.task_queue as task_queue
from orchestrator.coordination import cli as core_cli
from orchestrator.coordination.liveness import _heartbeat_cleanup
from orchestrator.coordination.task_queue import (
    cleanup_stale_queue_claims,
    latest_task_snapshots,
    queue_add,
    queue_claim,
    try_atomic_claim,
)
from orchestrator.coordination.types import ClaimResult, QueuedTaskState, ReleaseResult
from orchestrator.gossip_bus import GossipBus, GossipBusError
from orchestrator.heartbeat_monitor import (
    LIVENESS_STALLED_SEC,
    cleanup_stale_claims,
    find_agent_heartbeats,
    find_open_claims,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
async def bus(tmp_path: Path) -> GossipBus:
    """Return a freshly initialized, isolated GossipBus."""
    instance = GossipBus(str(tmp_path / "characterization.db"))
    await instance.init_db()
    return instance


def _advance_past_dead_threshold(monkeypatch: pytest.MonkeyPatch) -> float:
    """Move wall-clock time past the DEAD threshold for already-stored events.

    Events emitted before this call keep their real timestamps; anything
    emitted afterwards is stamped with the shifted clock.
    """
    shifted = time.time() + LIVENESS_STALLED_SEC + 60
    monkeypatch.setattr(time, "time", lambda: shifted)
    return shifted


async def _legacy_claim(bus: GossipBus, agent_id: str, task: str) -> None:
    """Record a legacy register + agent_claim pair for ``agent_id``."""
    await bus.emit(
        "heartbeat",
        {"kind": "agent_register", "agent_id": agent_id, "agent_type": "t", "model": "m"},
    )
    await bus.emit("heartbeat", {"kind": "agent_claim", "agent_id": agent_id, "task": task})


async def _queued_task_claimed_by(bus: GossipBus, agent_id: str, name: str) -> str:
    """Enqueue ``name`` and claim it for ``agent_id``; return the task id."""
    await queue_add(bus, name, "Phase-1", "NORMAL", "", None)
    snapshots = await latest_task_snapshots(bus)
    task_id = next(tid for tid, s in snapshots.items() if s.get("task_name") == name)
    assert await queue_claim(bus, task_id, agent_id) is None
    return task_id


async def _claim_row_holder(bus: GossipBus, task_id: str) -> str | None:
    """Return the agent holding the task_claims row, or None if absent."""
    async with bus.connect() as db:
        cursor = await db.execute(
            "SELECT agent_id FROM task_claims WHERE task_id = ?", (task_id,)
        )
        row = await cursor.fetchone()
    return row[0] if row else None


# ── CLI surface and manual-only invariant ───────────────────────────────────


def test_heartbeat_cli_has_exactly_seven_manual_leaves_and_no_daemon() -> None:
    """The heartbeat group exposes seven one-shot leaves; there is no daemon."""
    parser = core_cli.build_parser()
    heartbeat_action = next(
        a for a in parser._subparsers._group_actions[0].choices["heartbeat"]._actions
        if a.dest == "subcmd"
    )
    assert set(heartbeat_action.choices) == {
        "list", "check", "dashboard", "pulse", "kill", "timeline", "cleanup",
    }
    assert not (REPO_ROOT / "orchestrator" / "coordination" / "daemon.py").exists()
    assert not hasattr(heartbeat_monitor, "heartbeat_cleanup")


def test_compat_shims_expose_the_same_cleanup_handler() -> None:
    """D2: every historical script entrypoint re-exports the canonical handler."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        import agent_coordination
        import agent_coordination_core
        import agent_coordination_legacy
        import agent_coordination_phases
    finally:
        sys.path.remove(str(REPO_ROOT / "scripts"))
    for module in (
        agent_coordination,
        agent_coordination_core,
        agent_coordination_legacy,
        agent_coordination_phases,
    ):
        assert module._heartbeat_cleanup is _heartbeat_cleanup
        assert module.main is core_cli.main


async def test_cleanup_handler_prints_and_returns_none_when_nothing_released(
    bus: GossipBus, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CLI handler returns None, so the process exit code is 0 either way."""
    result = await _heartbeat_cleanup(bus)
    assert result is None
    assert capsys.readouterr().out.strip() == "no stale claims released"
    assert core_cli._exit_code(result) == 0


async def test_cleanup_handler_reports_no_releases_for_held_claims(bus: GossipBus, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """A manual cleanup does not release claims merely classified DEAD."""
    await _legacy_claim(bus, "dead-a", "task-1")
    _advance_past_dead_threshold(monkeypatch)
    await _heartbeat_cleanup(bus)
    assert capsys.readouterr().out.strip() == "no stale claims released"


def test_cli_cleanup_on_corrupt_database_exits_nonzero_without_traceback(
    tmp_path: Path,
) -> None:
    """GossipBusError from initialization is reported as ERROR with exit 1."""
    db_path = tmp_path / "corrupt.db"
    db_path.write_bytes(b"not a sqlite database")
    env = {**os.environ, "GOSSIP_DB_PATH": str(db_path)}
    env.pop("PT_STATE_DIR", None)
    env.pop("GOSSIP_PEERS", None)
    result = subprocess.run(
        [sys.executable, "scripts/agent_coordination.py", "heartbeat", "cleanup"],
        capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 1
    assert "ERROR" in result.stderr
    assert "Traceback" not in result.stderr


# ── Legacy agent_claim cleanup ──────────────────────────────────────────────


async def test_max_age_seconds_argument_is_accepted_but_ignored(bus: GossipBus) -> None:
    """Only the fixed DEAD classification matters; max_age_seconds is unused."""
    await _legacy_claim(bus, "fresh-agent", "task-fresh")
    assert await cleanup_stale_claims(bus, max_age_seconds=0) == []
    assert [c["task"] for c in await find_open_claims(bus)] == ["task-fresh"]


async def test_legacy_dead_holder_is_held_without_release_event(bus: GossipBus, monkeypatch: pytest.MonkeyPatch) -> None:
    """Silence does not establish termination or emit an agent release."""
    await _legacy_claim(bus, "dead-agent", "task-x")
    _advance_past_dead_threshold(monkeypatch)
    assert await cleanup_stale_claims(bus) == []
    assert await heartbeat_monitor._fetch_heartbeat_events(bus, ("agent_release",)) == []
    assert [c["task"] for c in await find_open_claims(bus)] == ["task-x"]


async def test_repeated_manual_cleanup_is_idempotent(bus: GossipBus, monkeypatch: pytest.MonkeyPatch) -> None:
    """Repeated cleanup retains the same claim."""
    await _legacy_claim(bus, "dead-agent", "task-x")
    _advance_past_dead_threshold(monkeypatch)
    assert await cleanup_stale_claims(bus) == []
    assert await cleanup_stale_claims(bus) == []
    assert [c["task"] for c in await find_open_claims(bus)] == ["task-x"]


async def test_kill_then_cleanup_holds_recent_claim(bus: GossipBus) -> None:
    """A recorded kill is not an attestation that a process stopped."""
    await _legacy_claim(bus, "killed-agent", "task-k")
    await bus.emit("heartbeat", {"kind": "agent_killed", "agent_id": "killed-agent", "reason": "manual"})
    assert await cleanup_stale_claims(bus) == []
    assert [c["task"] for c in await find_open_claims(bus)] == ["task-k"]


async def test_pulse_after_kill_revives_and_prevents_release(bus: GossipBus) -> None:
    """A pulse after a kill clears the kill marker, so cleanup keeps the claim."""
    await _legacy_claim(bus, "revived", "task-r")
    await bus.emit("heartbeat", {"kind": "agent_killed", "agent_id": "revived", "reason": "x"})
    await bus.emit("heartbeat", {"kind": "agent_pulse", "agent_id": "revived"})
    assert await cleanup_stale_claims(bus) == []


async def test_legacy_cleanup_rechecks_liveness_before_emit(
    bus: GossipBus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The release transaction keeps the claim when its own read sees a live holder."""
    await _legacy_claim(bus, "late-pulser", "task-late")
    _advance_past_dead_threshold(monkeypatch)
    real_heartbeats = heartbeat_monitor.find_agent_heartbeats

    async def live_inside_transaction(
        target_bus: GossipBus,
        agent_id: str | None = None,
        *,
        connection: object | None = None,
    ) -> dict[str, dict]:
        """Outer classification stays DEAD. The locked read sees the revival."""
        found = await real_heartbeats(target_bus, agent_id, connection=connection)
        if connection is not None and "late-pulser" in found:
            found = dict(found)
            found["late-pulser"] = {**found["late-pulser"], "status": "ACTIVE"}
        return found

    monkeypatch.setattr(heartbeat_monitor, "find_agent_heartbeats", live_inside_transaction)
    assert await cleanup_stale_claims(bus) == []
    assert [c["task"] for c in await find_open_claims(bus)] == ["task-late"]


async def test_cleanup_never_attempts_legacy_release_write(bus: GossipBus, monkeypatch: pytest.MonkeyPatch) -> None:
    """A release insertion is not attempted when claims are held."""
    await _legacy_claim(bus, "dead-a", "task-1")
    _advance_past_dead_threshold(monkeypatch)
    async def unexpected_insert(*args: object, **kwargs: object) -> None:
        """Fail if held-claim cleanup attempts to publish a release."""
        raise AssertionError("cleanup attempted a write")
    monkeypatch.setattr(bus, "insert_event", unexpected_insert)
    assert await cleanup_stale_claims(bus) == []
    assert [c["task"] for c in await find_open_claims(bus)] == ["task-1"]


async def test_legacy_claim_remains_held_when_release_store_would_fail(bus: GossipBus, monkeypatch: pytest.MonkeyPatch) -> None:
    """A would-be release write cannot change the held claim."""
    await _legacy_claim(bus, "dead-db", "task-db")
    _advance_past_dead_threshold(monkeypatch)
    async def injected_lock(*args: object, **kwargs: object) -> None:
        """Model a release store that would reject writes if invoked."""
        raise sqlite3.OperationalError("injected lock")
    monkeypatch.setattr(bus, "insert_event", injected_lock)
    assert await cleanup_stale_claims(bus) == []
    assert [c["task"] for c in await find_open_claims(bus)] == ["task-db"]


async def test_bridge_cleanup_does_not_forward_release(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Holding a claim does not forward a release over the LAN bridge."""
    from orchestrator.lan_gossip_bridge import LanGossipBridge
    bridge = LanGossipBridge(str(tmp_path / "bridge.db"), peers=[])
    forwarded: list[str] = []
    async def spy(event_type: str, payload: dict, event_uuid: str) -> None:
        """Record forwarded event identities without contacting a peer."""
        forwarded.append(event_uuid)
    await _legacy_claim(bridge, "dead-lan", "task-lan")
    monkeypatch.setattr(bridge, "forward_committed", spy)
    _advance_past_dead_threshold(monkeypatch)
    assert await cleanup_stale_claims(bridge) == []
    assert forwarded == []
    assert [c["task"] for c in await find_open_claims(bridge)] == ["task-lan"]


async def test_read_errors_after_initialization_are_not_wrapped(
    bus: GossipBus,
) -> None:
    """Liveness reads use raw SQL; a store error surfaces as sqlite3.Error."""
    async with bus.connect() as db:
        await db.execute("DROP TABLE gossip")
        await db.commit()
    with pytest.raises(aiosqlite.OperationalError):
        await cleanup_stale_claims(bus)


# ── Distributed-queue (task_claims) cleanup ─────────────────────────────────


async def test_queue_cleanup_holds_dead_holder_and_retry_count(bus: GossipBus, monkeypatch: pytest.MonkeyPatch) -> None:
    """The claim and folded state remain intact when the worker is silent."""
    task_id = await _queued_task_claimed_by(bus, "dead-q", "queue-work")
    _advance_past_dead_threshold(monkeypatch)
    assert await cleanup_stale_claims(bus) == []
    assert await _claim_row_holder(bus, task_id) == "dead-q"
    state = (await latest_task_snapshots(bus))[task_id]
    assert state["status"] == QueuedTaskState.CLAIMED.value
    assert state.get("retry_count", 0) == 0


async def test_queue_cleanup_does_not_fold_or_release_held_holder(bus: GossipBus, monkeypatch: pytest.MonkeyPatch) -> None:
    """A held claim requires no folded snapshot or release write."""
    task_id = await _queued_task_claimed_by(bus, "dead-q", "handover-work")
    async def unexpected_fold(target_bus: GossipBus) -> dict:
        """Fail if cleanup folds task state instead of leaving the claim held."""
        raise AssertionError("held claim should not be folded")
    monkeypatch.setattr(task_queue, "latest_task_snapshots", unexpected_fold)
    assert await cleanup_stale_queue_claims(bus, {"dead-q"}) == []
    assert await _claim_row_holder(bus, task_id) == "dead-q"


async def test_queue_release_contention_is_silently_skipped(
    bus: GossipBus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A CONTENTION result is neither reported as released nor raised."""
    task_id = await _queued_task_claimed_by(bus, "dead-q", "busy-work")

    async def always_busy(*_args: object, **_kwargs: object) -> ReleaseResult:
        """Return contention without releasing the retained claim."""
        return ReleaseResult.CONTENTION

    monkeypatch.setattr(task_queue, "release_claim_with_event", always_busy)
    assert await cleanup_stale_queue_claims(bus, {"dead-q"}) == []
    assert await _claim_row_holder(bus, task_id) == "dead-q"


async def test_queue_holder_without_liveness_events_is_never_released(
    bus: GossipBus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only agents seen by find_agent_heartbeats can be classified DEAD."""
    assert await try_atomic_claim(bus, "orphan-task", "ghost") == ClaimResult.WON
    _advance_past_dead_threshold(monkeypatch)
    assert "ghost" not in await find_agent_heartbeats(bus)
    assert await cleanup_stale_claims(bus) == []
    assert await _claim_row_holder(bus, "orphan-task") == "ghost"


async def test_queue_cleanup_with_no_dead_agents_skips_the_query(bus: GossipBus) -> None:
    """An empty dead set returns immediately without touching task_claims."""
    assert await cleanup_stale_queue_claims(bus, set()) == []
