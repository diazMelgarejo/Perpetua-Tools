# Review remediation convergence — 2026-08-27 through 2026-08-29

## Purpose

Record the cross-repository fixes, failure classes, authority boundaries, and
review-remediation method established across Orama, Perpetua, Agate,
Claude-Desktop-LLM, and Perpetua-Tools during 2026-08-27 through 2026-08-29.

This is retrieval-oriented operational memory. It should help future agents
reuse the reasoning and avoid reopening already-settled architectural questions.

## Canonical review-remediation loop

Use this sequence for review-driven work:

```text
recall .agent memory first
  -> resolve exact current PR head
  -> read every requested review and current unresolved thread
  -> verify each finding against current code/docs
  -> classify valid / already fixed / outdated
  -> cluster valid findings by owning invariant
  -> fix the owning abstraction once
  -> touch each affected file once where practical
  -> add regression evidence for behavioral fixes
  -> commit by logical failure class
  -> push once per repository
  -> verify exact pushed SHA
  -> inspect CI and review state as separate gates
  -> re-sweep review threads
  -> record reusable lessons
```

Do not patch review comments mechanically one at a time when several comments
share one root cause.

Do not duplicate a fix merely because a historical review still mentions it.
Current source and current thread state decide whether work remains.

## Branch and mutation discipline

Review remediation stays on the reviewed branch until it is integrated through
the operator-approved path.

Preserve:

```text
review -> reviewed branch -> remediation commits -> CI/review -> integration
```

A request to `save`, `sync`, `update`, `fix`, `commit`, or `push` does not grant
permission to merge a pull request.

Merge only when the operator explicitly instructs a merge.

The accidental `perpetua-core` PR #1 merge during a sync-only task is a process
failure to learn from, not a precedent. Do not infer merge authorization from a
request to synchronize repositories.

## Exact-head evidence rule

A successful earlier SHA does not prove a later SHA.

Keep these gates distinct:

```text
local tests
GitHub Actions
status checks
SAST/security review
CodeRabbit review threads
mergeability
```

Never summarize them as "all green" unless the exact current head supports that
claim. Absence of workflow runs is not a passing workflow result.

## MiniGraph state isolation

`PerpetuaState.merge(delta)` requires two independent copy layers:

```python
return self.model_copy(update=deepcopy(delta), deep=True)
```

Why both are load-bearing:

- `deep=True` isolates mutable fields inherited from the previous state;
- `deepcopy(delta)` isolates caller-owned mutable values supplied in the update.

Pydantic applies update values after copying the existing model. Therefore
`deep=True` alone does not isolate nested objects passed through `delta`.

Regression evidence must prove both directions of isolation and preserve
ordinary delta application.

## MiniGraph mutation boundary

Immutability is a boundary property, not a universal ban on mutation.

```text
value / versioned specification
  immutable or persistent updates preferred

builder / workspace / buffer / cache
  intentional local mutation allowed when it is the documented API

compiled / published / observed snapshot
  immutable after publication
```

For MiniGraph:

```text
MiniGraph
  mutable construction builder
        |
        | compile()
        v
CompiledGraph
  detached execution snapshot
```

`add_node()` and `add_edge()` remain builder mutations. `compile()` is the
load-bearing topology snapshot boundary. Persistent structural sharing belongs
to future versioned `GraphSpec`, not the existing MiniGraph builder API.

## MiniGraph scheduler and observation contract

The canonical execution shape is:

```text
CompiledGraph._run()
  sole scheduler
        |
        v
GraphObservation(event, state, delta?)
        |
        +---------------------+
        |                     |
        v                     v
aobserve()               GraphEvent
rich trusted                  |
in-process pull               v
                        asteps()
                        sanitized pull
```

`GraphEvent` is control-plane-only. `GraphObservation` is trusted in-process
execution evidence.

`GraphPlugin` fan-out drains `aobserve()` once and offers every observation to
every registered plugin in deterministic registration order.

The callback contract is generic `on_observation(...)`, not a partial callback
surface that loses `edge.selected`, `interrupt`, or `done`.

