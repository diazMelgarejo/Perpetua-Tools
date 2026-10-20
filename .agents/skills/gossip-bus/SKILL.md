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

Resolve the canonical repository root, in order, using the first candidate
whose `bin/orama-system/skills/gossip-bus/SKILL.md` exists as a file. Never hardcode a workstation path — search
instead. Do not guess or fall back to a different repository's copy if none
resolves.

1. `ORAMA_SYSTEM_ROOT` or `ORAMA_SYSTEM_PATH`, if set.
2. `$(git rev-parse --show-toplevel 2>/dev/null)` — correct only when the
   current working directory is already inside the canonical repo itself.
3. A bounded, marker-based search of the current git repo's parent and
   grandparent directories (depth 2) for a sibling checkout containing `bin/orama-system/skills/gossip-bus/SKILL.md`
   — the same crawl `scripts/git/resolve_sibling_git_repo.sh` performs. If
   the current directory is not inside a git repo, this step has nothing to
   search from and is skipped.

```bash
ROOT=""
for cand in "$ORAMA_SYSTEM_ROOT" "$ORAMA_SYSTEM_PATH" \
    "$(git rev-parse --show-toplevel 2>/dev/null)"; do
  [ -n "$cand" ] && [ -f "$cand/bin/orama-system/skills/gossip-bus/SKILL.md" ] && ROOT="$cand" && break
done
if [ -z "$ROOT" ] && base="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  parent="$(dirname "$base")"
  for d in "$parent"/*/ "$(dirname "$parent")"/*/; do
    [ -f "${d}bin/orama-system/skills/gossip-bus/SKILL.md" ] && ROOT="${d%/}" && break
  done
fi
```

If `$ROOT` is still empty, report the canonical skill as unavailable and ask
for its location only if the task genuinely needs it.

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
