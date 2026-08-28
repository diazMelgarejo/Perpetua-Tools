# Weekly reconciliation — 2026-08-23 through 2026-08-29

This record captures the major architecture, security, observability, graph, and
memory-governance work completed or materially advanced during the week. It is
an append-only semantic summary, not a replacement for the individual lessons,
PR histories, or rendered `LESSONS.md`.

## 1. PT security/reliability convergence

### PR #362 — security/reliability closure

Merged work included:

- split-identity SSRF pool pinning;
- one shared sync/async orama HTTP dispatch path;
- atomic cost-budget reservation/commit/rollback across awaited work;
- related CodeRabbit remediation and regression coverage.

The reusable principle is to close TOCTOU and policy drift at the abstraction
boundary rather than patching individual call sites.

### PRs #363–#365 — Layer-3 egress + telemetry + coordination

The stack established:

- macOS packet-filter enforcement against metadata/link-local destinations;
- explicit verification of active kernel state and rules;
- redacted egress telemetry;
- two-tier telemetry cardinality separating validation hops from one logical
  request-complete record;
- coordination bias/echo-loop detection;
- Kubernetes/Cilium/Calico egress policy support.

Security and observability were treated as one boundary: validate/authorize the
effect, then emit privacy-safe evidence about what happened.

## 2. PT observability contract stack

### PR #367 — pf ordering + egress telemetry cardinality

The verifier now checks active packet-filter state, anchor equality, and root
ruleset ordering so an earlier broad allow rule cannot silently neutralize the
security floor.

Telemetry distinguishes per-hop `egress_validation` from one
`egress_request_complete` event per logical request.

### PR #368 — typed DomainObservation + OTel exporter

PT added:

- Pydantic-v2 discriminated domain observations;
- privacy-safe typed attributes with `extra="forbid"`;
- provenance requirements;
- OpenTelemetry span/log projection;
- internal-only refusal at the network-export boundary;
- JSON schema/golden fixtures.

This established the durable rule that rich local evidence is not automatically
safe external telemetry. Redaction/classification precedes export.

### PR #369 — multi-agent bias sentinel + runbook

Coordination evidence now tracks distinct logical agents before classifying
group agreement collapse. Repetition by one agent is an echo loop, not
multi-agent groupthink.

The detector remains advisory under the Amplifier Principle: observation does
not silently become authority to cancel approvals or mutate agent state.

### PR #371 — observability trust-boundary closure

Merged fixes included:

- HTTPS-only OTLP endpoints;
- rejection of userinfo/query/fragment and non-global targets;
- DNS pinning while preserving TLS hostname/SNI validation;
- environment-proxy isolation;
- reuse of an installed OTel provider without private SDK mutation;
- stable optional-SDK behavior;
- symlink-resistant, descriptor-relative, atomic, permission-restricted local
  Periscope trajectory writes;
- exact-SHA CI/review remediation discipline.

The review-remediation lesson was reinforced: recall `.agent` first, cluster all
current review findings by root cause, fix the source abstraction, verify the
exact pushed SHA, and re-sweep review threads after every push.

### PR #372 — PT-P5 runtime producer

Merged the runtime producer vertical slice:

```text
canonical redacted EgressEvent
  -> typed DomainObservation
  -> optional official OTel exporter
```

It added recursion prevention for collector traffic, deterministic
flush/shutdown, a fixed-input smoke command, and focused runtime/exporter tests.

The exporter/provider remains optional infrastructure, not graph-kernel logic.

## 3. MiniGraph final reconciliation — Aug 26 onward

The week reconciled the shipped/canonical MiniGraph, Kimi rewrite/review, and
pre-existing v2 pattern-mining library.

Canonical execution shape became:

```text
CompiledGraph._run()
  sole scheduler
        |
        v
GraphObservation(event, state, delta?)
        |
        +-----------------------+
        |                       |
        v                       v
GraphPlugin fan-out         GraphEvent
        |                       |
        |                       v
        |                    asteps()
        v
checkpointer / tracer / audit / trusted observers
```

Key decisions:

- canonical `PerpetuaState` retained;
- invoke first, then await returned awaitables;
- strict dict-delta and route contracts;
- END is the sole normal terminal route;
- exact max-step accounting;
- structural interrupt handling stays in the kernel without plugin imports;
- `CompiledGraph` owns one traversal implementation;
- `GraphEvent` is sanitized structural evidence;
- `GraphObservation` is rich trusted in-process evidence;
- `GraphPlugin` remains live because one run can require N simultaneous
  observers;
- observer delivery symmetry is distinct from plugin action symmetry;
- `MiniGraph` remains a mutable builder and `compile()` is the detached runtime
  boundary;
- future versioned `GraphSpec` is the natural persistent/immutable value layer.

## 4. The blanket immutability rule was located and superseded

The previously hard-to-locate global rule was found in:

