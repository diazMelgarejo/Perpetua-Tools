# Cross-repo remediation final state — 2026-08-29

## Purpose

Record the final branch-level outcome of the 2026-08-27 through 2026-08-29
review-remediation cycle across Orama, Perpetua core, Agate,
Claude-Desktop-LLM, and Perpetua-Tools.

Read this together with
`REVIEW_REMEDIATION_CONVERGENCE_2026-08-27_TO_2026-08-29.md`.
That companion record owns the detailed reasoning and reusable method; this
record owns the final exact branch state and unresolved boundary.

## Unifying invariant

The three latest review rounds converge on one rule:

> Fail closed at authority boundaries, and make documentation say exactly what
> the runtime enforces.

Apply that rule to routing, observer ownership, hardware readiness, endpoint
identity, provider selection, state isolation, and documentation status.

A review comment is not itself the authority. Verify it against the exact
current head, identify the owning invariant, fix the abstraction once, add
regression evidence where behavior changes, and then reconcile every live
co-authoritative document.

## Orama PR 333

Repository: `diazMelgarejo/orama-system`

Branch:

```text
2026-08-27-minigraph-final-reconciliation
```

Final reviewed head for this cycle:

```text
63dc330263cc4947cc9f81a675d3d8f77e5ccb34
```

Commit-of-record:

```text
docs(v2): harmonize canonical MiniGraph authority
```

The latest six consistency findings are resolved at this head:

- plugin callbacks use one generic observation contract and await returned
  awaitables;
- `PerpetuaState.merge()` examples consistently use
  `model_copy(update=copy.deepcopy(delta), deep=True)`;
- `GraphPlugin` can receive every structural observation kind through
  `on_observation(...)`;
- Sentinel/verification and dynamic-routing policy ownership remain in the
  Orama evaluator/policy layer, not MiniGraph;
- the lightweight docstring parser is documented as Google-style only;
- typed reducers, deterministic fan-in, and last-write-wins prevention remain
  R3 targets rather than current whole-delta behavior.

The same harmonization records the post-merge core corrective branch without
claiming that branch is merged.

Exact-head evidence observed for `63dc330...`:

- CodeRabbit status: success;
- Markdown Lint: success;
- PR body anti-clobber guard: success;
- Endpoint Policy Peer Contract: success;
- PR body Summary restore: success;
- Test Suite: success;
- CI - Test & Build: success;
- Agent security scans: success.

## Perpetua-core post-merge convergence

The historical reconciliation PR merged to `main` as:

```text
d1c0dfca12fef5df6e6b15c602e765e299279676
```

A post-merge audit found two executable gaps that passing tests had not covered:

1. an unknown route could escape `_resolve_edge()` and fail later as `KeyError`;
2. observer fan-out shared mutable nested `state`/`delta` objects between
   listeners.

Corrective branch:

```text
2026-08-29-001-post-merge-convergence
```

Current corrective head recorded in this cycle:

```text
1fb26bca65afbeaafa2bd356afe824d7df070ba1
```

The branch remains **not merged**. It contains the executable corrections,
regression proof, a current post-merge convergence record, and repository-facing
documentation cleanup.

Corrections:

- unknown non-`END` routes must name a registered node and fail with `ValueError`
  at route resolution otherwise;
- each plugin receives a detached `GraphObservation` payload using a deep copy
  of state and delta;
- regression tests prove unknown-route rejection, listener isolation, and live
  final-state isolation;
- `docs/POST_MERGE_CONVERGENCE_2026-08-29.md` records the authority/status
  boundary;
- `README.md` states the cross-repository authority split rather than describing
  LLM/hardware policy as core-owned;
- `docs/PROGRESS.md` labels itself as the historical May 2026 RC-1 salvage ledger
  and points to the current convergence record.

No merge was performed. Exact-head CI/status must be checked separately before
claiming `1fb26bc...` green.

## Agate PR 1

Repository: `oramasys/agate`

Branch:

```text
2026-08-29-mhs-local-metal-alignment
```

Final reviewed head for this cycle:

```text
abf50cb2227fd18e02ad47f3b1bcbc0d471926e5
```

The readiness contract now fails closed:

```text
missing readiness      -> deny placement
stale readiness        -> deny placement
unavailable readiness  -> deny placement
```

`--ignore-affinity` cannot convert any of those states into approval. Boundary
tests are required for all three states with and without the affinity override.
Provider health and loaded-model state remain provider-adapter authority.

The latest readiness review thread is resolved and CodeRabbit status is success.
No PR-triggered workflow runs were returned for this head; that is not a CI-pass
claim.

## Claude-Desktop-LLM PR 1

Repository: `diazMelgarejo/Claude-Desktop-LLM`

Branch:

```text
2026-08-29-canonical-typescript-modernization
```

Current remote head:

```text
cb082afccb8e8242f16124bbf0e0a7645c619f0b
```

The shared provider-selection guard is fixed at this head: only an omitted
`provider` falls back to `activeProvider`; every explicitly supplied value other
than `ollama` or `lmstudio` is rejected before provider selection. Regression
coverage includes `local_llm_query`.

One current review finding remains unresolved remotely:

> A non-loopback hostname that resolves to a loopback IP must not inherit
> loopback trust.

Canonical endpoint identity rule:

```text
declared loopback identity + loopback destination
  -> eligible for local trust

non-loopback hostname + DNS result 127.0.0.0/8 or ::1
  -> reject
```

The rejection must happen before remote opt-in, host allowlisting, or HTTPS can
permit the request. Direct `localhost`, `.localhost`, and direct loopback IP
literals remain valid local identities.

A deterministic regression should inject/replace hostname resolution so an
allowlisted `https://provider.example/` resolving to `127.0.0.1` is rejected as
`non_loopback_denied`.

The GitHub integration available during this cycle can read the repository but
returns `403 Resource not accessible by integration` for Git-data writes to this
personal repository. Therefore the SSRF correction is prepared as an
apply-ready patch rather than falsely claimed as remotely synced.

CodeRabbit status on `cb082af...` is success, but the SSRF inline review thread
remains unresolved. No PR-triggered workflow runs were returned for this head.

## Perpetua-Tools memory branch

Repository: `diazMelgarejo/Perpetua-Tools`

Branch:

```text
docs/claude-desktop-llm-observability-doctrine-20260829
```

This branch contains both the detailed remediation doctrine and this final-state
record. It remains branch-only and unmerged unless the operator explicitly
orders a merge.

## Non-negotiable process rules

- `save`, `sync`, `update`, `fix`, `commit`, and `push` do not authorize merge;
- merge only on an explicit direct merge instruction;
- re-read the exact current head immediately before a write;
- stop stale writes rather than overwriting a branch that moved;
- absence of workflow runs is not a passing result;
- resolved review thread, CI success, mergeability, and local tests are distinct
  evidence classes;
- technology exclusion is not architecture deletion;
- blocked/deferred is not rejected;
- provider-native observability does not delete the provider contract;
- MHS convergence does not imply current MHS conformance.

## Retrieval cues

Recall this record for:

- final 2026-08-29 review-remediation state;
- Orama PR 333 harmonization;
- post-merge MiniGraph route/observer correction;
- Agate fail-closed readiness;
- Claude DNS-to-loopback SSRF hardening;
- provider validation;
- branch-only synchronization and no-merge discipline.
