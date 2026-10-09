# R3 registry, execution and replay review

Date: 2026-10-09 UTC / 2026-10-10 Asia/Manila.
Status: review fixes published; broad remaining-capabilities program incomplete.

## Exact publication evidence

| Repository / PR | Published head | Role |
| --- | --- | --- |
| Perpetua Core #9 | `34e4a8d22212d38d6ab100c1ad7fb2b19f56cb68` | R3 candidate; production pin unchanged |
| Orama-System #390 | `7b7f9d84e43f0709115588a95b13a78badb8369f` | Canonical ADR, qualification profiles, replay audit |
| Oramasys #25 | `48715ff237f72235d31f75238239c8f491c9951b` | Policy fixes, merged registry tests, both CI lanes |

Oramasys #24 is merged. Its registry corrections were integrated into #25 with a
real merge preserving both parent histories. Orama #391 merged into #390, not
main: its D-LG-6 ADR is present there. No PR was merged in this review.

The production Core pin remains
`04759a50c748444ff97136ea95c1e1289eac3a1a`. The candidate-only file
`requirements/compatibility-core-candidate.txt` pins the exact Core head above.
Both Oramasys workflows check out the exact Orama head above, set
`ORAMA_DOCS_V2_REGISTRY`, and compare canonical bytes with the active snapshot.

## Fixed and independently reviewed

- Core parser rejects unknown graph/node/edge/reducer/join keys that otherwise
  disappear outside canonical identity. Metadata remains the extension field.
- Policy runs structural validation before indexing reducers or joins; duplicates
  cannot conceal a forbidden earlier declaration.
- Custom folds receive detached base and contributions. Mutate-then-fail does
  not corrupt a prior observation.
- Ownership requires both Core ownership and the GraphSpec record for computes.
  Duplicate records fail before indexing. NodeSpec/EdgeSpec mutation tests fail.
- Complete producer/consumer ReducerKind and JoinKind inventories are pinned;
  missing-inventory and literal-drift mutations fail. Independent review found
  this gap after the initial fixes and confirmed the other runtime fixes.
- Candidate EdgeSpec.declared_targets is structural: it selects fanout branches.
- Earlier Greptile provenance/default-join fixes were verified, not duplicated.

## Qualification profiles and digests

Baseline bytes are preserved. Additive candidate profiles qualify the two lanes
without silently promoting schema 2 or claiming merged R3.

| Profile | SHA-256 | Meaning |
| --- | --- | --- |
| baseline | `c1bf6b519f703184745e61142f259ae8eb73d163210bb1395437f8a82c2b402f` | Preserved earlier evidence |
| policy-r3 | `7aeed7456db148383698f6df97a38632dbf72f23d411f9c773ed6cb10ab777fb` | Current policy on production schema-1 Core |
| core-r3 | `498e9383667252b841845d4dc061853adfe3e3864d976a3e2f7c8a59eea3adab` | Current policy on candidate schema-2 Core |

Canonical paths: Orama `docs/v2/references/loop-graph-compatibility-2026-10-09/`.
Snapshots: Oramasys `src/tests/fixtures/graph-ownership-registry*.json`.

## Validation and limits

- Full Core suite with external Agate fixture: 255 passed; 90.96% coverage.
- Full candidate application and actual offline framework oracles: 333 passed,
  zero skips; LangGraph 1.0.3, LangChain Core 1.0.7, Pydantic AI slim 1.0.18.
- Framework-free production-Core suite: 307 passed, one expected gated R3 skip;
  87.27% coverage. Canonical registry comparison ran rather than skipped.
- Core and application wheels build; pip check and compile smoke pass; Telos
  network-authority lint passes. Changed Orama Markdown and repository hygiene
  pass. Independent reviewer ran 63 Core and 39 consumer focused tests.
- Exact-head remote poll: Core 3.11/3.12 and all four application CI jobs green; Orama
  remaining checks in progress at publication checkpoint. Consult live checks
  before merge; a historical green run does not certify a new head.

These tests qualify supported cells, not 100% upstream drop-in replacement.
LangGraph fanout export, dynamic Send, nested regions, upstream type identity,
checkpoint wire parity and unbuffered sync streaming remain deferred.

## Replay and audit boundary

SqliteCheckpointer stores node/state snapshots, without frontier, lineage,
version identity, grants or effect reconciliation. Loading state and calling
ainvoke starts from START; earlier effects may execute again. resume_policy
MERGE/DROP changes scratchpad only, not authority or traversal status.
Idempotent declarations are intent, not provider dedupe or exactly-once proof.

R3 atomically commits a local folded delta after branches settle. It cannot undo
external effects already performed. first_success uses branch-name order after
all branches settle, not first completion. Detached provenance reaches plugin
observations, but legacy checkpoint rows do not preserve that provenance.

Durable HITL, executable artifact admission, production foreign-provider
transport, durable replay/R4 and full upstream facade replacement are not
implemented by these review fixes. Keep production foreign effects refused
until the authority, containment/transport and durable-effect slice is qualified.

## Both coordinated pairs: what changes at every lockstep update

Use the existing LOCKSTEP_PINNING_PROTOCOL_2026-10-09.md and canonical Orama
revision-2 plan. For Core/Oramasys, update the candidate SHA, oracle lock,
structural/policy profile digests, exact docs checkout and both lane evidence.
Only after reviewed Core integration and downstream/oracle revalidation may the
production pin and baseline registry advance together.

For PT/Orama, record exact peer heads, shared contract/fixture digests, canonical
docs pointer, paired tests, review-fix revisions and CI checkpoint in both
handoffs. PT remains a portable memory consumer; no Core runtime dependency is
introduced into PT. Publish the canonical Orama revision first and PT memory
last. Do not force-push or overwrite historical evidence.

## Diagnosis and next actions

The current shell had no GitHub credential helper; HTTPS push failed before
changing a ref. The authenticated GitHub connector created equivalent trees,
compared them with tested local tree hashes, and advanced each branch once with
an expected-head check and no force. This is an authentication-context difference,
not evidence that earlier pushes were fabricated. Commit SHAs differ from local
objects because the API creates its own commit metadata; file trees match.

Before merge: re-poll exact-head CI and all new review threads. Then follow the
reviewed producer/consumer promotion sequence. Implement deferred work as the
measurable gates in the canonical audit, not as assumed feature parity.

Durable lessons: lesson_5baa161852f3, lesson_0bc38d2086e0 and
lesson_d437eec0d177, graduated using the memory tools. Historical JSONL prefixes
must remain byte-identical.

[Canonical audit](https://github.com/diazMelgarejo/orama-system/blob/7b7f9d84e43f0709115588a95b13a78badb8369f/docs/v2/references/remaining-capabilities/R3-AUDIT-REPLAY-AND-COMPATIBILITY-2026-10-10.md)

