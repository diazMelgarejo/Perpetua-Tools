# Claude-Desktop-LLM provider-native observability doctrine — 2026-08-29

## Purpose

Record the corrected cross-repository architecture rule for
`diazMelgarejo/Claude-Desktop-LLM`, `oramasys/agate`, Orama planning, and
Perpetua migration work so future agents do not infer an architecture rewrite
from the decision to exclude OpenTelemetry.

## Canonical rule

OpenTelemetry is explicitly out of scope for Claude-Desktop-LLM **because
observability should target Ollama and LM Studio directly through their native
runtime/provider surfaces**.

This is an observability implementation decision only.

It MUST NOT be interpreted as a reason to simplify, replace, or remove the
canonical Claude-Desktop-LLM architecture.

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

Provider-native runtime/model evidence attaches at the two provider/runtime
boundaries.

## Observability authority

Primary evidence sources are the native Ollama and LM Studio runtime/provider
surfaces, including the subset actually required by the product:

- runtime/model health and availability;
- loaded-model state;
- model lifecycle/load state where exposed;
- request outcome and provider errors;
- native usage/timing information where exposed;
- local compute/runtime state relevant to diagnosis.

An optional normalized diagnostic projection may exist above those sources.

An optional redacted local JSONL/audit record may exist as secondary evidence.

Neither is the source observability authority.

Explicitly out of scope:

```text
OpenTelemetry SDK
OTLP exporter
Collector topology
generic telemetry backend requirement
```

PT's OpenTelemetry implementation remains valid for PT. It is a reference for
redaction/evidence boundaries, not a stack to cargo-cult into
Claude-Desktop-LLM.

## MCP v2 sequencing gate

MCP v2 design/migration for Claude-Desktop-LLM is blocked and unscheduled until:

1. Orama and Perpetua v2 migration into the `oramasys/*` repository family is
   complete;
2. authority handoffs are explicit;
3. target integration contracts are merged and authoritative.

No speculative compatibility shim should be added before this gate opens.

## Agate relationship

`oramasys/agate` is the cold-local-metal hardware capability, affinity,
model-fit, routing, and hard placement/resource-constraint authority.

It is MHS-convergent, not presently MHS-conformant while Anthropic's Model
Hardware Standard remains a research preview.

Claude-Desktop-LLM is the conceptual runtime companion:

```text
Agate
  where may/should the model run?
        |
        v
Claude-Desktop-LLM
  how is the selected local runtime operated?
        |
   +----+----+
   |         |
Ollama   LM Studio
```

Neither repository should absorb the other's authority.

## Storage-plan correction

The prepared Phase-1 Claude-Desktop-LLM patch, not the stale ASCII-only plan
regex, is the current implementation authority for local storage names.

It permits ordinary spaces, Unicode, and internal dots while rejecting
separators, control characters, Windows-reserved names, trailing dot/space, and
path escape. It also verifies that the resolved candidate file's parent equals
the resolved intended storage directory.

Do not regress the implementation to
`^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$` merely to match an older planning document.

## Governance lesson

```text
technology exclusion != architecture deletion
provider-native observability != provider-contract deletion
secondary JSONL evidence != observability authority
MCP v2 deferred/blocked != rejected forever
MHS convergence != current MHS conformance
```

When multiple planning documents disagree, back-propagate the latest explicit
correction into the older documents or mark them superseded. Do not leave
partially contradictory plans co-authoritative.

## Three-day remediation ledger — 2026-08-27 through 2026-08-29

The recurring lesson across the latest Orama, Perpetua, Agate, and
Claude-Desktop-LLM reviews is:

> **Fail closed at authority boundaries, and make documentation say exactly what
> the runtime enforces.**

Future agents MUST analyze a whole review round before editing, cluster findings
by root cause, fix each affected file once, commit cohesive failure classes, and
push once per repository. Do not treat each inline comment as an independent
patch if several comments share one underlying contract.

### Exact-head review discipline

Before remediation:

1. fetch the PR's exact current head;
2. read all review submissions and unresolved threads;
3. verify every finding against that current head;
4. classify each as live, already fixed, superseded, or documentation-only;
5. do not manufacture duplicate changes for already-resolved findings.

After remediation:

1. re-fetch the exact head;
2. inspect fresh review-thread state and CI separately;
3. do not claim CI passed when checks are pending or absent;
4. absence of workflow runs is not success;
5. never resolve a review thread unless the implementation or authoritative
   documentation actually contains the fix.

### Perpetua-core state isolation and CI hardening

The merged `oramasys/perpetua-core` remediation established two concrete rules:

- `PerpetuaState.merge()` requires **both** `deep=True` and
  `deepcopy(delta)`. The first isolates inherited nested mutable state; the
  second isolates caller-owned mutable values supplied in the update delta.
  These are separate aliasing hazards and neither substitutes for the other.
- GitHub Actions checkout uses `persist-credentials: false`; do not regress CI
  jobs to a credential-bearing checkout when the job only needs read access.

Review findings that request these changes are stale if current code already
contains them. Verify before touching the repository.

### Orama MiniGraph contract harmonization

The reconciliation work repeatedly exposed drift between architecture records,
examples, plans, and executable contracts. The stable method is to define one
contract and force all references to project from it.

Current invariants:

- there is one scheduler/traversal truth, not competing public scheduler seams;
- trusted rich observations and sanitized public events are distinct surfaces;
- plugin fan-out must drain one observation stream and deliver observations in
  deterministic registration order;
- callback settlement semantics must be explicit: synchronous and asynchronous
  callbacks are both supported only when returned awaitables are inspected and
  awaited before delivery is considered complete;
