from __future__ import annotations

import time

from orchestrator.gossip_bus import GossipBus
from orchestrator.heartbeat_monitor import (
    cleanup_stale_claims,
    find_agent_heartbeats,
    find_open_claims,
)
from orchestrator.coordination.paths import current_worktree_label


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
    print(f"Worktree: {data.get('current_worktree') or registration.get('worktree', '?')}")
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


_TIMELINE_STATUS_LABELS = {
    "agent_register": "REGISTERED",
    "agent_claim": "CLAIMED",
    "agent_release": "RELEASED",
}


async def _heartbeat_timeline(bus: GossipBus, agent_id: str, hours: int) -> None:
    cutoff = time.time() - hours * 3600
    events = await bus.tail(limit=1000, event_type="heartbeat")
    print(f"Timeline for {agent_id}:")
    for event in reversed(events):
        payload = event["payload"]
        if event["ts"] < cutoff or payload.get("agent_id") != agent_id:
            continue
        kind = payload.get("kind", "?")
        status = _TIMELINE_STATUS_LABELS.get(kind, kind)
        print(
            f"{int(event['ts'])} {status} "
            f"{payload.get('task') or payload.get('reason') or ''}"
        )


async def _heartbeat_cleanup(bus: GossipBus) -> None:
    released = await cleanup_stale_claims(bus)
    print("released: " + ", ".join(released) if released else "no stale claims released")
