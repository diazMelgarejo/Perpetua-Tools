"""Distributed task queue: enqueuing, atomic claiming, completing, retrying,
and listing over the GossipBus event log.

Extracted from orchestrator/coordination/cli.py as part of the Part 2
consolidation module split (docs/next/2026-07-17-coordination-module-
consolidation-plan.md's canonical orchestrator/coordination/{paths,claims,
reorder_buffer,task_queue,phases}.py target layout).
"""
from __future__ import annotations

import asyncio
import aiosqlite
import json
import re
import time
import uuid
from typing import Optional

from orchestrator.gossip_bus import GossipBus, GossipBusError
from orchestrator.coordination.paths import current_worktree_label
from orchestrator.coordination.types import (
    ClaimResult,
    QueuedTaskState,
    ReleaseResult,
    TaskPriority,
)


def _error(message: str) -> bool:
    import sys

    print(f"ERROR: {message}", file=sys.stderr)
    return False


_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")


async def queue_add(
    bus: GossipBus,
    task_name: str,
    phase: str,
    priority: str,
    notes: str,
    depends_on: Optional[str],
    source_ref: Optional[str] = None,
    expected_base_sha: Optional[str] = None,
) -> bool | None:
    """Enqueue a new task with optional priority and dependencies.

    source_ref/expected_base_sha are optional here (not yet hard-required)
    -- see .agent/AGENTS.md's "Board-job source line" doctrine, which this
    schema is the producer-side half of. Making them mandatory outright
    would break every existing caller across this repo's own test suite
    with no coordinated update, and the doctrine explicitly spans this
    repo and orama-system's shared convention -- flipping to hard-required
    needs that cross-repo rollout done deliberately, not silently bundled
    into one file's fix. When provided, both are validated and persisted;
    omitting them still works, matching every existing caller unchanged.
    """
    if source_ref is not None and not source_ref.strip():
        return _error("source_ref, if given, must not be empty")
    if expected_base_sha is not None and not _SHA_RE.match(expected_base_sha):
        return _error(
            f"expected_base_sha {expected_base_sha!r} is not a valid git SHA "
            "(7-40 hex characters)"
        )
    task_id = f"{phase}-{task_name}-{uuid.uuid4().hex[:8]}"
    priority_enum = TaskPriority.from_string(priority)
    depends_on_list = [t.strip() for t in depends_on.split(",")] if depends_on else []
    payload = {
        "kind": "task_enqueue",
        "task_id": task_id,
        "task_name": task_name,
        "phase": phase,
        "priority": priority_enum.name,
        "priority_level": priority_enum.value,
        "status": QueuedTaskState.QUEUED.value,
        "assigned_agent": None,
        "retry_count": 0,
        "max_retries": 3,
        "depends_on": depends_on_list,
        "notes": notes,
    }
    if source_ref is not None:
        payload["source_ref"] = source_ref.strip()
    if expected_base_sha is not None:
        payload["expected_base_sha"] = expected_base_sha
    await bus.emit("heartbeat", payload)
    print(f"enqueued: {task_id} ({phase}, {priority_enum.name})")


_TASK_EVENT_KINDS = (
    "task_enqueue",
    "task_claim",
    "task_complete",
    "task_failed",
    "task_abandoned",
)


async def fetch_task_events(bus: GossipBus, task_id: Optional[str] = None) -> list[dict]:
    """Fetch task-lifecycle events (task_enqueue/claim/complete/failed/
    abandoned), optionally scoped to one task_id, directly via a targeted
    SQL query rather than a size-bounded tail() call filtered in Python.

    No LIMIT, and deliberately so: bus.tail(event_type="heartbeat") also
    carries agent-liveness pulses and other unrelated heartbeat traffic
    that has nothing to do with tasks, so a size-bounded window over that
    combined stream can silently drop an old-but-still-open task's
    founding task_enqueue event (dependencies, retry_limit, initial phase)
    once enough unrelated heartbeat volume accumulates -- corrupting that
    task's folded snapshot with no error, no warning. This query is
    already narrowed to just the 5 task-relevant kinds at the SQL level
    (and, when task_id is given, to that one task too), so an unbounded
    fetch stays cheap regardless of how large the bus grows, and a task's
    full history is always available to fold correctly.

    Returned oldest-first (ORDER BY id ASC) so callers can fold by plain
    forward iteration + dict.update(), letting later (newer) events'
    fields naturally overwrite earlier ones -- no reversed() needed.
    """
    kind_placeholders = ",".join("?" for _ in _TASK_EVENT_KINDS)
    query = (
        "SELECT id, event_uuid, ts, event_type, payload_json FROM gossip "
        "WHERE event_type = 'heartbeat' "
        f"AND json_extract(payload_json, '$.kind') IN ({kind_placeholders})"
    )
    params: list = list(_TASK_EVENT_KINDS)
    if task_id is not None:
        query += " AND json_extract(payload_json, '$.task_id') = ?"
        params.append(task_id)
    query += " ORDER BY id ASC"
    async with bus.connect() as db:
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
    return [
        {
            "row_id": row[0],
            "uuid": row[1],
            "ts": row[2],
            "event_type": row[3],
            "payload": json.loads(row[4]),
        }
        for row in rows
    ]


