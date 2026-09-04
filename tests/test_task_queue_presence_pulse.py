"""tests/test_task_queue_presence_pulse.py

Regression coverage for "a board log() is not a heartbeat -- post
presence right after every genuine live-agent dispatch update."

Covers: queue_claim, queue_complete, queue_fail (both the retry and the
max-retries-exceeded/abandon paths) each post an explicit agent_pulse
event. cleanup_stale_queue_claims -- which releases claims on behalf of
agents already confirmed DEAD -- must NOT post a pulse; doing so would
incorrectly refresh a dead agent's liveness and defeat the entire
purpose of stale-claim cleanup.
"""
from __future__ import annotations

import pytest

from orchestrator.coordination.task_queue import (
    queue_add,
    queue_claim,
    queue_complete,
    queue_fail,
    cleanup_stale_queue_claims,
    latest_task_snapshots,
)
from orchestrator.gossip_bus import GossipBus


@pytest.fixture
async def bus(tmp_path):
    db = str(tmp_path / "test.db")
    b = GossipBus(db)
    await b.init_db()
    return b


async def _pulse_count(bus: GossipBus, agent_id: str) -> int:
    events = await bus.tail(event_type="heartbeat", limit=1000)
    return sum(
        1
        for e in events
        if e["payload"].get("kind") == "agent_pulse"
        and e["payload"].get("agent_id") == agent_id
    )


async def _add_and_claim(bus: GossipBus, agent_id: str) -> str:
    await queue_add(bus, "presence-pulse-work", "Phase-1", "NORMAL", "", None)
    snapshots = await latest_task_snapshots(bus)
    task_id = next(iter(snapshots))
    await queue_claim(bus, task_id, agent_id)
    return task_id


async def test_queue_claim_posts_presence_pulse(bus):
    before = await _pulse_count(bus, "agent-a")
    await _add_and_claim(bus, "agent-a")
    after = await _pulse_count(bus, "agent-a")
    assert after == before + 1


async def test_queue_complete_posts_presence_pulse(bus):
    task_id = await _add_and_claim(bus, "agent-b")
    before = await _pulse_count(bus, "agent-b")
    await queue_complete(bus, task_id, "agent-b", "done")
    after = await _pulse_count(bus, "agent-b")
    assert after == before + 1


async def test_queue_fail_retry_path_posts_presence_pulse(bus):
    task_id = await _add_and_claim(bus, "agent-c")
    before = await _pulse_count(bus, "agent-c")
    await queue_fail(bus, task_id, "agent-c", "transient error")
    after = await _pulse_count(bus, "agent-c")
    assert after == before + 1


async def test_queue_fail_abandon_path_posts_presence_pulse(bus):
    task_id = await _add_and_claim(bus, "agent-d")
    # Exhaust retries (max_retries defaults to 3) to reach the abandon path.
    for _ in range(3):
        await queue_claim(bus, task_id, "agent-d")
        await queue_fail(bus, task_id, "agent-d", "retry")
    before = await _pulse_count(bus, "agent-d")
    await queue_claim(bus, task_id, "agent-d")
    await queue_fail(bus, task_id, "agent-d", "final failure")
    after = await _pulse_count(bus, "agent-d")
    # +2, not +1: the explicit queue_claim above also posts its own pulse,
    # in addition to the abandon-path pulse from queue_fail itself.
    assert after == before + 2


async def test_dead_agent_cleanup_does_not_post_presence_pulse(bus):
    """The whole point of stale-claim cleanup is that the agent is
    confirmed unresponsive -- refreshing its liveness here would be
    actively wrong, not just unnecessary."""
    task_id = await _add_and_claim(bus, "dead-agent")
    before = await _pulse_count(bus, "dead-agent")
    await cleanup_stale_queue_claims(bus, {"dead-agent"})
    after = await _pulse_count(bus, "dead-agent")
    assert after == before
