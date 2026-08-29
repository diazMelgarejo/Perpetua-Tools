# Cross-repository remediation doctrine — 2026-08-27 to 2026-08-30

## Purpose

Record the concrete fixes, review method, and architecture/security invariants
established across Orama, Perpetua, Agate, and Claude-Desktop-LLM during the
2026-08-27 through 2026-08-30 remediation cycle.

Future agents MUST use this record before reconstructing these decisions from
review comments, stale plan prose, or neighboring repositories.

## Unifying rule

The three review streams converged on one rule:

> Fail closed at authority boundaries, and make the documentation say exactly
> what the runtime enforces.

This means:

- identify which component owns each decision;
- reject unknown, stale, invalid, or unauthorised inputs at that boundary;
- do not let adjacent layers silently infer or override that decision;
- make examples, tests, plans, and review-status prose match the implementation;
- distinguish implemented, pushed, merged, deferred, blocked, and proposed;
- do not broaden architecture from a local implementation choice.

## Review-remediation procedure

For review-driven work, use this sequence:

1. recall `.agent` memory before reconstructing procedure;
2. read every requested review and current unresolved thread first;
3. re-fetch the exact current PR or branch head;
4. verify each finding against that exact head;
5. cluster findings by root cause and authority boundary;
6. fix each affected file once rather than layering comment-by-comment edits;
7. add regression evidence for the root cause, not only the reported line;
8. commit by logical failure class;
9. push the working branch once after the logical commits are prepared;
10. re-fetch exact-head checks and review threads after the push;
11. never claim CI, review, merge, or deployment status from stale evidence.

A finding already fixed on the exact head is a no-op. Do not manufacture a
second change merely to create activity.

## Merge and sync rule

`save`, `sync`, `update`, `fix`, `complete`, and `push` do NOT authorize a
merge.

A merge requires an explicit user instruction to merge.

When the user asks to sync existing working branches:

- save/commit the intended changes;
- push to the existing branch;
- leave the PR open unless an explicit merge instruction is given.

## PerpetuaState isolation

The final state-isolation rule has two independent copy layers:

```python
self.model_copy(update=deepcopy(delta), deep=True)
```

Why both are load-bearing:

- `deep=True` isolates nested mutable values inherited from the existing model;
- `deepcopy(delta)` isolates mutable values still owned by the caller because
  Pydantic applies update values after copying the model.

Future documentation MUST NOT regress to either of these incomplete forms:

```python
self.model_copy(update=delta)
self.model_copy(update=delta, deep=True)
```

The regression proof must include a caller-held nested mutable value supplied
inside `delta` and confirm later caller mutation does not change the merged
state.

## MiniGraph and observer authority

The architecture correction established these distinct surfaces:

- one private scheduler/traversal authority;
- a rich trusted in-process observation surface containing execution state and
  node delta where applicable;
- a sanitized public/control-plane event projection;
- plugin fan-out that observes one traversal rather than re-running it.

Documentation must use one scheduler and one observation contract consistently.

Plugin delivery requirements:

- every registered plugin is offered the complete ordered observation stream;
- plugin semantic filtering happens after delivery;
- synchronous and asynchronous callback results must both settle before awaited
  delivery is complete;
- default delivery is fail-closed;
- observation payloads must be detached or otherwise protected so one plugin
  cannot mutate data seen by later plugins or the live traversal;
- plugin-enabled execution must preserve final-state parity with an equivalent
  no-plugin execution.

Do not claim callback coverage for event kinds that the protocol cannot expose.
If complete-stream delivery is required, the protocol needs a generic
observation callback or an equivalent complete callback surface.

## Current reducer semantics versus R3

Current `PerpetuaState.merge()` is a whole-delta apply with isolation. It is not
an implicit typed-reducer or deterministic parallel-join system.

Therefore current behavior MUST NOT be described as guaranteeing:

- conflict-free generic parallel fan-in;
- deterministic parallel completion ordering;
- prevention of last-write-wins for conflicting fields.

Those guarantees belong to the planned R3 typed-reducer plus explicit-join
contract unless and until implemented and tested.

## Evaluation and routing ownership

MiniGraph owns execution mechanics. It does not own policy meanings such as
"verified", golden-dataset acceptance, evaluator thresholds, or dynamic agent
selection policy.

Canonical ownership:

- evaluator / verification policy: Orama evaluator or policy layer;
- GraphSpec/runtime policy: produces concrete executable routing decisions;
- MiniGraph: executes the resulting topology and execution-specific behavior.

Pattern-reference documents must not reassign verification or dynamic-routing
policy back into MiniGraph after their reconciliation headers move it upward.

## Tool-schema docstring scope

The dependency-minimal tool extraction plan supports one documented docstring
format: Google-style docstrings.

Do not document reStructuredText/Sphinx `:param name:` syntax unless support is
explicitly implemented and tested. Avoid multi-format parser scope creep.

