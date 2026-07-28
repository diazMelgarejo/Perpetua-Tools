# Periscope dual-pedigree mirrors and reanchor record

**Date:** 2026-07-28  
**Status:** completed recovery; preserve as operational evidence  
**Scope:** `diazMelgarejo/periscope` branch topology and the 2026-07-28
post-expunge ancestry repair

## Canonical three-branch model

| Branch | Role | Upstream / integration contract |
| --- | --- | --- |
| `main` | mirror only | Must remain tree-identical to `latentsignal-org/periscope` `main`; it is not an agent PR target. |
| `agentsview` | mirror only | Must remain tree-identical to `kenn-io/agentsview` `main`; the upstream repository was previously named `wesm/agentsview`. |
| `merged` | integrative build line | Has both mirror tips in its ancestry and carries the preserved Periscope/fork work tree. All agent PRs target this branch. |

Sources that establish this doctrine:

- `orama-system/docs/reference/periscope-cursor-repo-rules.md` § Branch model
- `orama-system/docs/v2/21-periscope-l4-glass.md`
- `periscope/docs/ARCHITECTURE.md`
- `.agent/memory/working/WORKSPACE_PR_BASE_BRANCHES_2026-07-28.md`

## Observed state before recovery

These are evidence, not a generic claim about Git's normal ancestry:

| Probe | Result |
| --- | --- |
| `origin/main` vs `latentsignal-org/periscope` `main` | tree-identical at `852b8e381ead918dc70e64c25233c124b8ecb5e1` |
| `origin/agentsview` vs `kenn-io/agentsview` `main` | stale at `234d7a24c9cbc6606d445e3f364e6e69c3ea5e27`; upstream tip was `6c3317ad69eb1383928833dda006957a7a2d1f0d` |
| old `origin/merged` | correct content but broken post-expunge ancestry at `34fec05d5bef356da9655df0f39a9f1fe53ae8ca` |
| shared historical graph point | `5f9e809fb1a69c762f6c0ae4e3d3c2db504897af`; do not use it as a rewrite-health verdict |

Tree-twin probes found:

- `9ef7a74af7f38f4a9f9b73b230b6b1e424336a3a` has the same tree as
  current Periscope mirror `852b8e3`.
- `47ca74c675c7292490c903f8b4497875f8267faa` has the same tree as the
  pre-sync agentsview lineage point `22cf1394`; it was not a substitute for
  the current `kenn-io` tip.

The ordinary single-base `rebase --onto` probe conflicted immediately because
`merged` integrates two independently evolved pedigrees. That failure was
expected evidence that this was not Case B single-lineage reanchor work.

## Executed recovery

Preserved remote backup tags before each force update:

| Tag | Preserved ref |
| --- | --- |
| `backup/pre-reanchor-agentsview-20260728-015854` | `234d7a24c9cbc6606d445e3f364e6e69c3ea5e27` |
| `backup/pre-reanchor-merged-20260728-015854` | `34fec05d5bef356da9655df0f39a9f1fe53ae8ca` |

1. Force-with-lease updated `agentsview` from `234d7a2` to the verified
   `kenn-io/agentsview` mirror tip `6c3317a`.
2. Rebuilt `merged` from the current `main` mirror. An `ours` merge recorded
   `main` and `agentsview` as the two parents, then `read-tree` restored the
   exact old `merged` tree. The resulting tip is
   `6cf2f38f1223ab00121572352920edacfb73680b`.
3. Verified `tree(6cf2f38f) == tree(34fec05d)` before force-with-lease
   updating `merged`.
4. Replayed the semantic deltas for open PRs #10 and #11 onto the repaired
   `merged` base, preserving their reviewed final-tree deltas.

Post-recovery graph predicates:

```text
merge-base(origin/merged, origin/main)       = 852b8e3
merge-base(origin/merged, origin/agentsview) = 6c3317a
tree(origin/merged) == tree(backup/pre-reanchor-merged-20260728-015854)
```

## Recreate safely next time

1. Read `orama-system/bin/orama-system/skills/git-history-surgery/SKILL.md`
   and its `references/reanchor-after-rewrite.md`; do not use ahead/behind
   counts or `merge-base` alone across an expunge rewrite.
2. Fetch each upstream by its real source:

   ```bash
   git fetch https://github.com/latentsignal-org/periscope.git \
     main:refs/remotes/upstream-latentsignal/main
   git fetch https://github.com/kenn-io/agentsview.git \
     main:refs/remotes/upstream-kenn/main
   ```

3. Prove both mirror trees with `git diff --quiet`, then record exact remote
   lease SHAs with `git ls-remote --heads origin main agentsview merged`.
4. Create and push immutable backup tags for every ref that will be
   force-updated. Do not proceed without them.
5. First simulate in a disposable worktree. For a two-pedigree `merged`
   branch, do not blindly rebase one lineage onto the other:

   ```bash
   git checkout -B <probe> origin/main
   git merge -s ours --no-ff origin/agentsview -m "integrative: dual-pedigree anchor"
   git read-tree --reset -u origin/merged^{tree}
   git commit --amend -m "reanchor: restore merged tree on dual-pedigree base"
   git diff --quiet origin/merged HEAD
   git merge-base --is-ancestor origin/main HEAD
   git merge-base --is-ancestor origin/agentsview HEAD
   ```

6. Only after all three predicates pass, force-push with the recorded,
   ref-specific `--force-with-lease`.
7. Recreate every open `merged`-based PR from repaired `origin/merged` plus
   its *old-base-to-old-head tree delta*. Verify that intended final tree,
   tests, and GitHub mergeability survive. Never assume a pre-rewrite PR
   ancestry is still reviewable.
8. Run `reanchor_scan.sh` against the appropriate reference:
   `origin/merged` for PR branches, `origin/main` for the Periscope mirror
   pedigree, and `origin/agentsview` for the agentsview mirror pedigree.
   A one-commit semantic branch above its twin is expected; it is not a
   recovery failure.

## Reflection and guardrails

- A correct tree with invalid ancestry is a real operational defect: GitHub
  reviews, mergeability, and future replay depend on graph health.
- Tree identity (`%T`) answers whether content survived a rewrite. Graph
  ancestry answers whether the recovered branch can participate in the next
  merge. Both proofs are needed.
- The dual-pedigree `ours`-merge plus exact tree replay intentionally preserves
  both upstream parents without selecting either upstream's files as the
  resulting product tree.
- Do not delete or move the backup tags merely because the repair succeeds;
  they are the audit and rollback evidence.
- The rename from `wesm/agentsview` to `kenn-io/agentsview` changes the remote
  URL only. It does not change the `agentsview` mirror role.
