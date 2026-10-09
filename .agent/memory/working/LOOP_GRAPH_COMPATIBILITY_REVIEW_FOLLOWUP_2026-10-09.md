# Loop/graph final review — append-only follow-up

**Date:** 2026-10-09 UTC. **Historical cutoff:** revision 3 local verification,
before PR publication. Current qualification is appended below.
This new record qualifies earlier research without editing accepted candidates,
episodic rows or rendered lessons. It is not a newly graduated semantic lesson.

## Canonical records

- [Orama revision 3 execution index](https://github.com/diazMelgarejo/orama-system/blob/docs/loop-graph-compatibility-r3/docs/v2/references/loop-graph-compatibility-2026-10-09/README.md)
- [Current resolutions](https://github.com/diazMelgarejo/orama-system/blob/docs/loop-graph-compatibility-r3/docs/v2/references/loop-graph-compatibility-2026-10-09/REVISION-3-RESOLUTIONS.md)
- [New durable refusal/HITL contract](https://github.com/diazMelgarejo/orama-system/blob/docs/loop-graph-compatibility-r3/docs/v2/references/2026-10-09-compatibility-refusal-hitl-contract.md)
- [PT evidence plan](../../../../docs/plans/2026-10-09-minigraph-compatibility-evidence-plan.md)

GitHub links now use PR branches; their original revision 3 publication-target
claim described the historical cutoff, not current merge state. Full
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
