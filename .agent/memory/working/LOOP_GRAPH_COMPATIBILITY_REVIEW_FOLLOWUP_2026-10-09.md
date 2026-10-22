# Loop/graph final review — append-only follow-up

**Date:** 2026-10-09 UTC. **Historical cutoff:** revision 3 local verification,
before PR publication. Current qualification is appended below.
This new record qualifies earlier research without editing accepted candidates,
episodic rows or rendered lessons. It is not a newly graduated semantic lesson.

## Canonical records

- [Orama revision 3 execution index](https://github.com/diazMelgarejo/orama-system/blob/19a81cdff1ef6031f5b31a1b982f6eb46fc84033/docs/v2/references/loop-graph-compatibility-2026-10-09/README.md)
- [Current resolutions](https://github.com/diazMelgarejo/orama-system/blob/main/docs/v2/references/loop-graph-compatibility-2026-10-09/REVISION-3-RESOLUTIONS.md)
- [New durable refusal/HITL contract](https://github.com/diazMelgarejo/orama-system/blob/main/docs/v2/references/2026-10-09-compatibility-refusal-hitl-contract.md)
- [PT evidence plan](../../../../docs/plans/2026-10-09-minigraph-compatibility-evidence-plan.md)

GitHub links now target `main`; the PR branches were deleted after merge. The
original revision 3 publication-target claim described the historical cutoff. Full
original archive members are preserved byte-for-byte in Orama's history folder.

## Lessons from the review

1. "Honors a configuration key" does not prove invalid-input safety. Semaphore
   zero blocks forever; bool/float bounds can weaken the bound. Validate before
   constructing any task or producing effects, including empty batches.
2. Evidence must carry every fixture and assert outcomes. A fake-package alias
   prototype without its package is not reproducible; print-only observations
   are not acceptance tests. Use a disposable process and temporary fixtures.
3. Same module/class identity is insufficient. Import machinery can rewrite
   native `__spec__`; test metadata and pickle identity, then separately test
   real-framework behavior and installer metadata. Meta-path discovery does not
   prove pip dependency resolution.
4. Compare public event contracts and causal partial order. Do not suppress
   payload differences or impose total order on parallel supersteps.
5. A proposed approval schema is not a shipped mechanism. Durable use accounting,
   exact request/policy binding and unknown-outcome reconciliation must exist
   before an override can execute. Until then remain denied/pending.
6. Keep research scope honest: native Pydantic AI patterns do not authorize a
   production runtime bridge. Separate proposals, user decisions, executed
   evidence and publication status.
7. PR merge refs are not a complete cross-repository inventory. Explicitly scope
   observations and never turn incomplete absence evidence into a global claim.

## Boundaries

PT and Orama remain independent v1 systems with no v2 dependency. New facade,
replacement binding and bridges belong in `oramasys/oramasys`; existing adapters
stay in Core. Agate/Phylax/Telos remain sole policy owners. All parity is best
effort under enforcement. No override, dependency pin, force-push or merge was
performed as part of this local repair.

## Later resolution — revision 4

The earlier local/publication-pending state is the revision 3 cutoff.
The operator later approved D-LG-1's separate policy/transclusion and D-LG-4
Phase 1. Core and Oramasys now have tested bounded implementation in their
existing PRs. Production effects and durable approvals remain gated.
See [the closure record](LOOP_GRAPH_REVISION4_CLOSURE_2026-10-09.md) for the
memory lineage, durable lessons, tests and current next actions.
No historical candidate or episodic/semantic row was edited in place.


## Later resolution — authorized follow-up publication

On 2026-10-09 UTC the operator authorized subsequent corrective patches and
publication until this review batch is complete. The prior one-update limit no
longer blocks follow-up repairs; merge approval remains separate.

- Core #8 follow-up: `82ce99190e25f9e06513c0fd47326eba4a6ab802`. Advisory routing declarations
  no longer restrict valid native nodes or END. Import contracts match framework
  families and preserve independent lookalikes.
- Oramasys #23 follow-up: `172231848efc6d2b7a6182716010756cc9b44fe6`. The isolated oracle snapshot
  includes editables 0.5, graph tools diagnose a missing output, and the oracle
  candidate pins the new Core commit. Real routing regressions cover declared,
  undeclared and terminal destinations.

The revision 3 index above is now immutable and identifies the historical
cutoff accurately. Earlier append-only lesson and candidate records remain
unchanged. Fresh CI must be assessed at these exact heads; prior local results
are evidence from the earlier session, not a fresh run in the resumed session.
The resumed shell stalled, including simple echo commands, so publication used
GitHub git-data operations with explicit base-tree, file-content and
parent-preservation checks. No merge, force update or branch deletion occurred.


## Final nitpick closure and exact-head evidence

The broader review also covered review-body nitpicks. Dynamic-import lint now
resolves literal concatenation and literal-only f-strings; unresolved arguments
produce an explicit review finding instead of silently disappearing. The
test-first Core commit observed four expected failures on both interpreters
before the fix. Scanner contracts remain synchronized across Core and Oramasys.

- Final Core head: `b9b44775633c393ed709176a9bb1332014ab9320`. Python 3.11/3.12:
  184 passed and 1 optional-framework module skipped each; 87.88% coverage.
- Final Oramasys head: `1669fe6bfbc93c9e0017dea9a364856bc2d37208`. Python 3.11/3.12 real
  offline oracle matrix: 283 passed each; regular CI passed.
- Orama's active prototype evidence test now uses pytest and is explicitly
  invoked by CI. Historical attachments remain unchanged.

Read the [immutable final coordination handoff](https://github.com/diazMelgarejo/orama-system/blob/e2fad9e7c84ef65696e35a429456e55d8f5633cd/docs/v2/references/loop-graph-compatibility-2026-10-09/FOLLOWUP-VERIFICATION-AND-HANDOFF.md)
before applying or replaying any older patches. Earlier follow-up heads and
counts above describe intermediate snapshots; this section supersedes them.
The current Core oracle candidate is test-only. Merge and production-pin
promotion remain separate operator decisions. Durable HITL and full replacement
compatibility remain unfinished capabilities.

## Budget stop and portable gap errors (later follow-up)

A review of the final heads found two Oramasys defects that the counts above
did not expose, both fixed in Oramasys `d938dac` and recorded in Orama
`9dfe070`:

- On `UsageLimitExceeded`, `as_node` returned an error delta, so downstream
  nodes (including effect nodes) still ran and the run ended `done`. It now
  raises Core's structural `Interrupt` with reason `budget_exhausted` and
  `resumable: false`.
- The gap error classes could not be unpickled; they now rebuild from their
  constructor arguments.

Both new tests fail on `1669fe6`. Local Python 3.12 against Core candidate
`b9b4477`: oracle environment 284 passed, framework-free suite 271 passed.
Core needed no further change.

Lesson: a green count does not prove behaviour. The budget bug survived 283
passing tests because its test had no node after the agent. Add the
adversarial shape (a node after the stop, an undeclared route) before trusting
a suite.
