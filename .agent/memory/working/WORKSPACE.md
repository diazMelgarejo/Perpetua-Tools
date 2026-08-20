# WORKSPACE — current task state

**Updated:** 2026-08-20 (Standards Convergence, SSRF Defense-in-Depth, Frugality Harmonization)  
**Claimed by:** Agnes (`agnes-antigravity-claude`)  
**Active branch (PT):** `fix/pt-standards-convergence-20260818`  
**Active branch (orama):** `fix/oramasys-standards-convergence-20260818`  

## Current focus

| Area | Branch / PR | Role |
| ---- | ----------- | ---- |
| **Standards & Defect Convergence** | `fix/pt-standards-convergence-20260818` (PT), `fix/oramasys-standards-convergence-20260818` (orama) | **Done locally, pending review** — OS-D2, OS-D4, OS-D5, OS-D3 in orama; PT-D1, PT-D3 in PT. All 73/73 and 65/65 tests green. |
| **Unified Strategic Roadmap** | `UNIFIED_STANDARDS_SSRF_FRUGALITY_CONVERGENCE_2026-08-20.md` | **Consolidated** — 3-layer socket-pinning SSRF defense, Grok 4.6 199k cliff gate, Perplexity Gemini 3.7 Flash frugality engine, MAESTRO/Amplifier governance. |
| **Hermes Wave 0 (taxonomy + lane tags)** | orama graft branches (`cursor/hermes-openclaw-graft-audit-f559`, `2026-08-05-002-hermes-graft-plan-reference-fix`) | **Done, pending review** — L-H1 / L-PT / L-Fleet taxonomy + lane tags; chronology **precedes** Wave 1 |
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
| ECC Overlay & Tier-5 Harmonization | `ECC_OVERLAY_HARMONIZATION_AND_TIER5_STATUS_2026-08-17.md` |
| PR354 Memory Union Analysis | `PR354_MEMORY_UNION_ANALYSIS_2026-08-15.md` |
| Tier-5 Apprentice Stacks & Lineage | `TIER5_PIPELINE_AND_APPRENTICE_STACKS_2026-08-15.md` |
| Apprentice-01 Voice Memory | `2026-08-10-oramasys-apprentice-01-voice-memory.md` |
| Apprentice-02 Voice Memory | `2026-08-10-oramasys-apprentice-02-voice-memory.md` |
| Interrupted Reasoning Recovery | `2026-08-10-interrupted-reasoning-branch-recovery.md` |
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

- [ ] Operator review/merge orama Hermes graft branches (Wave 0 taxonomy +
      Wave 1–2 envelope — both **done, pending review**, not released)
- [ ] Push orama `2026-08-05-002-hermes-graft-plan-reference-fix` + open/update
      PR when operator authorizes (4 local commits, 38/38 tests)
- [ ] Wave 1 follow-ups (post-review): `hermes-orama` buffered `--json`;
      Windows PowerShell adapter coverage or explicit exclusion; Win Hermes
      partner canary self-experiment
- [ ] Appendix C build (task API, fleet mgr, verifier, scheduler, recursive,
      HITL) — v2.1++ / oramasys migration
- [ ] PT thin sync of Wave 0 SKILL lane tags after orama graft PR review
      (Wave 0 core work done on orama side)
- [ ] Re-enable gbrain autopilot after embedding/timeout fix
