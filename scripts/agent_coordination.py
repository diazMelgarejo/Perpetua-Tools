#!/usr/bin/env python3
"""Stable coordination facade over the retained legacy CLI implementation."""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Optional

import aiosqlite

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts import agent_coordination_legacy as _impl  # noqa: E402
from scripts.agent_coordination_legacy import (  # noqa: E402
    GossipBus,
    PhaseState,
    QueuedTaskState,
    TaskPriority,
    current_worktree_label,
)
from orchestrator.heartbeat_monitor import (  # noqa: E402
    cleanup_stale_claims,
    find_agent_heartbeats,
    find_open_claims,
)

# Public legacy command helpers intentionally stay on the retained implementation;
# queue/phase helpers below override only the corrected centralized paths.

_register = _impl._register
_agents = _impl._agents
_claim = _impl._claim
_release = _impl._release
_list = _impl._list
_log = _impl._log
_phase_start = _impl._phase_start
_phase_update = _impl._phase_update
_phase_complete = _impl._phase_complete
_phase_block = _impl._phase_block
_phase_unblock = _impl._phase_unblock
_phase_list = _impl._phase_list
_phase_status = _impl._phase_status
_detect_blockers = _impl._detect_blockers
_claim_with_seq = _impl._claim_with_seq
_buffer_status = _impl._buffer_status
_buffer_drain = _impl._buffer_drain
_workflow_critical_path = _impl._workflow_critical_path
_queue_add = _impl._queue_add
_queue_claim = _impl._queue_claim
_queue_complete = _impl._queue_complete
_queue_fail = _impl._queue_fail
_queue_list = _impl._queue_list
_queue_status = _impl._queue_status
main = _impl.main


async def _latest_task_snapshots(bus: GossipBus) -> dict[str, dict]:
    """Fold newest-first append-only events into current task snapshots."""
    events = await bus.tail(limit=1000, event_type="heartbeat")
    snapshots: dict[str, dict] = {}
    accepted = {
        "task_enqueue",
        "task_claim",
        "task_complete",
        "task_failed",
        "task_abandoned",
    }
    for event in reversed(events):
        payload = event["payload"]
        task_id = payload.get("task_id")
        if not task_id or payload.get("kind") not in accepted:
            continue
        snapshots.setdefault(task_id, {}).update(payload)
    return snapshots


async def _get_latest_phase_state(
    bus: GossipBus, phase_name: str
) -> Optional[PhaseState]:
    events = await bus.tail(limit=500, event_type="heartbeat")
    for event in events:
        payload = event["payload"]
        if payload.get("kind") == "phase_event" and payload.get("phase_name") == phase_name:
            return PhaseState.from_payload(payload)
    return None


async def _all_phase_states(bus: GossipBus) -> dict[str, PhaseState]:
    events = await bus.tail(limit=500, event_type="heartbeat")
    latest: dict[str, PhaseState] = {}
    for event in events:
        payload = event["payload"]
        if payload.get("kind") != "phase_event":
            continue
        phase_name = payload.get("phase_name")
        if phase_name and phase_name not in latest:
            latest[phase_name] = PhaseState.from_payload(payload)
    return latest


_CREATE_CLAIMS_TABLE = """
CREATE TABLE IF NOT EXISTS task_claims (
    task_id    TEXT PRIMARY KEY,
    agent_id   TEXT NOT NULL,
    claimed_at REAL NOT NULL
)
"""
_LOCK_RETRIES = 3
_LOCK_RETRY_SECONDS = 0.05


async def _ensure_claims_table(bus: GossipBus) -> None:
    async with bus.connect() as db:
        await db.execute(_CREATE_CLAIMS_TABLE)
        await db.commit()


