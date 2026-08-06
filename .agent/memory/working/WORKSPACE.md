# WORKSPACE — current task state

**Updated:** 2026-08-04 (Hermes graft + dispatch taxonomy + gbrain index refresh)  
**Active branch:** `2026-08-03-001-periscope-fts5-tag-lesson`

## Current focus

| Area | Branch / PR | Role |
| ---- | ----------- | ---- |
| **PT (this repo)** | `2026-08-03-001-periscope-fts5-tag-lesson` | periscope FTS5 tag lesson + memory batch |
| **orama graft audit** | `cursor/hermes-openclaw-graft-audit-f559` | Hermes/OpenClaw graft + dispatch taxonomy |
| **Grant HMAC (landed)** | orama #260 + PT #320 merged to `main` | Follow-up on `post-grant-followup-*` branches |

## Read this first

| Priority | Doc |
| -------- | --- |
| 1 | `HERMES_GRAFT_DISPATCH_CORRECTIONS_REPORT_2026-08-04.md` — full corrections report + synthesis |
| 2 | orama `hermes-dispatch-taxonomy.md` — L-H1 / L-PT / L-Fleet canonical |
| 3 | orama `docs/plans/2026-08-03-hermes-openclaw-graft-audit-plan.md` — Phase 1.5 + Wave 0 |

## Hermes dispatch doctrine (2026-08-04)

Three lanes — **never conflate in prose:**

| Lane | What runs | orama examples |
| ---- | --------- | -------------- |
| **L-H1** | Native `delegate_task` child AIAgents | Interactive Hermes session |
| **L-PT** | PT `spawn_hermes_agent()` / `hermes_harness.py` | `hermes-orama`, `hermes-delegate`, `hermes_spawn.sh` |
| **L-Fleet** | `coord_pulse` → `cursor-agent` | Win coder/autoresearcher queues |

`hermes-delegate` is **L-PT**, NOT `delegate_task`.
`REGISTRY.yml` is profile **staging**, not a runtime subagent tree.

## gbrain index (2026-08-04)

| Repo | Pages (approx) | Notes |
| ---- | ---------------- | ----- |
| Perpetua-Tools | 3191 | `gstack-code-078b0b90-f6179f` |
| orama-system | 905 | post-autopilot-stop sync |
| AlphaClaw | 516 | re-synced |
| periscope | 151+ | `oramasys/tools/periscope` refresh |

Autopilot disabled until timeout/embedding issues fixed. Re-enable LaunchAgent when stable.

## Saga docs (background)

| Topic | Path |
| ----- | ---- |
| Grant HMAC MVP | `PR_BODY_GRANT_HMAC_MVP_SAGA_2026-08-02.md` |
| PR222 Hermes staging | `PR222_HERMES_STAGING_SESSION_2026-07-27.md` |
| Guard sync epic | `GUARD_SYNC_EPIC_SAGA_COMPLETION_2026-08-01.md` |

## Operator quick path (Hermes Win)

```powershell
$env:ORAMA_SYSTEM_PATH = "<orama-system>"
$env:PERPETUA_TOOLS_PATH = "<Perpetua-Tools>"
.\scripts\install_coord_pulse.ps1 -Status
.\bin\orama-system\skills\hermes-harness\scripts\coord_pulse.ps1 -DryRun
```

Env must be User-level for scheduled tasks — `.env.local` not loaded by coord_pulse.

## Next

- [ ] Commit orama graft branch (taxonomy + plan Phase 1.5)
- [ ] Wave 0 SKILL lane tags (orama canonical → PT thin sync)
- [ ] periscope FTS5 tag lesson (branch purpose)
- [ ] Re-enable gbrain autopilot after embedding/timeout fix
