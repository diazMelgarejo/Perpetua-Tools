# E1 C2 Codex Review Appendix (2026-10-20)

**Document ID:** `PT-CHRONICLE-2026-10-20-E1-C2-CODEX-APPENDIX`
**Recording Agent:** `codex-reviewer`
**Parent Chronicle:** `E1_C2_SCHEMA_REVIEW_AND_MULTIAGENT_COORDINATION_CHRONICLE_2026-10-20.md`
**Layering Base:** Agnes's memory commit `04eca76d`
**Status:** additive review record; not a ratification, implementation authorization, or serving activation.

## Purpose and Scope

This appendix preserves the independent contract review that followed the parent
chronicle. It intentionally does not restate Agnes's four accepted lessons:
optional-capability collection, consumer-local acknowledgement coverage, exact
serialization claims, and retention-preserving archive migration. It records
only the separate conclusions reached while reviewing the E1 C2 documentation
stack.

The reviewed documentation was the two-layer E1 C2 split:

| Layer | Role | Review boundary |
| --- | --- | --- |
| Part 1--2 status addendum | historical/disposition metadata | may state the status of its own scope only |
| Part 3 schema amendment | proposed future contract | requires its own review and operator ratification against an exact immutable commit |

The status addendum now points to the amendment through the public stacked PR
dependency rather than treating an unratified document as if it were already
authority. The review did not activate `ORAMA_GRANT_SERVING`, authorize T3
implementation, promote pins, or create a new wire refusal code.

## Contract Findings and Corrections

### 1. Ratification Boundary Is Per Exact Document Head

A metadata-only addendum cannot ratify or authorize a dependent proposal merely
because both are reviewed together. The corrected disposition keeps Part 3
explicitly proposed, names its stack dependency, and requires a later operator
statement that identifies the exact Part 3 commit. This retains clean
historical evidence while preventing a status document from becoming a second
authority for a future schema.

### 2. Bootstrap Is a Complete Trust-Binding Operation

Signing an externally supplied digest is insufficient if the event body, issuer
key, and persisted floor are not bound to the same operation. The hardened
bootstrap contract requires all of the following:

1. Recompute the digest from canonical event bytes.
2. Require equality with the supplied digest.
3. Verify the signature against a locally trusted issuer key.
4. Persist issuer identity, key identity, version, digest, and acknowledgement
   floor atomically.
5. Treat an identical repeat as idempotent; refuse a divergent repeat without
   lowering or resetting retained state.

This makes replay behavior auditable and prevents a caller from using a valid
signature over one digest to smuggle a different event body or roll back a
checkpoint.

### 3. Cascade Authority Stops at the Issuer Boundary

The issuer can authoritatively identify dependent grants affected by its own
cascade decision. It cannot truthfully represent whether a consumer has
executed or consumed one of those grants. The schema therefore treats
`grant_ids` as issuer-authoritative affected dependencies. Consumers retain
their own dispatch and consumption gates; downstream notification, audit, and
recovery workflows may consume the issuer record without conflating it with
consumer execution state.

## Evidence and Follow-up

The three corresponding accepted lesson IDs are:

- `lesson_5fa3f57cb1fa` -- stacked-document ratification boundary.
- `lesson_49c7f5bdfd0f` -- complete anchor-bootstrap trust binding.
- `lesson_b7d5e4f79c48` -- issuer cascade authority versus consumer state.

The parent chronicle remains the source for the broader multi-agent sequence
and R1--R6 operating rules. Any later ratification must independently verify
the then-current remote PR head; this appendix is evidence of review, not a
substitute for that operator action.
