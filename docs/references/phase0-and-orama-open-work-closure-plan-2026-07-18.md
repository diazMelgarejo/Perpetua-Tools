# Phase-0 and Orama Open Work Closure Plan

Date: 2026-07-18
Inputs:

- the companion 29-document closure audit
- current Perpetua-Tools and orama-system repository state
- current coordination consolidation review

Status: planning handoff; no implementation or merge authorized by this file

## Objective

Turn every OPEN or AMBIGUOUS planning document into exactly one of four honest
states:

1. implemented and verified,
2. superseded with a pointer to the shipped implementation,
3. deliberately deferred with owner, trigger, and acceptance gate, or
4. retired with a recorded rationale.

Checkboxes, old PR badges, and historical "complete" prose are evidence, not
truth. Current `main`, current tests, and preserved security invariants decide
the status.

## Gate 0: Freeze a closure ledger

Create one row for every OPEN or AMBIGUOUS document with:

- repository and document path,
- category: implementation gap, post-rewrite content loss, stale specification,
  unresolved decision, or deliberate deferral,
- current code and test evidence,
- dependency and security impact,
- disposition,
- owner and branch,
- acceptance commands,
- final documentation update.

Do not edit status labels until the corresponding behavior or disposition is
verified. This prevents documentation cleanup from hiding unfinished work.

## Wave 1: Restore the live security boundary

### Orama P5 server-side swarm approval

Priority: Gate 0 security blocker

The audit describes P5 as unfinished on an old branch. Deeper history review
shows a more precise failure: the feature was previously merged, then its
security implementation disappeared from current `main` after later history
work. Current code still trusts a client-supplied approval boolean.

Execution:

1. Preserve old references; do not merge the old divergent branch wholesale.
2. Start a fresh branch from current `origin/main`.
3. Generate path-limited diffs for the historical T1, T2, and final security
   correction commits.
4. Reapply behavior in chronological order, retaining current-main behavior
   wherever unrelated code evolved.
5. Restore the final correction that uses a distinct server-only signing secret;
   do not restore the earlier bearer-token-as-signing-secret decision.
6. Complete T3-T7 with test-first coverage: missing, malformed, tampered,
   expired, wrong-preview, and valid token paths; rebuilt assignment dispatch;
   frontend token storage and launch gating.
7. Update the locked decision record to reflect the final secret design while
   preserving the explicit stateless replay-window tradeoff unless reopened by
   a separate decision.
8. Run backend, frontend, security, and repository-hygiene gates before review.

Acceptance: current `main` no longer accepts a client assertion as approval;
launch requires a server-verifiable preview-bound token; documentation and
tests describe the same contract.

Do not begin P6 discovery approval or downstream L1 work until P5 lands.

## Wave 2: Repair misleading specifications cheaply

These are low-risk documentation corrections and should be separate from new
runtime behavior.

### `PHASE-0-TASK-LIST.md`

Mark the unbuilt six-module design as superseded. Point to the STM and
`orchestrator/membership.py` path that actually shipped. Preserve the original
task list as provenance; do not rewrite history as though those modules existed.

### `TASK_A2_FINDINGS.md`

Add a correction banner stating that the scratch implementation was not merged
and its additive formula is not current. Point to the shipped multiplicative
formula and its tests.

### `peer_observation_tdd.md`

Prefer retirement or supersession unless an active implementation task needs the
document. If retained, rewrite only the formula-specific vectors against the
current multiplicative model and link the canonical decision or specification.

Acceptance: a new agent cannot reasonably infer that deleted scratch code or
the retired additive formula is production truth.

## Wave 3: Decide before building

### Heartbeat liveness hysteresis

Documents:

- `DELIVERABLE-2-HEARTBEAT-LIVENESS-REGENERATED.md`
- `PHASE-0-FIX-3-AND-MEDIUM-ITEMS-DECISION-BRIEF.md`

First issue a short decision record: implement now, defer to the v2 peer layer,
or retire because a newer liveness contract supersedes it. Do not implement from
the old spec until it is reconciled with the current heartbeat monitor and the
planned coordination `liveness.py` boundary.

If implementation is approved, require deterministic time-based tests for
promotion, demotion, hold-down, recovery, and threshold-edge behavior. If
deferred, name the v2 milestone and the trigger that reopens it.

### Medium decisions M1-M7

Run one bounded decision session covering sequence width, discovery fallback,
replay-cache eviction, and rate limiting. For each item record selected option,
rationale, compatibility impact, and implementation owner. Unselected options
must be marked rejected or deferred, not left as blank checkboxes.

Acceptance: no blank decision boxes remain without an explicit disposition.

## Wave 4: Program-level go or no-go decisions

### `PATTERN-MULTIAGENT-EXECUTION-PLAN.md`

Reconcile Tracks B-D against canonical `docs/v2/*` plans before resuming. Choose:

- resume only work that remains a prerequisite for Fleet Mode, with new owners
  and current acceptance gates, or
- formally shelve superseded or adversarial tracks and link the descope decision.

Do not revive the four-week program merely because the old checklist is open.

### Orama skill-standardization PR3

Document the credential-rotation disposition first. Revalidate the old file
inventory against current `main` and canonical in-repo skills, then either open
a narrowly scoped PR3 or mark the proposal superseded. Never embed credentials
or private environment values in the decision record.

Acceptance: each program has a current go or no-go decision and no silent gate.

## Parallel coordination work

The coordination consolidation is adjacent infrastructure, not a dependency of
the documentation corrections above.

1. Land the atomic queue-claim repair as a narrow Part 1 change.
2. Freeze all 29 CLI leaves and runtime handler provenance.
3. Consolidate capabilities behind parser-owned handlers.
4. Keep heartbeat migration separate from the immediate queue fix.
5. Require real-entrypoint parity before deleting compatibility modules.

## Ownership and branch discipline

- One owner and one branch per wave-sized change.
- No cross-editing another live agent's owned worktree.
- Preserve divergent historical branches until path-limited evidence is captured.
- Rebase or replay onto current main; do not merge rewrite-divergent history wholesale.
- Each PR updates the status documents it actually closes.
- Deferrals require an owner, milestone or trigger, and verification evidence.

## Recommended execution order

1. P5 security restoration.
2. Three misleading-document corrections.
3. Heartbeat hysteresis and M1-M7 decision records.
4. Pattern-program and skill-standardization go or no-go decisions.
5. P6 and downstream work only after P5.
6. Coordination consolidation proceeds in parallel after its Part 1 plan fixes.

## Final closure gate

Re-run the 29-document audit against current `main` in both repositories. Every
formerly OPEN or AMBIGUOUS row must include a commit or PR or explicit
disposition, tests where behavior changed, and a portable canonical pointer.
Record remaining external or hardware-bound work separately rather than calling
the whole plan complete.
