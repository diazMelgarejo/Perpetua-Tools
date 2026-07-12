#!/usr/bin/env python3
"""Stable facade for agent coordination state reduction.

The original CLI implementation is retained in ``agent_coordination_legacy``.
This facade corrects append-only GossipBus state reduction while preserving the
public functions and command-line interface.
"""
from __future__ import annotations

import time
import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts import agent_coordination_legacy as _impl
from orchestrator.heartbeat_monitor import (
    cleanup_stale_claims,
    find_agent_heartbeats,
    find_open_claims,
)

# Re-export the established public surface, including underscore-prefixed helpers
# used by the test suite and sibling automation.
for _name, _value in vars(_impl).items():
    if not _name.startswith("__"):
        globals()[_name] = _value


async def _latest_task_snapshots(bus: GossipBus) -> dict[str, dict]:
    """Fold append-only task events into current snapshots.

    ``GossipBus.tail`` returns newest-first. State must therefore be folded in
    reverse order so later events override earlier fields while retaining stable
    metadata (phase, priority, task name, dependency list) omitted by delta
    events such as claim/complete/fail.
    """
    events = await bus.tail(limit=1000, event_type="heartbeat")
    snapshots: dict[str, dict] = {}
    accepted = {
        "task_enqueue",
        "task_claim",
        "task_complete",
        "task_failed",
        "task_abandoned",
    }
    for ev in reversed(events):
        payload = ev["payload"]
        task_id = payload.get("task_id")
        if not task_id or payload.get("kind") not in accepted:
            continue
        snapshots.setdefault(task_id, {}).update(payload)
    return snapshots


async def _get_latest_phase_state(
    bus: GossipBus, phase_name: str
) -> Optional[PhaseState]:
    """Return the newest matching phase event."""
    events = await bus.tail(limit=500, event_type="heartbeat")
    for ev in events:  # newest first by contract
        payload = ev["payload"]
        if payload.get("kind") == "phase_event" and payload.get("phase_name") == phase_name:
            return PhaseState.from_payload(payload)
    return None


async def _all_phase_states(bus: GossipBus) -> dict[str, PhaseState]:
    """Return one newest snapshot per phase."""
    events = await bus.tail(limit=500, event_type="heartbeat")
    latest: dict[str, PhaseState] = {}
    for ev in events:  # newest first; first occurrence wins
        payload = ev["payload"]
        if payload.get("kind") != "phase_event":
            continue
        phase_name = payload.get("phase_name")
        if phase_name and phase_name not in latest:
            latest[phase_name] = PhaseState.from_payload(payload)
    return latest


async def _queue_claim(bus: GossipBus, task_id: str, agent_id: str) -> None:
    """Claim a queued task after validating current state and dependencies."""
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

    await bus.emit(
        "heartbeat",
        {
            "kind": "task_claim",
            "task_id": task_id,
            "assigned_agent": agent_id,
            "status": QueuedTaskState.CLAIMED.value,
            "worktree": current_worktree_label(),
        },
    )
    print(f"claimed: {task_id} by {agent_id}")


async def _queue_complete(bus: GossipBus, task_id: str, notes: str) -> None:
    """Mark an existing task as completed."""
    snapshots = await _latest_task_snapshots(bus)
    if task_id not in snapshots:
        print(f"ERROR: task {task_id} not found")
        return
    await bus.emit(
        "heartbeat",
        {
            "kind": "task_complete",
            "task_id": task_id,
            "status": QueuedTaskState.COMPLETED.value,
            "notes": notes,
        },
    )
    print(f"completed: {task_id}")


