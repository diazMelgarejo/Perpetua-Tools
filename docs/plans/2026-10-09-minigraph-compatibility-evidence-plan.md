# MiniGraph compatibility evidence plan

**Status:** v1 evidence plan; compatibility direction confirmed on 2026-10-09
**Cross-repository authority:** `orama-system/docs/v2/57-minigraph-final-reconciliation.md`

**Revision 3 canonical corrections:**
[Orama execution index](https://github.com/diazMelgarejo/orama-system/blob/docs/loop-graph-compatibility-r3/docs/v2/references/loop-graph-compatibility-2026-10-09/README.md).
These records are in the coordinated open Orama PR branch, not yet merged.
Original rev2 documents and ADRs are preserved there; PT does not fork them.

## Purpose

Perpetua-Tools owns v1 runtime telemetry, memory governance, and the evidence
needed to keep cross-repository claims honest. This plan records the evidence
rules for a future MiniGraph/LangChain/LangGraph compatibility program; it adds
no framework dependency and changes no runtime behavior.

## Claim discipline

Use these terms precisely:

| Claim | Required evidence |
| --- | --- |
| Framework-shaped adapter | Method/signature inspection only; no compatibility claim |
| Interoperable | Real framework-object integration tests pass for pinned versions |
| Supported surface | Every named symbol has an oracle fixture and passes it |
| Replacement-compatible | Unchanged upstream-importing caller fixtures pass after installation |
| Best-effort parity | Pinned public API evidence with policy refusals and implementation gaps separately disclosed |

Never infer a completed compatibility row from a matching final state alone.
Record the lockfile, interpreter, platform, installed artifacts, fixture hash,
candidate commit, upstream commit/version, command, and raw outcome for each
run. Keep raw logs and concrete workstation paths/topology local-only. Track
sanitized summaries and digests; document every permitted normalization. Public
events and their schemas must be compared with causal partial order where
upstream permits nondeterminism, not merely final state or total routing order.

## Required evidence classes

- Invocation: inputs, outputs, schemas, kwargs/config, invalid inputs, errors.
- Composition: both LCEL pipe directions with real framework objects.
- Streaming: first-event timing, incremental delivery, public event schema,
  cancellation and backpressure.
- Batch: per-input configuration, concurrency limits, ordering, cancellation,
  partial failure.
- Graph execution: reducers, joins, same-superstep visibility, dynamic sends,
  recursion limits, and conflict behavior.
- Recovery: thread/checkpoint lineage, interrupts, resume, crashes before and
  after external effects, provider reconciliation, and authorization after
  resume.
- Packaging: clean install, public import paths, metadata, and no accidental
  dependency leakage into normal v1 packages.

## Effect and loop evidence

One logical external operation needs a stable operation identity across retries.
An attempt counter is evidence about retries, never the idempotency key. Bind
the operation identity to the effect kind and canonical request digest; reject a
different request under a reused identity. When a crash leaves remote completion
unknown, reconcile with the provider or use its idempotency facility before any
retry. A local ledger entry by itself is insufficient.

Track loop bounds and authorization as runtime-owned invariants. A model can
propose a counter or route; it cannot authorize an effect or bypass a monotonic
limit. Capture the decision evidence without logging sensitive state/deltas in
the public event projection.

## Cross-repository handoff

PT records the evidence and lessons. Orama `docs/v2` owns the design records;
new facade/bridges belong in `oramasys/oramasys`, subject to ownership ADR approval.
Perpetua Core owns the neutral execution mechanics. A planned adapter must cite
the exact Core and Orama revisions it tests. Append superseding records for
changed conclusions; preserve earlier lessons and their dates.

Before declaring a row complete, run the corresponding Orama acceptance gate,
attach PT evidence, and request review.

## User clarification and historical reconciliation

On 2026-10-09 the user confirmed complete external LangChain/LangGraph API parity
through a compatibility layer, together with interoperability for callers that
already use those frameworks. Normal installations remain framework-free.
Detect a caller-installed framework lazily at the compatibility boundary and
select a supported translation bridge without changing the authoritative
scheduler. V2 has no deployed users constraining its internal redesign.

Record absent, supported-installed, unsupported-installed, broken-installed,
and mixed-object cases. Presence alone is not evidence that a version works.
No automatic installation or import hijacking follows from detection. Preserve
the same behavioral contracts in the native facade and real-framework bridge.

The current exclusions in Orama doc 57 are unfinished capabilities, not a
permanent reduction of the full parity goal. The uploaded ADR's test-only
framework restriction is superseded for caller-installed LangChain/LangGraph
bridges. Its default dependency prohibition remains. PT's earlier observer and
Pydantic AI pattern records remain historical evidence; this clarification does
not authorize Pydantic AI runtime adoption or dependencies from v1 into v2.

## Resolved enforcement and HITL policy

The canonical [new durable approval/refusal contract](https://github.com/diazMelgarejo/orama-system/blob/docs/loop-graph-compatibility-r3/docs/v2/references/2026-10-09-compatibility-refusal-hitl-contract.md)
and revision 3 resolutions govern this section. The historical description below
is an acceptance requirement, not an existing mechanism. Until the full durable
vertical slice is implemented, overrides remain denied/pending.
Both v0.x and v1.x upstream releases need separate oracle evidence. Pydantic AI
remains native-pattern adoption; a production agent bridge is deferred.

The user clarified later on 2026-10-09: apply ALL existing hardware,
authorization, and egress rules; upstream parity is always BEST EFFORT. Execute
automatically when allowed. Document every refusal and require human operator
review before any exception or policy change that enables the blocked operation.
This later instruction qualifies the earlier full-parity aspiration.

Capture operation/request identity, upstream API/version, policy revision,
returned denial rule IDs/reasons, expected upstream behavior, remediation, and
HITL state. Preserve refusal, operator approval/rejection, authorized change,
revalidation, and execution outcome as linked append-only evidence. Export only
sanitized evidence. A policy refusal is a successful enforcement outcome, but
never an ordinary upstream-parity pass.

Bind approval to authenticated operator identity, exact operation/request digest,
policy revision, scope, expiry, and use limits. Revalidate all applicable gates
before execution, on resume, and when relevant targets change. Missing, expired,
revoked, rejected, or out-of-scope approval leaves the operation blocked/pending.
No agent/caller self-approval, global bypass, or silent fallback is permitted.

Any blocked parity operation may be escalated for review. An override uses an
existing authorized policy exception/change path. Hardware infeasibility,
invalid authentication, or a rule with no exception requires remediation or a
separately authorized design change; operator approval cannot replace the
checks. Noninteractive runs remain denied/pending without indefinite blocking.

Add evidence cases for valid narrow exceptions, multiple independent denials,
expiry/revocation, changed request/target, replayed approval, and recovery after
approval. This document records a planned contract; it does not implement HITL
or change v1 runtime behavior.

## Revision 4 approved implementation and evidence

The earlier Phase-1 deferral is qualified by the operator's later approval.
[Current execution record](https://github.com/diazMelgarejo/orama-system/blob/docs/loop-graph-compatibility-r3/docs/v2/references/loop-graph-compatibility-2026-10-09/EXECUTION-REVISION-4.md)
records D-LG-1 policy binding and D-LG-4 offline bridges. No production provider
effect, runtime dependency or deferred approval is thereby permitted.

Core #8 adds an order mutation harness, exporter path-map repair and enforced
no-eager-import checks. Oramasys #23 adds ten pinned real LC/LG/Pydantic AI
offline cells, import/error semantics and independently bound policy intent.
Framework-free installation and the candidate-overlay suite are independently
verified. Full replacement and other release lines remain future evidence gates.

PT's [memory closure](../../.agent/memory/working/LOOP_GRAPH_REVISION4_CLOSURE_2026-10-09.md)
links four graduated lessons and the earlier records they qualify.
Accepted candidates and JSONL prefixes are preserved byte-for-byte.
Latest publication/CI state belongs to the exact-head PR comments, not historical
test counts. Merge order stays Orama #388 → PT #430 → Core #8 → Oramasys #23.
