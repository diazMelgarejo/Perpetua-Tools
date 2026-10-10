# WORKSPACE — current task state

**Updated:** 2026-10-10 UTC (P0 ACTIVATED — correction)
**Source:** Orama closure PR #396 (`P0-ACTIVATED-CLOSURE-2026-10-10.md`, receipt 4);
Oramasys #26 and #27 merged; Orama #394 and #395 merged.
**State:** Corrects the entries below that call the P0 plan unpublished and the
Oramasys dependency pre-R3. The P0 plan is published and executed. Oramasys `main`
(`fa6e1e37`) pins Core `4d217f6b9e94e36554a9427198b8c2c4b7febc47`, with a manifest,
a clean-install verifier and a result-file gate; the eight checks passed on that
commit. Orama `main` is `792f4744` plus the closure. P0 is ACTIVATED. Still open
for the operator: branch protection requiring the eight checks, and the action-pinning
decision on Oramasys #27. T1 and later stay gated; the entries below are history.

**Updated:** 2026-10-10 UTC (R4 documentation merged)
**Source:** Orama PR #392 merged to main as `bccc152`; PT PR #432 merged to main as `8cdd492`.
**State:** The R4 reference set, its T0 restoration/baseline record and the PT continuity
memory are merged. The T0 record's restoration source `662a360b` was not resolvable
from the remote at review; its hash table is exact only at the restoration commit
`2fd1e0a`, and later review edits to `PLAN-R4-EXECUTION.md` and `REVIEW-RECORD.md` are not
reflected in it. A draft P0 plan exists, unpublished, awaiting three operator decisions
(pin target, file location, evidence record shape). The production Oramasys dependency
remains pre-R3 Core `04759a5`; P0 is still open and gated. No pin, registry or code
change has been made.

