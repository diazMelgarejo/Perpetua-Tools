#!/usr/bin/env python3
"""scripts/agent_coordination_phases.py — Phase-based workflow tracking.

Phase state is tracked via "phase_event" events in GossipBus.
Each phase has a name, status, assigned agents, test counts, blockers, and timestamps.
Critical path analysis shows the longest dependency chain and estimated ETA.

Usage:
    # Phase tracking API
    python3 scripts/agent_coordination_phases.py phase list
    python3 scripts/agent_coordination_phases.py phase status <phase_name>
    python3 scripts/agent_coordination_phases.py phase start <phase_name> [--depends-on phase1,phase2] [--agent agent_id]
    python3 scripts/agent_coordination_phases.py phase update <phase_name> --tests-passing 50/69 [--agent agent_id]
    python3 scripts/agent_coordination_phases.py phase complete <phase_name>
    python3 scripts/agent_coordination_phases.py phase block <phase_name> --reason "reason text"
    python3 scripts/agent_coordination_phases.py phase unblock <phase_name> --reason "reason text"

    # Workflow analysis
    python3 scripts/agent_coordination_phases.py workflow critical-path
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.gossip_bus import GossipBus, _canonical_repo_state_dir  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Phase Data Structures
# ─────────────────────────────────────────────────────────────────────────────


class PhaseStatus(Enum):
    """Phase workflow status."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETE = "complete"