async def _try_atomic_claim(
    bus: GossipBus,
    task_id: str,
    agent_id: str,
    claim_payload: Optional[dict] = None,
) -> bool:
    """Atomically persist exclusive ownership and its append-only event.

    `BEGIN IMMEDIATE` serializes writers before either mutation. Integrity
    conflicts return False. Lock contention is retried briefly and then fails
    cleanly without leaving a claim row or an event behind.
    """
    payload = claim_payload or {
        "kind": "task_claim",
        "task_id": task_id,
        "assigned_agent": agent_id,
        "status": QueuedTaskState.CLAIMED.value,
        "worktree": current_worktree_label(),
    }
    for attempt in range(_LOCK_RETRIES):
        async with bus.connect() as db:
            try:
                await db.execute("BEGIN IMMEDIATE")
                await db.execute(_CREATE_CLAIMS_TABLE)
                await db.execute(
                    "INSERT INTO task_claims (task_id, agent_id, claimed_at) "
                    "VALUES (?, ?, ?)",
                    (task_id, agent_id, time.time()),
                )
                row_id, _event_uuid, safe_payload, inserted = await bus.insert_event(
                    db, "heartbeat", payload
                )
                await db.commit()
            except aiosqlite.IntegrityError:
                await db.rollback()
                return False
            except aiosqlite.OperationalError as exc:
                await db.rollback()
                locked = "locked" in str(exc).lower() or "busy" in str(exc).lower()
                if locked and attempt + 1 < _LOCK_RETRIES:
                    await asyncio.sleep(_LOCK_RETRY_SECONDS * (attempt + 1))
                    continue
                if locked:
                    return False
                raise
            except Exception:
                await db.rollback()
                raise
        if inserted:
            bus.schedule_embedding(row_id, safe_payload)
        return True
    return False


async def _release_claim(bus: GossipBus, task_id: str) -> None:
    """Free a task_id for reclaiming (on completion or requeue-after-failure)."""
    async with bus.connect() as db:
        await db.execute(_CREATE_CLAIMS_TABLE)
        await db.execute("DELETE FROM task_claims WHERE task_id = ?", (task_id,))
        await db.commit()


async def _release_claim_with_event(
    bus: GossipBus, task_id: str, event_type: str, payload: dict
) -> bool:
    """Atomically free ownership and record why, mirroring _try_atomic_claim's
    guarantee for the release side.

    Without this, a crash between a separate release DELETE and its event
    emit could free a claim row with no record of why (forensics gap), or
    record the terminal event while the row stays held -- blocking every
    future _try_atomic_claim on that task_id with a stale "already claimed"
    row forever. Same `BEGIN IMMEDIATE` + bounded-retry treatment as the
    claim path; returns False (not raised) if lock contention exhausts all
    retries, so callers can decide how to handle a release that didn't land.
    """
    for attempt in range(_LOCK_RETRIES):
        async with bus.connect() as db:
            try:
                await db.execute("BEGIN IMMEDIATE")
                await db.execute(_CREATE_CLAIMS_TABLE)
                await db.execute("DELETE FROM task_claims WHERE task_id = ?", (task_id,))
                row_id, _event_uuid, safe_payload, inserted = await bus.insert_event(
                    db, event_type, payload
                )
                await db.commit()
            except aiosqlite.OperationalError as exc:
                await db.rollback()
                locked = "locked" in str(exc).lower() or "busy" in str(exc).lower()
                if locked and attempt + 1 < _LOCK_RETRIES:
                    await asyncio.sleep(_LOCK_RETRY_SECONDS * (attempt + 1))
                    continue
                if locked:
                    return False
                raise
            except Exception:
                await db.rollback()
                raise
        if inserted:
            bus.schedule_embedding(row_id, safe_payload)
        return True
    return False