Sync and async plugin callbacks are both supported by inspecting the returned
value and awaiting awaitables. Default authoritative delivery is fail-closed.

Delivery symmetry is not action symmetry: a checkpointer may persist only
`node.end` while a tracer records the complete structural sequence.

## MiniGraph post-merge drift discovered on 2026-08-29

After `oramasys/perpetua-core` PR #1 merged at:

```text
d1c0dfca12fef5df6e6b15c602e765e299279676
```

its push workflow completed successfully, but a fresh contract comparison found
that passing tests did not prove every documented invariant.

Two executable gaps remain candidates for corrective follow-up:

1. unknown routes are not rejected at route resolution; they can reach node
   lookup and fail later as `KeyError`, while the Orama contract requires
   explicit unknown-route rejection at the routing boundary;
2. plugin fan-out passes the same rich observation object to every listener.
   The top-level dataclass is frozen, but nested `PerpetuaState` collections and
   `delta` remain mutable. A mutating listener can therefore affect later
   listeners unless delivery uses detached/read-only payloads.

Current tests cover empty/non-string routes, normal fan-out, async callback
settlement, registration order, fail-closed behavior, and no-op observer parity.
They do not yet prove unknown-route boundary failure or mutating-listener
isolation.

A green workflow proves the tested implementation, not untested invariants.

## Orama architecture and documentation authority

`diazMelgarejo/orama-system` owns specification and policy above the kernel:

- `GraphSpec`, `NodeSpec`, and `EdgeSpec`;
- graph lint, validation, and version selection;
- evaluator and promotion contracts;
- effect/approval/runtime policy;
- pattern reconciliation and architecture records.

`GraphSpec` execution fails closed on validation failure.

Verification/Sentinel policy and dynamic model/agent routing belong to the Orama
policy/evaluator layer. MiniGraph executes realized nodes and routes but does not
define what counts as verified or which agent/model policy should win.

Reference documents must not keep stale body text that contradicts a corrected
reconciliation header. Fix both the status/ownership statement and the older
adaptation prose in the same pass.

## Reducer and parallelism status

Current `PerpetuaState.merge()` is a whole-delta sequential state transition. It
is not a typed reducer framework.

Do not claim current guarantees for:

- deterministic parallel fan-in;
- typed per-field reducers;
- deterministic branch-completion ordering;
- prevention of last-write-wins conflicts.

Those remain R3 targets requiring explicit reducers and joins.

## Tool-schema extraction scope

The planned lightweight docstring parser supports one documented format:
Google-style docstrings.

Do not simultaneously document Sphinx/reStructuredText `:param name:` syntax
unless support and tests are deliberately expanded. One parser contract avoids
metadata drift between implementations.

## Agate authority and readiness

`oramasys/agate` owns cold-local-metal hardware facts and placement policy:

- host and accelerator identity/capability;
- Metal/MLX, CUDA, ROCm, and CPU/RAM capability;
- memory/VRAM facts;
- model fit and affinity;
- `PREFER`, `ALLOW`, and `NEVER` placement semantics;
- host/accelerator readiness;
- hard placement/resource constraints.

Provider health, loaded-model state, provider lifecycle, and provider-specific
runtime availability remain provider-adapter authority.

Readiness is fail-closed placement evidence:

```text
missing readiness      -> deny placement
stale readiness        -> deny placement
unavailable readiness  -> deny placement
```

`--ignore-affinity` may override Agate affinity enforcement where the GGUF RFC
permits it. It must not bypass hard memory/backend/readiness constraints or
provider-runtime health checks.

Boundary tests should cover missing, stale, and unavailable readiness both with
and without affinity override.

## Claude-Desktop-LLM architecture

Excluding OpenTelemetry does not shrink the Claude-Desktop-LLM architecture.
Retain:

```text
entrypoints / MCP transport
        |
canonical TypeScript implementation
        |
canonical tool registry
        |
effect policy + endpoint policy
        |
provider contract
   /            \
Ollama adapter   LM Studio adapter
   |                 |
Ollama runtime    LM Studio runtime
```

Observability targets Ollama and LM Studio directly through their native
runtime/provider surfaces.

