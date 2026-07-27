# docs/next/ — Index

**Added 2026-07-22** as part of the v1→v2 transition close-out. This
directory holds forward-looking analysis/design docs that predate a formal
plan file. Not all have been re-verified against current `main` — statuses
below are each doc's own self-reported status as of 2026-07-22, not a fresh
audit, unless marked "re-verified."

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

| Doc | Topic | Self-reported / re-verified status (2026-07-22) |
|---|---|---|
| `2026-07-17-coordination-module-consolidation-plan.md` | Coordination module consolidation | **Re-verified**: Parts 1/1b/1c/1d confirmed landed (`28c425f9`); Part 2 deferred to v2 (its own gate, "Phase 0F," doesn't exist anywhere in the repo); Part 3 already explicitly deferred by its own text |
| `2026-07-17-phase-board-fragmentation-analysis.md` | Investigation of a phase-board bug | Fixed by Codex (`9642ae24`) — doc records the investigation so the debugging path isn't re-walked |
| `2026-07-17-tool-use-limits-session-reflection.md` | Session retrospective | Honest retrospective — not a plan, no action items to close |
| `2026-07-17-frugal-pr-review-triage-pattern.md` | PR review triage pattern | Extracted from live use on PR #256, not hypothetical — reference pattern, not a pending task |
| `2026-07-19-heartbeat-daemon-design.md` | Heartbeat daemon design | DESIGN ONLY per explicit instruction — "scope now, build later"; not re-verified this pass, still design-stage |
| `2026-07-24-alphaclaw-tls-proxy-scaffolding.md` | AlphaClaw TLS proxy — v1 wiring status | v1 complete, PR #276 open; re-verified 2026-07-24 (pytest green) |
| `2026-07-25-pending-work-tracker.md` | Cross-repo pending-work tracker | See file — tracks PT #276 / orama #197 follow-ups |
| `2026-07-24-plan-windows-acl-alphaclaw-tls-proxy.md` | Windows ACL enforcement for the AlphaClaw TLS cert/key store | PLAN — not implemented; deprecated `SetFileSecurity` call in the source draft fixed to `SetNamedSecurityInfo` before filing, re-verified 2026-07-24 (EXA + Firecrawl against Microsoft/pywin32 docs) |

Related Phase 0 ontology: [`../phase-0-specifications/README.md`](../phase-0-specifications/README.md)
links the older STM, swarm-security, liveness, and review documents to the
forward-looking work tracked here.

Everything above except the coordination-module-consolidation-plan (which
this session's P3 trace directly touched, hence the full re-verify) is
**out of scope** for the 2026-07-22 frugality/privacy and cross-repo-
closure work. Listed here as a navigation index so a future session
doesn't have to rediscover this directory from scratch — re-verify any of
these against current `main` before trusting the table, per the same
discipline the closure ledger itself was built on.
