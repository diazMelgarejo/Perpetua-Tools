# R3 fan-out, reducers and joins: lockstep procedures and lessons (2026-10-10)

Author: Claude (review and publication agent). Append-only record. It extends,
and does not rewrite, the earlier records it links to.

Companions:
[lockstep pinning protocol](LOCKSTEP_PINNING_PROTOCOL_2026-10-09.md),
[Loop/Graph saga retrospective](LOOP_GRAPH_SAGA_RETROSPECTIVE_2026-10-10.md).

## Scope

The R3 work (concurrent fan-out regions, per-field reducers, joins) spans four
repositories and five pull requests, all open and unmerged when this was
written. The operator owns every merge.

| Repo | Role | PRs |
|---|---|---|
| Orama-System | planning and `docs/v2` authority; ownership registry | ownership registry and plan (D-LG-5); R3 ADR (D-LG-6, already merged into the registry branch) |
| Perpetua Core | dependency-minimal kernel | R3 mechanics: spec schema "2", reducers, joins, events, lint |
| Oramasys | code target | registry conformance tests; restrict-only reducer/join policy |
| Perpetua-Tools | evidence and memory | this record |

Boundaries held throughout: Orama holds no schema or runtime code; Core stays
dependency-minimal; LangChain, LangGraph and Pydantic AI are never dependencies;
endpoint security, generic admission and hardware belong to their own owners.

## Procedures (apply to any multi-repo lockstep stack)

### 1. Order and roles

1. Design record and ADR first (what the feature means), then the kernel
   change, then the downstream policy change, then the pin promotion with the
   registry flip. Never promote a production pin before upstream merges.
2. The production dependency pin stays on the last merged upstream commit.
   The candidate lane uses an immutable commit SHA as a test-only overlay.
3. The candidate lane sets a require-flag in CI so the dependent test module
   cannot be silently skipped there. The production lane skips that module with
   an explicit module-level skip, never an import error.
4. The ownership registry (planned vs implemented) and its downstream snapshot
   change together, in one reviewed step, with the pinned digest.

### 2. Per-change loop

1. Fetch before every push. Fetch refs one at a time: a single missing ref
   aborts a multi-ref fetch and a chained push then silently never runs.
2. Push each branch once per logical batch. Use an expected-head lease when
   rewriting.
3. After any upstream fix, update the candidate SHA in the downstream branch,
   re-run the candidate lane, and re-check CI on both heads.
4. Bind every review reply to the exact fixing SHA, then resolve the thread.
5. Re-read the PR head before replying "fixed in <sha>": the operator or
   another agent may have pushed since.

### 3. Cross-PR conflict check (not just file overlap)

Disjoint file lists do not mean no conflict. Before saying two PRs are
independent, merge both into a scratch branch and run the cross-cutting tests
(conformance, registry, snapshot, digest). In this stack, a planned-fields gate
in one PR failed when the other PR added those fields to code. Resolve by
flipping the registry entries in the same reviewed step, or by profile-qualified
registry files, never by weakening the gate.

### 4. Review-thread handling without GraphQL

Use the REST API only. Reply with the comment replies endpoint. Resolve and
unresolve threads through the host's review-thread routes, not GraphQL. A bot
that marks a finding "addressed in <sha>" needs no further action.

### 5. Notification triage

| Notification | Action |
|---|---|
| Rate-limit, skipped-review, own reply, check suite green | none |
| Finding, failing check, foreign commit on a watched branch | verify, fix, reply |
| Merged | stop watching; do not reopen or recreate |
| Merge-order or authority question | report once; do not retry blocked merges |

### 6. Environment

Scratch virtual environments can vanish between turns. Rebuild with the test
extras the suite needs, and put every peer repository on the import path. Print
the imported module path to confirm which checkout a test used. Failures caused
only by an absent optional owner package are environment failures, not code
failures; say so and rely on CI for those files.

### 7. Docs gates

Prose lines obey the repository line-length lint (tables are exempt). Check
`length > 100` outside tables before pushing documentation.

## Lessons (new; earlier ones stay as written)

1. **File-disjoint is not conflict-free.** Run the combined conformance tests on
   a scratch merge before reporting independence.
2. **Planned-field gates make premature code fail by design.** Plan the registry
   flip with the code, or qualify the registry by profile.
3. **Canonicalization must not hide invalid input.** Dropping an implied default
   (here the default `all` join) is safe only for a valid declaration. Validate
   first, so orphan and duplicate declarations still reach lint.
4. **Add a field, then find every reconstruction site.** A new observation field
   was dropped by the plugin copy of the observation. Grep for each place the
   type is rebuilt and test delivery end to end.
5. **Isolate concurrent inputs.** Each fan-out branch receives its own deep copy
   of the snapshot; a join that admits nothing must refuse like every other join.
6. **Reviewers' commits are not the head.** Bots review a commit; operators and
   other agents keep pushing. Re-read heads and CI before claiming state.
7. **Pin the candidate, not the branch.** Candidate overlays use immutable SHAs
   and must follow each upstream fix; a stale candidate tests old code.
8. **Binding contracts for callables.** Spec records a stable reference derived
   from the bound callable; Core never imports a callable from a string.
9. **State what checkpoint events mean.** Only events after the commit carry
   committed state; pre-commit events do not.

## Open items at time of writing

- Merge order for the operator: registry/plan PR, then the Core PR, then the
  Oramasys policy PR; the pin promotion and registry flip follow the Core merge.
- Re-pin the Oramasys candidate lane to the final Core head after the Core PR
  settles.
- Update the integrated hand-off plan for R3.

## Security invariant observed

No private identity, address, credential, device or workstation literal was
written into tracked content. Records name categories only.
