# Loop/Graph compatibility saga: what happened and what it taught (2026-10-10)

Author: Claude (review and publication agent). Append-only record. It qualifies,
and does not rewrite, the earlier closure records it links to.
Companion: [lockstep pinning protocol](LOCKSTEP_PINNING_PROTOCOL_2026-10-09.md).

## Outcome

All four planned pull requests reached `main`.

| Repo | PR | Result |
|---|---|---|
| perpetua-core | #8 | merged as `04759a5` (tree-identical to reviewed `b9b4477`) |
| Perpetua-Tools | #430 | merged |
| orama-system | #388 | merged |
| oramasys | #23 | merged as `fe8d39a`; production and candidate Core pin both `04759a5`; CI green on 3.11 and 3.12 |

Two docs-only link follow-ups (Orama #389, PT #431) were open and green when
this was written. The agent could not merge; the operator owned every merge.

## Timeline in one paragraph

Design record and ADRs (D-LG-1 ownership split, D-LG-4 Pydantic AI bridge)
were written first. Four PRs went up. A revision-4 delta review found two
blocking defects (exporter `path_map` restricted advisory `declared_targets`;
`budget_exhausted` returned a delta instead of stopping the run) and three
smaller ones (framework-family imports, missing `editables` in the oracle lock,
unpicklable gap errors). The author's local fixes were unpublished, so they were
recreated from review threads, harmonized, and pushed once per branch. Merges
then happened in the planned order, the Oramasys production pin moved from
`8dde861` to the merged Core SHA, and stale PR-branch links were rewritten to
`main`.

## Lessons (new; earlier ones stay as written)

1. **Advisory metadata must stay advisory.** An exporter that turns
   `declared_targets` into a restrictive route map changes behaviour. Admit every
   compiled node plus END, as the native scheduler does. A test must route to an
   undeclared target or it proves nothing.
2. **A "termination" that returns normally is not a termination.** Budget
   exhaustion has to end the run (non-resumable structural interrupt), and the
   test needs a downstream node that must not run. A last-node test passes
   either way.
3. **Reproduce before reporting.** Each blocking finding was reproduced against
   pinned real frameworks first (B1, B2, S3). Reports that say "verified by
   running" carry more weight than reading the diff.
4. **Local fixes that are not on any remote do not exist for a reviewer.**
   Check every head and pull ref before assuming a claimed fix is published.
   When recreating, say so, and prefer discarding the unpublished local commit
   over pushing both.
5. **Family-wide import rules.** Match exact roots or `family_` prefixes, not a
   fixed list, and keep AST scan, tripwire and metadata check consistent.
6. **Editable installs under `--no-build-isolation` need the build backend's
   helpers pinned** (`editables` for hatchling) in the lock.
7. **Verify which dependency a test actually imported.** A framework-free venv
   was still importing an older Core checkout; the pass count alone looked fine.
   Print the module path.
8. **Merge-tense and link rot.** Links to PR branches break when the branch is
   deleted at merge. Rewrite them to `main` in a follow-up at merge time, and
   update nearby prose ("unmerged") in the same change.
9. **PR-body guards are part of CI.** PT requires a `## Summary` heading and the
   template sections; a body without them fails a check and draws a bot warning.
   Open PRs through the REST API with a full template body.
10. **Merge authority is a boundary, not an obstacle.** The permission check
    blocked agent merges ("Merge Without Review") and even some read-only state
    probes. The right response was one attempt, then stop, state exactly what
    was needed, and not retry or route around it. The goal check kept reporting
    "not satisfied" for dozens of turns; repeating the same short status was
    correct, and the operator's merge ended it. Prefer one clear handoff message
    over repeated re-checks that cannot change the outcome.
11. **Foreign pushes happen.** The operator's agent pushed to a branch the
    agent had opened. Fetch before pushing and use an expected-head lease.
12. **Bot rate limits are not findings.** Review-limit notices need no action;
    a finding marked "addressed in <sha>" needs none either.

## Security invariant observed

No private identity, address, credential, device or workstation literal was
written into tracked content. Records name categories only.

## Pointers

- Earlier closure: [revision 4 closure](LOOP_GRAPH_REVISION4_CLOSURE_2026-10-09.md)
- Follow-up review: [review follow-up](LOOP_GRAPH_COMPATIBILITY_REVIEW_FOLLOWUP_2026-10-09.md)