## Agate hardware authority

Agate is the cold-local-metal hardware capability, fit, affinity, readiness, and
placement authority.

Agate owns facts such as:

- CPU/GPU/accelerator availability;
- Metal/MLX/CUDA/ROCm/CPU capability;
- RAM/VRAM and model-fit constraints;
- PREFER/ALLOW/NEVER affinity;
- host/accelerator readiness required for placement.

Claude-Desktop-LLM owns provider/runtime state such as:

- Ollama and LM Studio provider health;
- loaded-model state;
- provider lifecycle;
- provider-native runtime observations.

Readiness is a hard placement input. Missing, stale, unknown, or unavailable
host/accelerator readiness is insufficient evidence for placement and must fail
closed.

`--ignore-affinity` may override the Agate affinity verdict where the GGUF
contract permits it, but it must not bypass independent memory/VRAM fit,
backend availability, host/accelerator readiness, or provider/runtime-health
requirements.

Boundary tests must cover unknown/stale/unavailable readiness.

## Claude-Desktop-LLM architecture and observability

OpenTelemetry is out of scope for Claude-Desktop-LLM because provider-native
observability targets Ollama and LM Studio directly.

This changes only the observability implementation choice. It does NOT shrink
or replace the architecture.

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

Provider-native Ollama and LM Studio evidence is the authority. Optional
normalization or redacted JSONL is secondary evidence only.

MCP v2 remains blocked and unscheduled until Orama and Perpetua v2 migration
into `oramasys/*` is complete and the resulting authority handoffs/contracts
are merged and authoritative.

## Claude endpoint-policy hardening

The endpoint policy is local-first and fail-closed.

Required rules established during review remediation:

- only `http:` and `https:` schemes are structurally accepted;
- URL userinfo is rejected;
- direct loopback is permitted by default;
- non-loopback destinations require `ALLOW_REMOTE_LLM=1` and explicit host
  allowlisting;
- non-loopback destinations require HTTPS;
- endpoint validation and DNS resolution honor request abort/deadline signals;
- the hostname is resolved once and the connection is pinned to that vetted IP;
- redirects are bounded and each hop is revalidated;
- a non-loopback hostname that resolves to a loopback address is rejected;
- bracketed IPv6 loopback literals are normalized before `isIP()` checks;
- canonical IPv4-mapped IPv6 loopback forms are classified correctly.

The DNS-derived-loopback rule matters because an attacker-controlled hostname
must never earn loopback trust merely by resolving to `127.0.0.0/8`, `::1`, or
an equivalent mapped IPv6 representation.

## Claude provider and tool-input hardening

Explicit invalid provider values must be rejected.

Only an omitted provider may fall back to `activeProvider`.

This applies to every provider-selecting tool, not only
`switch_llm_provider`.

Other established hardening:

- `switch_llm_provider` cannot mutate state for invalid values;
- destructive tools are omitted from the advertised registry unless enabled;
- arbitrary provider/internal `Error.message` values are not exposed to MCP
  clients;
- only explicitly approved public error classes expose detail;
- Windows reserved device basenames are rejected even with extensions;
- template substitution uses literal replacement, not user-built regular
  expressions;
- JSON request deadlines remain active through response-body parsing;
- streaming model pulls have a bounded timeout/deadline.

## Claude repository authority migration

By 2026-08-30 the organization repository exists:

```text
oramasys/Claude-Desktop-LLM
```

Its `main` baseline is intended to represent the completed canonical TypeScript
modernization snapshot directly, not a merge into the historical personal
repository.

The verified baseline snapshot used for organization initialization is:

```text
cc06ed4878abf7b36c791755ef31466c70cd8ccf
```

Treat the organization repository as the forward authority once that baseline
is established and verified.

## Status vocabulary

Use these words precisely:

- `implemented`: present in code on the referenced exact head;
- `tested`: backed by the specifically cited test execution;
- `pushed`: present on a remote branch;
- `merged`: incorporated into the target branch;
- `proposed` / `in review`: not yet authoritative target-branch behavior;
- `deferred`: intended but not implemented in the current unit;
- `blocked`: intentionally prohibited until an external gate opens;
- `rejected`: explicitly not being adopted.

Do not collapse `pushed` into `merged`, `deferred` into `rejected`, or a tooling
exclusion into an architecture deletion.

## Retrieval cues

Use this memory for queries involving:

- CodeRabbit remediation;
- exact-head review closure;
- PerpetuaState merge isolation;
- MiniGraph scheduler or observer fan-out;
- GraphPlugin delivery;
- reducer R3 semantics;
- Agate readiness or `--ignore-affinity`;
- Claude endpoint policy / SSRF / provider validation;
- Claude provider-native observability;
- MCP v2 sequencing;
- `oramasys/Claude-Desktop-LLM` migration;
- sync versus merge semantics.
