# 2026-06-22 — The gbrain self-heal journey (problem → root cause → durable fix)

> Narrative companion to the atomic records: PT `.agent/memory/episodic/AGENT_LEARNINGS.jsonl`
> (skill `session-2026-06-22`, steps `diagnose-recurring-rot` + `automate-self-heal`), PT
> `.agent` lessons `36f924c161e1` / `d0d49b68ab24`, and the canonical procedure in
> [`orama-system/bin/orama-system/gstack/SKILL.md` §GBrain Ops](../../orama-system/bin/orama-system/gstack/SKILL.md).
> The script itself lives canonically at
> [`orama-system/scripts/gbrain/gbrain-selfheal.sh`](../../orama-system/scripts/gbrain/gbrain-selfheal.sh)
> (PT references it; not duplicated, per zero-fragmentation).

## The trigger

"Fix Gbrain sync — I have turned off autopilot, check?" → it was still running. Then: "Sync
BLOCKED at 8b86a874: 62 file(s) failed to parse." Then the real question: **"we had this
conversation last time but we need to 'fix' it again? why? how can we make it durable?"**

## The journey, step by step

1. **Checked autopilot — still alive.** PID 872 `gbrain autopilot --repo .`, PPID 1. It's a
   launchd agent (`com.gbrain.autopilot`, `KeepAlive=true`), so the user's "turn it off"
   (a kill) couldn't stick — only `launchctl unload -w` works.
2. **Diagnosed via `run_doctor`.** Score 50, `unhealthy`: **204 unacked parse failures**,
   `sync_freshness` FAIL (sources 16–29d stale), `multi_source_drift` (4477 misrouted slugs).
3. **Unblocked the immediate jam.** `gbrain sync --skip-failed` → "Acknowledged 204
   pre-existing failure(s)." Score 50→55. But a bare sync from the non-git workspace root
   (`$OPENCLAW_ROOT`, not a git repo) refused further ("Not a git repository") — gotcha #1.
4. **Mapped source → path.** The stale sources pointed at **OLD moved paths** (the pre-`~/code`
   synced-`Documents/` tree) — superseded duplicates spawned by this era's repo moves
   (iCloud-escape, →`~/code`). The skill's own table showed they were quarantined
   **2026-06-18 but left "pending removal"** — never finished. That deferral was the recurrence.
5. **Found the real home.** The user pointed out `orama-system/bin/orama-system/gstack/SKILL.md`
   already had §GBrain Ops (§2/§5/§6) — I'd missed it by searching only `skills/`. Lesson:
   extend the existing orama-owned skill, don't reinvent.
6. **Archived the 4 orphans** (reversible soft-delete); defs exported to a dated dir under
   `~/repo-backups/gbrain-stale-quarantine-20260622/orphan-sources.json`.
7. **Built the durable fix:** `gbrain-selfheal.sh` — idempotent guard that acks failures,
   refreshes the live sources with `--repo "<path>" --source <id>`, reports orphans/autopilot
   misconfig, and never auto-deletes; skips entirely if `gbrain_local_status != ok`. Wired into
   `start.sh` backgrounded so it never blocks startup. Extended `gstack/SKILL.md` with §7.
8. **Left autopilot unloaded** — per the skill's own §6, a single `--repo .` autopilot is the
   bug in a multi-repo workspace; the self-heal script is the replacement.
9. **Result:** `gbrain doctor` 50 → **95**. The only remaining flag is the archived
   `periscope-src` (expected noise; re-add from its `~/code/oramasys/tools/periscope` path if needed).

## Why it kept recurring (the durable insight)

The fixes lived only as **knowledge**, and removal steps were **deferred**. Two regenerating
causes: a launchd daemon that silently jams on unacked failures, and repo moves that spawn new
per-path sources while orphaning the old ones. Durability came from converting the manual fixes
into an **idempotent self-heal wired into startup**, and from **completing the archival in the
same pass** rather than leaving "pending removal."

## Gotchas worth keeping

- Per-source sync must `cd` into the repo (or pass `--repo "<path>"`) **and** `--source <id>`;
  a bare `gbrain sync` from a non-git cwd only acks failures then refuses.
- Non-interactive shells need `set -a; source ~/.gbrain/.env; set +a` for the DB URL.
- `gbrain autopilot` is launchd `KeepAlive=true` — stop with `launchctl unload -w`, never a kill.