async def task_snapshot(
    bus: GossipBus, task_id: str, events: Optional[list[dict]] = None
) -> Optional[dict]:
    """Fold append-only heartbeat events for one task into a merged snapshot."""
    if events is None:
        events = await fetch_task_events(bus, task_id=task_id)
    snapshot: dict = {}
    for ev in events:
        p = ev["payload"]
        if p.get("task_id") == task_id and p.get("kind") in _TASK_EVENT_KINDS:
            snapshot.update(p)
    return snapshot or None


_CREATE_CLAIMS_TABLE = """
CREATE TABLE IF NOT EXISTS task_claims (
    task_id    TEXT PRIMARY KEY,
    agent_id   TEXT NOT NULL,
    claimed_at REAL NOT NULL
)
"""
_LOCK_RETRIES = 3
_LOCK_RETRY_SECONDS = 0.05


async def ensure_claims_table(bus: GossipBus) -> None:
    async with bus.connect() as db:
        await db.execute(_CREATE_CLAIMS_TABLE)
        await db.commit()


async def latest_task_snapshots(bus: GossipBus) -> dict[str, dict]:
    """Fold append-only events into current task snapshots, across every
    task's complete history -- see fetch_task_events for why this must not
    be a size-bounded window."""
    events = await fetch_task_events(bus)
    snapshots: dict[str, dict] = {}
    for event in events:
        payload = event["payload"]
        task_id = payload.get("task_id")
        if not task_id or payload.get("kind") not in _TASK_EVENT_KINDS:
            continue
        snapshots.setdefault(task_id, {}).update(payload)
    return snapshots


