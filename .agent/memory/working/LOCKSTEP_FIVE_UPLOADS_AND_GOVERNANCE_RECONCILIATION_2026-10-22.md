# Lockstep Five-Upload Review And Governance Reconciliation

**Date:** 2026-10-22

**Status:** Evidence and local candidate deltas complete. No ratification,
merge, runtime-pin promotion, serving enablement, or production activation is
implied by this record.

## Scope

This record preserves the cross-repository review of five supplied inputs:

1. `references/lockstep-plan.zip`
2. `references/ollama-cloud-lockstep-pack.zip` (all seven members inspected)
3. `references/CROSS-REPO-REVIEW-AND-AGENT-HANDOFF-2026-10-21.md`
4. `references/E1-M1-RUTHLESS-REVIEW-2026-10-15.md`
5. `references/instruction.md`

Attached documents were treated as evidence and proposals, not as authority to
publish, ratify, or activate work.

## Verified Review Outcomes

- Historical lockstep PRs described by the supplied plans were already merged;
  they were not replayed merely because a historical plan named them.
- The current consumer and issuer implementation pair was independently
  inspected at the reviewed heads recorded in
  `references/2026-10-22-lockstep-final-evidence-receipt.json`.
- The receipt deliberately uses `EVIDENCE_ONLY_NOT_RATIFIED`. Passing tests,
  successful Actions runs, and a review record are distinct from an operator
  decision to merge, ratify, promote a pin, or enable serving.
- Ollama source research established only documented tag and pricing evidence.
  It did not establish a paid task benchmark, free-window status, candidate
  eligibility, or authorization to change a default registry route.

## Governance Reconciliation

The open governance PRs remain unchanged. Their parent heads contain the
governance modules absent from current `main`, so a fresh-main replacement
would not be an equivalent delta.

Two local, tested candidate patches reconcile the earlier minimal repair with
the optional scope/path proposal:

- `references/2026-10-22-orama-governance-reconciled-candidate.patch`
- `references/2026-10-22-pt-governance-reconciled-candidate.patch`

The reconciled contract is:

1. A presented proof always binds the normalized model, effort, and fast
   fields before any path-specific early return.
2. `path` and `scope` are optional claims for the trusted verifier to emit.
3. A supplied `path` must match the requested launch path.
4. `scope` must exactly equal the explicit requested approval scope; an
   unscoped legacy call remains compatible only with an unscoped proof.
5. This policy checks claim consistency only. Authenticity, task ownership,
   and signature verification remain responsibilities of the trusted verifier.

Focused governance validation passed in both repositories after reconciliation:

| Repository | Test result |
| --- | --- |
| orama-system | 458 passed |
| Perpetua-Tools | 462 passed |

## Lessons

1. Treat a review artifact as a proposal until the current branch, PR head,
   and CI evidence establish whether its suggested change is still applicable.
   Historical plans can accurately describe a past fix while being unsafe to
   replay against a later implementation.
2. Keep the state vocabulary precise: implemented, tested, published,
   reviewed, ratified, promoted, and activated are separate states. An
   evidence receipt must state which one it represents.
3. Optional authorization claims require explicit compatibility semantics.
   A verifier-issued optional claim may safely strengthen a proof only if a
   mismatch fails closed while absent claims retain the documented legacy
   behavior.
4. Cross-repository source-only compatibility probes should remain separate
   from runtime dependency pins until a dedicated promotion decision and
   qualification gate authorize a change.
5. Coordination evidence needs author, current actor, bounded endorsement,
   and takeover provenance. A board note is a discoverability record, not an
   authority transfer or a completion claim for another agent.

## Remaining Operator Decisions

1. Choose a publication route for the tested governance deltas without
   rewriting or silently altering the existing governance PRs.
2. Merge or otherwise disposition the reviewed runtime and issuer PRs through
   normal review.
3. Publish the separately validated documentation follow-up and resolve its
   review threads.
4. Ratify Part 3 at an exact reviewed head.
5. Authorize a bounded paid Ollama benchmark and verify expiry/eligibility
   evidence before any default registry change.
6. Decide whether the proposed Alexandria material becomes an adopted source
   of authority.
7. Separately approve any runtime-pin promotion, serving, or production
   activation.

## Coordination

The live GossipBus note `LOCKSTEP_GOVERNANCE_RECONCILIATION_AND_OPERATOR_GATES_20261022`
contains the evidence pointers, candidate patch hashes, validation results, and
the same operator gates. It is a coordination pointer only; this file is the
portable memory record.
