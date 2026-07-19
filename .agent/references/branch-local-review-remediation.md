# Branch-Local Review Remediation

Use this card whenever a review, CI failure, security finding, or agent handoff belongs to a pull request branch.

## Core invariant

**A review belongs to the branch that received it.** Preserve the lineage:

```text
review → reviewed branch → remediation commits → CI → merge → main
```

Do not transplant review-specific fixes onto `main` or an unrelated branch before the reviewed branch merges.

For coordination-board work, **the board row must also identify the source
line**. "Same board" and "same repo" are not enough: each worktree has its own
checked-out branch and file state. Before any write, resolve and record
`source_ref` plus `expected_base_sha`, then work from a fresh worktree at that
exact base.

## Why

Moving a valid fix to the wrong branch creates mutually incompatible histories, invalidates review provenance, multiplies conflicts, and makes agents repair coordination damage instead of the original defect.

## Required workflow

1. Resolve the reviewed PR and exact head branch.
2. For board/GossipBus jobs, write or verify the board row's `source_ref` and `expected_base_sha`.
3. Create a fresh worktree from that exact source; verify `git rev-parse HEAD` equals the expected base before editing.
4. Refresh from that head before every write; never rely on a cached blob SHA after another agent commits.
5. Cluster findings by shared invariant and owning abstraction.
6. Inspect each owning file once where possible.
7. Fix the abstraction, not each symptom.
8. Add focused regression tests for the invariant.
9. Keep `main` unchanged until the branch passes review and merges.
10. If a fix was accidentally applied elsewhere:
   - restore the unintended branch to its previous content;
   - replay the fix on the reviewed branch;
   - document the branch-ownership failure in memory.

## Pattern-level remediation

Group findings into contracts such as:

- persistence sanitization;
- crash-consistent lifecycle transitions;
- explicit encoding and timestamp normalization;
- authenticated ordering/equivocation;
- atomic database state plus event persistence;
- branch ownership and review provenance.

A single owning-boundary fix should protect all current and future call sites.

## Multi-agent rules

- One task has one owning branch until merge.
- One board row has one source ref and one expected base SHA before writes.
- Board state is shared; checked-out files are not. Do not work from the primary checkout just because it is the same repo.
- Agents may read other branches but may not move review fixes across branches without explicit operator direction.
- Announce file ownership before editing shared files.
- Re-fetch a file after any concurrent branch advance.
- Never overwrite a newer implementation with stale full-file content.
- Use one integrator for final conflict harmonization.
- Synthesize valid behaviors; never use wholesale `ours` or `theirs` resolution.

## Frugality rules

- Search exact symbols before broad reads.
- Fetch each owning file once per stable head.
- Batch related findings into one cohesive commit.
- Stop re-checking findings already proven fixed by current branch content and tests.

## Cross-skill application

- **Agent methodology:** apply before delegating parallel work or assigning branch ownership.
- **Code review:** bind every finding to the reviewed branch and classify by shared invariant.
- **AutoResearchers:** each researcher records its branch, task claim, evidence, and handoff; research outputs do not mutate integration branches directly.
- **Git discipline/history surgery:** preserve review lineage and use tree/content evidence before rebase, reset, or force operations.
- **Oramasys method:** use Context Immersion, integrative synthesis, TDD, and verification-before-done.

## Completion gate

A remediation is complete only when:

- all findings have a disposition: fixed, superseded by a deeper fix, or rejected with evidence;
- regression tests cover each shared invariant;
- the reviewed branch is mergeable;
- CI is green;
- no review-only change leaked onto another branch;
- the durable lesson and cross-skill references are recorded.
