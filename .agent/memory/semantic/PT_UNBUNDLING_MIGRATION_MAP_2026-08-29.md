# Perpetua-Tools unbundling migration map — 2026-08-29

## Purpose

Perpetua-Tools currently acts as an integration monorepo for concerns that should
not remain permanently co-owned by one runtime package. This record defines how
those capabilities migrate into `perpetua-core`, existing oramasys repositories,
and future satellite modules without a big-bang rewrite.

The rule is:

> Unbundle by stable capability contract and authority boundary, not by file
> location and not by copying everything into `perpetua-core`.

## Existing destination repositories

These repositories exist today:

```text
oramasys/perpetua-core
oramasys/oramasys
oramasys/agate
diazMelgarejo/orama-system
diazMelgarejo/Perpetua-Tools
```

Any additional satellite name below is a conceptual module boundary first.
Creating a standalone repository is a later decision based on dependency graph,
release cadence, ownership, and deployment needs.

## 1. `oramasys/perpetua-core`

Own only universal, dependency-minimal mechanics:

- `PerpetuaState`;
- `MiniGraph` and `CompiledGraph` execution;
- START/END and route semantics;
- `GraphEvent` and `GraphObservation`;
- generic `GraphPlugin` fan-out;
- generic interrupt, streaming, subgraph, and ToolNode mechanics;
- generic tool-schema derivation/validation;
- generic checkpoint plugin interface/persistence abstraction;
- future generic reducers/joins after R3 is specified.

Do NOT migrate into core:

- provider clients;
- HTTP/API servers;
- endpoint allow/deny policy;
- hardware routing policy;
- telemetry exporters;
- long-term memory stores;
- network discovery/membership;
- evaluation/experiment policy;
- application-specific approvals or cost policy.

Kernel test:

> If a capability needs to know which provider, workstation, tenant, policy,
> telemetry backend, fleet, or product is in use, it is almost certainly not a
> core kernel primitive.

## 2. `diazMelgarejo/orama-system`

Own specification and methodology authority:

- `GraphSpec`, `NodeSpec`, `EdgeSpec`;
- compiler/lint/version selection;
- topology classification;
- graph budgets and capability declarations;
- effect classification and approval policy;
- sandbox requirements;
- runtime outcome policy;
- verification/evaluator contracts;
- golden-dataset methodology;
- Karpathy March-of-Nines doctrine;
- Foundry evaluation/routing policy placement;
- Swarm/CrewAI/AutoGen pattern compilation guidance;
- optimizer experiment governance;
- migration and architecture records.

Canonical separation:

```text
mutator != evaluator
```

`orama-system` may target `perpetua-core`; core MUST NOT import upward from it.

## 3. `oramasys/oramasys`

Own application/service composition when the v2 application layer is ready:

- API/service entry points;
- approved GraphSpec consumption;
- application workflows;
- user-facing run/session APIs;
- integration composition of core + memory + telemetry + policy + adapters;
- deployment-specific defaults.

The application can depend on satellites. Satellites and core must not depend on
application code.

## 4. `oramasys/agate`

Own hardware capability and affinity contracts:

- machine/model capability declarations;
- hardware-tier compatibility;
- model/hardware affinity schemas;
- capability-based routing constraints;
- hardware discovery contract where it is part of affinity authority.

PT components such as model registry/transport and frugality routing must be
split by concern: the hardware-affinity facts belong in Agate, while provider
transport and application cost policy remain separate.

## 5. Memory satellite boundary

Current relevant PT surfaces include:

```text
.agent/memory/
orchestrator/memory_store.py
orchestrator/memory_embed.py
orchestrator/memory_rrf.py
orchestrator/memory_node.py
orchestrator/memory_governance.py
.agent/harness/salience.py
```

Target architecture:

```text
repo-local .agent knowledge
        |
        v
reusable memory engine
  episodic persistence
  semantic lesson store
  candidate graduation/rejection
  retrieval/ranking/RRF
  embeddings
  provenance/governance
        |
        v
optional storage/index adapters
```

Important boundary:

