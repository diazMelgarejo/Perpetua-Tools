---
name: gossip-bus
description: "Operate the GossipBus event bus for multi-agent coordination across both transports: intra-host (same-machine, SQLite FTS5 event log) and inter-host (LAN peer, WS/SSE + file-drop fallback). Activates for: gossip bus, emit event, agent coordination events, cross-machine messaging, mac win peer sync, lan peer channel, peer file drop."
---

# gossip-bus

This is a thin wrapper. The canonical skill lives in the orama-system repo at
the path below. Resolution is read-only and marker-verified — never fetch,
pull, prune, install, register, or modify anything while loading a skill.

- Canonical skill path (repo-relative): `bin/orama-system/skills/gossip-bus/SKILL.md`

## Before Use

Resolve the canonical repository root with the shared resolver
`scripts/resolve_orama_root.sh` (a thin wrapper over
`scripts/git/resolve_sibling_git_repo.sh`; do not re-implement discovery here). It:

1. honors `ORAMA_SYSTEM_PATH`, `ORAMA_SYSTEM_ROOT` or `ORAMA_ROOT` and **fails closed** when one is set
   but is not a valid, non-symlinked orama-system Git root (it never falls through to a crawl);
2. otherwise crawls two levels below this repo's parent and grandparent for marker-valid,
   non-symlinked Git roots; and
3. errors on zero or on more than one candidate, naming every candidate it found.

If the current directory is already inside the canonical repo, that repo is used (only when no override
is set). After resolution the skill file itself must exist, so a checkout that has the orama-system marker
but not this skill is rejected. Never hardcode a workstation path.

```bash
ROOT=""
PT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "${ORAMA_SYSTEM_PATH:-}${ORAMA_SYSTEM_ROOT:-}${ORAMA_ROOT:-}" ] \
    && [ -f "$PT_ROOT/bin/orama-system/skills/gossip-bus/SKILL.md" ]; then
  ROOT="$PT_ROOT"
elif [ -f "$PT_ROOT/scripts/resolve_orama_root.sh" ]; then
  ROOT="$( . "$PT_ROOT/scripts/resolve_orama_root.sh" && resolve_orama_root )" || ROOT=""
fi
[ -f "$ROOT/bin/orama-system/skills/gossip-bus/SKILL.md" ] || ROOT=""
```

The resolver runs in a subshell, so its shell options never leak into your session. If `$ROOT` is empty,
report the canonical skill as unavailable together with the resolver's error, and ask for its location
only if the task genuinely needs it. Do not guess or fall back to another repository's copy.

## Load Canonical Skill

Read `$ROOT/bin/orama-system/skills/gossip-bus/SKILL.md` and follow it (`$ROOT` is the root resolved under Before Use; the path is relative to the orama-system repo root — sibling checkout `../orama-system` in this workspace layout). Do not copy behavior from this wrapper.

The intra-host transport this skill documents is implemented here in Perpetua-Tools: `orchestrator/gossip_bus.py` (`GossipBus` class — SQLite FTS5 event log). The inter-host LAN peer transport lives in orama-system (`src/orama_system/lan_peer_channel.py`, `lan_peer_files.py`).

## Related Skills

- [`../agent-coordination-heartbeat/SKILL.md`](../agent-coordination-heartbeat/SKILL.md) — heartbeats are emitted onto this same intra-host GossipBus.
- [`../agent-methodology/SKILL.md`](../agent-methodology/SKILL.md) — Context Immersion (stage 1) should check GossipBus/LAN peer state before assuming an agent is silent because it's dead.

## Refresh (explicit maintenance only — never a side effect of loading)

Synchronizing the canonical repo is a separate, explicitly authorized action.
When asked to refresh it:

```bash
cd "$ROOT/bin/orama-system/skills/gossip-bus"
git fetch origin --prune
git status --short --branch
```

If the repo is on a tracking branch and the worktree is clean:

```bash
git pull --ff-only
```

If the worktree is dirty, the branch is not tracking origin, or fast-forward is impossible, do not overwrite local work. Report the drift and read the current canonical card with that caveat.

## Windows UTF-8 Note

On Windows PowerShell, set UTF-8 explicitly before reading or writing skill files:

```powershell
[Console]::InputEncoding=[System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8='1'
```
