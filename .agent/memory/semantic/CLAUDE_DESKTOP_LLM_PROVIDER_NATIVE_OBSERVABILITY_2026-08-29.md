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

## Cross-repository evidence

- `oramasys/agate` PR #1: MHS/local-metal positioning and corrected observability
  wording.
- `diazMelgarejo/orama-system` PR #333: cross-repo authority clarification.
- Claude-Desktop-LLM Phase-1 patch based on
  `fix/dependabot-6-vulnerable-packages@cdadfb7fdde03c5df3d8a4bbf654cb6f6d69da59`.
- 2026-08-29 systematic and `/autoplan` reviews reconciled to this doctrine.

## Retrieval cues

Recall this memory when working on:

- Claude-Desktop-LLM modernization;
- Ollama or LM Studio observability;
- OpenTelemetry scope decisions;
- Agate / MHS convergence;
- MCP v2 sequencing;
- provider-contract architecture;
- PT observability unbundling;
- contradictory modernization-plan documents.
