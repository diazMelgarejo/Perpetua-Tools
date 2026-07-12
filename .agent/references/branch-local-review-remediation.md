# Branch-Local Review Remediation

Use this card whenever a review, CI failure, security finding, or agent handoff belongs to a pull request branch.

## Core invariant

**A review belongs to the branch that received it.** Preserve the lineage:

```text
review → reviewed branch → remediation commits → CI → merge → main
```

Do not transplant review-specific fixes onto `main` or an unrelated branch before the reviewed branch merges.

## Why

Moving a valid fix to the wrong branch creates mutually incompatible histories, invalidates review provenance, multiplies conflicts, and makes agents repair coordination damage instead of the original defect.

## Required workflow

1. Resolve the reviewed PR and exact head branch.
2. Refresh from that head before every write; never rely on a cached blob SHA after another agent commits.
3. Cluster findings by shared invariant and owning abstraction.
4. Inspect each owning file once where possible.
5. Fix the abstraction, not each symptom.
6. Add focused regression tests for the invariant.
7. Keep `main` unchanged until the branch passes review and merges.
8. If a fix was accidentally applied elsewhere, repair lineage before doing more feature work.

## Wrong-branch recovery

When review commits leak onto `main` or another integration branch:

1. Identify the last clean commit that is also the reviewed PR's merge base.
2. Prove the leaked content is preserved on the reviewed branch or another durable ref.
3. With explicit operator authorization, move the unintended branch ref directly to the clean commit. Do not create a chain of inverse commits when the goal is to erase an accidental unpublished lineage.
4. Compare the repaired base against the PR head.
5. Rebase only when the PR is actually behind or its parentage prevents a clean review.

Decision table:

| Compare result | Action |
| --- | --- |
| `ahead > 0`, `behind = 0`, merge base equals repaired base | Leave PR history alone; no rebase |
| `behind > 0`, no semantic overlap | Rebase or fast-forward-update the PR branch after simulation |
| `behind > 0`, overlapping valid changes | Use integrative merge/rebase: synthesize both intents and retest |
| Wrong branch contains unique work not preserved elsewhere | Create a safety ref first; never discard unique work |

**Rebase is a means, not a cleanliness ritual.** Avoid rewriting an already reviewable branch merely to remove an old merge commit when the branch is fully based on the repaired `main` and has no missing base work.

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
- Read large files by narrow ranges; do not replace them unless the complete current content is available.

## Cross-skill application

- **Agent methodology:** apply before delegating parallel work or assigning branch ownership.
- **Code review:** bind every finding to the reviewed branch and classify by shared invariant.
- **AutoResearchers:** each researcher records its branch, task claim, evidence, and handoff; research outputs do not mutate integration branches directly.
- **Git discipline/history surgery:** establish the merge base, preserve safety refs, and use measured divergence before reset, rebase, or force operations.
- **Oramasys method:** use Context Immersion, integrative synthesis, TDD, and verification-before-done.

## Completion gate

A remediation is complete only when:

- all findings have a disposition: fixed, superseded by a deeper fix, or rejected with evidence;
- regression tests cover each shared invariant;
- the reviewed branch is mergeable;
- CI is green;
- no review-only change leaked onto another branch;
- the durable lesson and cross-skill references are recorded.