async def _queue_claim(bus: GossipBus, task_id: str, agent_id: str) -> None:
    snapshots = await _latest_task_snapshots(bus)
    task_state = snapshots.get(task_id)
    if not task_state:
        print(f"ERROR: task {task_id} not found")
        return

    status = task_state.get("status")
    if status == QueuedTaskState.CLAIMED.value:
        print(
            f"ERROR: {task_id} already claimed by "
            f"{task_state.get('assigned_agent')}."
        )
        return
    if status == QueuedTaskState.COMPLETED.value:
        print(f"ERROR: {task_id} already completed. Cannot reclaim.")
        return
    if status == "abandoned":
        print(f"ERROR: {task_id} was abandoned. Cannot reclaim.")
        return

    depends_on = task_state.get("depends_on", [])
    unmet = [
        dependency
        for dependency in depends_on
        if snapshots.get(dependency, {}).get("status")
        != QueuedTaskState.COMPLETED.value
    ]
    if unmet:
        print(f"ERROR: {task_id} unmet dependencies: {', '.join(unmet)}")
        return

    # Atomic gate: the snapshot checks above can both pass for two racing
    # claimants (read-then-write, no lock across the gap). This INSERT is
    # the actual exclusion point -- only one caller gets True. The claim row
    # and its heartbeat event commit together (see _try_atomic_claim) so a
    # crash between them can never leave one without the other.
    payload = {
        "kind": "task_claim",
        "task_id": task_id,
        "assigned_agent": agent_id,
        "status": QueuedTaskState.CLAIMED.value,
        "worktree": current_worktree_label(),
    }
    if not await _try_atomic_claim(bus, task_id, agent_id, payload):
        print(
            f"ERROR: {task_id} could not be claimed; another agent won "
            "or the coordination database remained busy. Retry safely."
        )
        return
    print(f"claimed: {task_id} by {agent_id}")


async def _queue_complete(bus: GossipBus, task_id: str, notes: str) -> None:
    snapshots = await _latest_task_snapshots(bus)
    if task_id not in snapshots:
        print(f"ERROR: task {task_id} not found")
        return
    # Free the atomic-claim row and record completion in one transaction --
    # a completed task is rejected by the status check in _queue_claim
    # regardless, but a crash between a separate release and emit could
    # otherwise free the row with no event explaining why, or record the
    # event while the row stays held (blocking every future claim on this
    # task_id with a stale "already claimed" row forever).
    released = await _release_claim_with_event(
        bus,
        task_id,
        "heartbeat",
        {
            "kind": "task_complete",
            "task_id": task_id,
            "status": QueuedTaskState.COMPLETED.value,
            "notes": notes,
        },
    )
    if not released:
        print(f"ERROR: {task_id} could not be completed; coordination database remained busy. Retry safely.")
        return
    print(f"completed: {task_id}")


async def _queue_fail(bus: GossipBus, task_id: str, notes: str) -> None:
    snapshots = await _latest_task_snapshots(bus)
    task_state = snapshots.get(task_id)
    if not task_state:
        print(f"ERROR: task {task_id} not found")
        return

    retry_count = int(task_state.get("retry_count", 0)) + 1
    max_retries = int(task_state.get("max_retries", 3))
    if retry_count <= max_retries:
        # Must release here, not just on complete -- the task goes back to
        # QUEUED and _queue_claim's atomic gate would otherwise reject every
        # future claim attempt with a stale "already claimed" row forever.
        # Release + event committed together, same reasoning as _queue_complete.
        released = await _release_claim_with_event(
            bus,
            task_id,
            "heartbeat",
            {
                "kind": "task_failed",
                "task_id": task_id,
                "retry_count": retry_count,
                "max_retries": max_retries,
                "status": QueuedTaskState.QUEUED.value,
                "assigned_agent": None,
                "notes": f"Retry {retry_count}/{max_retries}: {notes}",
            },
        )
        if not released:
            print(f"ERROR: {task_id} could not be requeued; coordination database remained busy. Retry safely.")
            return
        print(f"failed: {task_id}, retry {retry_count}/{max_retries}")
        return

    released = await _release_claim_with_event(
        bus,
        task_id,
        "heartbeat",
        {
            "kind": "task_abandoned",
            "task_id": task_id,
            "retry_count": retry_count,
            "max_retries": max_retries,
            "status": "abandoned",
            "assigned_agent": None,
            "notes": f"Abandoned after {max_retries} retries: {notes}",
        },
    )
    if not released:
        print(f"ERROR: {task_id} could not be abandoned; coordination database remained busy. Retry safely.")
        return
    print(f"abandoned: {task_id} (max retries exceeded)")


