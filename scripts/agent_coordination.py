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
from scripts import agent_coordination_core as _core  # noqa: E402
from scripts.agent_coordination_core import (  # noqa: E402
    ClaimResult,
    ClaimSequence,
    ReorderBuffer,
    _buffer_drain,
    _buffer_status,
    _claim_with_seq,
    _get_reorder_buffers,
    _queue_claim,
    _queue_complete,
    _queue_fail,
    _release_claim_with_event,
    _try_atomic_claim,
    canonical_db_path,
    canonical_repo_root,
    main,
)
from orchestrator.heartbeat_monitor import (  # noqa: E402
    cleanup_stale_claims,
    find_agent_heartbeats,
    find_open_claims,
)

# Public legacy command helpers intentionally stay on the retained implementation;
# queue/phase helpers below override only the corrected centralized paths.

_known_agent_ids = _impl._known_agent_ids
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
_workflow_critical_path = _impl._workflow_critical_path
_queue_add = _impl._queue_add
_queue_list = _impl._queue_list
_queue_status = _impl._queue_status


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
    _patched = globals()[_patched_name]
    setattr(_impl, _patched_name, _patched)
    # core.main() is the real CLI entrypoint; legacy-only patches left the
    # broken core implementations live for queue fail/claim/complete.
    setattr(_core, _patched_name, _patched)

if __name__ == "__main__":
    raise SystemExit(main())
