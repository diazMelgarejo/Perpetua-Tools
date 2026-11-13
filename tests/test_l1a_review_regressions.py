"""L-1a review regressions: canonical in-transaction liveness for the fence.

PR #496 review findings, pinned failing-first against the pre-fix fence:

* A worker that restarts after its DEAD classification but *before* capture
  pulses at a time older than the capture floor; the floor-only check let its
  claim be released. The release transaction must recheck canonical liveness.
* ``agent_killed`` and cleanup's ``auto_released`` agent_release events are
  records about a dead agent, not activity by it. They must neither fence a
  stale-claim release nor refresh the monitor's last-activity time.
* An empty capture must not fold the complete task history.

Deterministic barriers only: a mutable fake clock replaces ``time.time``.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from orchestrator.coordination import task_queue
from orchestrator.coordination.task_queue import (
    capture_stale_queue_claims,
    cleanup_stale_queue_claims,
    latest_task_snapshots,
    queue_add,
    release_captured_queue_claims,
    try_atomic_claim,
)
from orchestrator.coordination.types import ClaimResult
from orchestrator.gossip_bus import GossipBus
from orchestrator.heartbeat_monitor import (
    LIVENESS_STALLED_SEC,
    cleanup_stale_claims,
    find_agent_heartbeats,
    is_live_activity,
)

T0 = 1000.0
T_DEAD = T0 + LIVENESS_STALLED_SEC + 100.0


@pytest.fixture
async def bus(tmp_path: Path) -> GossipBus:
    """Return a freshly initialized, isolated GossipBus."""
    instance = GossipBus(str(tmp_path / "l1a-review.db"))
    await instance.init_db()
    return instance


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Replace time.time with a controllable clock; return the handle."""
    handle = {"now": T0}
    monkeypatch.setattr(time, "time", lambda: handle["now"])
    return handle


async def _emit(bus: GossipBus, clock: dict, at: float, payload: dict) -> None:
    """Emit one heartbeat payload at an exact fake-clock instant."""
    clock["now"] = at
    await bus.emit("heartbeat", payload)


async def _claimed_task(bus: GossipBus, clock: dict, agent_id: str = "w") -> str:
    """Register ``agent_id``, enqueue one task and claim it at T0."""
    await _emit(bus, clock, T0, {"kind": "agent_register", "agent_id": agent_id})
    await queue_add(bus, "review task", "Phase-1", "NORMAL", "", None)
    snapshots = await latest_task_snapshots(bus)
    task_id = next(t for t, s in snapshots.items() if s.get("task_name") == "review task")
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


async def test_restart_between_dead_classification_and_capture_keeps_claim(
    bus: GossipBus, clock: dict
) -> None:
    """Classified DEAD, restarted before capture: the pulse predates the floor
    but canonical liveness inside the release transaction refuses release."""
    task_id = await _claimed_task(bus, clock)
    clock["now"] = T_DEAD
    agents = await find_agent_heartbeats(bus)
    assert agents["w"]["status"] == "DEAD"
    await _emit(bus, clock, T_DEAD + 5, {"kind": "agent_pulse", "agent_id": "w"})
    clock["now"] = T_DEAD + 10
    captured = await capture_stale_queue_claims(bus, {"w"})
    assert [row["task_id"] for row in captured] == [task_id]
    released = await release_captured_queue_claims(bus, captured)
    assert released == []
    assert await _claim_row(bus, task_id) is not None


async def test_agent_killed_after_capture_does_not_fence_release(
    bus: GossipBus, clock: dict
) -> None:
    """An explicit kill recorded after capture is not liveness evidence."""
    task_id = await _claimed_task(bus, clock)
    clock["now"] = T_DEAD
    captured = await capture_stale_queue_claims(bus, {"w"})
    await _emit(
        bus, clock, T_DEAD + 30, {"kind": "agent_killed", "agent_id": "w", "reason": "ops"}
    )
    released = await release_captured_queue_claims(bus, captured)
    assert released == [task_id]
    assert await _claim_row(bus, task_id) is None


