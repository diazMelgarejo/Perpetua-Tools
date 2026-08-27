# MiniGraph observer + pattern-library reconciliation — 2026-08-27

## Status

Canonical cross-repo semantic note for PT memory. This note complements the
append-only graduated candidate `c8e4d29b7f31` and preserves
`lesson_4a711949b3ed` as provenance rather than editing it in place.

## Final observer synthesis

The correct execution/observation model is:

```text
CompiledGraph._run()
  one scheduler
       |
       v
GraphObservation
  event + PerpetuaState + optional node delta
       |
       +-----------------------------+
       |                             |
       v                             v
plugin-layer fan-out             GraphEvent projection
  Checkpointer                       |
  Tracer                             v
  Audit                           asteps()
  Interrupt observer                 |
                                     v
                               streaming/API/UI
```

Rules:

1. `_run()` remains the sole scheduler implementation.
2. `GraphObservation` is the rich trusted in-process observation contract.
3. `GraphEvent` remains sanitized control-plane data and excludes state/deltas.
4. `asteps()` is a pull projection and is not itself a multicast mechanism.
5. A plugin dispatcher drains the observation stream exactly once and pushes
   each observation to all registered `GraphPlugin` listeners.
6. Plugin delivery is deterministic in registration order and fail-closed by
   default; richer per-plugin failure policy may be layered above later.
7. Plugins never reimplement traversal or read private `_nodes`/`_edges`.

This supersedes only the observer-mechanism portion of
`lesson_4a711949b3ed`. That lesson's verified provenance chain remains valid:
`05-feasibility-review.md` anticipated the multi-consumer `GraphPlugin` need;
`08-technical-architecture-review.md` implemented that recommendation; later
`asteps()` work solved scheduler duplication but did not by itself solve
multicast observation.

## Recovered v2 pattern-library lineage

`orama-system/docs/v2/references/patterns/` is an evidence/reference layer for
v2 architecture, not discarded historical scaffolding.

- **LangGraph checkpoints/reducers:** retain session/thread identity, atomic
  checkpoint boundaries, and reducer lessons. Durable resume still requires
  graph/version identity, replay semantics, idempotency, and effect dedupe.
- **Pydantic AI tools:** retain `inspect.signature`, Pydantic schema derivation,
  docstring metadata, dependency injection, and strict validation without
  adopting the Pydantic AI runtime.
- **Karpathy March of Nines:** retain deterministic harnessing and verification;
  Sentinel/evaluator semantics belong above the MiniGraph kernel.
- **Swarm / CrewAI / AutoGen:** map handoffs to conditional edges, managerial
  workflows to subgraphs, and nested work to bounded subgraphs; richer
  parallelism still requires explicit reducers and joins.
- **Microsoft Foundry:** split evaluation, isolation, and dynamic routing into
  evaluator, effect/security policy, and GraphSpec/runtime-policy layers.

## Ownership

```text
diazMelgarejo/orama-system
  methodology + GraphSpec/NodeSpec/EdgeSpec authority
  pattern library + lint + evaluation + runtime/effect policy
                    |
                    v
oramasys/perpetua-core
  PerpetuaState + realized graph execution
  GraphObservation + GraphEvent + generic graph plugins
                    |
                    v
Perpetua-Tools
  runtime telemetry / memory governance / cross-repo semantic learning
```

## Deferred work

- R3: explicit reducers + joins for deterministic fan-in.
- R4: checkpoint lineage + replay/idempotency contract.
- Later: locked-evaluator graph optimization / trace-mined candidates.