- `.agent` files remain repo-local portable knowledge and operator state;
- reusable memory algorithms/storage code may become a satellite package;
- rendered `LESSONS.md` remains derived, not a hand-edited source of truth;
- append-only historical records remain append-only through migration;
- no migration may rewrite prior lessons merely to fit a new storage format.

A future standalone repo/package name such as `perpetua-memory` is provisional,
not yet an existing repository.

## 6. Observability satellite boundary

Current PT surfaces include the observability stack landed in PRs #367–#372,
plus:

```text
src/observability/
orchestrator/audit_log.py
orchestrator/redaction.py
orchestrator/provenance.py
orchestrator/periscope_adapter.py
```

Target contract:

```text
runtime evidence
  -> privacy classification/redaction
  -> typed DomainObservation
  -> local durable/audit sink and/or optional exporter adapters
```

Keep separate:

```text
perpetua-core
  structural GraphEvent/GraphObservation generation

observability module
  redaction, typed domain observations, lifecycle, OTel projection

network/security module
  endpoint validation, DNS pinning, proxy isolation
```

Exporter details MUST NOT migrate into graph scheduling.

A future `perpetua-observability` repository/package is provisional.

## 7. Coordination / mesh satellite boundary

Current relevant PT surfaces include:

```text
orchestrator/gossip_bus.py
orchestrator/lan_gossip_bridge.py
orchestrator/lan_discovery.py
orchestrator/membership.py
orchestrator/heartbeat_monitor.py
orchestrator/peer_record.py
orchestrator/fleet_topology.py
orchestrator/witness_quorum.py
orchestrator/equivocation.py
orchestrator/monotonic_gate.py
orchestrator/state_transition_manager.py
orchestrator/coordination/
orchestrator/mesh_auth.py
```

These form a coherent coordination/mesh family:

- membership/discovery;
- liveness;
- event gossip/replication;
- monotonic peer-state observation;
- quorum/equivocation evidence;
- coordination bias/echo-loop observation;
- mesh authentication.

They are not MiniGraph kernel concerns. Graph/application layers may consume them
through explicit interfaces.

Potential future repo/package names such as `perpetua-mesh` or
`perpetua-coordination` are provisional until the internal contracts are split
and tested.

## 8. Endpoint/network security boundary

Current inputs include:

```text
packages/endpoint-policy
packages/net_utils
SSRF fetch policy and safe transport helpers
egress/pf enforcement and verifiers
control-plane authentication
mesh authentication
key/secret helpers
```

Target principle:

> Endpoint authorization is a reusable security contract; provider clients and
> graph nodes consume it, but do not redefine it.

Separate policy from transport:

- authorization/classification decides whether a destination is allowed;
- transport enforces DNS pinning, redirect/proxy/TLS rules;
- application policy decides which capabilities a run may request.

Do not merge private-LAN model endpoint policy and public-internet fetch policy
into one ambiguous allowlist. They intentionally protect opposite threat models.

A dedicated security/policy satellite may emerge, but `packages/endpoint-policy`
is already a useful transitional package boundary.

## 9. Provider and agent adapters

Current inputs include:

```text
packages/alphaclaw-adapter
packages/alphaclaw-mcp
packages/local-agents
packages/mcpb-agents
orchestrator/alphaclaw_manager.py
orchestrator/alphaclaw_tls_proxy.py
orchestrator/openclaw_skill_resolver.py
orchestrator/perplexity_client.py
orchestrator/periscope_adapter.py
orchestrator/orama_mcp_client.py
orchestrator/orama_bridge.py
orchestrator/backend_resolver.py
orchestrator/model_transport.py
orchestrator/worker_registry.py
orchestrator/spawn_reconciliation.py
```

Adapters depend inward on stable contracts. Stable contracts MUST NOT import
adapters.

Recommended shape:

```text
core/public contracts
       ^
       |
adapter package
       ^
       |
application composition
```

Provider authentication, retry policy, wire formats, and vendor-specific model
metadata remain adapter concerns.

## 10. Research/evaluator boundary

