# Remaining work queue and review correction

Date: 2026-10-10 Asia/Manila. Latest operator direction: finish running work
without interrupting processes, then design and implement full upstream
replacement, durable HITL, foreign transport and R4; use new implementation PRs
based on merged predecessor work and create a handoff document. Existing review
fixes stay on their current PRs. No new merge authorization is inferred.

## Completed running work

- Core #9, Oramasys #25 and Orama #390 are green on their exact published heads.
- PT #433 was stacked on #432 and merged into its branch by the operator as
  `72dc89963473ac9e2c7d68d95ee8637059e72a57`. Both parent histories and records
  survived. PT #432 remains open against main; its current checks passed.
- The complete two-pair checklist and detailed candid assessment are present.
  Neither full replacement nor durable effects/replay is claimed implemented.

## Review 5476411379: one root cause, four findings

The original REST-only guidance conflated posting a reply with resolving a
thread, and generalized a prior token-specific observation. Official GitHub
documentation separates REST replies from GraphQL resolve/unresolve mutations.

Corrected the active procedure. Graduated `lesson_9b3602e9dabc` with explicit
supersession of `lesson_e268b391ba1d`. Preserved the original graduated JSON and
both historical JSONL prefixes; appended the episodic correction and regenerated
LESSONS.md through the tool. The earlier contents-write-only token's REST 403
and GraphQL success remain historical evidence, not a current capability promise.
An unverified host-specific REST route must never be taught as working.

## Next executable work

1. Publish this review fix on PT #432, verify its remote tree and fresh CI, and
   reply to all four original comments with the exact fixing revision.
2. Use the current canonical revision-2 plan and actual owner interfaces to
   write focused designs and executable plans for replacement, durable approvals
   and effects, mediated/contained foreign transport, and R4 recovery.
3. Produce a handoff binding exact baselines, owners, contract/schema versions,
   required adversarial tests, commands, outcomes and next authorized actions.
4. Implement reviewed slices with failing regressions first. New PRs must begin
   from the merged predecessor revisions requested by the operator; do not
   present a candidate branch as already merged or silently advance production.

At this checkpoint Core #9, Oramasys #25 and Orama #390 remain open. Their main
heads remain Core `04759a50c748444ff97136ea95c1e1289eac3a1a`, Oramasys
`61af13118d2cbcb1f575926876eb9a9c3b5cc612`, and Orama
`8eb182b2e05dfbb6ce5fc5d8fb5a8f7ea5095720`. Re-read them before choosing a
new implementation base. Current production Core pin stays `04759a5`.

Current design owners and gates are in Orama
`docs/v2/references/remaining-capabilities/IMPLEMENTATION-PLAN-REV2-2026-10-10.md`
and `R3-AUDIT-REPLAY-AND-COMPATIBILITY-2026-10-10.md` on #390.