async def test_pulse_after_kill_still_fences_release(bus: GossipBus, clock: dict) -> None:
    """A kill followed by a pulse after the floor is a restart: refuse."""
    task_id = await _claimed_task(bus, clock)
    clock["now"] = T_DEAD
    captured = await capture_stale_queue_claims(bus, {"w"})
    await _emit(
        bus, clock, T_DEAD + 10, {"kind": "agent_killed", "agent_id": "w", "reason": "ops"}
    )
    await _emit(bus, clock, T_DEAD + 20, {"kind": "agent_pulse", "agent_id": "w"})
    assert await release_captured_queue_claims(bus, captured) == []
    assert await _claim_row(bus, task_id) is not None


async def test_auto_release_does_not_refresh_dead_agent_liveness(
    bus: GossipBus, clock: dict
) -> None:
    """Cleanup's auto-release on a dead agent must not make it look ACTIVE."""
    await _emit(bus, clock, T0, {"kind": "agent_register", "agent_id": "w"})
    await _emit(
        bus,
        clock,
        T_DEAD,
        {"kind": "agent_release", "agent_id": "w", "task": "t", "auto_released": True},
    )
    agents = await find_agent_heartbeats(bus)
    assert agents["w"]["status"] == "DEAD"
    assert agents["w"]["last_heartbeat_ts"] == T0


async def test_agent_killed_does_not_refresh_last_activity(
    bus: GossipBus, clock: dict
) -> None:
    """The monitor keeps the last real activity time after an explicit kill."""
    await _emit(bus, clock, T0, {"kind": "agent_pulse", "agent_id": "w"})
    await _emit(
        bus, clock, T0 + 50, {"kind": "agent_killed", "agent_id": "w", "reason": "x"}
    )
    agents = await find_agent_heartbeats(bus)
    assert agents["w"]["status"] == "DEAD"
    assert agents["w"]["last_heartbeat_ts"] == T0


def test_live_activity_classification() -> None:
    """Pin which lifecycle kinds count as the agent's own activity."""
    assert is_live_activity({"kind": "agent_register"})
    assert is_live_activity({"kind": "agent_claim"})
    assert is_live_activity({"kind": "agent_pulse"})
    assert is_live_activity({"kind": "agent_release"})
    assert not is_live_activity({"kind": "agent_release", "auto_released": True})
    assert not is_live_activity({"kind": "agent_killed"})
    assert not is_live_activity({"kind": "task_failed"})


async def test_end_to_end_cleanup_releases_genuinely_dead_queue_claim(
    bus: GossipBus, clock: dict
) -> None:
    """Guard: the monitor's own auto-releases must not block the queue release
    that the same ``cleanup_stale_claims`` pass performs."""
    task_id = await _claimed_task(bus, clock)
    await _emit(bus, clock, T0, {"kind": "agent_claim", "agent_id": "w", "task": "legacy"})
    clock["now"] = T_DEAD
    released = await cleanup_stale_claims(bus)
    assert "legacy" in released
    assert task_id in released
    assert await _claim_row(bus, task_id) is None


async def test_empty_capture_skips_task_history_fold(
    bus: GossipBus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Neither cleanup path folds task history when nothing was captured."""

    async def _boom(_bus: GossipBus) -> dict:
        """Fail loudly if the full task-history fold is reached."""
        raise AssertionError("latest_task_snapshots must not run for empty capture")

    monkeypatch.setattr(task_queue, "latest_task_snapshots", _boom)
    assert await release_captured_queue_claims(bus, []) == []
    assert await cleanup_stale_queue_claims(bus, {"nobody"}) == []
    assert await cleanup_stale_queue_claims(bus, set()) == []


async def test_fence_reads_liveness_on_the_release_connection(
    bus: GossipBus, clock: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guard: the liveness recheck must not open a second connection."""
    task_id = await _claimed_task(bus, clock)
    clock["now"] = T_DEAD
    captured = await capture_stale_queue_claims(bus, {"w"})
    original = bus.connect
    opened: list[int] = []

    def _counting_connect(*args, **kwargs):
        """Count connections opened while the fenced release runs."""
        opened.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(bus, "connect", _counting_connect)
    result = await task_queue.release_claim_with_event(
        bus,
        task_id,
        "heartbeat",
        {"kind": "task_failed", "task_id": task_id, "status": "queued"},
        expected_agent_id="w",
        expected_claimed_at=captured[0]["claimed_at"],
        liveness_floor_ts=captured[0]["captured_at"],
    )
    assert result.name == "RELEASED"
    assert len(opened) == 1
