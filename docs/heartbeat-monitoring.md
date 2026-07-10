# Heartbeat Monitoring & Liveness Detection

## Overview

Heartbeat monitoring tracks agent liveness and enables automatic cleanup of stale claims from dead agents. Agents periodically emit heartbeat events that record their status, allowing the system to detect hung, stalled, or dead agents and automatically release claims to unblock other agents.

## Liveness States

Agents transition through four liveness states based on time since last activity:

| State | Time Since Activity | Meaning |
|-------|-------------------|---------|
| **ACTIVE** | < 60 sec | Agent is actively working |
| **IDLE** | 60-300 sec (1-5 min) | Agent is registered but not working |
| **STALLED** | 300-1800 sec (5-30 min) | Agent may be hung; needs manual review |
| **DEAD** | > 1800 sec (> 30 min) | Agent is presumed dead; auto-cleanup triggers |

## Core Functions

### `liveness_status(last_activity_ts: float) -> tuple[str, int]`

Determines the liveness status of an agent based on the last activity timestamp.

**Returns:** `(status, seconds_since_activity)` where status is one of: `ACTIVE`, `IDLE`, `STALLED`, `DEAD`.

```python
from orchestrator.heartbeat_monitor import liveness_status
import time

last_activity = time.time() - 150  # 2.5 minutes ago
status, seconds_since = liveness_status(last_activity)
print(f"Agent status: {status} ({seconds_since}s ago)")  # IDLE (150s ago)
```

### `find_agent_heartbeats(bus: GossipBus, agent_id: Optional[str] = None) -> dict[str, dict]`

Collects the latest heartbeat for each agent (or a specific agent if `agent_id` is provided).

**Returns:** Dict mapping `agent_id` to heartbeat data:
- `last_heartbeat_ts`: Unix timestamp of last activity
- `status`: Current liveness status (ACTIVE/IDLE/STALLED/DEAD)
- `work_in_progress`: Current task_id (if any)
- `uptime_seconds`: Seconds since registration
- `last_registration`: Latest register event payload

```python
agents = await find_agent_heartbeats(bus)
for agent_id, data in agents.items():
    print(f"{agent_id}: {data['status']}")
```

### `find_open_claims(bus: GossipBus) -> list[dict]`

Finds all open (unreleased) task claims.

**Returns:** List of claim dicts with `agent_id`, `task`, `claim_ts`, `worktree`, `notes`.

```python
claims = await find_open_claims(bus)
for claim in claims:
    print(f"Task '{claim['task']}' claimed by {claim['agent_id']}")
```

### `cleanup_stale_claims(bus: GossipBus, max_age_seconds: int = 1800) -> list[str]`

Auto-releases claims held by DEAD agents. This is called automatically when an agent is marked dead.

**Returns:** List of released task IDs.

```python
released = await cleanup_stale_claims(bus)
if released:
    print(f"Auto-released tasks: {', '.join(released)}")
```

## CLI Commands

### Register Heartbeat

Emit a heartbeat pulse for the current agent:

```bash
python3 scripts/agent_coordination.py heartbeat register <agent_id>
```

### List Agents

Show all tracked agents and their liveness status:

```bash
python3 scripts/agent_coordination.py heartbeat list

# Output:
# ACTIVE:
#   kimi-g1              claude-3.5-sonnet    [Phase-5 banner]
#
# IDLE:
#   cline-g2             gpt-4                
#
# STALLED:
#   older-agent-1        claude-3              (ALERT: may be hung)
```

### Check Agent

Show detailed info for a specific agent:

```bash
python3 scripts/agent_coordination.py heartbeat check <agent_id>

# Output:
# Agent: kimi-g1
#   Status:        ACTIVE
#   Type:          llm-agent
#   Model:         claude-3.5-sonnet
#   Worktree:      worktree-phase-1@/path
#   Uptime:        1234s
#   Last activity: 30s ago
#   Current task:  phase-5-testing
#   Notes:         Phase 5 banner generation
```

### Dashboard

Show comprehensive health dashboard with alerts:

```bash
python3 scripts/agent_coordination.py heartbeat dashboard

# Output:
# AGENT HEALTH (as of 2026-07-11 12:15:23 UTC):
#
# ACTIVE (last 60 sec):
#   kimi-g1              claude-3.5-sonnet    0m 42s
#
# IDLE (60-300 sec):
#   cline-g2             gpt-4                2m 18s
#
# STALLED (5-30 min):
#   older-agent-1        claude-3             8m 15s
#
# DEAD (30+ min):
#   ancient-agent        claude-2             47m 00s
#
# === ALERTS ===
# 1 STALLED agent(s) (may need manual intervention)
# 1 DEAD agent(s) (claims may be auto-released)
```

