# commit-clean merge-aware TDD procedure (2026-07-29)

Canonical for orama-system, Perpetua-Tools, AlphaClaw, and periscope git guard scripts.

## Policy sources

- orama `docs/TDD.md` — pre-code and pre-commit checklists
- orama `docs/wiki/12-cursor-cloud-commit-attribution.md` — mandatory `git add` → `verify-staged-for-commit` → `commit-clean` sequence
- orama `bin/orama-system/afrp/failure-modes.md` — empty-commit / unstaged-edit failure mode (2026-07-29)
- ECC `tdd-workflow` skill — tests before implementation; smallest failing test first

## Canonical TDD loop for `scripts/git/*`

1. **RED** — extend `scripts/git/commit_clean_test.sh` with the smallest scenario that fails on current `commit-clean.sh` (merge parents, MERGE_HEAD cleanup, trap hygiene, etc.).
2. **Run** — `bash scripts/git/commit_clean_test.sh` must fail for the right reason.
3. **GREEN** — implement the minimal fix in `scripts/git/commit-clean.sh` (or the test harness when the bug is test isolation).
4. **Run** — full harness green; `bash scripts/git/verify-git-guards.sh` passes.
5. **Sync** — edit canonical copy in **orama-system** `scripts/git/`, then `bash scripts/git/sync-attribution-guard-scripts.sh <target-repo>` to every sibling repo.
6. **Commit** — always `git add <paths>` → `verify-staged-for-commit.sh` → `commit-clean.sh` (never raw `git commit` on cloud agents).

## Merge-commit recipe (history-preserving synthesis)

```bash
git merge <other> --no-commit --no-ff
# path overlays / read-tree as needed
git add -- <intended paths>
bash scripts/git/verify-staged-for-commit.sh
bash scripts/git/commit-clean.sh -m "merge: ..."
# commit-clean auto-detects MERGE_HEAD parents; clears MERGE_HEAD/MERGE_MODE/MERGE_MSG
```

## Test harness rules (commit_clean_test.sh)

- EXIT trap: `${merge_tmp:+"$merge_tmp"}` / `${octopus_tmp:+"$octopus_tmp"}` — never pass empty args to `rm -rf`.
- After a fabricated `MERGE_HEAD` scenario (e.g. `--amend` test), **clear** `MERGE_HEAD`, `MERGE_MODE`, `MERGE_MSG` before the next merge setup.
- Merge setup must **assert success** and `MERGE_HEAD` presence — do not swallow merge failures with `|| true`.
- `commit-clean.sh` parent branch: key off `${#parents[@]}` not `${#commit_tree_args[@]}`.

## PR stack (2026-07-29)

| Repo | Branch | PR |
|------|--------|-----|
| orama-system | `cursor/commit-clean-merge-aware-f559` | #239 |
| Perpetua-Tools | `cursor/commit-clean-merge-aware-f559` | (this branch) |
| AlphaClaw | `cursor/commit-clean-merge-aware-f559` | #19 |
| periscope | `cursor/commit-clean-merge-aware-f559` | #34 |
