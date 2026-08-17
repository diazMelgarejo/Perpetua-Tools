# Operational Work Disposition (2026-08-14)

> **Purpose:** current navigation for operational work after the historical
> closure pass. This document records what is ready to execute, what is
> blocked, and what remains deliberately deferred. It does not claim a code
> merge or replace the evidence in the linked implementation plans.
>
> **Authority:** use the [Phase 0 master plan](../phase-0-specifications/PHASE-0-MASTER-PLAN-2026-07-27.md)
> for STM and mesh disposition, the [Tier-5 model registry gate](2026-08-11-model-registry-provenance.md)
> for provider configuration, and the linked Orama documents for cross-repo
> work. The older pending-work tracker is historical only.

## Verification Scope And Confidence

This refresh was reconciled against PT `origin/main` at `51c81247` and Orama
`origin/main` at `950eca33`. It is a documentation disposition, not a claim
that every planned item has been merged or released.

| Area | Verified Status | Confidence |
| --- | --- | --- |
| Gossip UUID and FastAPI regression | Fully repaired: `main` has idempotent UUID replay, duplicate-insert signaling, and explicit worker-thread initialization. | High |
| Historical pending trackers | Explicitly superseded; do not repair their old PR rows. | High |
| PT identity parity | Policy, schema, and audit engine are byte-identical with Orama. A copy-only Phase 3 task would duplicate work. | High |
| Identity Phase 4 | Requires a bounded consumer and legacy-list audit before closure. | Medium |
| AlphaClaw TLS core | Shipped; real Windows validation and policy decisions remain operational follow-ups. | High |
| Orama peer-mesh TLS/auth | Deferred to v2; do not start `secure_transport` work from this disposition. | High |
| Remote PR state | Not freshly verified: GitHub CLI authentication was unavailable during this reconciliation. Verify live PR state before writing a new merged-status claim. | High |

The older UUID report remains useful as a migration lesson, but its tracker
authority and Phase 3 identity status are outdated. This document preserves
the lesson while correcting those dispositions.

## Operating Rules

- A code item is **ready** only when its owning repository, branch base,
  acceptance tests, and security boundary are identified.
- A code item is **blocked** when a recorded review finding remains unresolved;
  documentation must not turn that state into a release claim.
- A task is **deferred** only when its trigger and owning v2 plan are named.
- Preserve history rather than rewriting status in superseded trackers. Put
  current disposition here and in the canonical master plan.

## Completed Or Superseded Evidence

