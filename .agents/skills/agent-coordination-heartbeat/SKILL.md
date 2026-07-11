---
name: agent-coordination-heartbeat
description: "Operate the agent-coordination heartbeat monitor for multi-agent liveness detection. Activates for: heartbeat monitoring, agent liveness, dead agent detection, cleanup stale claims, heartbeat register/list/check/dashboard/pulse/kill/timeline, agent_coordination.py heartbeat, gossip_bus heartbeat events."
---

# agent-coordination-heartbeat

This is a thin wrapper. The canonical skill lives in orama-system at the path below
(resolve the repo root at runtime — paths are never hardcoded).

- Canonical skill path (orama-system-relative): `bin/orama-system/skills/agent-coordination-heartbeat/SKILL.md`

## Before Use

Before relying on the canonical card, check whether the canonical repository can safely sync:

```bash
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT/bin/orama-system/skills/agent-coordination-heartbeat" 2>/dev/null || cd "$ROOT/../orama-system/bin/orama-system/skills/agent-coordination-heartbeat"
git fetch origin --prune
git status --short --branch
```

If the repo is on a tracking branch and the worktree is clean:

```bash
git pull --ff-only
```

If the worktree is dirty, the branch is not tracking origin, or fast-forward is impossible, do not overwrite local work. Report the drift and read the current canonical card with that caveat.

## Load Canonical Skill

Open and follow `bin/orama-system/skills/agent-coordination-heartbeat/SKILL.md` (relative to the orama-system repo root — sibling checkout `../orama-system` in this workspace layout). Do not copy behavior from this wrapper.

This skill operates `orchestrator/heartbeat_monitor.py` and `scripts/agent_coordination.py` in Perpetua-Tools itself — see `docs/heartbeat-monitoring.md` for the PT-side implementation the canonical skill drives.

## Related Skills

- [`../gossip-bus/SKILL.md`](../gossip-bus/SKILL.md) — heartbeat events are emitted onto the intra-host GossipBus; read it before extending liveness detection across hosts (LAN peer transport).
- [`../agent-methodology/SKILL.md`](../agent-methodology/SKILL.md) — Context Immersion (stage 1) should check heartbeat state before assuming an agent is silent because it's dead.

## Windows UTF-8 Note

On Windows PowerShell, set UTF-8 explicitly before reading or writing skill files:

```powershell
[Console]::InputEncoding=[System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8='1'
```
