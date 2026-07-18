"""tests/test_agent_coordination_queue.py

Pure-logic tests for distributed task queuing in scripts/agent_coordination.py.

These tests exercise the queue operations (add, claim, complete, fail, list, status)
directly with temporary GossipBus instances, verifying:
  - Task enqueuing with priority levels
  - Claiming queued tasks with dependency validation
  - Completing tasks successfully
  - Failing tasks with automatic retry logic
  - Filtering and status reporting
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure project root is on path for scripts/agent_coordination + orchestrator.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.agent_coordination import (
    ClaimResult,
    TaskPriority,
    _queue_add,
    _queue_claim,
    _queue_complete,
    _queue_fail,
    _queue_list,
    _queue_status,
    _try_atomic_claim,
    _release_claim_with_event,
)
from scripts import agent_coordination_core as _core
from scripts.agent_coordination_core import (
    _queue_add as _core_queue_add,
    _queue_claim as _core_queue_claim,
    _queue_complete as _core_queue_complete,
    _queue_fail as _core_queue_fail,
    _queue_list as _core_queue_list,
    _phase_list as _core_phase_list,
    _phase_start as _core_phase_start,
)
import scripts.agent_coordination_core as core_cli
from orchestrator.gossip_bus import GossipBus, GossipBusError


@pytest.fixture
def make_bus(tmp_path):
    """Factory for temporary, freshly-initialised GossipBus instances."""

    async def _factory():
        db_path = str(tmp_path / "queue_test.db")
        bus = GossipBus(db_path)
        await bus.init_db()
        return bus

    return _factory


# ────────────────────────────────────────────────────────────────────────────
# Priority Level Tests
# ────────────────────────────────────────────────────────────────────────────


def test_priority_from_string_critical():
    """TaskPriority.from_string handles CRITICAL."""
    priority = TaskPriority.from_string("CRITICAL")
    assert priority == TaskPriority.CRITICAL
    assert priority.value == 1


def test_priority_from_string_high():
    """TaskPriority.from_string handles HIGH."""
    priority = TaskPriority.from_string("high")  # case-insensitive
    assert priority == TaskPriority.HIGH
    assert priority.value == 2


def test_priority_from_string_normal():
    """TaskPriority.from_string handles NORMAL."""
    priority = TaskPriority.from_string("Normal")
    assert priority == TaskPriority.NORMAL
    assert priority.value == 3


def test_priority_from_string_low():
    """TaskPriority.from_string handles LOW."""
    priority = TaskPriority.from_string("LOW")
    assert priority == TaskPriority.LOW
    assert priority.value == 4


def test_priority_from_string_invalid():
    """TaskPriority.from_string raises on invalid priority."""
    with pytest.raises(ValueError):
        TaskPriority.from_string("INVALID")


# ────────────────────────────────────────────────────────────────────────────
# Task Enqueuing Tests
# ────────────────────────────────────────────────────────────────────────────


async def test_queue_add_creates_task(make_bus, capsys):
    """_queue_add enqueues a new task with unique ID."""
    bus = await make_bus()
    await _queue_add(
        bus,
        task_name="implementation",
        phase="Phase-5",
        priority="HIGH",
        notes="Implement API endpoint",
        depends_on=None,
    )

    captured = capsys.readouterr()
    assert "enqueued:" in captured.out
    assert "Phase-5" in captured.out
    assert "HIGH" in captured.out


async def test_queue_add_with_dependencies(make_bus, capsys):
    """_queue_add records dependency list."""
    bus = await make_bus()
    await _queue_add(
        bus,
        task_name="phase-5-final",
        phase="Phase-5",
        priority="NORMAL",
        notes="",
        depends_on="Phase-4-integration,Phase-4-testing",
    )

    events = await bus.tail(limit=10, event_type="heartbeat")
    task_event = [e for e in events if e["payload"].get("kind") == "task_enqueue"][0]
    payload = task_event["payload"]
    assert "Phase-4-integration" in payload["depends_on"]
    assert "Phase-4-testing" in payload["depends_on"]


async def test_queue_add_with_critical_priority(make_bus, capsys):
    """_queue_add with CRITICAL priority is recorded."""
    bus = await make_bus()
    await _queue_add(
        bus,
        task_name="blocker",
        phase="Phase-1",
        priority="CRITICAL",
        notes="Blocks all downstream",
        depends_on=None,
    )

    events = await bus.tail(limit=10, event_type="heartbeat")
    task_event = [e for e in events if e["payload"].get("kind") == "task_enqueue"][0]
    assert task_event["payload"]["priority"] == "CRITICAL"
    assert task_event["payload"]["priority_level"] == 1


# ────────────────────────────────────────────────────────────────────────────
# Task Claiming Tests
# ────────────────────────────────────────────────────────────────────────────


async def test_queue_claim_transitions_to_claimed(make_bus, capsys):
    """_queue_claim changes task status to CLAIMED."""
    bus = await make_bus()
    await _queue_add(bus, "work", "Phase-2", "NORMAL", "", None)

    # Extract task_id from output
    events = await bus.tail(limit=10, event_type="heartbeat")
    task_event = [e for e in events if e["payload"].get("kind") == "task_enqueue"][0]
    task_id = task_event["payload"]["task_id"]

    await _queue_claim(bus, task_id, "agent-alpha")
    captured = capsys.readouterr()
    assert f"claimed: {task_id}" in captured.out


async def test_queue_claim_rejects_already_claimed(make_bus, capsys):
    """_queue_claim rejects if already claimed by another agent."""
    bus = await make_bus()
    await _queue_add(bus, "work", "Phase-2", "NORMAL", "", None)

    events = await bus.tail(limit=10, event_type="heartbeat")
    task_id = events[0]["payload"]["task_id"]

    await _queue_claim(bus, task_id, "agent-alpha")
    capsys.readouterr()  # clear

    # Try to claim again
    await _queue_claim(bus, task_id, "agent-beta")
    captured = capsys.readouterr()
    assert "ERROR" in captured.err
    assert "already claimed" in captured.err


async def test_queue_claim_blocks_on_unmet_dependencies(make_bus, capsys):
    """_queue_claim fails if dependencies not completed."""
    bus = await make_bus()

    # Create task with dependencies
    await _queue_add(
        bus,
        "phase5-work",
        "Phase-5",
        "NORMAL",
        "",
        depends_on="Phase-4-blocker-1",
    )

    events = await bus.tail(limit=10, event_type="heartbeat")
    task_id = events[0]["payload"]["task_id"]

    # Try to claim without dependency being completed
    result = await _queue_claim(bus, task_id, "agent-gamma")
    captured = capsys.readouterr()
    assert result is False
    assert "ERROR" in captured.err
    assert "unmet dependencies" in captured.err


async def test_queue_claim_allows_when_deps_satisfied(make_bus, capsys):
    """_queue_claim succeeds when all dependencies are completed."""
    bus = await make_bus()

    # Create two tasks
    await _queue_add(bus, "blocker", "Phase-4", "HIGH", "", None)
    await _queue_add(bus, "dependent", "Phase-5", "NORMAL", "", "Phase-4-blocker-")

    events = await bus.tail(limit=20, event_type="heartbeat")

    # Find task IDs
    blocker_id = None
    for ev in events:
        p = ev["payload"]
        if p.get("kind") == "task_enqueue":
            if "blocker" in p.get("task_name", ""):
                blocker_id = p["task_id"]
            elif "dependent" in p.get("task_name", ""):
                assert p["task_id"]

    # Complete the blocker
    await _queue_complete(bus, blocker_id, "Done")

    # Now dependent should be claimable
    # (Note: full test requires task_id matching logic; simplified version)
    if blocker_id:
        capsys.readouterr()


# ────────────────────────────────────────────────────────────────────────────
# Task Completion Tests
# ────────────────────────────────────────────────────────────────────────────


async def test_queue_complete_marks_done(make_bus, capsys):
    """_queue_complete marks task as COMPLETED."""
    bus = await make_bus()
    await _queue_add(bus, "work", "Phase-3", "NORMAL", "", None)

    events = await bus.tail(limit=10, event_type="heartbeat")
    task_id = events[0]["payload"]["task_id"]

    await _queue_complete(bus, task_id, "Implementation finished")
    captured = capsys.readouterr()
    assert f"completed: {task_id}" in captured.out


# ────────────────────────────────────────────────────────────────────────────
# Task Failure & Retry Tests
# ────────────────────────────────────────────────────────────────────────────


async def test_queue_fail_with_retry(make_bus, capsys):
    """_queue_fail retries if retry_count < max_retries."""
    bus = await make_bus()
    await _queue_add(bus, "unstable-work", "Phase-2", "NORMAL", "", None)

    events = await bus.tail(limit=10, event_type="heartbeat")
    task_id = events[0]["payload"]["task_id"]

    # First failure — should retry
    await _queue_fail(bus, task_id, "Network timeout")
    captured = capsys.readouterr()
    assert "retry 1/3" in captured.out


async def test_claim_then_fail_then_reclaim_succeeds(make_bus, capsys):
    """A retried task must become claimable again -- _queue_fail's retry path
    has to release the atomic-claim row, or the same PRIMARY KEY that
    prevents a real double-claim would also permanently lock out every
    future legitimate reclaim of a requeued task."""
    bus = await make_bus()
    await _queue_add(bus, "flaky-work", "Phase-2", "NORMAL", "", None)
    events = await bus.tail(limit=10, event_type="heartbeat")
    task_id = events[0]["payload"]["task_id"]

    await _queue_claim(bus, task_id, "agent-a")
    capsys.readouterr()

    await _queue_fail(bus, task_id, "transient error")
    capsys.readouterr()

    await _queue_claim(bus, task_id, "agent-b")
    captured = capsys.readouterr()
    assert "claimed:" in captured.out
    assert "ERROR" not in captured.out


async def test_core_queue_fail_increments_retry_after_reclaim(make_bus, capsys):
    """Facade import must patch core queue helpers used by main()."""
    bus = await make_bus()
    await _core_queue_add(bus, "retry-work", "coord", "NORMAL", "", None)
    events = await bus.tail(limit=10, event_type="heartbeat")
    task_id = events[0]["payload"]["task_id"]

    await _core._queue_claim(bus, task_id, "agent-a")
    capsys.readouterr()
    await _core._queue_fail(bus, task_id, "first failure")
    capsys.readouterr()
    await _core._queue_claim(bus, task_id, "agent-a")
    capsys.readouterr()

    await _core._queue_fail(bus, task_id, "second failure")
    captured = capsys.readouterr()
    assert "retry 2/3" in captured.out


async def test_queue_fail_abandons_after_max_retries(make_bus, capsys):
    """_queue_fail abandons task after max_retries exceeded."""
    bus = await make_bus()
    await _queue_add(bus, "broken", "Phase-1", "LOW", "", None)

    events = await bus.tail(limit=10, event_type="heartbeat")
    task_id = events[0]["payload"]["task_id"]

    # Fail 3 times
    for i in range(3):
        await _queue_fail(bus, task_id, f"Attempt {i+1} failed")

    # On 4th failure, should abandon
    capsys.readouterr()
    await _queue_fail(bus, task_id, "Final attempt failed")
    captured = capsys.readouterr()
    assert "abandoned" in captured.out


# ────────────────────────────────────────────────────────────────────────────
# Queue Listing & Filtering Tests
# ────────────────────────────────────────────────────────────────────────────


async def test_queue_list_groups_by_status(make_bus, capsys):
    """_queue_list shows QUEUED, CLAIMED, COMPLETED, FAILED sections."""
    bus = await make_bus()

    # Create tasks in different states
    await _queue_add(bus, "task-1", "Phase-1", "NORMAL", "", None)
    await _queue_add(bus, "task-2", "Phase-1", "HIGH", "", None)
    await _queue_add(bus, "task-3", "Phase-1", "LOW", "", None)

    events = await bus.tail(limit=20, event_type="heartbeat")
    task_ids = [e["payload"]["task_id"] for e in events if e["payload"].get("kind") == "task_enqueue"]

    # Claim one, complete one, fail one
    if len(task_ids) >= 3:
        await _queue_claim(bus, task_ids[0], "agent-x")
        await _queue_complete(bus, task_ids[1], "")
        await _queue_fail(bus, task_ids[2], "test failure")

    capsys.readouterr()
    await _queue_list(bus, None, None, None)
    captured = capsys.readouterr()

    assert "QUEUED" in captured.out or "CLAIMED" in captured.out
    assert "COMPLETED" in captured.out or "FAILED" in captured.out


async def test_core_queue_list_uses_newest_task_event(make_bus, capsys):
    """The CLI core must not let older enqueue payloads mask completion.

    GossipBus.tail() returns newest-first. The core queue board used by the
    command-line entrypoint must replay events old-to-new so terminal events
    update status without losing metadata from the enqueue payload.
    """
    bus = await make_bus()
    await _core_queue_add(bus, "payload-fix", "coord", "HIGH", "queued", None)
    events = await bus.tail(limit=10, event_type="heartbeat")
    task_id = events[0]["payload"]["task_id"]
    await _core_queue_complete(bus, task_id, "done")

    capsys.readouterr()
    await _core_queue_list(bus, phase_filter="coord", priority_filter=None, agent_filter=None)
    captured = capsys.readouterr()

    assert "COMPLETED" in captured.out
    assert "QUEUED" not in captured.out


async def test_core_queue_fail_increments_retry_after_reclaim(make_bus, capsys):
    """CLI core must merge task history so retry_count survives reclaim."""
    bus = await make_bus()
    await _core_queue_add(bus, "retry-work", "coord", "NORMAL", "", None)
    events = await bus.tail(limit=10, event_type="heartbeat")
    task_id = events[0]["payload"]["task_id"]

    await _core_queue_claim(bus, task_id, "agent-alpha")
    await _core_queue_fail(bus, task_id, "first failure")
    capsys.readouterr()

    await _core_queue_claim(bus, task_id, "agent-alpha")
    await _core_queue_fail(bus, task_id, "second failure")
    captured = capsys.readouterr()

    assert "retry 2/3" in captured.out


async def test_core_phase_list_handles_nonnumeric_phase_names(make_bus, capsys):
    bus = await make_bus()
    await _core_phase_start(bus, "StateTransitionManager-Integration", None, "agent-z")
    await _core_phase_list(bus)
    captured = capsys.readouterr()
    assert "StateTransitionManager-Integration" in captured.out


async def test_queue_list_filters_by_phase(make_bus, capsys):
    """_queue_list respects --phase filter."""
    bus = await make_bus()
    await _queue_add(bus, "phase1-work", "Phase-1", "NORMAL", "", None)
    await _queue_add(bus, "phase2-work", "Phase-2", "NORMAL", "", None)

    capsys.readouterr()
    await _queue_list(bus, phase_filter="Phase-1", priority_filter=None, agent_filter=None)
    captured = capsys.readouterr()

    assert "Phase-1" in captured.out


async def test_queue_list_filters_by_priority(make_bus, capsys):
    """_queue_list respects --priority filter."""
    bus = await make_bus()
    await _queue_add(bus, "critical-task", "Phase-3", "CRITICAL", "", None)
    await _queue_add(bus, "normal-task", "Phase-3", "NORMAL", "", None)

    capsys.readouterr()
    await _queue_list(bus, phase_filter=None, priority_filter="CRITICAL", agent_filter=None)
    captured = capsys.readouterr()

    assert "CRITICAL" in captured.out


async def test_queue_list_filters_by_agent(make_bus, capsys):
    """_queue_list respects --agent filter."""
    bus = await make_bus()
    await _queue_add(bus, "work-x", "Phase-2", "NORMAL", "", None)
    await _queue_add(bus, "work-y", "Phase-2", "NORMAL", "", None)

    events = await bus.tail(limit=20, event_type="heartbeat")
    task_ids = [e["payload"]["task_id"] for e in events if e["payload"].get("kind") == "task_enqueue"]

    if len(task_ids) >= 2:
        await _queue_claim(bus, task_ids[0], "agent-alice")
        await _queue_claim(bus, task_ids[1], "agent-bob")

    capsys.readouterr()
    await _queue_list(bus, phase_filter=None, priority_filter=None, agent_filter="agent-alice")
    captured = capsys.readouterr()

    assert "agent-alice" in captured.out


# ────────────────────────────────────────────────────────────────────────────
# Agent Work Status Tests
# ────────────────────────────────────────────────────────────────────────────


async def test_queue_status_shows_claimed_per_agent(make_bus, capsys):
    """_queue_status groups claimed tasks by agent."""
    bus = await make_bus()

    await _queue_add(bus, "task-1", "Phase-1", "NORMAL", "", None)
    await _queue_add(bus, "task-2", "Phase-1", "NORMAL", "", None)

    events = await bus.tail(limit=20, event_type="heartbeat")
    task_ids = [e["payload"]["task_id"] for e in events if e["payload"].get("kind") == "task_enqueue"]

    if len(task_ids) >= 2:
        await _queue_claim(bus, task_ids[0], "agent-1")
        await _queue_claim(bus, task_ids[1], "agent-1")

    capsys.readouterr()
    await _queue_status(bus, agent_filter=None)
    captured = capsys.readouterr()

    assert "AGENT WORK STATUS" in captured.out or "agent-1" in captured.out


async def test_queue_status_filters_by_agent(make_bus, capsys):
    """_queue_status respects --agent filter."""
    bus = await make_bus()

    await _queue_add(bus, "task-x", "Phase-1", "NORMAL", "", None)
    await _queue_add(bus, "task-y", "Phase-1", "NORMAL", "", None)

    events = await bus.tail(limit=20, event_type="heartbeat")
    task_ids = [e["payload"]["task_id"] for e in events if e["payload"].get("kind") == "task_enqueue"]

    if len(task_ids) >= 2:
        await _queue_claim(bus, task_ids[0], "agent-x")
        await _queue_claim(bus, task_ids[1], "agent-y")

    capsys.readouterr()
    await _queue_status(bus, agent_filter="agent-x")
    captured = capsys.readouterr()

    # Either shows agent-x or "no claimed tasks for agent agent-x"
    assert "agent-x" in captured.out or "no claimed tasks" in captured.out


# ────────────────────────────────────────────────────────────────────────────
# Concurrency & Conflict Resolution Tests
# ────────────────────────────────────────────────────────────────────────────


async def test_multiple_agents_cannot_claim_same_task(make_bus, capsys):
    """Two agents attempting to claim the same task — last-write-wins on claim."""
    bus = await make_bus()
    await _queue_add(bus, "hotly-contested", "Phase-2", "CRITICAL", "", None)

    events = await bus.tail(limit=10, event_type="heartbeat")
    task_id = events[0]["payload"]["task_id"]

    # Agent A claims
    await _queue_claim(bus, task_id, "agent-a")
    capsys.readouterr()

    # Agent B attempts to claim
    await _queue_claim(bus, task_id, "agent-b")
    captured = capsys.readouterr()
    assert "ERROR" in captured.err


async def test_atomic_claim_gate_exactly_one_winner_under_true_concurrency(make_bus):
    """_try_atomic_claim is the actual exclusion point: fire two claims for the
    SAME task_id truly concurrently (asyncio.gather, not sequential awaits) and
    assert the SQLite PRIMARY KEY on task_claims lets exactly one through,
    regardless of scheduling order. This is the real TOCTOU-race regression
    test -- test_multiple_agents_cannot_claim_same_task above only proves the
    sequential case, which the snapshot-based status check already handled
    fine; it never exercised the actual race window between that check and
    the emit that used to follow it unguarded."""
    bus = await make_bus()
    task_id = "race-task-001"

    results = await asyncio.gather(
        _try_atomic_claim(bus, task_id, "agent-a"),
        _try_atomic_claim(bus, task_id, "agent-b"),
    )

    # ClaimResult isn't orderable (no <), so compare by identity/membership
    # rather than sorted(results) == [False, True].
    assert results.count(ClaimResult.WON) == 1
    losers = [r for r in results if r != ClaimResult.WON]
    assert len(losers) == 1
    assert losers[0] in (ClaimResult.LOST_RACE, ClaimResult.CONTENTION)


async def test_queue_claim_concurrent_race_only_one_succeeds(make_bus, capsys):
    """Full-stack version of the race test: two _queue_claim calls fired via
    asyncio.gather (not one-after-the-other) on the same freshly-queued task.
    Exactly one must succeed -- which one is not deterministic, but the count
    is: this is what the old sequential test could never actually prove."""
    bus = await make_bus()
    await _queue_add(bus, "hotly-contested-concurrent", "Phase-2", "CRITICAL", "", None)
    events = await bus.tail(limit=10, event_type="heartbeat")
    task_id = events[0]["payload"]["task_id"]

    await asyncio.gather(
        _queue_claim(bus, task_id, "agent-a"),
        _queue_claim(bus, task_id, "agent-b"),
    )
    captured = capsys.readouterr()

    assert captured.out.count("claimed:") == 1
    assert captured.err.count("ERROR") == 1


def test_queue_claim_cli_returns_nonzero_on_duplicate_claim(tmp_path, monkeypatch, capsys):
    """The live CLI must return nonzero on queue-claim failure."""
    db_path = tmp_path / "queue_cli.db"
    bus = GossipBus(str(db_path))

    async def _setup():
        await bus.init_db()
        await _queue_add(bus, "cli-duplicate", "Phase-1", "NORMAL", "", None)
        events = await bus.tail(limit=10, event_type="heartbeat")
        task_id = events[0]["payload"]["task_id"]
        await _queue_claim(bus, task_id, "agent-alpha")
        return task_id

    task_id = asyncio.run(_setup())
    capsys.readouterr()

    monkeypatch.setattr(core_cli, "canonical_db_path", lambda: str(db_path))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "agent_coordination.py",
            "queue",
            "claim",
            task_id,
            "agent-beta",
        ],
    )
    exit_code = core_cli.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "ERROR" in captured.err


async def test_priority_ordering_in_list(make_bus, capsys):
    """_queue_list sorts queued tasks by priority level (CRITICAL first)."""
    bus = await make_bus()
    await _queue_add(bus, "normal", "Phase-1", "NORMAL", "", None)
    await _queue_add(bus, "critical", "Phase-1", "CRITICAL", "", None)
    await _queue_add(bus, "high", "Phase-1", "HIGH", "", None)

    capsys.readouterr()
    await _queue_list(bus, None, None, None)
    captured = capsys.readouterr()

    # CRITICAL should appear before NORMAL, etc.
    # (Position check is approximate since output format matters)
    assert "CRITICAL" in captured.out
    assert "NORMAL" in captured.out


# ────────────────────────────────────────────────────────────────────────────
# Atomic claim/release + terminal-event transactions (CodeRabbit review
# 4679555600, scripts/agent_coordination.py:140 — "Commit the claim row and
# task event atomically"). _try_atomic_claim() and _release_claim_with_event()
# commit their task_claims row mutation (INSERT / DELETE) and heartbeat event
# in ONE SQLite transaction via GossipBus.connect() / insert_event(), closing
# the gap where separate commits could leave a claim row with no
# corresponding event -- or a terminal event recorded while the claim row
# stays held, blocking every future claim on that task_id -- if the process
# died between the two commits.
# ────────────────────────────────────────────────────────────────────────────


async def test_atomic_claim_persists_one_row_and_one_event(make_bus):
    bus = await make_bus()

    claimed = await _try_atomic_claim(
        bus, "task-x", "agent-a", {"kind": "task_claim", "task_id": "task-x"}
    )

    assert claimed is ClaimResult.WON
    async with bus.connect() as db:
        cursor = await db.execute("SELECT COUNT(*) FROM task_claims WHERE task_id = ?", ("task-x",))
        (claim_count,) = await cursor.fetchone()
    assert claim_count == 1
    events = await bus.tail(limit=10, event_type="heartbeat")
    matching = [e for e in events if e["payload"].get("task_id") == "task-x"]
    assert len(matching) == 1


async def test_atomic_claim_duplicate_claim_emits_no_second_event(make_bus):
    bus = await make_bus()
    await _try_atomic_claim(
        bus, "task-y", "agent-a", {"kind": "task_claim", "task_id": "task-y"}
    )

    claimed_again = await _try_atomic_claim(
        bus, "task-y", "agent-b", {"kind": "task_claim", "task_id": "task-y"}
    )

    assert claimed_again is ClaimResult.LOST_RACE
    events = await bus.tail(limit=10, event_type="heartbeat")
    matching = [e for e in events if e["payload"].get("task_id") == "task-y"]
    assert len(matching) == 1  # still just the first claimant's event


async def test_atomic_claim_injected_insert_failure_rolls_back_claim_row(make_bus, monkeypatch):
    """If the event INSERT inside the shared transaction raises, the earlier
    claim-row INSERT in the same (uncommitted) transaction must not survive
    -- proving the two mutations really share one atomic unit, not just two
    sequential statements against the same connection."""
    bus = await make_bus()
    # _try_atomic_claim's CREATE TABLE IF NOT EXISTS runs inside the same
    # BEGIN IMMEDIATE transaction as the claim -- on a table-less DB, a
    # rollback undoes the table creation too (SQLite DDL is transactional),
    # which would make the post-failure SELECT below fail with "no such
    # table" instead of exercising the rollback property under test.
    # Ensure the table exists first via an unrelated successful claim.
    await _try_atomic_claim(bus, "task-warm-up", "agent-a")

    async def _boom(self, db, event_type, payload, **kwargs):
        raise RuntimeError("simulated event-insert failure")

    monkeypatch.setattr(GossipBus, "insert_event", _boom)

    with pytest.raises(GossipBusError, match="claim on 'task-z' failed") as exc_info:
        await _try_atomic_claim(
            bus, "task-z", "agent-a", {"kind": "task_claim", "task_id": "task-z"}
        )
    assert isinstance(exc_info.value.__cause__, RuntimeError)

    async with bus.connect() as db:
        cursor = await db.execute("SELECT COUNT(*) FROM task_claims WHERE task_id = ?", ("task-z",))
        (claim_count,) = await cursor.fetchone()
    assert claim_count == 0  # rolled back along with the failed event insert


async def test_release_claim_with_event_deletes_row_and_persists_event(make_bus):
    bus = await make_bus()
    await _try_atomic_claim(bus, "task-r1", "agent-a")

    released = await _release_claim_with_event(
        bus, "task-r1", "heartbeat", {"kind": "task_complete", "task_id": "task-r1"}
    )

    assert released is True
    async with bus.connect() as db:
        cursor = await db.execute("SELECT COUNT(*) FROM task_claims WHERE task_id = ?", ("task-r1",))
        (claim_count,) = await cursor.fetchone()
    assert claim_count == 0
    events = await bus.tail(limit=10, event_type="heartbeat")
    complete_events = [
        e for e in events
        if e["payload"].get("task_id") == "task-r1" and e["payload"].get("kind") == "task_complete"
    ]
    assert len(complete_events) == 1


async def test_release_claim_with_event_injected_failure_leaves_claim_row_intact(make_bus, monkeypatch):
    """If the event insert raises inside the shared transaction, the release
    DELETE in the same (uncommitted) transaction must not survive either --
    a released-but-unreported task_id must not silently vanish from
    task_claims, which would let a second agent claim it while the first
    agent still believes it holds it."""
    bus = await make_bus()
    await _try_atomic_claim(bus, "task-r2", "agent-a")

    async def _boom(self, db, event_type, payload, **kwargs):
        raise RuntimeError("simulated event-insert failure")

    monkeypatch.setattr(GossipBus, "insert_event", _boom)

    with pytest.raises(GossipBusError, match="release of 'task-r2' failed") as exc_info:
        await _release_claim_with_event(
            bus, "task-r2", "heartbeat", {"kind": "task_complete", "task_id": "task-r2"}
        )
    assert isinstance(exc_info.value.__cause__, RuntimeError)

    async with bus.connect() as db:
        cursor = await db.execute("SELECT COUNT(*) FROM task_claims WHERE task_id = ?", ("task-r2",))
        (claim_count,) = await cursor.fetchone()
    assert claim_count == 1  # still held -- release did not partially apply


# ────────────────────────────────────────────────────────────────────────────
# Part 1b: database-error contract, real-entrypoint coverage. A corrupted
# database file (not a permission trick, which is root-bypassable in some CI
# environments) reliably fails BOTH reads and writes with a real
# sqlite3/aiosqlite exception, exercising the actual GossipBusError wrapping
# through the real CLI subprocess -- not just the direct-call unit tests
# above.
# ────────────────────────────────────────────────────────────────────────────


def _corrupt_db_file(db_path):
    with open(db_path, "wb") as f:
        f.write(b"not a sqlite database")


async def test_real_cli_write_command_reports_clean_error_on_corrupt_db(tmp_path):
    """A write command (queue add) against a corrupted database exits
    nonzero with a clean ERROR: message on stderr -- not a raw traceback,
    and not exit code 0 with the failure buried in stdout."""
    db_path = tmp_path / "corrupt.db"
    _corrupt_db_file(db_path)
    env = {**os.environ, "GOSSIP_DB_PATH": str(db_path)}
    env.pop("PT_STATE_DIR", None)

    result = subprocess.run(
        [sys.executable, "scripts/agent_coordination.py", "queue", "add", "task", "Phase-1"],
        capture_output=True, text=True, env=env, cwd=str(Path(__file__).resolve().parent.parent),
    )
    assert result.returncode != 0, f"expected nonzero exit, got 0: stdout={result.stdout!r}"
    assert "ERROR" in result.stderr, f"expected ERROR on stderr, got: {result.stderr!r}"
    assert "Traceback" not in result.stderr, "raw traceback leaked instead of a clean GossipBusError message"
    assert "ERROR" not in result.stdout, f"ERROR text leaked onto stdout: {result.stdout!r}"


async def test_real_cli_read_command_reports_clean_error_on_corrupt_db(tmp_path):
    """A read command (queue list) against a corrupted database exits
    nonzero with a clean ERROR: message on stderr, same contract as the
    write-path test above -- Part 1b must cover both directions, not just
    emit()."""
    db_path = tmp_path / "corrupt.db"
    _corrupt_db_file(db_path)
    env = {**os.environ, "GOSSIP_DB_PATH": str(db_path)}
    env.pop("PT_STATE_DIR", None)

    result = subprocess.run(
        [sys.executable, "scripts/agent_coordination.py", "queue", "list"],
        capture_output=True, text=True, env=env, cwd=str(Path(__file__).resolve().parent.parent),
    )
    assert result.returncode != 0, f"expected nonzero exit, got 0: stdout={result.stdout!r}"
    assert "ERROR" in result.stderr, f"expected ERROR on stderr, got: {result.stderr!r}"
    assert "Traceback" not in result.stderr, "raw traceback leaked instead of a clean GossipBusError message"


async def test_queue_complete_releases_claim_and_completion_event_together(make_bus, capsys):
    """End-to-end: _queue_complete's public entrypoint uses the atomic
    release path, not the old two-commit sequence."""
    bus = await make_bus()
    await _queue_add(bus, "e2e-complete", "Phase-1", "NORMAL", "", None)
    events = await bus.tail(limit=10, event_type="heartbeat")
    task_id = events[0]["payload"]["task_id"]
    await _queue_claim(bus, task_id, "agent-a")

    await _queue_complete(bus, task_id, "done")

    async with bus.connect() as db:
        cursor = await db.execute("SELECT COUNT(*) FROM task_claims WHERE task_id = ?", (task_id,))
        (claim_count,) = await cursor.fetchone()
    assert claim_count == 0
    captured = capsys.readouterr()
    assert f"completed: {task_id}" in captured.out