async def _queue_fail(bus: GossipBus, task_id: str, notes: str) -> None:
    """Requeue through ``max_retries`` failures, then abandon on the next."""
    snapshots = await _latest_task_snapshots(bus)
    task_state = snapshots.get(task_id)
    if not task_state:
        print(f"ERROR: task {task_id} not found")
        return

    retry_count = int(task_state.get("retry_count", 0)) + 1
    max_retries = int(task_state.get("max_retries", 3))
    if retry_count <= max_retries:
        await bus.emit(
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
        print(f"failed: {task_id}, retry {retry_count}/{max_retries}")
        return

    await bus.emit(
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
    print(f"abandoned: {task_id} (max retries exceeded)")


async def _queue_list(
    bus: GossipBus,
    phase_filter: Optional[str],
    priority_filter: Optional[str],
    agent_filter: Optional[str],
) -> None:
    """List current task snapshots, preserving enqueue metadata."""
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

    if grouped["queued"]:
        print(f"\nQUEUED ({len(grouped['queued'])} tasks):")
        for task_id in sorted(
            grouped["queued"],
            key=lambda tid: grouped["queued"][tid].get("priority_level", 999),
        ):
            state = grouped["queued"][task_id]
            print(
                f"  [{state.get('priority', '?'):8s}] {task_id}  "
                f"{state.get('phase', '?')}/{state.get('task_name', '?')}"
            )

    if grouped["claimed"]:
        print(f"\nCLAIMED ({len(grouped['claimed'])} tasks):")
        for task_id in sorted(grouped["claimed"]):
            state = grouped["claimed"][task_id]
            print(
                f"  [{state.get('priority', '?'):8s}] {task_id}  "
                f"← {state.get('assigned_agent', '?')}"
            )

    if grouped["completed"]:
        print(f"\nCOMPLETED ({len(grouped['completed'])} tasks):")
        print("  " + ", ".join(sorted(grouped["completed"])[:10]))

    if grouped["failed"]:
        print(f"\nFAILED ({len(grouped['failed'])} tasks):")
        for task_id in sorted(grouped["failed"]):
            state = grouped["failed"][task_id]
            print(
                f"  {task_id}  [{state.get('status', '?')}] retry "
                f"{state.get('retry_count', 0)}/{state.get('max_retries', 3)}"
            )


async def _queue_status(bus: GossipBus, agent_filter: Optional[str]) -> None:
    """Show currently claimed tasks grouped by agent."""
    states = await _latest_task_snapshots(bus)
    agent_work: dict[str, list[tuple[str, dict]]] = {}
    for task_id, state in states.items():
        if state.get("status") != QueuedTaskState.CLAIMED.value:
            continue
        agent = state.get("assigned_agent", "?")
        if agent_filter and agent != agent_filter:
            continue
        agent_work.setdefault(agent, []).append((task_id, state))

    if not agent_work:
        print("no claimed tasks" + (f" for agent {agent_filter}" if agent_filter else ""))
        return

    print("\nAGENT WORK STATUS:")
    for agent in sorted(agent_work):
        tasks = agent_work[agent]
        print(f"\n  {agent}  [{len(tasks)} tasks]:")
        for task_id, state in tasks:
            print(
                f"    - {task_id}  "
                f"({state.get('phase', '?')}/{state.get('task_name', '?')})"
            )


def _phase_sort_key(name: str) -> tuple[int, float, str]:
    """Sort Phase-N names numerically and all other phase names lexically."""
    parts = name.split("-")
    if len(parts) >= 2 and parts[0] == "Phase":
        try:
            nums = parts[1].split(".")
            major = int(nums[0])
            minor = float(f"0.{nums[1]}") if len(nums) > 1 else 0.0
            return (0, major + minor, name)
        except (ValueError, IndexError):
            pass
    return (1, 0.0, name)


async def _phase_list(bus: GossipBus) -> None:
    """List all phases with status and test progress."""
    phases = await _all_phase_states(bus)
    if not phases:
        print("no phases tracked yet")
        return

    for phase_name in sorted(phases.keys(), key=_phase_sort_key):
        phase = phases[phase_name]
        status_label = getattr(phase.status, "value", str(phase.status))
        test_str = (
            f"{phase.tests_passing}/{phase.total_tests}"
            if phase.total_tests
            else "0/0"
        )
        print(f"{phase_name:30s} {status_label:12s} tests={test_str}")
        owner = getattr(phase, "owner_agent", None) or getattr(phase, "agent", None)
        depends_on = getattr(phase, "depends_on", None) or []
        blockers = getattr(phase, "blockers", None) or []
        if owner:
            print(f"  owner: {owner}")
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
        reg = data.get("last_registration") or {}
        print(
            f"{data.get('status', '?'):8s} {agent_id} "
            f"model={reg.get('model', '?')} "
            f"work={data.get('work_in_progress') or '-'} "
            f"last={_format_age(int(time.time() - data.get('last_heartbeat_ts', time.time())))} ago"
        )


async def _heartbeat_check(bus: GossipBus, agent_id: str) -> None:
    agents = await find_agent_heartbeats(bus, agent_id)
    data = agents.get(agent_id)
    if not data:
        print(f"agent not found: {agent_id}")
        return
    reg = data.get("last_registration") or {}
    print(f"Agent: {agent_id}")
    print(f"Status: {data.get('status', '?')}")
    print(f"Type: {reg.get('agent_type', '?')}")
    print(f"Model: {reg.get('model', '?')}")
    print(f"Worktree: {reg.get('worktree', '?')}")
    print(f"Work: {data.get('work_in_progress') or '-'}")
    print(f"Uptime: {_format_age(int(data.get('uptime_seconds') or 0))}")
    if data.get("killed_reason"):
        print(f"Killed: {data['killed_reason']}")


async def _heartbeat_dashboard(bus: GossipBus) -> None:
    agents = await find_agent_heartbeats(bus)
    if not agents:
        print("no agents tracked yet")
        return
    open_claims = await find_open_claims(bus)
    print("AGENT HEALTH")
    counts: dict[str, int] = {}
    for data in agents.values():
        counts[data.get("status", "?")] = counts.get(data.get("status", "?"), 0) + 1
    print(
        "summary: "
        + ", ".join(f"{status}={count}" for status, count in sorted(counts.items()))
    )
    print(f"open_claims={len(open_claims)}")
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
    cutoff = time.time() - (hours * 3600)
    events = await bus.tail(limit=1000, event_type="heartbeat")
    rows = [
        ev
        for ev in reversed(events)
        if ev["ts"] >= cutoff and ev["payload"].get("agent_id") == agent_id
    ]
    if not rows:
        print(f"no activity for {agent_id}")
        return
    print(f"Timeline for {agent_id}")
    labels = {
        "agent_register": "REGISTERED",
        "agent_claim": "CLAIMED",
        "agent_release": "RELEASED",
        "agent_pulse": "PULSE",
        "agent_killed": "KILLED",
    }
    for ev in rows:
        payload = ev["payload"]
        label = labels.get(payload.get("kind"), payload.get("kind", "?"))
        task = payload.get("task") or payload.get("reason") or ""
        print(f"{int(ev['ts'])}  {label:10s} {task}")


async def _heartbeat_cleanup(bus: GossipBus) -> None:
    released = await cleanup_stale_claims(bus)
    if not released:
        print("no stale claims released")
        return
    print("released: " + ", ".join(released))


# Patch the retained implementation module so its CLI dispatch resolves these
# corrected state reducers too.
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
