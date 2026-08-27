# MiniGraph mutation + observer finalization — 2026-08-28

## Supersession chain

This record supersedes the remaining architectural overstatements in:

- `lesson_e0ff7f2d6717`;
- `lesson_1079e8c74f20` where this record is more specific.

It preserves the valid provenance in:

- `lesson_4a711949b3ed` (`GraphPlugin` origin and purpose);
- `c8e4d29b7f31` (`GraphObservation` / observer synthesis).

## The missing rule was found

The blanket instruction came from:

```text
orama-system/.cursor/rules/common-coding-style.mdc
```

It was an `alwaysApply: true` Cursor rule saying:

```text
ALWAYS create new objects, NEVER mutate existing ones
```

That wording has now been superseded on orama-system PR #333 by a
boundary-aware state/mutation policy.

## Canonical mutation boundaries

```text
value / versioned specification
  immutable or persistent updates preferred
  prior generations remain unchanged

builder / workspace / buffer / cache
  intentional local mutation allowed when it is the documented API
  mutation cannot leak across snapshot/publication boundaries

compiled / published / observed snapshot
  treat as immutable after publication
```

Consequences:

- `PerpetuaState.merge()` returns a deeply isolated next generation;
- `MiniGraph.add_node()` / `add_edge()` remain mutating builder operations;
- `MiniGraph.compile()` creates the detached runtime snapshot boundary;
- persistent structural sharing is retained for future versioned `GraphSpec`,
  not forced into MiniGraph's existing builder API.

## PerpetuaState

The verified Pydantic shallow-copy bug is now implemented in
`oramasys/perpetua-core` PR #1:

```python
self.model_copy(update=delta, deep=True)
```

`deep=True` prevents untouched nested mutable fields from being shared between
old and new state generations.

Precise invariant:

> Nodes and observers treat the state they receive as immutable input.
> `merge()` isolates produced generations; it does not freeze every Python
> container intrinsically.

## MiniGraph

MiniGraph remains:

```text
mutable construction builder
        |
        | compile()
        v
detached CompiledGraph snapshot
```

Changing `add_node()` / `add_edge()` into persistent-value methods would break
existing bare-call builder usage. Structural sharing belongs more naturally in
the future immutable/versioned GraphSpec layer.

## Observer contract

Execution remains:

```text
CompiledGraph._run()
  sole scheduler
        |
        v
GraphObservation(event, state, delta?)
        |
        +--------------------+
        |                    |
        v                    v
run_with_plugins()       GraphEvent
multicast                    |
                             v
                          asteps()
```

R2.4 is now split correctly:

1. **Delivery symmetry:** every registered plugin is offered the same complete
   observation sequence.
2. **Semantic filtering:** plugins may act on different subsets after identical
   delivery. A checkpointer may persist only `node.end`; a tracer may record all
   structural events.
3. **Observer transparency:** plugin-enabled final state must equal an
   equivalent no-plugin `ainvoke()` final state.

The old wording requiring heterogeneous plugins to *record* identical subsets
was overconstrained and is superseded.

## GraphSpec

Future versioned GraphSpec remains an `orama-system` responsibility and SHOULD
use immutable/persistent update semantics because it is a versioned definition
used for identity, diffing, optimization, review, and promotion.

GraphSpec validation remains fail-closed before realization/execution.

## Process note

The merge-conflict recovery mechanics captured in `lesson_e0ff7f2d6717` remain
valid operational memory. They are not MiniGraph architectural invariants.
