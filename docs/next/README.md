# docs/next/ — Index

**Added 2026-07-22** as part of the v1→v2 transition close-out. This
directory holds forward-looking analysis/design docs that predate a formal
plan file. Not all have been re-verified against current `main` — statuses
below are each doc's own self-reported status as of 2026-07-22, not a fresh
audit, unless marked "re-verified."

**Penultimate master plan (2026-07-27):**
[`../phase-0-specifications/PHASE-0-MASTER-PLAN-2026-07-27.md`](../phase-0-specifications/PHASE-0-MASTER-PLAN-2026-07-27.md)
(STM/swarm security — **not** coordination Phase 0F).

**Current operational disposition (2026-08-14):**
[`2026-08-14-operational-work-disposition.md`](2026-08-14-operational-work-disposition.md)
— the seven independently-gated operational workstreams, including the
blocked Tier-5 publication gate and explicit v2 deferrals.

**Coordination Phase 0F hub:**
[`../coordination/README.md`](../coordination/README.md) ·
terminology:
[`../coordination/PHASE-0-TERMINOLOGY-DISAMBIGUATION.md`](../coordination/PHASE-0-TERMINOLOGY-DISAMBIGUATION.md)

**Coordination Phase 0F autoplan:**
[`2026-07-27-coordination-phase-0f-part2-autoplan.plan.md`](2026-07-27-coordination-phase-0f-part2-autoplan.plan.md)

**Mesh security PR #222 (orama):**
[`2026-07-27-mesh-security-pr222-orama-pointer.md`](2026-07-27-mesh-security-pr222-orama-pointer.md)

**v1→v2 closure entry points** (start here for "what's the overall status
of open work across both repos"):

- `../../../orama-system/docs/plans/2026-07-22-cross-repo-out-of-scope-closure.md`
  — closure ledger for every plan flagged as not directly frugality/privacy-
  related during this session's P3 trace; four-state disposition
  (implemented / superseded / deferred-to-v2 / retired) for each. Item #7
  covers `2026-07-17-coordination-module-consolidation-plan.md` below
  directly.
- `../../../orama-system/references/tiered-model-implementation-navigator.md`
  — the overarching index this closure work traces back to.
- `../2026-05-31-tri-repo-alignment-completion-plan.md` — **re-verified**
  2026-07-22 (commit `4bf12868`): item #1 confirmed resolved, stale
  contradiction fixed, items #2/#3/#8 explicitly deferred to v2.
- `../phase-0-specifications/README.md` — Phase 0 STM/swarm knowledge graph
  and LLM-wiki index. Use this when a `docs/next` item depends on
  PeerObservation, confidence scoring, heartbeat/liveness, replay/dedup,
  witness quorum, threat-model premise checks, or PR #203/#205 review history.

## Contents

| Doc | Topic | Historical / current status |
| --- | --- | --- |
| `2026-07-27-mesh-security-pr222-orama-pointer.md` | Pre–PR #222 mesh backup + trusted-install pointer | **Operator** — Phase A on all LAN nodes before orama #222 merge |
| `2026-07-27-coordination-phase-0f-part2-autoplan.plan.md` | Coordination Phase 0F + Part 2 (`liveness.py`) | **Autoplan intake** — run `/autoplan` here; hub [`../coordination/README.md`](../coordination/README.md) |
| `2026-07-17-coordination-module-consolidation-plan.md` | Coordination module consolidation | Parts 1/1b/1c/1d landed; mother plan — see coordination hub |
| `2026-07-17-phase-board-fragmentation-analysis.md` | Investigation of a phase-board bug | Fixed by Codex (`9642ae24`) — doc records the investigation so the debugging path isn't re-walked |
| `2026-07-17-tool-use-limits-session-reflection.md` | Session retrospective | Honest retrospective — not a plan, no action items to close |
| `2026-07-17-frugal-pr-review-triage-pattern.md` | PR review triage pattern | Extracted from live use on PR #256, not hypothetical — reference pattern, not a pending task |
| `2026-07-19-heartbeat-daemon-design.md` | Heartbeat daemon design | DESIGN ONLY per explicit instruction — "scope now, build later"; not re-verified this pass, still design-stage |
| `2026-07-24-alphaclaw-tls-proxy-scaffolding.md` | AlphaClaw TLS proxy — v1 wiring status | Historical implementation record; core and Windows ACL support are merged, while hardware validation remains operational work |
| `2026-07-25-pending-work-tracker.md` | Cross-repo pending-work tracker | **SUPERSEDED**; retained for historical branch and PR provenance only |
| `2026-07-24-plan-windows-acl-alphaclaw-tls-proxy.md` | Windows ACL enforcement for the AlphaClaw TLS cert/key store | Historical implementation plan; code is merged, but real Windows validation remains an operator gate |
| `2026-08-11-model-registry-provenance.md` | Provider model-ID evidence and update gate | Tier-5 configuration source record; publication remains blocked until its independent review gates close |
| `2026-08-14-operational-work-disposition.md` | Current operational queue | **ACTIVE**; seven workstreams, exit gates, and explicit v2 deferrals |

Related Phase 0 ontology (STM/swarm — **not** coordination Phase 0F):
[`../phase-0-specifications/README.md`](../phase-0-specifications/README.md).
Coordination Phase 0F:
[`../coordination/README.md`](../coordination/README.md).

Everything above except the coordination-module-consolidation-plan (which
this session's P3 trace directly touched, hence the full re-verify) is
**out of scope** for the 2026-07-22 frugality/privacy and cross-repo-
closure work. Listed here as a navigation index so a future session
doesn't have to rediscover this directory from scratch — re-verify any of
these against current `main` before trusting the table, per the same
discipline the closure ledger itself was built on.
