# Hermes graft audit + dispatch taxonomy — full corrections report (2026-08-04)

> **Session:** Cursor agent synthesis after gbrain repair, EXA/FireCrawl research,
> Windows fleet evidence, PT memory recall, graft plan amendments.
> **orama branch:** `cursor/hermes-openclaw-graft-audit-f559` (ephemeral local worktree)
> **PT branch:** `2026-08-03-001-periscope-fts5-tag-lesson`
> **Canonical taxonomy:** orama `bin/orama-system/skills/hermes-harness/references/hermes-dispatch-taxonomy.md`

---

## Executive summary

orama conflated three unrelated dispatch lanes under the label "Hermes subagent."
Native NousResearch Hermes uses `delegate_task` (L-H1). PT uses direct `AIAgent`
scripts (L-PT). Windows fleet uses `coord_pulse` → `cursor-agent` (L-Fleet).
Grafting OpenClaw patterns into `hermes-delegate` without this split will
encode the wrong mental model. Wave 0 (taxonomy + lane tags) must precede
Wave 1 (JSON envelope harmonization).

---

## 1. `/sync-gbrain` operational repair

| Item | Status |
| ---- | ------ |
| Root cause | `gbrain autopilot` held global lock; repeated timeouts + PT pull errors + oversized embeddings |
| Memory sync | OK (15 imported prior session) |
| orama code index | 905 pages after manual sync |
| Autopilot | Disabled via LaunchAgent unload; plist preserved for re-enable |
| Stale lock | Quarantined, not deleted |
| PATH fix | `gbrain` at `~/.bun/bin/gbrain` — detect reported `no-cli` when PATH omitted |
| Re-enable | `launchctl bootstrap gui/$(id -u) "$HOME/Library/LaunchAgents/com.gbrain.autopilot.plist"` |