async def _queue_list(
    bus: GossipBus,
    phase_filter: Optional[str],
    priority_filter: Optional[str],
    agent_filter: Optional[str],
) -> None:
    states = await _latest_task_snapshots(bus)
    grouped = {"queued": {}, "claimed": {}, "completed": {}, "failed": {}}
    for task_id, state in states.items():
        if phase_filter and state.get("phase") != phase_filter:
            continue
        if priority_filter and state.get("priority") != priority_filter.upper():
            continue
        if agent_filter and state.get("assigned_agent") != agent_filter:
            continue
        status = state.get("status")
        if status == QueuedTaskState.QUEUED.value:
            grouped["queued"][task_id] = state
        elif status == QueuedTaskState.CLAIMED.value:
            grouped["claimed"][task_id] = state
        elif status == QueuedTaskState.COMPLETED.value:
            grouped["completed"][task_id] = state
        elif status in (QueuedTaskState.FAILED.value, "abandoned"):
            grouped["failed"][task_id] = state

    if not any(grouped.values()):
        print("no tasks match the given filters")
        return
    def _priority_rank(rows: dict, task_id: str) -> int:
        try:
            return TaskPriority.from_string(rows[task_id].get("priority", "NORMAL")).value
        except ValueError:
            return TaskPriority.NORMAL.value

    for label in ("queued", "claimed", "completed", "failed"):
        rows = grouped[label]
        if rows:
            print(f"\n{label.upper()} ({len(rows)} tasks):")
            # Highest urgency first (TaskPriority.CRITICAL=1 .. LOW=4), task_id
            # as a stable tiebreak -- the priority filter above already reads
            # this same field, so surfacing it here is the display half of
            # the same feature, not a separate concern.
            for task_id in sorted(rows, key=lambda t: (_priority_rank(rows, t), t)):
                state = rows[task_id]
                print(
                    f"  {task_id} status={state.get('status', '?')} "
                    f"priority={state.get('priority', 'NORMAL')} "
                    f"agent={state.get('assigned_agent') or '-'}"
                )


async def _queue_status(bus: GossipBus, agent_filter: Optional[str]) -> None:
    states = await _latest_task_snapshots(bus)
    claimed = [
        (task_id, state)
        for task_id, state in states.items()
        if state.get("status") == QueuedTaskState.CLAIMED.value
        and (not agent_filter or state.get("assigned_agent") == agent_filter)
    ]
    if not claimed:
        print("no claimed tasks" + (f" for agent {agent_filter}" if agent_filter else ""))
        return
    for task_id, state in claimed:
        print(f"{state.get('assigned_agent', '?')}: {task_id}")


def _phase_sort_key(name: str) -> tuple[int, tuple[int, ...], str]:
    """Sort Phase-N[.M[.…]] names numerically component-by-component, and
    all other phase names lexically.

    A float encoding of the minor version (e.g. "2.10" -> 2 + 0.10 = 2.1)
    breaks ordering for any two-digit-or-longer minor component: Phase-2.10
    would sort before Phase-2.9 because 0.10 < 0.9 as floats, even though
    10 > 9 numerically. Parsing every dot-separated component into its own
    integer and comparing as a tuple avoids that collision entirely.
    """
    parts = name.split("-")
    if len(parts) >= 2 and parts[0] == "Phase":
        try:
            components = tuple(int(n) for n in parts[1].split("."))
            return (0, components, name)
        except (ValueError, IndexError):
            pass
    return (1, (), name)


async def _phase_list(bus: GossipBus) -> None:
    """List all phases with status, test progress, and any assignment/
    dependency/blocker metadata attached to the phase state."""
    phases = await _all_phase_states(bus)
    if not phases:
        print("no phases tracked yet")
        return
    for phase_name in sorted(phases, key=_phase_sort_key):
        phase = phases[phase_name]
        status_label = getattr(phase.status, "value", str(phase.status))
        test_str = (
            f"{phase.tests_passing}/{phase.total_tests}"
            if phase.total_tests
            else "0/0"
        )
        print(f"{phase_name:30s} {status_label:12s} tests={test_str}")
        assigned = getattr(phase, "assigned_to", None) or []
        depends_on = getattr(phase, "depends_on", None) or []
        blockers = getattr(phase, "blockers", None) or []
        if assigned:
            print(f"  assigned_to: {', '.join(assigned)}")
        if depends_on:
            print(f"  depends_on: {', '.join(depends_on)}")
        if blockers:
            print(f"  blockers: {', '.join(blockers)}")


