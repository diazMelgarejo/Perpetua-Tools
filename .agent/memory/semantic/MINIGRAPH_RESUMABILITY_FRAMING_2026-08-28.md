# MiniGraph Resumability Framing — 2026-08-28

## Canonical clarification

Do not convert a wording correction into feature deletion.

The MiniGraph/orama reconciliation now uses this exact classification:

```text
LangGraph checkpoint/thread identity
    ADOPT

Atomic successful-boundary checkpoints
    ADOPT / ADAPT

Durable resumability
    ADOPT — R4 target

"perfect resumption"
    REJECT WORDING ONLY

durable deterministic resume
    ADOPT TARGET
```

The word "perfect" is rejected only when it implies an impossible universal
guarantee. The engineering target remains ambitious: save session/graph state,
checkpoint lineage, graph/version/schema identity, and replay metadata well
enough to resume predictably from an explicit compatible boundary.

Resumability is not total reversibility. Restoring graph state cannot rewind
time or erase an external side effect that already occurred. External effects
must be reconciled through effect identity, idempotency, deduplication,
compensation, or explicit human/policy handling.

## Governance rule

When reconciling mined patterns or older architecture notes:

1. distinguish **feature disposition** from **wording disposition**;
2. use `REJECT WORDING ONLY` when the capability survives but an absolute claim
   is too broad;
3. state the retained target beside the wording correction so future agents do
   not infer feature dropping;
4. treat `deferred` as "not implemented in this PR", not "rejected";
5. keep the design realistic about system boundaries while remaining ambitious
   about deterministic state saving and recovery.

## Current orama authority

PR #333 carries the clarification in the pattern reconciliation matrix,
LangGraph checkpoint extraction, observer/pattern reconciliation, execution
plan, and pattern catalogue. R4 remains the explicit durable deterministic
resume target.

## Related memory

- `lesson_e0ff7f2d6717` — recent MiniGraph reconciliation developments.
- `lesson_4a711949b3ed` — GraphPlugin/fan-out provenance chain.
- `MINIGRAPH_OBSERVER_PATTERN_RECONCILIATION_2026-08-27.md` — observer synthesis.
- `MINIGRAPH_MUTATION_OBSERVER_FINALIZATION_2026-08-28.md` — mutation/observer finalization.