**Lesson:** Do not run `/sync-gbrain` destructive code stage while autopilot active (#1734).

---

## 2. Windows Hermes — verified commands (not hypothetical)

**Lane L-Fleet** dominates operator runbooks. **L-H1 `delegate_task` not observed** in Win fleet results.

| Category | Actual commands / scripts | Lane |
| -------- | ------------------------- | ---- |
| Bootstrap | `platform\windows\install.ps1`, `install-hermes-harness.ps1` [-RunDoctor] | setup |
| Coord pulse | `scripts\install_coord_pulse.ps1`, `coord_pulse.ps1 -DryRun` | L-Fleet |
| Hermes CLI | `hermes backup`, `hermes doctor`, `hermes profile list` | setup |
| PT harness | `hermes_spawn.sh` start/stop/status (PID file for `python* hermes_harness.py`) | L-PT |
| Fleet dispatch | `cursor-agent --print --model composer-2.5` after `win_job_queue pulse-gate` | L-Fleet |
| Pipeline | `python …/hermes_harness.py` / `hermes-orama` | L-PT |

**Env trap:** Scheduled `coord_pulse` does **not** load `.env.local`. `ORAMA_SYSTEM_PATH` and
`PERPETUA_TOOLS_PATH` must be User-level env vars or explicit exports.

**Evidence files:** `win-self-improve-cycle-007.md`, `coord_pulse.ps1` lines 111–136,
`HERMES_OPENCLAW_STAGING_2026-07-26.md`, fleet merge runbook 2026-07-27.

---

## 3. Hermes / Win plan corrections (PT memory recall)

| Incident | Correction | PT anchor |
| -------- | ---------- | --------- |
| PR #222 body clobber | Append-only restore; aguara delta replaced Phase B scope | `PR222_HERMES_STAGING_SESSION_2026-07-27.md` |
| discover.py platform | `RUNNING_ON_WINDOWS`; Win LM Studio model list | AGENT_LEARNINGS 2026-06-25 |
| coord_pulse `$Args` | `-LanArgs` (PowerShell `$args` collision) | `win-hermes-gateway-review-request-2026-07-08.md` |
| hermes-spawn status | PID file + session allowlist; not `AIAgent.chat` probe | `lesson_9581e059df66` |
| Portable brain | Staged `bin/agents` SOUL ≠ full portable brain export | `lesson_3b2e42ac6ee2` |
| SKILL.md `1.` lists | LINT-010; Hermes reads raw markdown | episodic openclaw-skill-authoring |
| Integrative editing | CIDF corpus-amputation anti-pattern | `lesson_83c53b4aabf1` |

---

## 4. Native Hermes vs orama misconception (EXA + FireCrawl)

### L-H1 — Native `delegate_task` (NousResearch)

- Source: `tools/delegate_tool.py`, [delegation docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation)
- Child `AIAgent`: fresh conversation, own `task_id`, inherited toolsets minus blocklist
- Parent sees delegation call + **final summary only**
- Blocked child tools: `delegate_task`, `clarify`, `memory`, `send_message`, `cronjob`
- Orchestrator children wait for workers before returning

### L-PT — PT `hermes_harness.py`

- `spawn_hermes_agent()` → `AIAgent(...).chat()` with `ephemeral_system_prompt`
- `hermes-delegate`: ThreadPoolExecutor + parallel `spawn_hermes_agent("executor", …)` — **NOT** `delegate_task`
- `hermes_spawn.sh`: tracks PT harness PID, not interactive Hermes CLI session

### L-Fleet — Fleet coordination

- `coord_pulse.ps1` → `win_job_queue.py pulse-gate` → one `cursor-agent` job
- `subagent/win-coder/…` git branches = file inbox + git coordination fiction

### Misconstrual table

| orama claim today | Reality |
| ----------------- | ------- |
| `hermes-delegate` = Hermes subagents | L-PT parallel AIAgent threads |
| `REGISTRY.yml` = runtime subagent tree | Profile staging for `install_hermes_profiles.py` |
| `coord_pulse` = Hermes worker dispatch | L-Fleet cursor-agent |
| Universal envelope = internal Hermes model | orama L2 contract for partner CLIs |
| "Isolated context" in hermes-delegate SKILL | Not delegate_tool isolation semantics |

---

## 5. Graft plan amendments (orama `2026-08-03-hermes-openclaw-graft-audit-plan.md`)

**Added Phase 1.5** + **Wave 0 reorder** on graft branch (uncommitted on worktree):

1. **CREATE** `hermes-dispatch-taxonomy.md`
2. **Wave 0** — lane tags on skills + `REGISTRY.yml` `dispatch_lane` field
3. **SKIP** `recursive-spawn-protocol` → `hermes-delegate` until rename
4. **Wave 1** — JSON envelope on shell entrypoints (all lanes)
5. **NEW** optional `hermes-native-delegate` card (L-H1 docs only, no PT wrapper)

### `bin/agents/` staging amendments

| Role group | `dispatch_lane` | `native_hermes_delegate` |
| ---------- | --------------- | ------------------------ |
| context → crystallizer | `L-PT` | `false` |
| orchestrator | `L-Fleet` (Win default) | `false` |
| coder / win-researcher / autoresearcher | `L-Fleet` | `false` |
| hermes-monitor | `L-H1` (interactive only) | `true` (future skills) |

---

## 6. EXA + FireCrawl sources

| URL | Use |
| --- | --- |
| hermes-agent.nousresearch.com/docs/user-guide/features/delegation | `delegate_task` behavior |
| hermes-agent.nousresearch.com/docs/developer-guide/subagent-lifecycle-api | Plugin launch API |
| github.com/NousResearch/hermes-agent/blob/main/tools/delegate_tool.py | Blocklist + child semantics |

---

## 7. gbrain index status (2026-08-04)

| Repo | Source ID | Pages | Notes |
| ---- | --------- | ----- | ----- |
| orama-system | gstack-code-2159b4b9-595bce | 905 | Refreshed post-autopilot stop |
| Perpetua-Tools | gstack-code-078b0b90-f6179f | 3191 | Synced 2026-08-03 |
| AlphaClaw | gstack-code-alphaclaw-875d5b82 | 516 | Re-synced 2026-08-04 |
| periscope | gstack-code-periscope-6a1806f7 | 151 → refresh in progress | `oramasys/tools/periscope` |

`spawn_hermes_agent` / `delegate_task` code-def on orama index: 0 hits (expected — symbol lives in PT).

---

## 8. Assistant synthesis (reply preserved)

**What we were looking for:** (1) Windows Hermes actual commands, (2) plan correction incidents,
(3) native vs orama dispatch model, (4) graft amendments.

**Outcome:** Three-lane taxonomy is the gating doc. Win fleet runs L-Fleet (cursor-agent), not L-H1.
PT harness is L-PT. Do not graft OpenClaw recursive-spawn into `hermes-delegate` without rename.
Gbrain operational again; index PT/AlphaClaw/periscope refreshed or in progress.

**Next operator actions:**

1. Commit orama graft branch: taxonomy + plan Phase 1.5
2. PT Wave 0: lane tags in `hermes-delegate` / `hermes-orama` SKILL prose (via orama canonical sync)
3. Re-enable gbrain autopilot only after timeout/embedding issues repaired
4. Graduate lessons via `learn.py` (this session batch)

---

## Recall

```bash
python3 .agent/tools/recall.py "Hermes dispatch taxonomy L-H1 L-PT L-Fleet"
python3 .agent/tools/recall.py "hermes-delegate not delegate_task"
python3 .agent/tools/recall.py "coord_pulse cursor-agent"
python3 .agent/tools/recall.py "graft audit wave zero taxonomy"
```

## Cross-links

| Doc | Path |
| --- | ---- |
| PR222 Hermes staging | `PR222_HERMES_STAGING_SESSION_2026-07-27.md` |
| Hermes integration authority | `HERMES_INTEGRATION_AUTHORITY_2026-06-28.md` |
| orama graft plan | orama `docs/plans/2026-08-03-hermes-openclaw-graft-audit-plan.md` |
| Taxonomy (canonical) | orama `hermes-harness/references/hermes-dispatch-taxonomy.md` |