- state examples must use the same two-layer copy contract as executable
  `PerpetuaState.merge()`: `model_copy(update=deepcopy(delta), deep=True)`;
- complete-observation claims must match the actual plugin callback surface;
- evaluator/verification policy and dynamic-routing policy belong above the
  execution kernel; MiniGraph executes concrete nodes/edges and does not own
  success policy;
- current whole-delta merge behavior MUST NOT be documented as if future typed
  reducers, deterministic parallel joins, or last-write-wins prevention already
  exist.

When a reference document describes an R3/R4/R5 target, mark it as planned; do
not phrase future guarantees as current runtime behavior.

### Agate authority and readiness fail-closed rule

Agate owns hardware facts, model fit/affinity, placement policy, and
host/accelerator readiness. It does **not** own provider health, loaded-model
state, provider lifecycle, or provider-specific runtime availability; those stay
behind Claude-Desktop-LLM or another provider adapter.

Readiness is hard placement evidence:

- missing readiness => insufficient evidence => deny placement;
- stale readiness => insufficient evidence => deny placement;
- unavailable readiness => deny placement;
- `--ignore-affinity` may bypass Agate affinity enforcement, including a GGUF
  `NEVER` verdict where the RFC allows it, but MUST NOT bypass memory/VRAM fit,
  required backend presence, host/accelerator readiness, or provider-runtime
  health checks.

Boundary tests should cover missing, stale, and unavailable readiness both with
and without the affinity override.

### Claude-Desktop-LLM endpoint and tool boundaries

The modernization review hardened several fail-closed boundaries:

- loopback provider endpoints may use HTTP; non-loopback endpoints require
  explicit remote opt-in, host allowlisting, and HTTPS;
- endpoint-validation/DNS work must honor the same abort deadline as the
  provider request;
- DNS/IP pinning is required for hostname use; redirect hops are independently
  revalidated;
- a hostname that is not itself loopback MUST NOT gain loopback privileges just
  because DNS resolves it to `127.0.0.0/8`, `::1`, or an IPv4-mapped loopback
  address. Treat that as an SSRF boundary violation and deny it before remote
  allowlist/HTTPS policy can grant access;
- only an **omitted** provider selector may fall back to `activeProvider`.
  Explicit values other than `ollama` or `lmstudio` must be rejected for every
  provider-selecting tool before dispatch or mutation;
- request deadlines remain active through JSON body consumption, not merely
  until headers arrive;
- Ollama model-pull streaming has a bounded deadline and must not hang forever;
- arbitrary internal/provider `Error.message` values are not public MCP error
  text; only explicitly approved safe error classes expose details;
- Windows reserved device basenames remain reserved even when the caller adds an
  extension, e.g. `CON.txt` or `LPT1.md`;
- advertised JSON schemas are not authorization or runtime validation by
  themselves. Enforce security-sensitive values inside the handler/policy
  boundary too.

### Markdown/documentation convergence

Markdown lint fixes are not merely cosmetic when docs are the architecture
contract. Rewrap or add fenced-block languages without changing semantics, then
re-check the entire affected older-doc set because concurrent force-updates can
reintroduce broader Markdownlint failures after a narrower fix landed.

Do not silently change architecture while solving lint.

### Repository-write and merge discipline

`save`, `sync`, `update`, `fix`, `complete`, `commit`, or `push` do **not** mean
merge. **Never merge unless the user explicitly instructs "merge".**

For multi-file remediation when the user requires one push per repository:

- construct logical commits first using Git data operations;
- update the branch ref once after the final commit;
- do not fall back to one Contents-API commit/push per file if that violates the
  requested push discipline;
- if connector permissions block Git-object creation, prepare an exact-head
  apply-ready patch and report the blocker rather than claiming the repository
  was updated.

### Cross-repo unifying invariant

Use this decision test whenever architecture, security, and documentation
intersect:

```text
What layer owns the fact or decision?
        |
        v
Is evidence current and sufficient?
        |
   no --+--> deny / defer / remain unknown
        |
       yes
        v
Does the runtime enforce the documented rule at the same boundary?
        |
   no --+--> fix implementation or narrow documentation
        |
       yes
        v
Expose only the projection appropriate to the consumer
```

This applies equally to hardware readiness, endpoint authorization, provider
selection, state isolation, observation fan-out, effect policy, and future
GraphSpec validation.

## Cross-repository evidence

- `oramasys/agate` PR #1: MHS/local-metal positioning and corrected observability
  wording.
- `diazMelgarejo/orama-system` PR #333: cross-repo authority clarification and
  MiniGraph reconciliation.
- `oramasys/perpetua-core` PR #1 / merged `main`: state-isolation and CI checkout
  hardening.
- `diazMelgarejo/Claude-Desktop-LLM` PR #1: canonical TypeScript modernization,
  endpoint hardening, provider deadlines, handler validation, and public-error
  boundaries.
- Claude-Desktop-LLM Phase-1 patch based on
  `fix/dependabot-6-vulnerable-packages@cdadfb7fdde03c5df3d8a4bbf654cb6f6d69da59`.
- 2026-08-29 systematic and `/autoplan` reviews reconciled to this doctrine.

## Retrieval cues

Recall this memory when working on:

- Claude-Desktop-LLM modernization;
- Ollama or LM Studio observability;
- endpoint/SSRF policy or provider selection;
- OpenTelemetry scope decisions;
- Agate / MHS convergence and hardware readiness;
- MCP v2 sequencing;
- provider-contract architecture;
- MiniGraph state/observer/reducer contracts;
- PT observability unbundling;
- CodeRabbit review remediation;
- exact-head CI/review verification;
- contradictory modernization-plan documents;
- multi-file commit/push sequencing.