Current PT inputs include:

```text
orchestrator/autoresearch_bridge.py
orchestrator/tier5_budget.py
orchestrator/tier5_execution.py
orchestrator/tiered_pipeline.py
```

Do not place research mutation and acceptance logic together in core.

Target split:

- reusable provider/research adapters -> adapter satellite;
- candidate generation/search mechanics -> research/optimization module;
- acceptance metrics/evaluator contracts -> `orama-system` authority;
- execution of a verification node -> ordinary core graph mechanics.

The evaluator remains independent from whatever mutates the candidate.

## 11. PT agent harness / operations boundary

Current inputs include:

```text
.agent/harness/
.agent/loops/ci-sweeper.json
.agent/loops/daily-triage.json
.agent/loops/pr-babysitter.json
.agent/loops/constraints.json
scripts/review/
orchestrator/ecc_tools_sync.py
```

These are operational-agent infrastructure:

- tool hooks;
- context/salience management;
- CI/review babysitting;
- repository hygiene;
- memory reflection/recall orchestration;
- cross-repo sync operations.

They may consume core, memory, observability, and Git/provider adapters. They do
not define graph-kernel semantics.

## 12. Application-control-plane boundary

Current PT inputs include:

```text
orchestrator/control_plane.py
orchestrator/control_plane_asgi.py
orchestrator/control_plane_auth.py
orchestrator/fastapi_app.py
orchestrator/supervisor.py
orchestrator/agent_tracker.py
orchestrator/display_state.py
orchestrator/onboarding.py
```

These are application/service composition candidates for `oramasys/oramasys` or
an application-specific service module, not `perpetua-core`.

## 13. Strangler migration algorithm

For each capability cluster:

1. inventory files, imports, tests, schemas, persistent formats, APIs, CLIs, and
   consumers;
2. identify the current authoritative implementation and every mirror;
3. add/retain contract tests that describe behavior before movement;
4. define the destination public interface without changing behavior;
5. implement/move behind that interface;
6. dual-run or differential-test legacy/new paths where safe;
7. migrate consumers incrementally;
8. verify exact parity and failure behavior;
9. announce the new authority and a sunset version/date/condition;
10. remove legacy writable copies only after no consumer depends on them;
11. record provenance and any semantic change in PT `.agent` and the owning
    repository's ADR/plan.

## 14. Non-negotiable migration invariants

- No big-bang copy of PT into `perpetua-core`.
- No provider/network/storage dependency in the core scheduler.
- No silent dual writable sources of truth.
- Temporary mirrors name their authority and sunset condition.
- Historical memory remains append-only.
- Security policy remains fail-closed while representations are consolidated.
- `mutator != evaluator` remains true after every module split.
- Core never imports upward from policy/application repositories.
- Every semantic move is accompanied by regression/contract evidence.

## 15. Immediate next migration sequence

After the current MiniGraph PRs merge:

1. finish R2.5 plugin criticality/backpressure contract;
2. implement R3 reducers/joins;
3. specify R4 durable deterministic resume and effect identity;
4. implement/version R5 GraphSpec in `orama-system`;
5. freeze R6 evaluator contracts;
6. inventory PT module dependency edges cluster-by-cluster;
7. choose the first low-risk extraction with existing package boundaries;
8. run a strangler migration and use it as the template for later satellites.

Good first extraction candidates are capabilities already partly isolated under
`packages/`, because their import and test boundaries are easier to measure than
large `orchestrator/` modules. The final ordering still depends on an explicit
dependency-graph inventory rather than filename intuition.

## Related memory

Read with:

- `WEEKLY_RECONCILIATION_2026-08-23_TO_2026-08-29.md`;
- `MINIGRAPH_OBSERVER_PATTERN_RECONCILIATION_2026-08-27.md`;
- `MINIGRAPH_MUTATION_OBSERVER_FINALIZATION_2026-08-28.md`;
- `MINIGRAPH_RESUMABILITY_FRAMING_2026-08-28.md`;
- `lesson_230c6d2c5a7e` and its related MiniGraph lessons.