| Area | Disposition | Evidence |
| --- | --- | --- |
| Gossip UUID contract migration | **DONE** | UUID persistence, idempotent replay, duplicate-insert signaling, HTTP propagation, and worker-thread initialization are present in PT `main`. The reusable lesson is to migrate persistence, contract, callers, transport, lifecycle, and tests as one vertical slice. |
| Historical pending-work trackers | **SUPERSEDED** | Both trackers state that the Phase 0 master plan supersedes them. They remain provenance, not a queue. |
| Identity Phase 3 parity | **DONE** | PT and Orama currently carry byte-identical identity policy, schema, and audit-engine files. Do not open a copy-only synchronization task. |
| AlphaClaw TLS core and Windows ACL support | **DONE** | The shipped core remains opt-in. Operational validation and policy choices are listed below. |
| Peer-mesh TLS and pluggable auth | **DEFERRED v2** | The v1 bearer-on-authenticated-transport minimum is complete; the broader peer-mesh design remains owned by [Orama v2 plan 49](https://github.com/diazMelgarejo/orama-system/blob/main/docs/v2/49-peer-mesh-auth-tls-v2-plan.md). |

## Seven Operational Items

Work these in order unless a security incident requires a narrower emergency
change. Each item is independently reviewable; do not combine it with an
unrelated code migration.

| # | Workstream | State | Start From | Exit Gate |
| --- | --- | --- | --- | --- |
| 1 | Tier-5 publication closure | **BLOCKED** | [Model registry provenance gate](2026-08-11-model-registry-provenance.md) | Reserve budget atomically before provider dispatch, account conservatively for partial-stage failure, close the recorded review findings, and pass focused transport, auth, and cost tests. |
| 2 | Identity Phase 4 audit | **NOW** | Orama [integrated identity plan](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-07-24-unified-identity-audit-integrated-plan.md) | Prove every production consumer delegates to the shared audit engine. Remove only a verified duplicate authority, or record that no removable authority remains. |
| 3 | Mesh operator backup and readiness | **NOW** | [Phase 0 master plan, operator gate](../phase-0-specifications/PHASE-0-MASTER-PLAN-2026-07-27.md#10-operator-pre-v2-gate-ordered) | Each participating node has an operator-controlled recovery copy of its local mesh configuration and secrets before topology changes. |
| 4 | Mesh end-to-end verification | **NOW** | [Mesh security finality report](https://github.com/diazMelgarejo/orama-system/blob/main/docs/next/fleet-mesh/2026-07-26-pr224-mesh-security-finality-report.md) | Install hooks and verify authenticated gossip emit/tail plus runtime probes on every participating node. Record only sanitized evidence. |
| 5 | Mesh Phase B IP expunge | **IN PROGRESS** | Orama mesh migration ladder | Complete Items 3 and 4, then review the change as a dedicated security migration. Do not infer topology from a tracked document. |
| 6 | AlphaClaw TLS hardware validation | **NOW** | PT TLS scaffolding and Windows ACL plans | Run the existing tests and a real Windows operator validation. Decide certificate rotation, administrative pinning, mTLS, and default enablement in separately approved follow-ups. |
| 7 | Hermes Windows harness smoke | **NOW** | Orama Hermes migration operator plan | Complete the live Windows install and idempotence smoke, preserve sanitized evidence, and update the owning Hermes record only after the operator gate passes. |

## Deliberately Not In This Queue

- Peer-mesh `secure_transport`, certificate management, provider-pluggable
  authentication, and chained audit logging remain v2 work.
- G7 portal notifications are optional v1 work, not a prerequisite for the
  seven operational items above.
- STM P5/P6/P13 production wiring remains superseded by the single-operator
  threat-model descope until its documented fleet-mode trigger occurs.
- `vendor/ecc-tools` reconciliation is a separate provenance and submodule
  task. Do not absorb local submodule state into an operational documentation
  or Tier-5 publication commit.

## Handoff Checklist

1. Start from the named source document and verify the owning branch base.
2. Claim one workstream and state its exit gate before editing.
3. Keep documentation, code, and operator evidence in their respective
   logical commits.
4. Re-run the relevant tests and repository hygiene before publication.
5. After a gate closes, update this document and the canonical master plan;
   leave superseded trackers intact.

## Documentation And Code Sequencing

1. Keep this PT documentation refresh on the Tier-5 branch as a standalone
   logical batch. Do not stage concurrent `.agent`, `.codex`, or submodule
   changes.
2. Update the PT master plan and `docs/next` index with the verified
   disposition. Do not rewrite the superseded pending trackers.
3. In a separate Orama documentation worktree based on its current `main`, add
   `bin/orama-system/skills/oramasys-method/references/contract-migration.md`.
   It must define the vertical slice `persistence -> contract -> callers ->
   transport -> lifecycle -> tests`, include the sanitized UUID case study,
   state return-contract and migration-exception rules, and provide an
   end-to-end regression matrix.
4. Link that Orama reference from the canonical `oramasys-method`,
   `code-review`, and `agent-methodology` entrypoints. Use existing wrappers;
   do not create copied skill content.
5. Before future code changes, run the Identity Phase 4 audit: classify every
   identity-looking structure as policy authority, compatibility code, or test
   fixture. Remove only a duplicate production authority with equivalence
   tests; otherwise record verified closure without manufacturing a refactor.

## Publication Discipline

The intended logical commits are:

1. `docs(status): reconcile canonical cross-repo disposition`
2. `docs(oramasys): add contract migration vertical-slice method`
3. `refactor(identity): remove verified duplicate policy authority` only if
   the Phase 4 audit finds one

Before the single future push, verify clean worktrees, focused identity and
guard tests, repository hygiene in each affected repository, links, and
`git diff --check`. The Tier-5 transport branch remains unpublished until its
separate publication gate is closed.
