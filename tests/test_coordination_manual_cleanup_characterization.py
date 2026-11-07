"""Characterization tests for PT's manual v1 stale-claim cleanup (closure C2).

These tests pin the CURRENT behavior of ``heartbeat cleanup`` and its helpers
so that later work can detect any drift. They are expected to pass on the
code they were written against; passing is their purpose, not evidence that
the behavior is desirable. Several of them pin known gaps (time-of-check /
time-of-use liveness, retry-count resurrection, silently skipped contention)
that ratified decision D1 assigns to the separate v2 Controller rather than
to PT. PT remains manual: nothing here schedules or automates the cleanup.

Reference: docs/coordination/manual-cleanup-characterization-2026-11-06.md.
"""
from __future__ import annotations

import os
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


async def test_cleanup_handler_lists_released_names(
    bus: GossipBus, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Released legacy task names are printed comma-separated in claim order."""
    await _legacy_claim(bus, "dead-a", "task-1")
    await _legacy_claim(bus, "dead-b", "task-2")
    _advance_past_dead_threshold(monkeypatch)
    await _heartbeat_cleanup(bus)
    assert capsys.readouterr().out.strip() == "released: task-1, task-2"


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


async def test_legacy_release_is_emitted_on_behalf_of_the_dead_holder(
    bus: GossipBus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The release names the original holder and is marked auto_released."""
    await _legacy_claim(bus, "dead-agent", "task-x")
    _advance_past_dead_threshold(monkeypatch)
    assert await cleanup_stale_claims(bus) == ["task-x"]
    events = await heartbeat_monitor._fetch_heartbeat_events(bus, ("agent_release",))
    assert len(events) == 1
    payload = events[0]["payload"]
    assert payload["agent_id"] == "dead-agent"
    assert payload["task"] == "task-x"
    assert payload["auto_released"] is True
    assert payload["reason"] == "agent dead for 30+ min"
    # Copied from the claim. find_open_claims stores None for a missing label,
    # so the "?" default in cleanup_stale_claims is never reached.
    assert payload["worktree"] is None
    assert await find_open_claims(bus) == []


async def test_repeated_manual_cleanup_is_idempotent(
    bus: GossipBus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second manual run finds nothing because the first closed the claim."""
    await _legacy_claim(bus, "dead-agent", "task-x")
    _advance_past_dead_threshold(monkeypatch)
    assert await cleanup_stale_claims(bus) == ["task-x"]
    assert await cleanup_stale_claims(bus) == []


async def test_kill_then_cleanup_releases_even_a_recent_claim(bus: GossipBus) -> None:
    """``kill`` alone releases nothing; a separate ``cleanup`` call is required."""
    await _legacy_claim(bus, "killed-agent", "task-k")
    await bus.emit(
        "heartbeat", {"kind": "agent_killed", "agent_id": "killed-agent", "reason": "manual"}
    )
    assert [c["task"] for c in await find_open_claims(bus)] == ["task-k"]
    assert await cleanup_stale_claims(bus) == ["task-k"]


async def test_pulse_after_kill_revives_and_prevents_release(bus: GossipBus) -> None:
    """A pulse after a kill clears the kill marker, so cleanup keeps the claim."""
    await _legacy_claim(bus, "revived", "task-r")
    await bus.emit("heartbeat", {"kind": "agent_killed", "agent_id": "revived", "reason": "x"})
    await bus.emit("heartbeat", {"kind": "agent_pulse", "agent_id": "revived"})
    assert await cleanup_stale_claims(bus) == []


async def test_liveness_is_not_rechecked_at_release_time(
    bus: GossipBus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Known gap: a pulse landing after classification does not stop release.

    Liveness is read once; the legacy release is a plain append with no
    conditional check against the holder's latest heartbeat. D1 assigns
    expiry/fencing checks inside an authoritative transaction to v2 only.
    """
    await _legacy_claim(bus, "late-pulser", "task-late")
    _advance_past_dead_threshold(monkeypatch)
    real_find_open_claims = heartbeat_monitor.find_open_claims

    async def pulse_then_find(target_bus: GossipBus) -> list[dict]:
        """Renew presence after stale classification but before claim lookup."""
        await target_bus.emit("heartbeat", {"kind": "agent_pulse", "agent_id": "late-pulser"})
        return await real_find_open_claims(target_bus)

    monkeypatch.setattr(heartbeat_monitor, "find_open_claims", pulse_then_find)
    assert await cleanup_stale_claims(bus) == ["task-late"]
    agents = await find_agent_heartbeats(bus, "late-pulser")
    assert agents["late-pulser"]["status"] == "ACTIVE"


async def test_partial_failure_keeps_earlier_releases_and_propagates(
    bus: GossipBus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Releases are separate appends: a failure mid-sweep is not rolled back."""
    await _legacy_claim(bus, "dead-a", "task-1")
    await _legacy_claim(bus, "dead-b", "task-2")
    _advance_past_dead_threshold(monkeypatch)
    real_emit = bus.emit
    calls = {"n": 0}

    async def failing_second_emit(event_type: str, payload: dict, **kwargs: object) -> str:
        """Fail the second release to expose already-persisted partial progress."""
        if payload.get("kind") == "agent_release":
            calls["n"] += 1
            if calls["n"] == 2:
                raise GossipBusError("injected write failure")
        return await real_emit(event_type, payload, **kwargs)

    monkeypatch.setattr(bus, "emit", failing_second_emit)
    with pytest.raises(GossipBusError):
        await cleanup_stale_claims(bus)
    assert [c["task"] for c in await find_open_claims(bus)] == ["task-2"]


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


async def test_queue_cleanup_requeues_dead_holder_without_touching_retry_count(
    bus: GossipBus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Known gap: the requeue keeps retry_count and always sets QUEUED."""
    task_id = await _queued_task_claimed_by(bus, "dead-q", "queue-work")
    _advance_past_dead_threshold(monkeypatch)
    assert await cleanup_stale_claims(bus) == [task_id]
    assert await _claim_row_holder(bus, task_id) is None
    state = (await latest_task_snapshots(bus))[task_id]
    assert state["status"] == QueuedTaskState.QUEUED.value
    assert state["retry_count"] == 0
    assert state["assigned_agent"] is None
    assert state["notes"] == "Auto-released: agent dead-q dead; task returned to queue"


async def test_queue_release_is_conditional_on_the_current_holder(
    bus: GossipBus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the row changed hands after the SELECT, the release is LOST_RACE."""
    task_id = await _queued_task_claimed_by(bus, "dead-q", "handover-work")
    real_snapshots = task_queue.latest_task_snapshots

    async def reassign_then_snapshot(target_bus: GossipBus) -> dict[str, dict]:
        """Change the claim holder before returning the stale task snapshot."""
        async with target_bus.connect() as db:
            await db.execute(
                "UPDATE task_claims SET agent_id = 'new-owner' WHERE task_id = ?",
                (task_id,),
            )
            await db.commit()
        return await real_snapshots(target_bus)

    monkeypatch.setattr(task_queue, "latest_task_snapshots", reassign_then_snapshot)
    assert await cleanup_stale_queue_claims(bus, {"dead-q"}) == []
    assert await _claim_row_holder(bus, task_id) == "new-owner"


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
