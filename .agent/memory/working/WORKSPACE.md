# WORKSPACE — current task state

**Updated:** 2026-08-20 (Standards Convergence, SSRF Defense-in-Depth, Frugality Harmonization)  
**Claimed by:** Agnes (`agnes-antigravity-claude`)  
**Active branch (PT):** `fix/pt-standards-convergence-20260818`  
**Active branch (orama):** `fix/oramasys-standards-convergence-20260818`  

## Current focus

### Historical observability review closure snapshot (2026-08-24)

> Historical snapshot retained for provenance; this is not the current active workspace state.

**Completed on existing PRs:** PT #371 and orama-system #328 are mergeable
with all GitHub checks green. The closure corrected five review-proven gaps:
exact remote tree reconstruction for large memory blobs; stable optional-OTel
module seams in CI; explicit CA-bundle preservation while disabling proxy
inheritance; a POSIX race test that exercises descriptor-relative writes and
fails closed; and an ADR that scopes HTTPS and platform guarantees precisely.
The durable claims and one episodic reflection are in the graduated memory
records dated 2026-08-24.

| Area | Branch / PR | Role |
| ---- | ----------- | ---- |
| **SSRF Layer-2 Docs Shipped** | `fix/oramasys-standards-convergence-20260818` (orama) | **Done (c841ed31)** — `T5-SSRF-orama-layer2-docs-provisional-to-shipped-7a767b81`. Marked Layer 2 as SHIPPED with Split-Identity pool isolation in Docs 32 & SSRF Plan. |
| **Tier-5 Durable Budget Ledger** | `fix/pt-standards-convergence-20260818` (PT) | **Done (0fa78a01, 806690ef)** — `PT-T5-SETTLE-004` (Tier5ExecutionService & runner callbacks) and `PT-T5-API-005` (FastAPI endpoints & status route). 141/141 tests green. |
| **Cross-Repo Tier-5 Parity** | `cross-repo-parity-ORAMA-T5-PARITY-006-8b31eee1` | **Done** — Parity verified against Doc 52 (`52-tier5-frugality-storage-consumer-mapping.md`) and Reference Guide 08. |
| **Reference Guide 08** | `references/08-DOC53-CODERABBIT-REMEDIATION-AND-TIER5-HANDOFF-REPORT-2026-08-20.md` | **Done** — Doc 53 CodeRabbit remediation (7 findings resolved), unpushed review discipline, and Tier-5 handoff state. |
| **Reference Guide 07** | `references/07-MULTI-AGENT-CONVERGENCE-AND-REMEDIATION-REFERENCE-2026-08-20.md` | **Done** — Complete cross-linked reference guide for git remediation doctrines, 199k token cliff, cheapest-tool-first ladder, and GossipBus topology. |
| **Doc 53 CodeRabbit Remediation** | `fix/oramasys-standards-convergence-20260818` (orama) | **Done locally (07860b8d)** — Resolved all 7 CodeRabbit review findings on Doc 53 finance critique with deep research citations. |
| **Session Synthesis (2026-08-20)** | `SESSION_SYNTHESIS_ALPHACLAW_PR29_AND_MASTER_PLAN_2026-08-20.md` | **Done** — Full AlphaClaw PR #29 restore & CodeRabbit CI fix pushed (`70e0f9d8`), master plan synthesized, doc 53 linked, post-tool hook path priority fixed (`c8fac600`). |
| **Standards & Defect Convergence** | `fix/pt-standards-convergence-20260818` (PT), `fix/oramasys-standards-convergence-20260818` (orama) | **Done locally, pending review** — OS-D2..OS-D5 in orama (5152288e); PT-D1, PT-D3, hook fix, and Codex config in PT (1a463d1f). 141/141 targeted tests green, 24/24 SSRF tests green. |
| **Unified Strategic Roadmap** | `UNIFIED_STANDARDS_SSRF_FRUGALITY_CONVERGENCE_2026-08-20.md` | **Consolidated** — 3-layer socket-pinning SSRF defense, Grok 4.6 199k cliff gate, Perplexity Gemini 3.7 Flash frugality engine, MAESTRO/Amplifier governance. |
| **AlphaClaw PR #29 Alignment** | `2026-08-05-001-mcp-consolidation-to-pt` → PR #29 | **Done & Pushed** — Reverted 1caaa6ab narrowing (+512 lines instincts), migrated CI to pnpm, tracked cursor attribution rules (`70e0f9d8`), base updated to `clean/macos-26` (MERGEABLE). |

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
