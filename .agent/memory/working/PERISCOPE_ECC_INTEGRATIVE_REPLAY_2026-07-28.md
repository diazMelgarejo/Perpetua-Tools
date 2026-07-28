# Periscope ECC integrative replay — path-scoped PR technique

**Date:** 2026-07-28  
**Status:** completed; preserve as operational evidence  
**Scope:** periscope PR #12 ECC fusion after PR #10 merge; orama-system doctrine capture

## Situation

| Item | Detail |
|------|--------|
| PR | [periscope #12](https://github.com/diazMelgarejo/periscope/pull/12) |
| Base | `merged` (not `main` — mirror only) |
| PR #10 | Already merged ECC 11-path bundle onto `merged` @ `f4a43cd6` |
| PR #12 (before replay) | 2 commits from pre-#10 `merged` (`015cd4ef`) |
| GitHub state | `mergeable: CONFLICTING`, `mergeStateStatus: DIRTY` |

## Root cause

PR #12 stacked the **full ECC bundle add** on an integration base that had moved
forward. GitHub saw duplicate/conflicting paths. A straight merge or rebase would
have ping-ponged `main`/`merged`/branch history without delivering the intended
**harmonized synthesis** (PR #10 workflows + PR #12 dependency evidence).

## Technique — path-scoped replay on fresh integration base

1. **Preserve synthesis outside the branch being rewritten**  
   Fusion content lived in a separate disposable worktree (for example
   `$TMPDIR/periscope-ecc-fusion-review`).
   Do not extract harmonized blobs from the PR branch you are about to force-push.

2. **Reset PR branch to fresh `origin/merged`**

   ```bash
   git fetch origin merged
   git checkout -B ecc-tools/periscope-1785200140258 origin/merged
   ```

3. **Replay only proven unique paths** (not the full 11-file bundle):

   ```text
   .agents/skills/periscope/SKILL.md
   .claude/skills/periscope/SKILL.md
   .claude/homunculus/instincts/inherited/periscope-instincts.yaml
   ```

4. **Stage before `commit-clean.sh`** — it does not `git add`; empty commits are silent failures.

5. **Exclude timestamp churn** — omit `.claude/ecc-tools.json` and `.claude/identity.json`
   unless intentionally harmonized.

6. **Single commit + `git push --force-with-lease`**

## Integrative-merge content preserved

| Source | Kept in synthesis |
|--------|-------------------|
| PR #10 | Contribution/testing workflows; 15 stable instinct IDs |
| PR #12 | Dependency-update workflow; richer 4-commit evidence; 2 new instinct IDs |
| Both | Dependency instinct pair with `## Related` cross-links (different triggers) |
| Verified | Go/Svelte/Tauri architecture; colocated test layout (`*_test.go`, `*.test.ts`, `frontend/e2e/`) |
| Mirror | Agents ↔ Claude `SKILL.md` byte-identical |

## Result

| Field | Value |
|-------|-------|
| Head | `9e465d9c` |
| Commits on PR | 1 (was 2) |
| Files changed | 3 (+305 / −132) |
| GitHub | `MERGEABLE`, `CLEAN` |

## orama-system doctrine (PR #236)

Captured on `cursor/periscope-ecc-sidecar-f559`:

- `bin/orama-system/skills/git-history-surgery/references/path-scoped-pr-replay-reference-card.md`
- `bin/orama-system/skills/periscope-ecc/SKILL.md` — PR replay section
- `bin/orama-system/skills/oramasys-method/references/integrative-merge.md` — worked example
- `scripts/periscope/verify-ecc-skill-mirror.sh` — idempotent mirror probe (SKIP if absent)

## Recreate safely

1. Read `orama-system/bin/orama-system/skills/git-history-surgery/references/path-scoped-pr-replay-reference-card.md`.
2. Confirm integration base: periscope → `merged`; never replay onto `main`.
3. Run `bash scripts/periscope/verify-ecc-skill-mirror.sh` after harmonization.
4. Use integrative-merge **synthesize** mode — do not pick one ECC run over the other.

## Related memory

- `.agent/memory/working/PERISCOPE_DUAL_PEDIGREE_REANCHOR_2026-07-28.md` — dual-pedigree reanchor (different problem; same "replay paths not whole branch" discipline)
- `.agent/memory/working/WORKSPACE_PR_BASE_BRANCHES_2026-07-28.md` — periscope PRs target `merged`
- `.agent/memory/working/PERISCOPE_AGENTSVIEW_RENAME_CATALOGUE_2026-07-28.md` — rename map for upstream merges
- [orama-system PR #236](https://github.com/diazMelgarejo/orama-system/pull/236) — periscope ECC lazy sidecar