def _format_age(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


async def _heartbeat_list(bus: GossipBus) -> None:
    agents = await find_agent_heartbeats(bus)
    if not agents:
        print("no agents tracked yet")
        return
    for agent_id in sorted(agents):
        data = agents[agent_id]
        registration = data.get("last_registration") or {}
        print(
            f"{data.get('status', '?'):8s} {agent_id} "
            f"model={registration.get('model', '?')} "
            f"work={data.get('work_in_progress') or '-'} "
            f"last={_format_age(int(time.time() - data.get('last_heartbeat_ts', time.time())))} ago"
        )


async def _heartbeat_check(bus: GossipBus, agent_id: str) -> None:
    agents = await find_agent_heartbeats(bus, agent_id)
    data = agents.get(agent_id)
    if not data:
        print(f"agent not found: {agent_id}")
        return
    registration = data.get("last_registration") or {}
    print(f"Agent: {agent_id}")
    print(f"Status: {data.get('status', '?')}")
    print(f"Type: {registration.get('agent_type', '?')}")
    print(f"Model: {registration.get('model', '?')}")
    print(f"Worktree: {registration.get('worktree', '?')}")
    print(f"Work: {data.get('work_in_progress') or '-'}")
    if data.get("killed_reason"):
        print(f"Killed: {data['killed_reason']}")


async def _heartbeat_dashboard(bus: GossipBus) -> None:
    agents = await find_agent_heartbeats(bus)
    if not agents:
        print("no agents tracked yet")
        return
    claims = await find_open_claims(bus)
    counts: dict[str, int] = {}
    for data in agents.values():
        status = data.get("status", "?")
        counts[status] = counts.get(status, 0) + 1
    print("summary: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"open_claims={len(claims)}")
    await _heartbeat_list(bus)


async def _heartbeat_pulse(bus: GossipBus, agent_id: str) -> None:
    await bus.emit(
        "heartbeat",
        {
            "kind": "agent_pulse",
            "agent_id": agent_id,
            "worktree": current_worktree_label(),
            "timestamp": time.time(),
        },
    )
    print(f"pulse: {agent_id}")


async def _heartbeat_kill(bus: GossipBus, agent_id: str, reason: str) -> None:
    await bus.emit(
        "heartbeat",
        {
            "kind": "agent_killed",
            "agent_id": agent_id,
            "worktree": current_worktree_label(),
            "reason": reason,
            "timestamp": time.time(),
        },
    )
    print(f"killed: {agent_id}")


async def _heartbeat_timeline(bus: GossipBus, agent_id: str, hours: int) -> None:
    cutoff = time.time() - hours * 3600
    events = await bus.tail(limit=1000, event_type="heartbeat")
    for event in reversed(events):
        payload = event["payload"]
        if event["ts"] < cutoff or payload.get("agent_id") != agent_id:
            continue
        print(f"{int(event['ts'])} {payload.get('kind', '?')} {payload.get('task') or payload.get('reason') or ''}")


async def _heartbeat_cleanup(bus: GossipBus) -> None:
    released = await cleanup_stale_claims(bus)
    print("released: " + ", ".join(released) if released else "no stale claims released")


for _patched_name in (
    "_get_latest_phase_state",
    "_all_phase_states",
    "_phase_list",
    "_queue_claim",
    "_queue_complete",
    "_queue_fail",
    "_queue_list",
    "_queue_status",
    "_heartbeat_list",
    "_heartbeat_check",
    "_heartbeat_dashboard",
    "_heartbeat_pulse",
    "_heartbeat_kill",
    "_heartbeat_timeline",
    "_heartbeat_cleanup",
):
    setattr(_impl, _patched_name, globals()[_patched_name])

main = _impl.main

if __name__ == "__main__":
    raise SystemExit(main())