Do not add OpenTelemetry SDK, OTLP exporter, or Collector topology merely for
alignment with PT. Optional normalized or redacted JSONL evidence remains
secondary diagnostic/audit material.

## Claude endpoint and request hardening

The review series established these endpoint/request invariants:

- loopback endpoints are allowed by default;
- remote endpoints require explicit remote opt-in and host allowlisting;
- non-loopback endpoints require HTTPS;
- endpoint validation observes the request abort signal;
- DNS/IP is resolved once and connection-time pinned;
- redirect hops are revalidated;
- a non-loopback hostname that resolves to loopback must be rejected rather
  than inheriting loopback trust;
- explicitly supplied invalid provider names are rejected;
- only an omitted provider may fall back to `activeProvider`;
- JSON request deadlines remain active through body parsing;
- streaming model pulls have bounded deadlines;
- arbitrary provider/internal error messages are not exposed to MCP clients.

The unifying rule is identity consistency: policy trust belongs to the declared
endpoint identity plus the vetted resolved destination. A DNS answer must not
silently transform an untrusted hostname into a trusted loopback identity.

## Claude storage hardening

Storage names preserve ordinary spaces, Unicode, and internal dots while
rejecting path separators, control characters, trailing dot/space, oversized
names, path escape, and Windows reserved device basenames.

Windows reserved-name checks include extensions such as `CON.txt` and
`LPT1.md` by validating the stem before the first dot.

Do not regress to the stale ASCII-only planning regex.

## MCP v2 sequencing

Claude-Desktop-LLM MCP v2 work remains blocked and unscheduled until:

1. Orama and Perpetua v2 migration into `oramasys/*` is complete;
2. authority handoffs are explicit;
3. integration contracts are merged and authoritative.

Blocked means sequencing-gated, not rejected forever.

## Cross-repository ownership map

```text
oramasys/perpetua-core
  universal dependency-minimal execution mechanics

oramasys/agate
  cold-local-metal hardware capability/readiness/fit/placement

diazMelgarejo/orama-system
  GraphSpec/lint/evaluation/effect/runtime policy

diazMelgarejo/Claude-Desktop-LLM
  canonical local-model server/provider architecture
  Ollama + LM Studio adapters and provider-native observability

diazMelgarejo/Perpetua-Tools
  memory/telemetry/security/coordination/adapters during strangler unbundling
```

Do not move authority merely because two components are conceptually bundled.

## Documentation convergence rule

A correction is incomplete if only one of several co-authoritative records is
updated.

When reviews expose contradictory docs:

1. identify the authoritative implementation and architecture record;
2. update every live co-authoritative statement in the same remediation pass;
3. mark historical material historical or superseded instead of silently
   leaving it normative;
4. distinguish current behavior from planned R3/R4/R5 behavior;
5. link field-level contracts to tested code when implementation owns details.

Wording disposition and feature disposition are separate:

```text
technology excluded != architecture deleted
blocked/deferred != rejected
provider-native observability != provider-contract deletion
MHS convergence != current MHS conformance
```

## Related memory

Read this with:

- `WEEKLY_RECONCILIATION_2026-08-23_TO_2026-08-29.md`;
- `MINIGRAPH_MUTATION_OBSERVER_FINALIZATION_2026-08-28.md`;
- `MINIGRAPH_CORE_LATEST_REVIEW_CLOSURE_2026-08-29.md`;
- `CLAUDE_DESKTOP_LLM_PROVIDER_NATIVE_OBSERVABILITY_2026-08-29.md`;
- `PT_UNBUNDLING_MIGRATION_MAP_2026-08-29.md`;
- `BRANCH_LOCALITY_AND_REVIEW_PROVENANCE.md`.

## Retrieval cues

Recall this record for:

- CodeRabbit or security-review remediation;
- exact-SHA verification;
- MiniGraph scheduler/state/observer questions;
- Orama GraphSpec/evaluator ownership;
- Agate readiness or MHS questions;
- Claude endpoint/SSRF/provider/observability hardening;
- cross-repository authority disputes;
- documentation drift after implementation changes;
- requests to sync, push, or merge reviewed branches.