```text
orama-system/.cursor/rules/common-coding-style.mdc
```

with `alwaysApply: true` and the old blanket instruction to always create new
objects and never mutate existing ones.

It was superseded by a boundary-aware contract:

```text
value / versioned specification
  immutable/persistent update preferred

builder / workspace / buffer / cache
  bounded intentional local mutation allowed when it is the API contract

compiled / published / observed snapshot
  immutable after publication
```

PT's separate append-only memory rule remains valid because it protects
historical evidence rather than imposing a universal coding style.

## 5. Pattern-mining work was recovered, not discarded

The existing v2 reference library remains engineering evidence beneath the
canonical architecture.

```text
LangGraph
  checkpoints/session identity -> durable resume R4
  typed reducers               -> deterministic parallelism R3

Pydantic AI
  signature/schema extraction  -> generic ToolNode/tool-schema mechanics
  full runtime dependency      -> not adopted

Karpathy March of Nines
  deterministic harness        -> evaluator/verification doctrine

Swarm
  handoff                      -> conditional edge

CrewAI
  manager/delegation           -> GraphSpec/subgraph pattern

AutoGen
  nested conversations         -> bounded subgraph

Foundry
  evaluation                   -> evaluator layer
  isolation                    -> effect/security policy
  dynamic routing              -> GraphSpec/runtime policy
```

Canonical law retained:

```text
mutator != evaluator
```

## 6. Resumability framing was corrected without dropping the feature

Canonical classification:

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

The target is rigorous saved-boundary recovery and deterministic replay
planning, not total reversibility or time travel. External effects that already
happened require idempotency, deduplication, compensation, or explicit
human/policy reconciliation.

Feature disposition and wording disposition are separate. `deferred` means not
implemented in the current PR, not rejected.

## 7. State isolation was corrected twice

First correction:

```python
model_copy(update=delta, deep=True)
```

closed aliasing of untouched nested mutable fields inherited from the old state.

The latest core review found a second distinct leak: Pydantic applies `update`
values after the deep copy, so mutable values supplied through `delta` remained
caller-aliased.

Final required shape:

```python
model_copy(update=deepcopy(delta), deep=True)
```

On 2026-08-29 this was ported into `oramasys/perpetua-core` PR #1 at:

```text
488bc6cc440247ca86811c46ae0dd05869898324
```

with a regression proving caller-held delta mutation and merged-state mutation
cannot cross the boundary.

## 8. Core PR CI credential finding was fixed

The latest PT lesson `lesson_230c6d2c5a7e` preserved a real CodeRabbit/zizmor
finding: `actions/checkout@v4` persisted checkout credentials into later
pull-request-controlled test steps.

The same core commit `488bc6cc...` now sets:

```yaml
persist-credentials: false
```

Do not mark either latest core finding closed solely because the commit exists.
Exact-head CI and current review-thread state remain separate closure evidence.

## 9. GitHub access-method lesson

This week also exposed a tooling mistake: earlier attempts treated one failing
GitHub access path as proof the repository was inaccessible. PT memory now
requires trying an appropriate alternate read method before concluding a public
resource is unavailable.

The durable lesson is method-agnostic:

> Do not generalize a transport/tool failure into a repository-access claim.
> Verify the resource through another permitted access path when available.

## 10. Memory-governance corrections

The MiniGraph reconciliation produced several append-only memory corrections:

- observer provenance was preserved while its mechanism conclusion evolved;
- the unsupported ad-hoc `supersedes` candidate field was not edited in place;
- corrected graduated linkage uses `related_lesson_ids`;
- `LESSONS.md` remains rendered output and is not hand-edited;
- historical mistakes remain visible instead of being silently rewritten.

This week therefore reinforced a general PT rule:

```text
recall first
-> modify the source of truth
-> preserve append-only history
-> exact-SHA verify
-> re-sweep reviews
-> record the reusable lesson
```

## 11. Transition to unbundled ownership

PT currently integrates memory, telemetry, security policy, coordination/mesh,
adapters, provider clients, application orchestration, and operational-agent
harnesses in one repository.

The migration plan is now explicit: unbundle by capability contract, not by
copying PT wholesale into `perpetua-core`.

Detailed ownership and strangler migration are recorded in:

```text
.agent/memory/semantic/PT_UNBUNDLING_MIGRATION_MAP_2026-08-29.md
```

and the canonical orama-system plan:

```text
docs/v2/plans/2026-08-29-pattern-backlog-and-pt-unbundling.md
```

## Related lessons

This record should be read with:

- `lesson_230c6d2c5a7e` — latest core findings and access-method correction;
- `lesson_e0ff7f2d6717` — intermediate MiniGraph catch-up;
- `lesson_1079e8c74f20` — mutable builder correction;
- `lesson_1687311690d7` — located blanket immutability rule;
- `lesson_4a711949b3ed` — original GraphPlugin provenance/fan-out finding.
