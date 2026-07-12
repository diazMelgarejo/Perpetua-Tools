---
name: gossip-bus
description: "Operate the GossipBus event bus for multi-agent coordination across both transports: intra-host (same-machine, SQLite FTS5 event log) and inter-host (LAN peer, WS/SSE + file-drop fallback). Activates for: gossip bus, emit event, agent coordination events, cross-machine messaging, mac win peer sync, lan peer channel, peer file drop."
---

# gossip-bus

This is a thin wrapper. The canonical skill lives in orama-system at the path below
(resolve the repo root at runtime — paths are never hardcoded).

- Canonical skill path (orama-system-relative): `bin/orama-system/skills/gossip-bus/SKILL.md`

## Before Use

Before relying on the canonical card, check whether the canonical repository can safely sync:

```bash
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT/bin/orama-system/skills/gossip-bus" 2>/dev/null || cd "$ROOT/../orama-system/bin/orama-system/skills/gossip-bus"
git fetch origin --prune
git status --short --branch
```

If the repo is on a tracking branch and the worktree is clean:

```bash
git pull --ff-only
```

If the worktree is dirty, the branch is not tracking origin, or fast-forward is impossible, do not overwrite local work. Report the drift and read the current canonical card with that caveat.

## Load Canonical Skill

Open and follow `bin/orama-system/skills/gossip-bus/SKILL.md` (relative to the orama-system repo root — sibling checkout `../orama-system` in this workspace layout). Do not copy behavior from this wrapper.

The intra-host transport this skill documents is implemented here in Perpetua-Tools: `orchestrator/gossip_bus.py` (`GossipBus` class — SQLite FTS5 event log). The inter-host LAN peer transport lives in orama-system (`src/orama_system/lan_peer_channel.py`, `lan_peer_files.py`).

## Related Skills

- [`../agent-coordination-heartbeat/SKILL.md`](../agent-coordination-heartbeat/SKILL.md) — heartbeats are emitted onto this same intra-host GossipBus.
- [`../agent-methodology/SKILL.md`](../agent-methodology/SKILL.md) — Context Immersion (stage 1) should check GossipBus/LAN peer state before assuming an agent is silent because it's dead.

## Windows UTF-8 Note

On Windows PowerShell, set UTF-8 explicitly before reading or writing skill files:

```powershell
[Console]::InputEncoding=[System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8='1'
```
