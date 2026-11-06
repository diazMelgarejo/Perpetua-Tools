# C1 Perpetua-Tools documentation dispositions (2026-11-06)

Closure row C1, Perpetua-Tools portion. Canonical register: Orama
`docs/v2/MASTER-CLOSURE-AND-IMPLEMENTATION-PLAN-2026-11-06.md`. Input: the
November 6 architecture review (§4.5, the coordination-path part of §5, and
§7.5). Its findings were treated as claims and checked against this
repository's base revision (`e4cd20e`, PT `main` after #480). Historical bodies
are preserved; fixes are narrow dated notes only.

Dispositions: **fixed** (corrected here or by an earlier merge),
**superseded**, **historical** (correct as a dated record; no change),
**rejected** (the claim does not hold), **blocked** (needs an owner decision or
evidence not available here). "Not verified" means the check was not possible
from this checkout.

## Cross-document findings

| # | Finding | Disposition | Evidence |
| --- | --- | --- | --- |
| 1 | `PHASE-0-MASTER-PLAN-2026-07-27.md` Mesh Phase D names `perpetua-core` as v2 authority (review cited :117; at base, §4 line 122 and §12.3 line 335) | **fixed** | Dated status note under the existing 2026-11-06 banner: superseded by ADR 62 (Telos endpoint/address, Phylax principal/capability). The 2026-11-06 banner from #480 covered only the coordination owner. |
| 2 | July 17 consolidation plan: "Part 2 remains deferred to v2 oramasys" | **fixed (routed)** | Dated note: Part 2 landed in PT (`liveness.py` exists); v2 is a separate parity migration under doc 68 §1/§11 |
| 3 | August 23 Part 3 draft open; no `daemon.py` | **superseded** | Existing ratification banner (#480) plus a new scope note mapping §2–§5 to master-plan items 1 and 4–7 and D1/D2 |
| 4 | `docs/coordination/README.md` lists `liveness.py` as TODO | **fixed** | Dated note: landed. The `phases.py` LAN-gap TODO is also historical: `phases.py` builds no bus and receives `make_gossip_bus` from `cli.py`. |
| 5 | `PHASE-0-MASTER-PLAN:201` (base) heartbeat-daemon design "DEFERRED v2" | **fixed** | Same dated note: D1 keeps PT manual; automatic release is v2 Controller only |
| 6 | `.agent/memory/semantic/LESSONS.md:138` (`lesson_f66a1b3f7cc5`) not struck through | **fixed** (by #480) | Now line 151: struck through with `superseded_by=lesson_3cfe09c6fa49`. No memory edit made here. |
| 7 | `PT_UNBUNDLING_MIGRATION_MAP_2026-08-29.md` §2/§7/§8 owner names omit Telos, Phylax and the Controller | **fixed** (by #480) | The "2026-11-06 additive ownership reconciliation" section names D-LG-1/5 (Core GraphSpec), ADR 62 (Telos and Phylax) and the internal Oramasys Controller. Its last open sentence (Part 3 daemon needs a scope decision) is answered by D1, recorded in the Part 3 plan banner. The memory file was not edited. |
| 8 | PT `README.md:3,16,41`, `docs/REPO-CROSS-REFERENCE.md:12`, `docs/MIGRATION.md:38` self-description goes beyond the maps' "scoped evidence" | **blocked** | Positioning statements in live entry docs need an owner decision; the maps remain the scoped authority. Not changed here. |
| 9 | PT README layer table omits Perpetua Core, Telos, Phylax, Agate and v2 destinations | **blocked** | Same owner decision as #8 |
| 10 | "Perplexity-Tools" appears only as history | **historical** | Review states no broken links; nothing to change |

## Plan status lines (review §7.5)

| Plan | Review status | Disposition | Evidence |
| --- | --- | --- | --- |
| `.agent/memory/working/2026-07-16-agentic-stack-upstream-contribution-plan.md` | open, plan only | **historical** | Self-described "not executed"; no claim to correct |
| `.agent/…/PR_BODY_ANTI_CLOBBER_ENFORCEMENT_PLAN.md` | complete | **historical** | — |
| `.agent/…/SESSION_SYNTHESIS_ALPHACLAW_PR29…2026-08-20.md` | historical | **historical** | Session record |
| `.agent/…/portal-facade-review-and-plan.md` | complete | **historical** | The `perplexity-api` path is a historical mention |
| `docs/2026-05-31-tri-repo-alignment-completion-plan.md` | header "active resume anchor" | **fixed (routed)** | Dated note: not the active anchor; Phase 0 master plan (line 204 at base) records it done/deferred; points to the closure handoff |
| `docs/next/2026-07-17-coordination-module-consolidation-plan.md` | "Part 2 → v2" stale | **fixed (routed)** | Row 2 |
| `docs/next/2026-07-24-plan-windows-acl-alphaclaw-tls-proxy.md` | partial | **historical** | Phase 0 master plan (line 203 at base) records it done (#278); not re-verified |
| `docs/next/2026-07-27-coordination-phase-0f-part2-autoplan.plan.md` | likely done | **fixed (routed)** | Dated note: `liveness.py` extraction done; remaining 0F rows route to the coordination README |
| `docs/next/2026-08-23-coordination-consolidation-part3-plan.md` | open draft | **superseded** | Row 3 |
| `phase-0/2026-07-11-STM-integration-plan` | done | **historical** | — |
| `phase-0/2026-07-12-autoplan-final-approval-gate` | done | **historical** | — |
| `phase-0/2026-07-12-stm-next-increment-plan` | closed | **historical** | — |
| `phase-0/2026-07-12-stm-remediation-plan` | done | **historical** | — |
| `phase-0/PATTERN-MULTIAGENT-EXECUTION-PLAN` | reference | **historical** | — |
| `phase-0/PHASE-0-MASTER-PLAN-2026-07-27` | wrong v2 owner | **fixed** | Row 1 |
| `docs/plan-review-migration-plan-3` | historical | **historical** | — |
| `docs/plans/2026-05-31-gate2-implementation-plan.md` | "RESOLVED" banner vs "in progress" | **fixed (routed)** | Dated note. The banner's SHA does not resolve after the history rewrite; `stopServer` exists in `packages/alphaclaw-adapter/src/index.js`. |
| `docs/plans/2026-05-31-track-bc-claude-desktop-mcpb.md` | merge not verified | **historical** | `vendor/Claude-Desktop-LLM` is a submodule in `.gitmodules` on `main`, so the content is present; the branch merge itself was not verified |
| `docs/plans/2026-07-12-pr206-multi-agent-remediation-completion-plan.md` | PR-scoped | **historical** | Not verified |
| `docs/plans/2026-07-13-branch-local-pattern-remediation-card.md` | says "active" | **historical** | A reference card; "active" may still be correct. Not verified; not changed. |
| `docs/plans/2026-07-13-pr211-lan-gossip-progress.md` | says "review-ready" | **fixed (routed)** | Dated note: bridge and tests are on `main`; the PR merge itself is not verified |
| `docs/plans/2026-07-14-final-remedy-primary-plan.md` | historical | **historical** | — |
| `docs/plans/2026-07-22-rogue-commits-analysis-feedback.md` | historical | **historical** | — |
| `docs/plans/2026-07-31-ci-workflow-consolidation-plan.md` | partial | **historical** | Self-described partial; not re-verified |
| `docs/plans/2026-08-21-pt-endpoint-hardening-checklists.md` | 2 of ~40 boxes ticked; files exist | **fixed** | Dated note: boxes not a current backlog; both files exist; v1-only per ADR 62. Current count: 2 ticked, 53 unticked. |
| `docs/plans/2026-10-09-minigraph-compatibility-evidence-plan.md` | current | **historical** | No change |
| `docs/plans/autoresearch-orchestrator-adoption` | "canonical" | **blocked** | Not verified; needs the owner's current autoresearch status |
| `docs/references/coordination-consolidation-plan-review-2026-07-18.md` | evidence | **historical** | — |
| `docs/references/phase0-and-orama-open-work-closure-plan-2026-07-18.md` | planning handoff | **historical** | Authorizes nothing |
| `docs/superpowers/plans/2026-05-20-codex-review-remaining-fixes` | resolved | **historical** | — |
| `docs/superpowers/plans/2026-08-14-tier5-durable-budget-ledger` | implemented | **historical** | `orchestrator/tier5_budget.py` exists |
| `docs/superpowers/plans/2026-09-03-agent-handoff-validation-v1` | implemented | **historical** | `orchestrator/handoff_validation.py` exists |
| `docs/wiki/2026-04-20-LM-Studio-autodiscovery-PLAN` | resolved | **historical** | `orchestrator/lan_discovery.py` exists |

## Status notes routed here (pre-existing markdown lint debt)

CI lints every changed Markdown file in full. These five historical files already fail
markdownlint at base, so editing them in place would require reformatting preserved text.
Their 2026-11-06 status notes are recorded here instead and apply to the named file.
The lint debt stays explicit; it is not exempted or called verified.

| File | markdownlint errors at base |
| --- | --- |
| `docs/2026-05-31-tri-repo-alignment-completion-plan.md` | 35 |
| `docs/next/2026-07-17-coordination-module-consolidation-plan.md` | 75 |
| `docs/next/2026-07-27-coordination-phase-0f-part2-autoplan.plan.md` | 2 |
| `docs/plans/2026-05-31-gate2-implementation-plan.md` | 6 |
| `docs/plans/2026-07-13-pr211-lan-gossip-progress.md` | 5 |

### `docs/2026-05-31-tri-repo-alignment-completion-plan.md`

> **2026-11-06:** No longer the active resume anchor. The Phase 0 master plan
> records this plan as done (item #1) with #2/#3/#8 deferred to v2. Current
> closure routing is the Orama master closure register, entered from
> [`next/MASTER-CLOSURE-HANDOFF-2026-11-06.md`](../next/MASTER-CLOSURE-HANDOFF-2026-11-06.md).

### `docs/next/2026-07-17-coordination-module-consolidation-plan.md`

> **2026-11-06:** "Part 2 remains deferred to v2 oramasys" is stale. The Part 2
> module split landed in PT, including `orchestrator/coordination/liveness.py`.
> Any v2 move is a separate parity migration, not a deferral of this plan: Orama
> doc 68 §1 and §11 rule out replacing v1 coordination in place or importing v1
> runtime code. Current v1 cleanup behavior is recorded in
> [`../coordination/manual-cleanup-characterization-2026-11-06.md`](../coordination/manual-cleanup-characterization-2026-11-06.md).

### `docs/next/2026-07-27-coordination-phase-0f-part2-autoplan.plan.md`

> **2026-11-06 status:** The `liveness.py` extraction is done: the seven
> heartbeat handlers live in `orchestrator/coordination/liveness.py`, and
> `cli.py` imports them. Cleanup side effects are characterized in
> [`../coordination/manual-cleanup-characterization-2026-11-06.md`](../coordination/manual-cleanup-characterization-2026-11-06.md).
> Any remaining Phase 0F rows are tracked in `docs/coordination/README.md`.

### `docs/plans/2026-05-31-gate2-implementation-plan.md`

> **2026-11-06:** The "in progress" status above is stale; the resolution
> banner at the top applies. The cited SHA predates the history rewrite and does
> not resolve on current `main`, but `stopServer` exists in
> `packages/alphaclaw-adapter/src/index.js`.

### `docs/plans/2026-07-13-pr211-lan-gossip-progress.md`

> **2026-11-06:** The `review-ready` front-matter status is historical. The LAN
> gossip bridge (`orchestrator/lan_gossip_bridge.py`) and its tests are on
> `main`. Whether PR #211 itself merged was not verified, because the history
> rewrite changed commit identities.

## Not covered

Markdown lint was not run on the changed files in this lane, so the
formatting of the new notes is not verified. Existing formatting debt in the
preserved plans is unchanged.