### Pulse (Force Alive)

Manually emit a heartbeat to mark an agent as alive (for restart recovery):

```bash
python3 scripts/agent_coordination.py heartbeat pulse <agent_id>
```

### Kill Agent

Manually mark an agent as dead and trigger auto-cleanup:

```bash
python3 scripts/agent_coordination.py heartbeat kill <agent_id> --reason "hung on Phase-4"
```

### Timeline

Show activity timeline for an agent:

```bash
python3 scripts/agent_coordination.py heartbeat timeline <agent_id> --hours 24

# Output:
# Timeline for agent-1 (last 24h):
#
# 2026-07-11 12:15:23  REGISTERED  [llm-agent/claude-3.5-sonnet]
# 2026-07-11 12:16:45  CLAIMED     phase-5-testing
# 2026-07-11 14:30:22  RELEASED    phase-5-testing
# 2026-07-11 14:31:00  PULSE       (heartbeat)
```

## Integration with Task Claims

When claiming a task, agents should emit a heartbeat as part of the claim event:

```bash
# Register
python3 scripts/agent_coordination.py register kimi-g1 llm-agent claude-3.5-sonnet "Phase 5"

# Claim task (updates heartbeat automatically)
python3 scripts/agent_coordination.py claim kimi-g1 phase-5-testing "working on banner generation"

# Emit periodic pulses while working (every 60-120 seconds)
python3 scripts/agent_coordination.py heartbeat pulse kimi-g1

# Release when done
python3 scripts/agent_coordination.py release kimi-g1 phase-5-testing
```

## Auto-Cleanup Trigger

When an agent is marked DEAD (> 30 min no activity), the system automatically:

1. Finds all open claims held by that agent
2. Emits release events for each stale claim
3. Prints a list of released tasks

This prevents hung agents from blocking other agents indefinitely.

## Implementation Details

### Event Types

Heartbeat events use the `heartbeat` event type and `kind` field:

- `agent_register`: Initial registration with type, model, worktree
- `agent_claim`: Claim a task (updates `work_in_progress`)
- `agent_release`: Release a task
- `agent_pulse`: Periodic heartbeat (keeps agent ACTIVE)
- `agent_killed`: Manual death marker (triggers cleanup)
- `agent_note`: Freeform status message

### Time Thresholds

Configured as constants in `orchestrator/heartbeat_monitor.py`:

```python
LIVENESS_ACTIVE_SEC = 60      # < 60s: ACTIVE
LIVENESS_IDLE_SEC = 300       # < 300s: IDLE (from ACTIVE boundary)
LIVENESS_STALLED_SEC = 1800   # < 1800s: STALLED (from IDLE boundary)
# > 1800s: DEAD
```

Adjust these if coordination requires faster/slower detection.

### Query Limits

Heartbeat analysis queries up to 500 recent heartbeat events. For long-running orchestrations with many agents, this may miss history older than the limit. Monitor via `heartbeat list` or `heartbeat dashboard` periodically.

## Testing

Run unit and integration tests:

```bash
python3 -m pytest tests/test_agent_coordination_heartbeat.py -v
```

Tests cover:
- Liveness state transitions at boundaries
- Agent heartbeat tracking (single, multiple, filtering)
- Open claim detection and release
- Stale claim auto-cleanup
- Edge cases (pulse extends lifespan, killed agent)

All 20 tests pass without external dependencies (no Ollama, network, etc.).

## Next Steps

1. **Periodic Pulse Script**: Create a daemon that emits pulses every 60s for a running agent
2. **Dashboard Alerts**: Integrate with external alerting (Slack, email) for STALLED/DEAD agents
3. **Configurable Thresholds**: Support per-phase or per-agent liveness windows
4. **Historical Analytics**: Archive heartbeat history for post-mortem analysis of hung agents

## See Also

- [`orchestrator/gossip_bus.py`](../orchestrator/gossip_bus.py) — GossipBus event log
- [`orchestrator/heartbeat_monitor.py`](../orchestrator/heartbeat_monitor.py) — Core implementation
- [`scripts/agent_coordination.py`](../scripts/agent_coordination.py) — CLI interface
- [`tests/test_agent_coordination_heartbeat.py`](../tests/test_agent_coordination_heartbeat.py) — Tests
