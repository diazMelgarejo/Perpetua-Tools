"""Phase-based workflow tracking: status, test progress, dependencies,
blockers, and critical-path analysis over the GossipBus event log.

Extracted from orchestrator/coordination/cli.py as part of the Part 2
consolidation module split (docs/next/2026-07-17-coordination-module-
consolidation-plan.md's canonical orchestrator/coordination/{paths,claims,
reorder_buffer,task_queue,phases}.py target layout).
"""
from __future__ import annotations

import json
import time
from typing import Optional

from orchestrator.gossip_bus import GossipBus
from orchestrator.coordination.types import PhaseState, PhaseStatus


def _error(message: str) -> bool:
    import sys

    print(f"ERROR: {message}", file=sys.stderr)
    return False


def _warning(message: str) -> bool:
    import sys

    print(f"WARNING: {message}", file=sys.stderr)
    return False


async def fetch_phase_events(
    bus: GossipBus, phase_name: Optional[str] = None
) -> list[dict]:
    """Fetch phase lifecycle events directly via SQL, not a size-bounded tail().

    Same rationale as task_queue.fetch_task_events: unrelated heartbeat
    traffic can push a phase's founding or terminal events out of a
    bounded tail window, making completed phases vanish from the board or
    allowing restarts.
    """
    query = (
        "SELECT id, event_uuid, ts, event_type, payload_json FROM gossip "
        "WHERE event_type = 'heartbeat' "
        "AND json_extract(payload_json, '$.kind') = ?"
    )
    params: list = ["phase_event"]
    if phase_name is not None:
        query += " AND json_extract(payload_json, '$.phase_name') = ?"
        params.append(phase_name)
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


async def latest_phase_states(bus: GossipBus) -> dict[str, PhaseState]:
    """Fold append-only phase events into current phase snapshots."""
    latest: dict[str, PhaseState] = {}
    for event in await fetch_phase_events(bus):
        payload = event["payload"]
        phase_name = payload.get("phase_name")
        if phase_name:
            latest[phase_name] = PhaseState.from_payload(payload)
    return latest


async def get_latest_phase_state(bus: GossipBus, phase_name: str) -> Optional[PhaseState]:
    """Retrieve the latest state for a given phase."""
    snapshot: Optional[dict] = None
    for event in await fetch_phase_events(bus, phase_name=phase_name):
        snapshot = event["payload"]
    return PhaseState.from_payload(snapshot) if snapshot else None


async def all_phase_states(bus: GossipBus) -> dict[str, PhaseState]:
    """Retrieve the latest state for all phases."""
    return await latest_phase_states(bus)


async def phase_start(
    bus: GossipBus,
    phase_name: str,
    depends_on: Optional[list[str]] = None,
    agent_id: Optional[str] = None,
) -> bool | None:
    """Start a phase (transition to in_progress)."""
    existing = await get_latest_phase_state(bus, phase_name)
    if existing and existing.status == PhaseStatus.COMPLETE:
        return _warning(f"Phase '{phase_name}' is already COMPLETE. Cannot restart.")

    phase = existing or PhaseState(phase_name=phase_name, status=PhaseStatus.NOT_STARTED)
    phase.status = PhaseStatus.IN_PROGRESS
    phase.started_at = time.time()
    if depends_on:
        phase.depends_on = depends_on
    if agent_id and agent_id not in phase.assigned_to:
        phase.assigned_to.append(agent_id)

    await bus.emit("heartbeat", phase.to_payload())
    print(f"started: {phase_name} (depends_on: {phase.depends_on})")


async def phase_update(
    bus: GossipBus,
    phase_name: str,
    tests_passing: Optional[int] = None,
    total_tests: Optional[int] = None,
    agent_id: Optional[str] = None,
) -> bool | None:
    """Update phase test progress."""
    phase = await get_latest_phase_state(bus, phase_name)
    if not phase:
        return _error(f"Phase '{phase_name}' not found. Run 'phase start' first.")

    if tests_passing is not None:
        phase.tests_passing = tests_passing
    if total_tests is not None:
        phase.total_tests = total_tests
    if agent_id and agent_id not in phase.assigned_to:
        phase.assigned_to.append(agent_id)

    await bus.emit("heartbeat", phase.to_payload())
    pct = (
        f" ({100*phase.tests_passing//phase.total_tests if phase.total_tests else 0}%)"
        if phase.total_tests
        else ""
    )
    print(f"updated: {phase_name} {phase.tests_passing}/{phase.total_tests}{pct}")


