"""PT #525: tests for the strictly-increasing claim stamp.

Verifies that task_claims.claimed_at is made strictly increasing per task_id
via the persistent task_claim_hwm table and math.nextafter.
"""
from __future__ import annotations

import types
from pathlib import Path

import pytest

from orchestrator.coordination import task_queue
from orchestrator.coordination.task_queue import (
    release_claim_with_event,
    try_atomic_claim_stamped,
)
from orchestrator.coordination.types import ClaimResult, ReleaseResult
from orchestrator.gossip_bus import GossipBus

SAME_TICK = 1_764_000_000.0


@pytest.fixture
async def bus(tmp_path: Path) -> GossipBus:
    b = GossipBus(tmp_path / "test_stamp.db")
    await b.init_db()
    return b


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(task_queue, "time", types.SimpleNamespace(time=lambda: SAME_TICK))


async def _release(bus: GossipBus, task_id: str, agent: str, stamp: float | None) -> ReleaseResult:
    return await release_claim_with_event(
        bus,
        task_id,
        "heartbeat",
        {"kind": "task_failed", "task_id": task_id},
        expected_agent_id=agent,
        expected_claimed_at=stamp,
    )


@pytest.mark.asyncio
async def test_same_name_reclaim_in_one_clock_tick_gets_a_strictly_greater_stamp(bus: GossipBus) -> None:
    first, t1 = await try_atomic_claim_stamped(bus, "task-1", "agent-a")
    assert first is ClaimResult.WON
    assert t1 is not None
    assert await _release(bus, "task-1", "agent-a", t1) is ReleaseResult.RELEASED
    second, t2 = await try_atomic_claim_stamped(bus, "task-1", "agent-a")
    assert second is ClaimResult.WON and t2 is not None and t2 > t1


@pytest.mark.asyncio
async def test_a_stale_worker_holding_the_old_stamp_cannot_release_the_replacement_claim(bus: GossipBus) -> None:
    _, t1 = await try_atomic_claim_stamped(bus, "task-1", "agent-a")
    assert t1 is not None
    await _release(bus, "task-1", "agent-a", t1)
    _, t2 = await try_atomic_claim_stamped(bus, "task-1", "agent-a")
    assert t2 is not None
    assert await _release(bus, "task-1", "agent-a", t1) is ReleaseResult.LOST_RACE
    assert await _release(bus, "task-1", "agent-a", t2) is ReleaseResult.RELEASED


@pytest.mark.asyncio
async def test_a_lost_race_does_not_advance_the_high_water_mark(bus: GossipBus) -> None:
    _, t1 = await try_atomic_claim_stamped(bus, "task-1", "agent-a")
    assert t1 is not None
    loser, stamp = await try_atomic_claim_stamped(bus, "task-1", "agent-b")
    assert loser is ClaimResult.LOST_RACE and stamp is None
    await _release(bus, "task-1", "agent-a", t1)
    _, t2 = await try_atomic_claim_stamped(bus, "task-1", "agent-b")
    assert t2 is not None and t2 > t1


@pytest.mark.asyncio
async def test_a_clock_that_steps_backwards_never_reissues_a_stamp(
    bus: GossipBus, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, t1 = await try_atomic_claim_stamped(bus, "task-1", "agent-a")
    assert t1 is not None
    await _release(bus, "task-1", "agent-a", t1)
    monkeypatch.setattr(task_queue, "time", types.SimpleNamespace(time=lambda: SAME_TICK - 3600))
    _, t2 = await try_atomic_claim_stamped(bus, "task-1", "agent-a")
    assert t2 is not None and t2 > t1