async def try_atomic_claim(
    bus: GossipBus,
    task_id: str,
    agent_id: str,
    claim_payload: Optional[dict] = None,
) -> ClaimResult:
    """Atomically persist exclusive ownership and its append-only event.

    `BEGIN IMMEDIATE` serializes writers before either mutation. Integrity
    conflicts report a lost race. Lock contention is retried briefly and then
    reports contention without leaving a claim row or an event behind.
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
                return ClaimResult.LOST_RACE
            except aiosqlite.OperationalError as exc:
                await db.rollback()
                locked = "locked" in str(exc).lower() or "busy" in str(exc).lower()
                if locked and attempt + 1 < _LOCK_RETRIES:
                    await asyncio.sleep(_LOCK_RETRY_SECONDS * (attempt + 1))
                    continue
                if locked:
                    return ClaimResult.CONTENTION
                raise GossipBusError(f"claim on {task_id!r} failed: {exc}") from exc
            except Exception as exc:
                await db.rollback()
                raise GossipBusError(f"claim on {task_id!r} failed: {exc}") from exc
        if inserted:
            bus.schedule_embedding(row_id, safe_payload)
        return ClaimResult.WON
    return ClaimResult.CONTENTION


async def release_claim_with_event(
    bus: GossipBus,
    task_id: str,
    event_type: str,
    payload: dict,
    expected_agent_id: Optional[str] = None,
) -> ReleaseResult:
    """Atomically free ownership and record why, mirroring try_atomic_claim's
    guarantee for the release side.

    Without this, a crash between a separate release DELETE and its event
    emit could free a claim row with no record of why (forensics gap), or
    record the terminal event while the row stays held -- blocking every
    future try_atomic_claim on that task_id with a stale "already claimed"
    row forever. Same `BEGIN IMMEDIATE` + bounded-retry treatment as the
    claim path.

    expected_agent_id, when given, makes the DELETE conditional on the
    caller actually being the current claim holder, and checks the deleted
    rowcount before emitting the event at all. Without this, the snapshot
    status check callers do beforehand is a read-then-write race: between
    that read and this transaction, the claim can have already changed
    hands (failed and reclaimed by someone else) -- a stale caller's
    unconditional `DELETE FROM task_claims WHERE task_id = ?` would then
    delete the NEW claimant's row and emit a terminal event out from under
    them. Conditioning on `agent_id` and checking rowcount == 1 turns that
    race into a clean LOST_RACE rather than silent data corruption.
    """
    for attempt in range(_LOCK_RETRIES):
        async with bus.connect() as db:
            try:
                await db.execute("BEGIN IMMEDIATE")
                await db.execute(_CREATE_CLAIMS_TABLE)
                if expected_agent_id is not None:
                    cursor = await db.execute(
                        "DELETE FROM task_claims WHERE task_id = ? AND agent_id = ?",
                        (task_id, expected_agent_id),
                    )
                    if cursor.rowcount != 1:
                        await db.rollback()
                        return ReleaseResult.LOST_RACE
                else:
                    await db.execute(
                        "DELETE FROM task_claims WHERE task_id = ?", (task_id,)
                    )
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
                    return ReleaseResult.CONTENTION
                raise GossipBusError(f"release of {task_id!r} failed: {exc}") from exc
            except Exception as exc:
                await db.rollback()
                raise GossipBusError(f"release of {task_id!r} failed: {exc}") from exc
        if inserted:
            bus.schedule_embedding(row_id, safe_payload)
        return ReleaseResult.RELEASED
    return ReleaseResult.CONTENTION


async def queue_claim(bus: GossipBus, task_id: str, agent_id: str) -> bool | None:
    snapshots = await latest_task_snapshots(bus)
    task_state = snapshots.get(task_id)
    if not task_state:
        return _error(f"task {task_id} not found")

    status = task_state.get("status")
    if status == QueuedTaskState.CLAIMED.value:
        return _error(
            f"{task_id} already claimed by {task_state.get('assigned_agent')}."
        )
    if status == QueuedTaskState.COMPLETED.value:
        return _error(f"{task_id} already completed. Cannot reclaim.")
    if status == "abandoned":
        return _error(f"{task_id} was abandoned. Cannot reclaim.")

    depends_on = task_state.get("depends_on", [])
    # depends_on is authored with short task_name values (e.g.
    # "PT-T5-CONTRACT-001"), but `snapshots` is keyed by the full
    # auto-generated task_id ("tier5-ledger-PT-T5-CONTRACT-001-20bfe0fc",
    # see queue_add). A direct snapshots.get(dependency) lookup can never
    # match, which made every dependent task permanently unclaimable
    # regardless of upstream completion. Resolve by task_id first, falling
    # back to a task_name match across all snapshots.
    by_task_name = {
        state.get("task_name"): state
        for state in snapshots.values()
        if state.get("task_name")
    }
    unmet = [
        dependency
        for dependency in depends_on
        if (snapshots.get(dependency) or by_task_name.get(dependency, {})).get(
            "status"
        )
        != QueuedTaskState.COMPLETED.value
    ]
    if unmet:
        return _error(f"{task_id} unmet dependencies: {', '.join(unmet)}")

    # Atomic gate: the snapshot checks above can both pass for two racing
    # claimants (read-then-write, no lock across the gap). This INSERT is
    # the actual exclusion point -- only one caller gets True. The claim row
    # and its heartbeat event commit together (see try_atomic_claim) so a
    # crash between them can never leave one without the other.
    payload = {
        "kind": "task_claim",
        "task_id": task_id,
        "assigned_agent": agent_id,
        "status": QueuedTaskState.CLAIMED.value,
        "worktree": current_worktree_label(),
    }
    claim_result = await try_atomic_claim(bus, task_id, agent_id, payload)
    if claim_result == ClaimResult.LOST_RACE:
        return _error(
            f"{task_id} could not be claimed; another agent won the race. "
            "Refresh status and retry if appropriate."
        )
    if claim_result == ClaimResult.CONTENTION:
        return _error(
            f"{task_id} could not be claimed; coordination database remained "
            "busy. Retry safely."
        )
    print(f"claimed: {task_id} by {agent_id}")


async def queue_complete(bus: GossipBus, task_id: str, agent_id: str, notes: str) -> bool | None:
    snapshots = await latest_task_snapshots(bus)
    task_state = snapshots.get(task_id)
    if not task_state:
        return _error(f"task {task_id} not found")
    status = task_state.get("status")
    if status != QueuedTaskState.CLAIMED.value:
        if status == QueuedTaskState.COMPLETED.value:
            return _error(f"{task_id} is already completed.")
        if status == "abandoned":
            return _error(f"{task_id} was abandoned; cannot complete.")
        return _error(
            f"{task_id} is not claimed (status: {status or 'unknown'}); "
            "only a currently-claimed task can be completed."
        )
    if task_state.get("assigned_agent") != agent_id:
        return _error(
            f"{task_id} is claimed by {task_state.get('assigned_agent')!r}, "
            f"not {agent_id!r}; only the current claimant can complete it."
        )
    # Free the atomic-claim row and record completion in one transaction --
    # a completed task is rejected by the status check in queue_claim
    # regardless, but a crash between a separate release and emit could
    # otherwise free the row with no event explaining why, or record the
    # event while the row stays held (blocking every future claim on this
    # task_id with a stale "already claimed" row forever).
    result = await release_claim_with_event(
        bus,
        task_id,
        "heartbeat",
        {
            "kind": "task_complete",
            "task_id": task_id,
            "status": QueuedTaskState.COMPLETED.value,
            "notes": notes,
        },
        expected_agent_id=agent_id,
    )
    if result == ReleaseResult.LOST_RACE:
        return _error(
            f"{task_id}'s claim changed before completion landed (raced by "
            "another agent); refresh status and retry if appropriate."
        )
    if result == ReleaseResult.CONTENTION:
        return _error(
            f"{task_id} could not be completed; coordination database remained "
            "busy. Retry safely."
        )
    print(f"completed: {task_id}")


async def queue_fail(bus: GossipBus, task_id: str, agent_id: str, notes: str) -> bool | None:
    snapshots = await latest_task_snapshots(bus)
    task_state = snapshots.get(task_id)
    if not task_state:
        return _error(f"task {task_id} not found")
    status = task_state.get("status")
    if status != QueuedTaskState.CLAIMED.value:
        if status == QueuedTaskState.COMPLETED.value:
            return _error(f"{task_id} is already completed; cannot fail.")
        if status == "abandoned":
            return _error(f"{task_id} was already abandoned.")
        return _error(
            f"{task_id} is not claimed (status: {status or 'unknown'}); "
            "only a currently-claimed task can be failed."
        )
    if task_state.get("assigned_agent") != agent_id:
        return _error(
            f"{task_id} is claimed by {task_state.get('assigned_agent')!r}, "
            f"not {agent_id!r}; only the current claimant can fail it."
        )
    retry_count = int(task_state.get("retry_count", 0)) + 1
    max_retries = int(task_state.get("max_retries", 3))
    if retry_count <= max_retries:
        # Must release here, not just on complete -- the task goes back to
        # QUEUED and queue_claim's atomic gate would otherwise reject every
        # future claim attempt with a stale "already claimed" row forever.
        # Release + event committed together, same reasoning as queue_complete.
        result = await release_claim_with_event(
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
            expected_agent_id=agent_id,
        )
        if result == ReleaseResult.LOST_RACE:
            return _error(
                f"{task_id}'s claim changed before the failure landed (raced "
                "by another agent); refresh status and retry if appropriate."
            )
        if result == ReleaseResult.CONTENTION:
            return _error(
                f"{task_id} could not be requeued; coordination database "
                "remained busy. Retry safely."
            )
        print(f"failed: {task_id}, retry {retry_count}/{max_retries}")
        return

    result = await release_claim_with_event(
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
        expected_agent_id=agent_id,
    )
    if result == ReleaseResult.LOST_RACE:
        return _error(
            f"{task_id}'s claim changed before abandonment landed (raced by "
            "another agent); refresh status and retry if appropriate."
        )
    if result == ReleaseResult.CONTENTION:
        return _error(
            f"{task_id} could not be abandoned; coordination database remained "
            "busy. Retry safely."
        )
    print(f"abandoned: {task_id} (max retries exceeded)")


async def queue_list(bus: GossipBus, phase_filter: Optional[str], priority_filter: Optional[str], agent_filter: Optional[str]) -> None:
    """List queued tasks grouped by status, with optional filters."""
    # Same unbounded fold as claim/fail/complete -- a size-bounded tail() over
    # the combined heartbeat stream can drop a task's founding task_enqueue
    # once enough unrelated pulse traffic accumulates, making open work vanish
    # from the board with no error (see fetch_task_events).
    task_states = await latest_task_snapshots(bus)
    queued, claimed, completed, failed = {}, {}, {}, {}
    for task_id, state in task_states.items():
        if phase_filter and state.get("phase") != phase_filter:
            continue
        if priority_filter and state.get("priority") != priority_filter.upper():
            continue
        if agent_filter and state.get("assigned_agent") != agent_filter:
            continue
        status = state.get("status")
        if status == QueuedTaskState.QUEUED.value:
            queued[task_id] = state
        elif status == QueuedTaskState.CLAIMED.value:
            claimed[task_id] = state
        elif status == QueuedTaskState.COMPLETED.value:
            completed[task_id] = state
        elif status in (QueuedTaskState.FAILED.value, "abandoned"):
            failed[task_id] = state
    if queued or claimed or completed or failed:
        if queued:
            print(f"\nQUEUED ({len(queued)} tasks):")
            for task_id in sorted(queued.keys(), key=lambda tid: queued[tid].get("priority_level", 999)):
                state = queued[task_id]
                print(f"  [{state.get('priority', '?'):8s}] {task_id}  {state.get('phase', '?')}/{state.get('task_name', '?')}")
        if claimed:
            print(f"\nCLAIMED ({len(claimed)} tasks):")
            for task_id in sorted(claimed.keys()):
                state = claimed[task_id]
                print(f"  [{state.get('priority', '?'):8s}] {task_id}  ← {state.get('assigned_agent', '?')}")
        if completed:
            print(f"\nCOMPLETED ({len(completed)} tasks):")
            completed_ids = ", ".join(sorted(completed.keys())[:10])
            if len(completed) > 10:
                completed_ids += f", ... +{len(completed) - 10} more"
            print(f"  {completed_ids}")
        if failed:
            print(f"\nFAILED ({len(failed)} tasks):")
            for task_id in sorted(failed.keys()):
                state = failed[task_id]
                print(f"  {task_id}  [{state.get('status', '?')}] retry {state.get('retry_count', 0)}/{state.get('max_retries', 3)}")
    else:
        print("no tasks match the given filters")


async def cleanup_stale_queue_claims(
    bus: GossipBus, dead_agent_ids: set[str]
) -> list[str]:
    """Re-queue tasks whose atomic ``task_claims`` row is held by dead agents.

    ``heartbeat cleanup`` already auto-releases legacy ``agent_claim`` rows,
    but the distributed queue's exclusion gate lives in ``task_claims``. A
    dead claimant leaves that row behind forever unless we delete it and emit a
    requeue event, which otherwise blocks every future ``queue claim``.
    """
    if not dead_agent_ids:
        return []

    placeholders = ",".join("?" for _ in dead_agent_ids)
    async with bus.connect() as db:
        await db.execute(_CREATE_CLAIMS_TABLE)
        cursor = await db.execute(
            f"SELECT task_id, agent_id FROM task_claims "
            f"WHERE agent_id IN ({placeholders})",
            tuple(sorted(dead_agent_ids)),
        )
        rows = await cursor.fetchall()

    released: list[str] = []
    snapshots = await latest_task_snapshots(bus)
    for task_id, agent_id in rows:
        task_state = snapshots.get(task_id, {})
        result = await release_claim_with_event(
            bus,
            task_id,
            "heartbeat",
            {
                "kind": "task_failed",
                "task_id": task_id,
                "retry_count": int(task_state.get("retry_count", 0)),
                "max_retries": int(task_state.get("max_retries", 3)),
                "status": QueuedTaskState.QUEUED.value,
                "assigned_agent": None,
                "notes": (
                    f"Auto-released: agent {agent_id} dead; task returned to queue"
                ),
            },
            expected_agent_id=agent_id,
        )
        if result == ReleaseResult.RELEASED:
            released.append(task_id)
    return released


async def queue_status(bus: GossipBus, agent_filter: Optional[str]) -> None:
    """Show status of all claimed tasks per agent."""
    task_states = await latest_task_snapshots(bus)
    agent_work = {}
    for task_id, state in task_states.items():
        if state.get("status") == QueuedTaskState.CLAIMED.value:
            agent = state.get("assigned_agent", "?")
            if agent_filter and agent != agent_filter:
                continue
            if agent not in agent_work:
                agent_work[agent] = []
            agent_work[agent].append((task_id, state))
    if agent_work:
        print("\nAGENT WORK STATUS:")
        for agent in sorted(agent_work.keys()):
            tasks = agent_work[agent]
            print(f"\n  {agent}  [{len(tasks)} tasks]:")
            for task_id, state in tasks:
                print(f"    - {task_id}  ({state.get('phase', '?')}/{state.get('task_name', '?')})")
    else:
        print("no claimed tasks" + (f" for agent {agent_filter}" if agent_filter else ""))
