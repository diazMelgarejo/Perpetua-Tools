"""Legacy/basic claim-board implementation.

The original intra-machine claim/release API (register, agents, claim, release,
list, log) lives here. It is intentionally separate from the queued-task claim
mechanism in task_queue.py — the two share the verb "claim" in the CLI surface
but have distinct semantics.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from orchestrator.gossip_bus import GossipBus  # noqa: E402
from orchestrator.heartbeat_monitor import find_open_claims  # noqa: E402
from orchestrator.coordination.paths import current_worktree_label  # noqa: E402


async def _known_agent_ids(bus: GossipBus) -> set[str]:
    events = await bus.tail(limit=200, event_type="heartbeat")
    return {
        ev["payload"]["agent_id"]
        for ev in events
        if ev["payload"].get("kind") == "agent_register"
    }


async def register_agent(
    bus: GossipBus,
    agent_id: str,
    agent_type: str,
    model: str,
    notes: str,
) -> None:
    """Register an agent on the coordination board."""
    await bus.emit(
        "heartbeat",
        {
            "kind": "agent_register",
            "agent_id": agent_id,
            "agent_type": agent_type,
            "model": model,
            "worktree": current_worktree_label(),
            "notes": notes,
        },
    )
    print(f"registered: {agent_id} ({agent_type}/{model})")


async def list_agents(bus: GossipBus) -> None:
    """List agents registered on the coordination board."""
    events = await bus.tail(limit=200, event_type="heartbeat")
    latest: dict[str, dict] = {}
    for ev in reversed(events):  # oldest first, so later overwrites
        p = ev["payload"]
        if p.get("kind") != "agent_register":
            continue
        latest[p["agent_id"]] = {
            "agent_type": p.get("agent_type", "?"),
            "model": p.get("model", "?"),
            "worktree": p.get("worktree", "?"),
            "notes": p.get("notes", ""),
            "ts": ev["ts"],
        }
    if not latest:
        print("no agents registered yet")
        return
    for agent_id, info in latest.items():
        print(
            f"{agent_id}  [{info['agent_type']}/{info['model']}]  "
            f"({info['worktree']})  {info['notes']}"
        )


async def claim_task(
    bus: GossipBus, agent_id: str, task: str, notes: str
) -> None:
    """Emit a basic claim event for a task."""
    known = await _known_agent_ids(bus)
    if agent_id not in known:
        print(
            f"WARNING: '{agent_id}' has not registered this session — "
            f"run 'register {agent_id} <type> <model>' first so others can identify you. "
            f"Proceeding anyway (registration is advisory, not enforced)."
        )
    await bus.emit(
        "heartbeat",
        {
            "kind": "agent_claim",
            "agent_id": agent_id,
            "task": task,
            "worktree": current_worktree_label(),
            "notes": notes,
        },
    )
    print(f"claimed: {task} by {agent_id} ({current_worktree_label()})")


async def release_task(bus: GossipBus, agent_id: str, task: str) -> None:
    """Emit a basic release event for a task."""
    await bus.emit(
        "heartbeat",
        {
            "kind": "agent_release",
            "agent_id": agent_id,
            "task": task,
            "worktree": current_worktree_label(),
        },
    )
    print(f"released: {task} by {agent_id}")


async def list_claims(bus: GossipBus, task_filter: str | None) -> None:
    """List open basic claims, optionally filtered by task name."""
    # Reuse the unbounded SQL fold from heartbeat_monitor — a size-bounded
    # tail() over the combined heartbeat stream can drop founding agent_claim
    # events once enough unrelated pulse traffic accumulates.
    claims = await find_open_claims(bus)
    if task_filter:
        claims = [claim for claim in claims if claim.get("task") == task_filter]
    if not claims:
        print("no open claims" + (f" for '{task_filter}'" if task_filter else ""))
        return
    for claim in claims:
        task = claim.get("task", "?")
        print(
            f"OPEN  {task}  <- {claim.get('agent_id')}  "
            f"({claim.get('worktree')})  {claim.get('notes', '')}"
        )


async def log_message(bus: GossipBus, agent_id: str, message: str) -> None:
    """Log a note from an agent to the coordination board."""
    await bus.emit(
        "heartbeat",
        {"kind": "agent_note", "agent_id": agent_id, "message": message},
    )
    print("logged")