**Updated:** 2026-10-10 UTC (R4 ratification and T0 restoration)
**Source:** Orama PR #392, `docs/v2/references/r4-safety-compatibility-platform-2026-10-10/`
**State:** The operator ratified D-LG-7, its named contracts and D-LG-6 (with
Core #9 `4d217f6` and Oramasys #25 `f4dbf33` as implementation evidence). T0
restored the full R4 reference set from Orama commit `662a360` after a browser
publication truncated ten documents, and refreshed the canonical registry baseline.
The production Oramasys dependency remains pre-R3 Core `04759a5`; P0 must still
requalify and promote that pin. R3 mechanics are merged, but `ainvoke(loaded_state)`
still begins traversal at `START`; it is not durable continuation. Durable HITL,
foreign-provider transport and provider effects remain gated. The backward-clock
high-water rule is fail-closed and its trusted-time recovery procedure is frozen at T0.

**Updated:** 2026-10-09 UTC / 2026-10-10 Asia/Manila (R3 registry and replay review)
**Session record:** `memory/working/R3_REGISTRY_REPLAY_REVIEW_2026-10-10.md`
**State:** Core #9, Orama #390 and Oramasys #25 review fixes published. Core
production pin remains `04759a5`. Two explicit candidate registry profiles qualify
both consumer CI lanes. Durable replay, HITL, production foreign transport and
full upstream replacement remain open; do not treat this audit as their closure.
PT #432 remains the base memory PR, separate from merged PT #431. PT #433 merged into
`docs/r3-lockstep-memory` on 2026-10-09 UTC; its procedures and retrospective are
therefore part of #432's current history, not an open follow-up. No wider feature
completion is claimed.

**Updated:** 2026-10-06 (Sites saga crystallization)
**Session record:** `memory/working/ORAMASYS_SITES_SAGA_CRYSTALLIZATION_2026-09-10_TO_2026-10-06.md`
**State:** PT #429 remains the active leaf for canonical-memory review repairs.
The new record links the memory-integrity incidents, v1 Sites/MCP readiness,
authenticated-plugin evidence, review repairs and future-agent gates. It is
append-only; historical JSONL content was not rewritten. Do not merge before
fresh CodeRabbit/CI review and exact remote-head verification.

**Updated:** 2026-10-02 (PT PR #418 and Orama PR #376 containment cycle)
**Session record:** `memory/working/2026-10-02-containment-cross-repo-cycle.md`
**State:** Local containment hardening is committed and validated. PT retries
containment annotation writes within one cleanup lifecycle and emits a
fail-closed response pair for persistent direct-child annotation failure.
Orama accepts only the two compatible containment pairs plus a true
both-fields-absent legacy response. The in-memory jobs-log cache is deferred
to v2. Publication order: PT PR #418, then Orama PR #376.

**Updated:** 2026-09-30 (Three-day cycle synthesis: PR #404, PR #408, PR #410,
PR #413, Oramasys PR #20)
**Session record:** `memory/working/2026-09-30-three-day-cycle-pr404-pr408-pr410-pr413-synthesis.md`
**Board:** Live SQLite GossipBus (`.state/perpetua_core.db`)
**State:** PR #404 merged into `origin/main` (`8f97473c`). PR #408 (`37427fba`),
PR #410 (`ad4a4136`), and PR #413 (`f1c4dd00`) rebased and stacked cleanly on
main. Supervisor terminal-only replay guard and queued spec recovery verified
green (75/75 tests). Oramasys PR #20 (`3e9818c7`) verified green (218/218
tests). Coordination status and board-authority doctrine were recorded on
GossipBus.

**Updated:** 2026-09-28 (portal facade audit + swarm approval fixes)
**Session record:** `memory/working/PORTAL_FACADE_ORAMA_SWARM_2026-09-28.md`
**State:** Perpetua-Tools draft #404 is reopened on
`cursor/portal-facade-route-jobs-3c54` (`POST /models/route`, job identity
hoist, top-level role fields). Orama portal launch/approval fixes are on
`cursor/portal-swarm-approval-fixes-3c54`. Knowledge search, MCP, and A2A
were not added to Perpetua. Neither pull request is merged.

**Updated:** 2026-09-25 (Cross-repo Gate 4 dialer + migration board
cycle — additive session pointer)
**Session records:**
`memory/working/2026-09-25-cross-repo-gate4-dialer-and-migration-board-cycle.md`
and
`memory/working/MIGRATION_BOARD_RECONCILIATION_AND_CLINEPASS_FIX_2026-09-25.md`
**Agent:** `cline-session-20260907` · **Board:** PT GossipBus
**State:** Six migration reminder rows reconciled closed against verified
lanes; one operator-only row left queued with a runbook; dead-claimant
claim cleared. Cross-repo dialer parity work recorded; nothing merged by
that session.

**Updated:** 2026-09-12 (UTC; live remote re-verification and migration-debt
status renewal)
**Claimed by:** current operator session
**Current authoritative status:** see
`MIGRATION_DEBT_AFRP_CIDF_STATUS_2026-09-12.md`. It records the fresh remote
state: the verified migration/debt deltas are in their respective `main`
branches; do not create replacement PRs without first finding a new, non-empty
delta.

## Current addendum — migration debt, AFRP/CIDF, and Telos (2026-09-12 UTC)

- Orama System `main` contains AFRP PR #356 (`39988ce…`); its root skill already
  activates AFRP and CIDF.  The durable rule is fresh live-authority reads before
  and after a consequential remote action.
- Perpetua Core `main` contains the Telos discovery and required-`graph_id`
  changes (PRs #3/#4).  Agate PR #3 and Oramasys PR #11 are also merged.
- The only material remaining release gate is evidence from the three physical
  hardware-profile canaries; cloud verification cannot substitute for it.
- Historical sections below remain provenance, not live work instructions.

## Current focus

### Hermes-Security/DX close-out + cross-repo verification sweep (2026-09-12, claude-main)

**Queue tasks completed (all 3 claimed and closed):**

| Task | Result |
| ---- | ------ |
| `Hermes-Security-resolve-perp-harness-remote-trust` | Additive `_pt_remote_trusted()` check in `resolve_perp_harness.sh` — real git remote must match the canonical PT URL when one is configured; no-remote case (all 9 pre-existing marker-only fixtures) still accepted. RED confirmed before the fix (reverted source, watched 2 rejection tests genuinely fail). 21/21 tests. |
| `Hermes-DX-hermes-quickstart-doc` | New `references/quickstart.md` — every command's output verified against real script source + a live run, not guessed. |
| `Hermes-DX-hermes-command-card-template` | `openclaw-status/SKILL.md` template applied to `hermes-spawn`/`hermes-delegate`/`hermes-orama`, additive only. Also closed a pre-existing OSSF-1 frontmatter/Boundaries gap on all 3 files (never previously touched since that gate landed). |

All 3 landed on `orama-system` PR #355 (3 logical-batch commits, single push).

**Cross-repo verification sweep (given 3 explicit CodeRabbit fix requests + a handoff report):**

- `oramasys/oramasys#6`, `oramasys/agate#2` (review 5175271655),
  `oramasys/perpetua-core#4` — all 3 requested findings were **already fixed
  and CodeRabbit-confirmed** at each PR's current HEAD before any code was
  touched. Verified via `git log`/API, not re-applied. Lesson recorded
  (`lesson_c660861f37c1`): always check a relayed CodeRabbit finding against
  current HEAD first.
- `oramasys/agate#2` had 2 **genuinely unresolved** findings on a *different*
  review (TS packaging/import-path bug in `hardware_profiles.ts`; a
  `TypeError`-before-`ValueError` gap on `verdict_tier`). A prior session's
  local fix (`f569de2`, unpushed) already addressed both correctly —
  verified 73/73 Python + 4/4 TypeScript tests, then fast-forward-pushed
  directly onto PR #2's branch. PR #2 now `CLEAN`.
- A handoff report claimed push was blocked by a "stale/exposed Git HTTPS
  credential," recommending rotation. **Did not rotate anything** — verified
  first (`gh auth status` showed a valid active keyring token; a dry-run
  push succeeded cleanly). The real cause was almost certainly a shadowed
  `GITHUB_TOKEN` env var in that other session's shell, not a compromised
  credential. Lesson recorded (`lesson_75f7eaa356e9`): verify an auth
  failure directly before ever rotating a credential on another session's
  say-so.
- `oramasys/telos` (`main` @ `b214308`, no open PRs) and `oramasys#8` (closed
  as superseded, confirmed no unique delta) — both confirmed exactly as
  reported by `codex-telos-pr8-remediation`; nothing further needed.

**PT-side status:** PT PR #382 (Gate 4 Half B) and #383 (F01 wrapper resync)
both merged since — the branch/worktree churn from that is expected, not a
problem.

### MigrationDebt-20260911/12 closure (2026-09-12)

> Current session state, recorded by kimi-for-coding during the MigrationDebt program close-out.
> The 2026-08-24 snapshot below is retained for provenance only.

**Board sweep:** all stale MigrationDebt rows on the coordination board were
closed (7 rows terminal-closed); the queue is at zero active claims. Malformed
`depends_on` rows cannot be claimed or failed via the normal queue verbs — they
are terminal-closed via an append-only `task_failed` bus event with
`retry_count=max` (lesson: never delete board rows).

**Publications (4 PRs awaiting operator merge):**

| Area | Branch / PR | State |
| ---- | ----------- | ----- |
| Agate migration-debt close-out | diazMelgarejo/agate-system PR #2 | CI green, mergeable |
| oramasys migration-debt evidence | orama-system PR #7 | open |
| PT evidence foundations | PT `migration/pt-evidence-foundations-20260911` → PR #385 | open; carries this memory commit |
| oramasys outbound decision ledger | orama-system PR #10 | stacked on convergence branch `baf04c1`; suite 105/105 (RED-first) |

**Agate 1B contract review:** PASSED — TypeScript consumer contract review
recorded in the OpenClaw references tree (agate-1b typescript contract review,
2026-09-11).

**Memory this session:** 4 episodic reflections + 8 graduated lessons
(board-row terminal-close, heartbeat cleanup scope vs. queue claims, MiniGraph
Interrupt→interrupted-state conversion, `asyncio.wait_for` empty-string
TimeoutError translation, fresh-worktree-per-packet discipline, RED-first
evidence capture, plus the 2 recorded above from the Hermes-Security/DX
close-out: `lesson_c660861f37c1` and `lesson_75f7eaa356e9`).

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

- [x] P0 Core-pin requalification in Oramasys: ACTIVATED 2026-10-10 (see top entry). Was next after the completed R4
      ratification and T0 restoration/baseline refresh. Then take independently
      reviewed T1/T2 and T3 slices. Approval does not waive any safety gate or
      authorize provider effects.
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
