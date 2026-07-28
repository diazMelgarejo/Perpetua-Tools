# Workspace PR base branches (integration lines)

**Updated:** 2026-07-28  
**Status:** active policy — agents must not open PRs against `main` for these repos

## Rule

When pushing agent work from the cloud VM workspace, **never target `main`** for AlphaClaw or periscope. Branch from and open PRs against the integration line below.

| Repo | Integration base | Upstream `main` role | Agent branch example |
|------|------------------|----------------------|----------------------|
| [AlphaClaw](https://github.com/diazMelgarejo/AlphaClaw) | `feature/MacOS-post-install` | tracks upstream only | `cursor/attribution-guard-sync-f559` |
| [periscope](https://github.com/diazMelgarejo/periscope) | `merged` | default branch; not agent merge target | `cursor/attribution-guard-sync-f559` |
| [orama-system](https://github.com/diazMelgarejo/orama-system) | `main` (exception) | primary integration | `cursor/*-f559` |
| [Perpetua-Tools](https://github.com/diazMelgarejo/Perpetua-Tools) | `main` (exception) | primary integration | `cursor/*-f559` |

## Open PRs (2026-07-28)

| PR | Head | Base |
|----|------|------|
| [AlphaClaw #17](https://github.com/diazMelgarejo/AlphaClaw/pull/17) | `cursor/attribution-guard-sync-f559` | `feature/MacOS-post-install` |
| [periscope #7](https://github.com/diazMelgarejo/periscope/pull/7) | `cursor/attribution-guard-sync-f559` | `merged` |
| [periscope #12](https://github.com/diazMelgarejo/periscope/pull/12) | `ecc-tools/periscope-1785200140258` | `merged` (ECC integrative fusion — path-scoped replay) |

## Agent workflow

```bash
# AlphaClaw
git fetch origin feature/MacOS-post-install
git checkout -B cursor/<task>-f559 origin/feature/MacOS-post-install
# … commit …
git push -u origin cursor/<task>-f559
# PR base: feature/MacOS-post-install

# periscope
git fetch origin merged
git checkout -B cursor/<task>-f559 origin/merged
# … commit …
git push -u origin cursor/<task>-f559
# PR base: merged
```

## Related lessons

- `lesson_881de77084d5` — AlphaClaw reverse-merge flow (`feature/MacOS-post-install` never merges into `main` directly)
- `lesson_292b1558dde2` — D3 AlphaClaw `feature/MacOS-post-install` locked decision
- `.agent/references/branch-local-review-remediation.md` — review belongs to the branch that received it
- `.agent/memory/working/PERISCOPE_DUAL_PEDIGREE_REANCHOR_2026-07-28.md` — audited periscope `main` / `agentsview` / `merged` model, mirror sources, expunge-rewrite evidence, and reproducible dual-pedigree recovery
- `.agent/memory/working/PERISCOPE_AGENTSVIEW_RENAME_CATALOGUE_2026-07-28.md` — indexed agentsview→periscope rename map for upstream merges (96 files / 514 matches on merged @ 6cf2f38f)
- `.agent/memory/working/PERISCOPE_ECC_INTEGRATIVE_REPLAY_2026-07-28.md` — path-scoped PR replay for ECC fusion (PR #12 after PR #10); orama `path-scoped-pr-replay-reference-card.md`

## PR body edits

READ → backup → write before any PR description update (see orama-system CIDF `integrative-editing-examples` §1).
