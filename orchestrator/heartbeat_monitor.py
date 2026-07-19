"""orchestrator/heartbeat_monitor.py

Heartbeat monitoring and liveness detection for multi-agent coordination.

Agents periodically emit heartbeat events to track liveness and enable automatic
cleanup of stale claims from dead agents.

Liveness rules:
  - ACTIVE:  last_heartbeat < 60 sec ago
  - IDLE:    60-300 sec (1-5 min ago)
  - STALLED: 300-1800 sec (5-30 min ago)
  - DEAD:    > 1800 sec (> 30 min ago)

Stale claims from DEAD agents are automatically released to unblock other agents.
"""
from __future__ import annotations

import json
import time
from typing import Optional

from orchestrator.gossip_bus import GossipBus


# Liveness thresholds (in seconds)
LIVENESS_ACTIVE_SEC = 60
LIVENESS_IDLE_SEC = 300
LIVENESS_STALLED_SEC = 1800

_AGENT_LIVENESS_KINDS = (
    "agent_register",
    "agent_claim",
    "agent_release",
    "agent_killed",
    "agent_pulse",
)
_AGENT_CLAIM_KINDS = ("agent_claim", "agent_release")


async def _fetch_heartbeat_events(
    bus: GossipBus,
    kinds: tuple[str, ...],
    agent_id: Optional[str] = None,
) -> list[dict]:
    """Fetch agent-lifecycle heartbeat events via SQL, not a bounded tail().

    Unrelated heartbeat traffic (task queue events, phase events, other
    agents' pulses) can push an agent's registration or latest pulse out of a
    size-bounded tail window, making live agents disappear from monitoring or
    open claims vanish from dashboards/cleanup.
    """
    kind_placeholders = ",".join("?" for _ in kinds)
    query = (
        "SELECT id, event_uuid, ts, event_type, payload_json FROM gossip "
        "WHERE event_type = 'heartbeat' "
        f"AND json_extract(payload_json, '$.kind') IN ({kind_placeholders})"
    )
    params: list = list(kinds)
    if agent_id is not None:
        query += " AND json_extract(payload_json, '$.agent_id') = ?"
        params.append(agent_id)
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


def liveness_status(last_activity_ts: float) -> tuple[str, int]:
    """Determine liveness status and time_since_activity in seconds.

    Args:
        last_activity_ts: Unix timestamp of last agent activity.

    Returns:
        Tuple of (status, seconds_since_activity) where status is one of:
        - "ACTIVE":  last_heartbeat < 60 sec ago
        - "IDLE":    60-300 sec ago
        - "STALLED": 300-1800 sec (5-30 min) ago
        - "DEAD":    > 1800 sec (> 30 min) ago
    """
    now = time.time()
    seconds_since = now - last_activity_ts

    if seconds_since < LIVENESS_ACTIVE_SEC:
        return "ACTIVE", int(seconds_since)
    elif seconds_since < LIVENESS_IDLE_SEC:
        return "IDLE", int(seconds_since)
    elif seconds_since < LIVENESS_STALLED_SEC:
        return "STALLED", int(seconds_since)
    else:
        return "DEAD", int(seconds_since)


async def find_agent_heartbeats(
    bus: GossipBus, agent_id: Optional[str] = None
) -> dict[str, dict]:
    """Collect latest heartbeat for each agent (or specific agent if agent_id given).

    Registration begins a new liveness epoch. In particular, a fresh
    ``agent_register`` clears any prior explicit kill marker so a restarted
    process is assessed from its current events rather than remaining DEAD
    forever because of historical state.

    Returns dict mapping agent_id -> {
        'last_heartbeat_ts': float,
        'status': str,  # ACTIVE/IDLE/STALLED/DEAD
        'work_in_progress': str|None,
        'uptime_seconds': int,
        'last_registration': dict,  # latest register event
    }
    """
    events = await _fetch_heartbeat_events(bus, _AGENT_LIVENESS_KINDS, agent_id)

    agent_data: dict[str, dict] = {}
    last_ts_per_agent: dict[str, float] = {}

    for ev in events:
        p = ev["payload"]
        agent = p.get("agent_id")
        if not agent:
            continue
        if agent_id and agent != agent_id:
            continue

        kind = p.get("kind")

        if agent not in agent_data:
            agent_data[agent] = {
                'work_in_progress': None,
                'last_registration': {},
                'registration_ts': None,
                'killed_reason': None,
            }

        # Update last_heartbeat_ts (track most recent for each agent).
        # Events are iterated oldest-first, so every later event for the same
        # agent supersedes the previous timestamp.
        last_ts_per_agent[agent] = ev["ts"]

        if kind == "agent_register":
            agent_data[agent]['last_registration'] = p
            agent_data[agent]['registration_ts'] = ev["ts"]
            # A restart via re-registration is live evidence the agent is
            # no longer dead — clear any prior terminal kill state so it
            # can be scored by liveness again instead of being stuck DEAD.
            agent_data[agent]['killed_reason'] = None
        elif kind == "agent_claim":
            agent_data[agent]['work_in_progress'] = p.get("task")
        elif kind == "agent_release":
            if agent_data[agent].get('work_in_progress') == p.get("task"):
                agent_data[agent]['work_in_progress'] = None
        elif kind == "agent_killed":
            agent_data[agent]['work_in_progress'] = None
            agent_data[agent]['killed_reason'] = p.get("reason", "")
        elif kind == "agent_pulse":
            # A pulse after a kill event is also restart-recovery evidence
            # (docs use pulse, not just register, for recovery).
            agent_data[agent]['killed_reason'] = None

    for agent, data in agent_data.items():
        last_ts = last_ts_per_agent.get(agent, time.time())
        status, _ = liveness_status(last_ts)
        if data.get('killed_reason') is not None:
            status = "DEAD"
        data['status'] = status
        data['last_heartbeat_ts'] = last_ts
        reg_ts = data.get('registration_ts', last_ts)
        data['uptime_seconds'] = int(time.time() - reg_ts) if reg_ts else 0

    return agent_data


async def find_open_claims(bus: GossipBus) -> list[dict]:
    """Find all open (unclosed) task claims."""
    events = await _fetch_heartbeat_events(bus, _AGENT_CLAIM_KINDS)
    state: dict[str, dict] = {}

    for ev in events:
        p = ev["payload"]
        if p.get("kind") not in ("agent_claim", "agent_release"):
            continue
        task = p.get("task", "?")
        if p["kind"] == "agent_claim":
            state[task] = {
                'agent_id': p.get("agent_id"),
                'task': task,
                'claim_ts': ev["ts"],
                'worktree': p.get("worktree"),
                'notes': p.get("notes", ""),
            }
        else:
            state.pop(task, None)

    return list(state.values())


async def cleanup_stale_claims(bus: GossipBus, max_age_seconds: int = 1800) -> list[str]:
    """Auto-release claims held by DEAD agents."""
    agents = await find_agent_heartbeats(bus)
    dead_agents = {aid for aid, data in agents.items() if data['status'] == 'DEAD'}

    open_claims = await find_open_claims(bus)
    stale = [c for c in open_claims if c['agent_id'] in dead_agents]

    released_tasks = []
    for claim in stale:
        await bus.emit(
            "heartbeat",
            {
                "kind": "agent_release",
                "agent_id": claim["agent_id"],
                "task": claim["task"],
                "worktree": claim.get("worktree", "?"),
                "auto_released": True,
                "reason": "agent dead for 30+ min",
            },
        )
        released_tasks.append(claim["task"])

    return released_tasks
