"""L-1a interim cleanup fence: failing-first tests for the claimed_at guard
and the in-transaction liveness recheck on the queue-claim release path.

Governing plan: QUEUE-FENCING-AND-RECOVERY-CONSOLIDATED-PLAN-2026-11-11.md,
sections 4.3 and 7. The defect tests assert the POST-repair behavior and are
expected to FAIL against the unfenced code (a stale cleanup releases the
claim of a worker that restarted between capture and release). Guard tests
pin the cases that must keep working: clean release of a genuinely dead
claim, and contention behavior.

Deterministic barriers only: a mutable fake clock replaces ``time.time``.
There are no sleeps and no wall-clock dependence in the fence decisions; the
only waits are the existing bounded lock-retry backoff inside
``release_claim_with_event`` (contention test).
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from orchestrator.coordination.task_queue import (
    _CREATE_CLAIMS_TABLE,
    capture_stale_queue_claims,
    cleanup_stale_queue_claims,
    latest_task_snapshots,
    queue_add,
    release_claim_with_event,
    release_captured_queue_claims,
    try_atomic_claim,
)
from orchestrator.coordination.types import ClaimResult, ReleaseResult
from orchestrator.gossip_bus import GossipBus

T_CLAIM = 1000.0
T_CAPTURE = 1010.0
T_PULSE = 1040.0
T_AFTER = 1100.0


@pytest.fixture
async def bus(tmp_path: Path) -> GossipBus:
    """Return a freshly initialized, isolated GossipBus."""
    instance = GossipBus(str(tmp_path / "l1a.db"))
    await instance.init_db()
    return instance


@pytest.fixture
def fake_clock(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Replace time.time with a controllable clock; return the handle."""
    clock = {"now": T_CLAIM}
    monkeypatch.setattr(time, "time", lambda: clock["now"])
    return clock


async def _claimed_task(bus: GossipBus, clock: dict, agent_id: str = "w") -> str:
    """Enqueue one task and atomically claim it at T_CLAIM; return the id."""
    clock["now"] = T_CLAIM
    await queue_add(bus, "demo task", "Phase-1", "NORMAL", "", None)
    snapshots = await latest_task_snapshots(bus)
    task_id = next(tid for tid, s in snapshots.items() if s.get("task_name") == "demo task")
    assert await try_atomic_claim(bus, task_id, agent_id) is ClaimResult.WON
    return task_id


async def _claim_row(bus: GossipBus, task_id: str) -> tuple | None:
    """Return (agent_id, claimed_at) for the task_claims row, or None."""
    async with bus.connect() as db:
        cursor = await db.execute(
            "SELECT agent_id, claimed_at FROM task_claims WHERE task_id = ?",
            (task_id,),
        )
        return await cursor.fetchone()


async def _task_event_count(bus: GossipBus, task_id: str, kind: str) -> int:
    """Count heartbeat events of ``kind`` recorded for ``task_id``."""
    async with bus.connect() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM gossip WHERE event_type = 'heartbeat' "
            "AND json_extract(payload_json, '$.kind') = ? "
            "AND json_extract(payload_json, '$.task_id') = ?",
            (kind, task_id),
        )
        (count,) = await cursor.fetchone()
    return count


async def _agent_pulse(bus: GossipBus, clock: dict, agent_id: str, at: float) -> None:
    """Emit one agent liveness pulse at an exact fake-clock instant."""
    clock["now"] = at
    await bus.emit(
        "heartbeat",
        {"kind": "agent_register", "agent_id": agent_id, "agent_type": "t", "model": "m"},
    )


# ── defect tests: fail (red) on the unfenced code, pass (green) after ──────


async def test_cleanup_refuses_release_when_worker_pulsed_after_capture(
    bus: GossipBus, fake_clock: dict
) -> None:
    """The L-1 schedule: capture claim A, worker restarts and pulses, cleanup
    resumes -> the release must be REFUSED and claim A's row, the folded task
    state and the event log must be unchanged."""
    task_id = await _claimed_task(bus, fake_clock)
    fake_clock["now"] = T_CAPTURE
    captured = await capture_stale_queue_claims(bus, {"w"})
    assert [row["task_id"] for row in captured] == [task_id]
    assert captured[0]["claimed_at"] == T_CLAIM
    assert captured[0]["captured_at"] == T_CAPTURE
    await _agent_pulse(bus, fake_clock, "w", T_PULSE)
    released = await release_captured_queue_claims(bus, captured)
    assert task_id not in released
    row = await _claim_row(bus, task_id)
    assert row == ("w", T_CLAIM)
    snapshots = await latest_task_snapshots(bus)
    state = snapshots[task_id]
    assert state.get("status") == "claimed"
    assert state.get("assigned_agent") == "w"
    assert await _task_event_count(bus, task_id, "task_failed") == 0


