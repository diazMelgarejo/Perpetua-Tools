# Periscope PR #16 integrative harmonization — path-scoped additive replay

**Date:** 2026-07-28  
**Status:** completed — head rewritten on GitHub  
**Scope:** [periscope #16](https://github.com/diazMelgarejo/periscope/pull/16) ECC bundle vs `origin/merged`; second application of PR #12 path-scoped replay technique

## Situation

| Item | Detail |
|------|--------|
| PR | [periscope #16](https://github.com/diazMelgarejo/periscope/pull/16) — `ecc-tools[bot]` auto ECC bundle |
| Base | `merged` (not `main` — mirror only) |
| Branch | `ecc-tools/periscope-1785246953340` |
| Pre-harmonization head | `f7fdef69` (11-path wholesale regen) |
| `origin/merged` | Already carries integrative ECC from PRs #10/#12 @ `44593b77` |

## Problem — wholesale PR #16 would regress merged ECC

| Regression | `origin/merged` (keep) | PR #16 wholesale (reject) |
|------------|------------------------|---------------------------|
| `SKILL.md` depth | 115 lines — full workflows | 89 lines — thinner bundle |
| Instinct naming | kebab-case aligned with frontend reality | PascalCase naming instinct (wrong) |
| `ecc-tools.json` | Security-evidence score present (14) | Score dropped to 0 |
| PR #10/#12 synthesis | Dependency workflow pair + alias notes | Amputated / missing |

Root cause matches PR #12: ECC bot regenerated the **full 11-path bundle** on a base that
already landed integrative fusion. Accepting wholesale would ping-pong history without
delivering additive intent.

## Technique — additive path-scoped replay (PR #12 card)

Canonical procedure: `.agent/memory/working/PERISCOPE_ECC_INTEGRATIVE_REPLAY_2026-07-28.md`

1. **Preserve synthesis outside the branch being rewritten**  
   Extract harmonized blobs from a disposable worktree or manual synthesis — not from the
   pre-reset PR head you are about to force-push away.

2. **Reset PR branch to fresh `origin/merged`**

   ```bash
   git fetch origin merged
   git checkout -B ecc-tools/periscope-1785246953340 origin/merged
   ```

3. **Replay only proven unique paths** (not the full 11-file bundle):

   ```text
   .agents/skills/periscope/SKILL.md
   .claude/skills/periscope/SKILL.md
   .claude/homunculus/instincts/inherited/periscope-instincts.yaml
   ```

4. **Synthesize** PR #16 insights into the merged superset — never pick one ECC run over the other.

5. **Exclude timestamp churn** — omit `.claude/ecc-tools.json` and `.claude/identity.json`
   unless intentionally harmonized (skipped on this replay).

6. **Stage before `commit-clean.sh`** — it does not `git add`; empty commits are silent failures.

7. **Single commit + `git push --force-with-lease`**

## Integrative content preserved + added

| Source | Kept / added |
|--------|----------------|
| PR #10/#12 on `merged` | Full SKILL workflows; dependency instinct pair with `## Related` cross-links; alias notes; security evidence metadata |
| PR #16 (additive only) | `periscope-arch-type-based`; `periscope-workflow-update-integration-analysis-doc` |
| Layer-2 evidence | Expanded commit-format / length evidence — `docs:` and `fix(frontend):` examples from `merged-local-rebased-on-origin`; length averages 55–68 chars |
| SKILL | `/update-integration-analysis` workflow section; agents ↔ Claude `SKILL.md` byte-identical |

### New instinct IDs (from PR #16, unioned into synthesis)

- `periscope-arch-type-based`
- `periscope-workflow-update-integration-analysis-doc`

## Result

| Field | Value |
|-------|-------|
| Branch | `ecc-tools/periscope-1785246953340` |
| Head | `0544ccf4` |
| Replaced | `f7fdef69` |
| Delta vs `merged` | +107 / −10 on 3 paths |
| Push | `git push --force-with-lease` |

## Related (not in PR #16)

| Item | Detail |
|------|--------|
| [periscope #15](https://github.com/diazMelgarejo/periscope/pull/15) | Layer-2 docs branch `merged-local-rebased-on-origin` @ `e5affe8c` — integration plan, synthesis analysis, frontend strictness; **not yet on `merged`** |
| [Perpetua-Tools #295](https://github.com/diazMelgarejo/Perpetua-Tools/pull/295) | `cursor/periscope-l4-adapter-f559` @ `fdc42b0f` — L4 adapter prune, supervisor tests, synthesis memory |

## Recreate safely

1. Read `.agent/memory/working/PERISCOPE_ECC_INTEGRATIVE_REPLAY_2026-07-28.md` and
   `orama-system/bin/orama-system/skills/git-history-surgery/references/path-scoped-pr-replay-reference-card.md`.
2. Confirm integration base: periscope → `merged`; never replay onto `main`.
3. Compare instinct IDs: **union only**; reject duplicate naming regressions (PascalCase vs kebab-case).
4. Verify SKILL mirror: `diff .agents/skills/periscope/SKILL.md .claude/skills/periscope/SKILL.md`
5. Run `bash scripts/periscope/verify-ecc-skill-mirror.sh` after harmonization (SKIP if absent).
6. Use integrative-merge **synthesize** mode — do not pick one ECC run over the other.

## Related memory

| Doc | Topic |
|-----|--------|
| `PERISCOPE_ECC_INTEGRATIVE_REPLAY_2026-07-28.md` | PR #12 path-scoped ECC fusion (first application of this technique) |
| `PERISCOPE_MERGED_LOCAL_INTEGRATIVE_SYNTHESIS_2026-07-28.md` | Layer-2 `merged-local-rebased-on-origin` synthesis |
| `WORKSPACE_PR_BASE_BRANCHES_2026-07-28.md` | Integration bases; open PR table |
| `PERISCOPE_DUAL_PEDIGREE_REANCHOR_2026-07-28.md` | Dual-pedigree reanchor discipline |
| `PERISCOPE_L4_REVALIDATION_DRAFT_2026-07-28.md` | PT adapter / openclaw_dirs contract |

## Recall

```bash
python .agent/tools/recall.py "periscope PR 16 ECC integrative harmonization path-scoped replay"
```
