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
- Wrap each `require_merge` call in `if require_merge ...; then` so scenario assertions short-circuit when setup fails (CodeRabbit PT #298 review 4812918328).
- `commit-clean.sh` parent branch: key off `${#parents[@]}` not `${#commit_tree_args[@]}`.

## What happened (session chronology — 2026-07-29)

1. **Root bug:** `commit-clean.sh` used `commit-tree` with only `HEAD^`, dropping `MERGE_HEAD` parents during history-preserving synthesis merges (PT PR #297 / periscope PR #29 context).
2. **TDD fix (orama PR #239):** Extended `commit_clean_test.sh` first, then made `commit-clean.sh` merge-aware (auto-detect `MERGE_HEAD`, N-way octopus, clear merge artifacts).
3. **CodeRabbit round 1 (#4812744637):** Trap hygiene (`${var:+"$var"}`), clear fabricated `MERGE_HEAD` between scenarios, `require_merge` helper, parent check on `parents[]`.
4. **Stale sync hazards observed:**
   - Dirty sibling checkouts (AlphaClaw on `deps-npm`, periscope on `ecc-bundle`) blocked `git checkout` — **use disposable worktrees** for cross-repo sync, not in-place checkout.
   - `REPO_ROOT=/agent/repos/AlphaClaw` in cloud env breaks `ensure_hooks_installed.sh` in other repos — **`unset REPO_ROOT` before push**.
   - Running `sync-attribution-guard-scripts.sh` on wrong branch still copies bytes but leaves git index confused — always sync inside the target PR branch worktree.
5. **AlphaClaw PR #20:** Path-scoped ECC replay onto `feature/MacOS-post-install` — integration base already had richer June ECC; harmonized delta empty; force-pushed base SHA (`04d4fc03`), GitHub auto-closed PR.
6. **CodeRabbit round 2 (PT #298, #4812918328):** `require_merge` return value must gate each scenario block — prevents misleading secondary failures when `MERGE_HEAD` was never created.

## Propagation recipe (minimum friction)

```bash
unset REPO_ROOT
# 1. Edit orama-system scripts/git/* (canonical)
bash scripts/git/commit_clean_test.sh
# 2. commit on cursor/commit-clean-merge-aware-f559
# 3. For each sibling repo:
WT=/tmp/<repo>-cc-sync && git -C <repo> worktree add -B cursor/commit-clean-merge-aware-f559 "$WT" origin/cursor/commit-clean-merge-aware-f559
bash orama-system/scripts/git/sync-attribution-guard-scripts.sh "$WT"
# commit + push from $WT; git worktree remove "$WT"
```

## PR stack (2026-07-29)

| Repo | Branch | PR |
|------|--------|-----|
| orama-system | `cursor/commit-clean-merge-aware-f559` | #239 |
| Perpetua-Tools | `cursor/commit-clean-merge-aware-f559` | #298 |
| AlphaClaw | `cursor/commit-clean-merge-aware-f559` | #19 |
| periscope | `cursor/commit-clean-merge-aware-f559` | #34 |