async def phase_complete(bus: GossipBus, phase_name: str) -> bool | None:
    """Mark phase as complete."""
    phase = await get_latest_phase_state(bus, phase_name)
    if not phase:
        return _error(f"Phase '{phase_name}' not found.")

    if phase.status == PhaseStatus.COMPLETE:
        print(f"Phase '{phase_name}' is already complete.")
        return

    # Verify blockers are cleared
    if phase.blockers:
        return _warning(
            f"Phase '{phase_name}' has blockers: {phase.blockers}. "
            "Clear them before marking complete."
        )

    phase.status = PhaseStatus.COMPLETE
    phase.completed_at = time.time()
    await bus.emit("heartbeat", phase.to_payload())
    print(f"completed: {phase_name}")


async def phase_block(bus: GossipBus, phase_name: str, reason: str) -> bool | None:
    """Mark phase as blocked."""
    phase = await get_latest_phase_state(bus, phase_name)
    if not phase:
        return _error(f"Phase '{phase_name}' not found.")

    phase.status = PhaseStatus.BLOCKED
    if reason not in phase.blockers:
        phase.blockers.append(reason)

    await bus.emit("heartbeat", phase.to_payload())
    print(f"blocked: {phase_name} — {reason}")


async def phase_unblock(bus: GossipBus, phase_name: str, reason: str) -> bool | None:
    """Unblock a phase by removing a specific blocker."""
    phase = await get_latest_phase_state(bus, phase_name)
    if not phase:
        return _error(f"Phase '{phase_name}' not found.")

    if reason in phase.blockers:
        phase.blockers.remove(reason)

    if not phase.blockers:
        phase.status = PhaseStatus.IN_PROGRESS
    else:
        phase.status = PhaseStatus.BLOCKED

    await bus.emit("heartbeat", phase.to_payload())
    print(f"unblocked: {phase_name}")


def phase_sort_key(name: str) -> tuple[int, tuple[int, ...] | tuple[()], str]:
    """Sort Phase-N[.M[.…]] names numerically; other names lexically."""
    parts = name.split("-")
    if len(parts) >= 2 and parts[0] == "Phase":
        try:
            components = tuple(int(n) for n in parts[1].split("."))
            return (0, components, name)
        except (ValueError, IndexError):
            pass
    return (1, (), name)


async def phase_list(bus: GossipBus) -> None:
    """List all phases with status and test progress."""
    phases = await all_phase_states(bus)
    if not phases:
        print("no phases tracked yet")
        return

    for phase_name in sorted(phases.keys(), key=phase_sort_key):
        phase = phases[phase_name]
        status_emoji = {
            PhaseStatus.COMPLETE: "✅",
            PhaseStatus.IN_PROGRESS: "🔄",
            PhaseStatus.BLOCKED: "⛔",
            PhaseStatus.NOT_STARTED: "⏳",
        }.get(phase.status, "?")

        test_str = (
            f"{phase.tests_passing}/{phase.total_tests}"
            if phase.total_tests
            else "0/0"
        )
        elapsed = ""
        if phase.started_at:
            end_time = phase.completed_at or time.time()
            hours = (end_time - phase.started_at) / 3600
            elapsed = f" [{hours:.1f}h elapsed]"

        deps_str = f" → Depends-on: {', '.join(phase.depends_on)}" if phase.depends_on else ""
        blockers_str = (
            f" → Blockers: {', '.join(phase.blockers)}" if phase.blockers else ""
        )

        print(
            f"{status_emoji} {phase_name:<30} {phase.status.value:<15} "
            f"{test_str} tests{elapsed}{deps_str}{blockers_str}"
        )