@dataclass
class PhaseState:
    """Represents a workflow phase and its current state."""
    phase_name: str
    status: PhaseStatus
    assigned_to: list[str] = field(default_factory=list)
    total_tests: int = 0
    tests_passing: int = 0
    blockers: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    notes: str = ""
    estimated_duration_hours: float = 0.0

    def to_payload(self) -> dict:
        """Convert to JSON-serializable payload for GossipBus."""
        return {
            "kind": "phase_event",
            "phase_name": self.phase_name,
            "status": self.status.value,
            "assigned_to": self.assigned_to,
            "total_tests": self.total_tests,
            "tests_passing": self.tests_passing,
            "blockers": self.blockers,
            "depends_on": self.depends_on,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "notes": self.notes,
            "estimated_duration_hours": self.estimated_duration_hours,
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "PhaseState":
        """Reconstruct PhaseState from GossipBus payload."""
        return cls(
            phase_name=payload["phase_name"],
            status=PhaseStatus(payload["status"]),
            assigned_to=payload.get("assigned_to", []),
            total_tests=payload.get("total_tests", 0),
            tests_passing=payload.get("tests_passing", 0),
            blockers=payload.get("blockers", []),
            depends_on=payload.get("depends_on", []),
            started_at=payload.get("started_at"),
            completed_at=payload.get("completed_at"),
            notes=payload.get("notes", ""),
            estimated_duration_hours=payload.get("estimated_duration_hours", 0.0),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────


def canonical_repo_root() -> Path:
    """Resolve the shared repo root common to every worktree of this repo.

    Delegates to gossip_bus._canonical_repo_state_dir(), the single
    canonical resolver -- it already handles submodule/bare-repo anchoring,
    a subprocess timeout, and error fallback correctly; this file's own
    prior inline reimplementation had none of those and would raise
    uncaught on a git failure. Falls back to cwd only when git resolution
    itself fails (not in a repo).
    """
    state = _canonical_repo_state_dir()
    return state.parent if state is not None else Path.cwd()


def canonical_db_path() -> str:
    return str(canonical_repo_root() / ".state" / "perpetua_core.db")


# ─────────────────────────────────────────────────────────────────────────────
# Phase Tracking Functions
# ─────────────────────────────────────────────────────────────────────────────


async def _get_latest_phase_state(bus: GossipBus, phase_name: str) -> Optional[PhaseState]:
    """Retrieve the latest state for a given phase."""
    events = await bus.tail(limit=500, event_type="heartbeat")
    for ev in events:  # newest first (tail returns in reverse order)
        p = ev["payload"]
        if p.get("kind") == "phase_event" and p.get("phase_name") == phase_name:
            return PhaseState.from_payload(p)
    return None


async def _all_phase_states(bus: GossipBus) -> dict[str, PhaseState]:
    """Retrieve the latest state for all phases."""
    events = await bus.tail(limit=500, event_type="heartbeat")
    latest: dict[str, PhaseState] = {}
    for ev in events:  # newest first
        p = ev["payload"]
        if p.get("kind") != "phase_event":
            continue
        phase_name = p.get("phase_name")
        # Only store if not seen yet (this is the newest for this phase)
        if phase_name and phase_name not in latest:
            latest[phase_name] = PhaseState.from_payload(p)
    return latest


async def _phase_start(
    bus: GossipBus,
    phase_name: str,
    depends_on: Optional[list[str]] = None,
    agent_id: Optional[str] = None,
) -> None:
    """Start a phase (transition to in_progress)."""
    existing = await _get_latest_phase_state(bus, phase_name)
    if existing and existing.status == PhaseStatus.COMPLETE:
        print(f"WARNING: Phase '{phase_name}' is already COMPLETE. Cannot restart.")
        return

    phase = existing or PhaseState(phase_name=phase_name, status=PhaseStatus.NOT_STARTED)
    phase.status = PhaseStatus.IN_PROGRESS
    phase.started_at = time.time()
    if depends_on:
        phase.depends_on = depends_on
    if agent_id and agent_id not in phase.assigned_to:
        phase.assigned_to.append(agent_id)

    await bus.emit("heartbeat", phase.to_payload())
    print(f"started: {phase_name} (depends_on: {phase.depends_on})")


async def _phase_update(
    bus: GossipBus,
    phase_name: str,
    tests_passing: Optional[int] = None,
    total_tests: Optional[int] = None,
    agent_id: Optional[str] = None,
) -> None:
    """Update phase test progress."""
    phase = await _get_latest_phase_state(bus, phase_name)
    if not phase:
        print(f"ERROR: Phase '{phase_name}' not found. Run 'phase start' first.")
        return

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


async def _phase_complete(bus: GossipBus, phase_name: str) -> None:
    """Mark phase as complete."""
    phase = await _get_latest_phase_state(bus, phase_name)
    if not phase:
        print(f"ERROR: Phase '{phase_name}' not found.")
        return

    if phase.status == PhaseStatus.COMPLETE:
        print(f"Phase '{phase_name}' is already complete.")
        return

    # Verify blockers are cleared
    if phase.blockers:
        print(
            f"WARNING: Phase '{phase_name}' has blockers: {phase.blockers}. "
            f"Clear them before marking complete."
        )
        return

    phase.status = PhaseStatus.COMPLETE
    phase.completed_at = time.time()
    await bus.emit("heartbeat", phase.to_payload())
    print(f"completed: {phase_name}")


async def _phase_block(bus: GossipBus, phase_name: str, reason: str) -> None:
    """Mark phase as blocked."""
    phase = await _get_latest_phase_state(bus, phase_name)
    if not phase:
        print(f"ERROR: Phase '{phase_name}' not found.")
        return

    phase.status = PhaseStatus.BLOCKED
    if reason not in phase.blockers:
        phase.blockers.append(reason)

    await bus.emit("heartbeat", phase.to_payload())
    print(f"blocked: {phase_name} — {reason}")


async def _phase_unblock(bus: GossipBus, phase_name: str, reason: str) -> None:
    """Unblock a phase by removing a specific blocker."""
    phase = await _get_latest_phase_state(bus, phase_name)
    if not phase:
        print(f"ERROR: Phase '{phase_name}' not found.")
        return

    if reason in phase.blockers:
        phase.blockers.remove(reason)

    if not phase.blockers:
        phase.status = PhaseStatus.IN_PROGRESS
    else:
        phase.status = PhaseStatus.BLOCKED

    await bus.emit("heartbeat", phase.to_payload())
    print(f"unblocked: {phase_name}")


async def _phase_list(bus: GossipBus) -> None:
    """List all phases with status and test progress."""
    phases = await _all_phase_states(bus)
    if not phases:
        print("no phases tracked yet")
        return

    def phase_sort_key(name: str) -> tuple[int, tuple[int, ...], str]:
        """Sort Phase-N[.M[...]] numerically; all other names lexically."""
        parts = name.split("-")
        if len(parts) >= 2 and parts[0] == "Phase":
            try:
                components = tuple(int(n) for n in parts[1].split("."))
                return (0, components, name)
            except (ValueError, IndexError):
                pass
        return (1, (), name)

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


async def _phase_status(bus: GossipBus, phase_name: str) -> None:
    """Show detailed status of a single phase."""
    phase = await _get_latest_phase_state(bus, phase_name)
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


async def _detect_blockers(
    bus: GossipBus, phase: PhaseState, all_phases: dict[str, PhaseState]
) -> list[str]:
    """Detect phases blocking this phase (unfulfilled dependencies)."""
    blocking = []
    for dep in phase.depends_on:
        dep_phase = all_phases.get(dep)
        if not dep_phase or dep_phase.status != PhaseStatus.COMPLETE:
            blocking.append(dep)
    return blocking


async def _workflow_critical_path(bus: GossipBus) -> None:
    """Show critical path (longest dependency chain) and ETA."""
    phases = await _all_phase_states(bus)
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
    print(f"\n=== Critical Path Analysis ===")
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


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


async def _amain(args: argparse.Namespace) -> None:
    bus = GossipBus(canonical_db_path())
    await bus.init_db()
    if args.cmd == "phase":
        if args.subcmd == "list":
            await _phase_list(bus)
        elif args.subcmd == "status":
            await _phase_status(bus, args.phase_name)
        elif args.subcmd == "start":
            depends_on = args.depends_on.split(",") if args.depends_on else None
            await _phase_start(bus, args.phase_name, depends_on, args.agent)
        elif args.subcmd == "update":
            # Parse "50/69" format if provided
            tests_passing = None
            total_tests = None
            if args.tests_passing:
                if "/" in args.tests_passing:
                    tp, tt = args.tests_passing.split("/")
                    tests_passing = int(tp)
                    total_tests = int(tt)
                else:
                    tests_passing = int(args.tests_passing)
            await _phase_update(bus, args.phase_name, tests_passing, total_tests, args.agent)
        elif args.subcmd == "complete":
            await _phase_complete(bus, args.phase_name)
        elif args.subcmd == "block":
            await _phase_block(bus, args.phase_name, args.reason)
        elif args.subcmd == "unblock":
            await _phase_unblock(bus, args.phase_name, args.reason)
    elif args.cmd == "workflow":
        if args.subcmd == "critical-path":
            await _workflow_critical_path(bus)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    # Phase tracking commands
    p_phase = sub.add_parser("phase", help="Manage workflow phases")
    phase_sub = p_phase.add_subparsers(dest="subcmd", required=True)

    phase_sub.add_parser("list", help="List all phases with status")

    p_phase_status = phase_sub.add_parser("status", help="Show detailed phase status")
    p_phase_status.add_argument("phase_name")

    p_phase_start = phase_sub.add_parser("start", help="Start a phase")
    p_phase_start.add_argument("phase_name")
    p_phase_start.add_argument("--depends-on", default=None, help="Comma-separated list of phases this depends on")
    p_phase_start.add_argument("--agent", default=None, help="Agent ID starting this phase")

    p_phase_update = phase_sub.add_parser("update", help="Update phase progress")
    p_phase_update.add_argument("phase_name")
    p_phase_update.add_argument("--tests-passing", default=None, help="Tests passing (e.g. '50/69' or '50')")
    p_phase_update.add_argument("--agent", default=None, help="Agent ID updating progress")

    p_phase_complete = phase_sub.add_parser("complete", help="Mark phase as complete")
    p_phase_complete.add_argument("phase_name")

    p_phase_block = phase_sub.add_parser("block", help="Block a phase")
    p_phase_block.add_argument("phase_name")
    p_phase_block.add_argument("--reason", required=True, help="Reason for blocking")

    p_phase_unblock = phase_sub.add_parser("unblock", help="Unblock a phase")
    p_phase_unblock.add_argument("phase_name")
    p_phase_unblock.add_argument("--reason", required=True, help="Blocker reason to remove")

    # Workflow analysis commands
    p_workflow = sub.add_parser("workflow", help="Workflow analysis")
    workflow_sub = p_workflow.add_subparsers(dest="subcmd", required=True)
    workflow_sub.add_parser("critical-path", help="Show critical path and ETA")

    args = ap.parse_args()
    asyncio.run(_amain(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