async def test_release_refuses_when_agent_pulsed_after_liveness_floor(
    bus: GossipBus, fake_clock: dict
) -> None:
    """Unit fence: a heartbeat newer than the liveness floor refuses the
    release inside the same BEGIN IMMEDIATE transaction."""
    task_id = await _claimed_task(bus, fake_clock)
    await _agent_pulse(bus, fake_clock, "w", T_PULSE)
    result = await release_claim_with_event(
        bus,
        task_id,
        "heartbeat",
        {"kind": "task_failed", "task_id": task_id, "status": "queued"},
        expected_agent_id="w",
        expected_claimed_at=T_CLAIM,
        liveness_floor_ts=T_CAPTURE,
    )
    assert result is ReleaseResult.REFUSED
    assert await _claim_row(bus, task_id) == ("w", T_CLAIM)
    assert await _task_event_count(bus, task_id, "task_failed") == 0


async def test_cleanup_holds_claim_row_for_unknown_task(
    bus: GossipBus, fake_clock: dict
) -> None:
    """Uncertain-effect case: a claim row whose task has no folded snapshot is
    legacy-unverified and must be held, not blindly requeued."""
    fake_clock["now"] = T_CLAIM
    async with bus.connect() as db:
        await db.execute(_CREATE_CLAIMS_TABLE)
        await db.execute(
            "INSERT INTO task_claims (task_id, agent_id, claimed_at) VALUES (?, ?, ?)",
            ("unknown-task", "w", T_CLAIM),
        )
        await db.commit()
    released = await cleanup_stale_queue_claims(bus, {"w"})
    assert "unknown-task" not in released
    assert await _claim_row(bus, "unknown-task") == ("w", T_CLAIM)
    assert await _task_event_count(bus, "unknown-task", "task_failed") == 0


async def test_release_refuses_when_claim_row_owner_changed(
    bus: GossipBus, fake_clock: dict
) -> None:
    """Different-owner case: if the row now belongs to another agent, the
    stale releaser must get LOST_RACE and the new owner's row must survive."""
    task_id = await _claimed_task(bus, fake_clock)
    async with bus.connect() as db:
        await db.execute(
            "UPDATE task_claims SET agent_id = 'x' WHERE task_id = ?", (task_id,)
        )
        await db.commit()
    result = await release_claim_with_event(
        bus,
        task_id,
        "heartbeat",
        {"kind": "task_failed", "task_id": task_id, "status": "queued"},
        expected_agent_id="w",
        expected_claimed_at=T_CLAIM,
        liveness_floor_ts=T_CAPTURE,
    )
    assert result is ReleaseResult.LOST_RACE
    assert await _claim_row(bus, task_id) == ("x", T_CLAIM)
    assert await _task_event_count(bus, task_id, "task_failed") == 0


async def test_release_refuses_when_claimed_at_moved_after_capture(
    bus: GossipBus, fake_clock: dict
) -> None:
    """Captured claimed_at no longer matching the row means the claim changed
    hands (re-claim) between capture and release: refuse, keep the new row."""
    task_id = await _claimed_task(bus, fake_clock)
    async with bus.connect() as db:
        await db.execute(
            "UPDATE task_claims SET claimed_at = ? WHERE task_id = ?",
            (T_AFTER, task_id),
        )
        await db.commit()
    result = await release_claim_with_event(
        bus,
        task_id,
        "heartbeat",
        {"kind": "task_failed", "task_id": task_id, "status": "queued"},
        expected_agent_id="w",
        expected_claimed_at=T_CLAIM,
        liveness_floor_ts=T_CAPTURE,
    )
    assert result is ReleaseResult.LOST_RACE
    assert await _claim_row(bus, task_id) == ("w", T_AFTER)
    assert await _task_event_count(bus, task_id, "task_failed") == 0


# ── guard tests: desired behavior that must survive the repair ─────────────


async def test_cleanup_still_releases_truly_dead_claim(
    bus: GossipBus, fake_clock: dict
) -> None:
    """No liveness after capture: the genuinely dead claim is released, the
    row disappears, one requeue event is recorded and retry counters are
    preserved in the folded state."""
    task_id = await _claimed_task(bus, fake_clock)
    floor = fake_clock["now"]
    captured = await capture_stale_queue_claims(bus, {"w"})
    released = await release_captured_queue_claims(bus, captured)
    assert task_id in released
    assert await _claim_row(bus, task_id) is None
    assert await _task_event_count(bus, task_id, "task_failed") == 1
    snapshots = await latest_task_snapshots(bus)
    state = snapshots[task_id]
    assert state.get("status") == "queued"
    assert state.get("assigned_agent") is None
    assert state.get("retry_count", 0) == 0


async def test_release_contention_keeps_row_intact(
    bus: GossipBus, fake_clock: dict, tmp_path: Path
) -> None:
    """Contention case: a concurrent writer holding the database leaves the
    fenced release with CONTENTION and the row untouched."""
    import aiosqlite

    task_id = await _claimed_task(bus, fake_clock)
    holder = await aiosqlite.connect(str(tmp_path / "l1a.db"))
    try:
        await holder.execute("BEGIN IMMEDIATE")
        result = await release_claim_with_event(
            bus,
            task_id,
            "heartbeat",
            {"kind": "task_failed", "task_id": task_id, "status": "queued"},
            expected_agent_id="w",
            expected_claimed_at=T_CLAIM,
        )
        assert result is ReleaseResult.CONTENTION
        assert await _claim_row(bus, task_id) == ("w", T_CLAIM)
        await holder.execute("ROLLBACK")
    finally:
        await holder.close()