async def phase_status(bus: GossipBus, phase_name: str) -> None:
    """Show detailed status of a single phase."""
    phase = await get_latest_phase_state(bus, phase_name)
    if not phase:
        print(f"Phase '{phase_name}' not found.")
        return

    print(f"\n=== Phase: {phase_name} ===")
    print(f"Status: {phase.status.value}")
    print(f"Tests: {phase.tests_passing}/{phase.total_tests}")
    print(f"Assigned to: {', '.join(phase.assigned_to) if phase.assigned_to else 'none'}")
    print(
        f"Dependencies: {', '.join(phase.depends_on) if phase.depends_on else 'none'}"
    )
    print(f"Blockers: {', '.join(phase.blockers) if phase.blockers else 'none'}")
    if phase.started_at:
        print(f"Started at: {phase.started_at}")
    if phase.completed_at:
        print(f"Completed at: {phase.completed_at}")
    if phase.notes:
        print(f"Notes: {phase.notes}")
    print()


async def detect_blockers(
    bus: GossipBus, phase: PhaseState, all_phases: dict[str, PhaseState]
) -> list[str]:
    """Detect phases blocking this phase (unfulfilled dependencies)."""
    blocking = []
    for dep in phase.depends_on:
        dep_phase = all_phases.get(dep)
        if not dep_phase or dep_phase.status != PhaseStatus.COMPLETE:
            blocking.append(dep)
    return blocking


async def workflow_critical_path(bus: GossipBus) -> None:
    """Show critical path (longest dependency chain) and ETA."""
    phases = await all_phase_states(bus)
    if not phases:
        print("no phases tracked yet")
        return

    # Build dependency graph
    graph: dict[str, list[str]] = {}
    for phase_name, phase in phases.items():
        graph[phase_name] = phase.depends_on

    # Find all roots (phases with no dependencies)
    all_phases_set = set(phases.keys())
    roots = [p for p in all_phases_set if not phases[p].depends_on]
    if not roots:
        print("no root phases (circular dependency?)")
        return

    # Find longest path via DFS
    def longest_chain(node: str, visited: set[str]) -> tuple[list[str], float]:
        """Return (path, total_hours) for longest dependency chain from node."""
        if node in visited:
            return ([], 0.0)  # Cycle detected

        visited.add(node)
        phase = phases.get(node)
        if not phase:
            return ([], 0.0)

        current_duration = phase.estimated_duration_hours or 0.0
        if phase.completed_at and phase.started_at:
            current_duration = (phase.completed_at - phase.started_at) / 3600

        # Find longest path among dependents
        max_path: list[str] = []
        max_duration = 0.0
        for dependent, deps in graph.items():
            if node in deps:
                sub_path, sub_duration = longest_chain(dependent, visited.copy())
                if sub_duration + current_duration > max_duration:
                    max_duration = sub_duration + current_duration
                    max_path = [node] + sub_path

        if not max_path:
            max_path = [node]
            max_duration = current_duration

        return (max_path, max_duration)

    # Compute longest chain from each root
    longest_overall: list[str] = []
    longest_duration = 0.0
    for root in roots:
        path, duration = longest_chain(root, set())
        if duration > longest_duration:
            longest_duration = duration
            longest_overall = path

    # Compute ETA
    eta_hours = longest_duration
    print("\n=== Critical Path Analysis ===")
    print(f"Longest chain: {' → '.join(longest_overall)}")
    print(f"Total duration: {eta_hours:.1f} hours")
    print(f"ETA (if started now): +{eta_hours:.1f} hours\n")

    # Show phase durations
    for phase_name in longest_overall:
        phase = phases[phase_name]
        if phase.completed_at and phase.started_at:
            elapsed = (phase.completed_at - phase.started_at) / 3600
        else:
            elapsed = phase.estimated_duration_hours
        status = (
            "✅" if phase.status == PhaseStatus.COMPLETE else
            "🔄" if phase.status == PhaseStatus.IN_PROGRESS else
            "⏳"
        )
        print(f"  {status} {phase_name:<25} {elapsed:>5.1f}h")
