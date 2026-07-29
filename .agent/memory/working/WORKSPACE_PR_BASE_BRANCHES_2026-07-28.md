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
| [periscope #12](https://github.com/diazMelgarejo/periscope/pull/12) | `ecc-tools/periscope-1785200140258` | `merged` (ECC integrative fusion — path-scoped replay @ `9e465d9c`) |
| [periscope #16](https://github.com/diazMelgarejo/periscope/pull/16) | `ecc-tools/periscope-1785246953340` | `merged` (ECC additive replay @ `0544ccf4`; replaced regressive `f7fdef69`) |
| [periscope #15](https://github.com/diazMelgarejo/periscope/pull/15) | `merged-local-rebased-on-origin` | `merged` (layer-2 docs + frontend @ `e5affe8c`; not yet on `merged`) |
| [Perpetua-Tools #295](https://github.com/diazMelgarejo/Perpetua-Tools/pull/295) | `cursor/periscope-l4-adapter-f559` | `main` (L4 `periscope_adapter` @ `fdc42b0f` + supervisor wiring) |

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
- `.agent/memory/working/PERISCOPE_L4_IMPLEMENTATION_2026-07-28.md` — L4 adapter wiring, security doc removal, lineage epic
- `.agent/memory/working/PERISCOPE_MERGED_LOCAL_INTEGRATIVE_SYNTHESIS_2026-07-28.md` — salvaged local `merged` (20 commits), layer-1 tree-twin reanchor (`merged-local-reanchored`), layer-2 integrative synthesis on `origin/merged` (`merged-local-rebased-on-origin`); tips for agents
- `.agent/memory/working/PERISCOPE_PR16_INTEGRATIVE_HARMONIZATION_2026-07-28.md` — PR #16 ECC additive path-scoped replay (second application after PR #12); regressive wholesale bundle rejected

## Published recovery branches (periscope, 2026-07-28)

| Branch | Integration role |
|--------|------------------|
| `origin/merged` | Canonical integration line (`44593b77`) |
| `origin/merged-local-reanchored` | Layer 1 — salvaged alternate history grafted onto twin `852b8e38` |
| `origin/merged-local-rebased-on-origin` | Layer 2 — harmonized delta on current `merged` (L4 docs + frontend strictness); candidate for PR to `merged` |

Do not confuse layer 1 (history artifact) with layer 2 (forward integration). See synthesis memory card above.

## PR body edits

**Append-only rule** (`lesson_3b13ab0a45d4`): never replace the original Summary with a follow-up delta.

```bash
# Backup → append → write full merged body
bash scripts/cursor/append-pr-body.sh diazMelgarejo/Perpetua-Tools 298 \
  --title "Follow-up: …" --file follow-up.md
```

`ManagePullRequest update_pr` and `gh pr edit` replace the **entire** body — pass the reconstructed original + all follow-ups, not just the new paragraph. Preserve CodeRabbit auto-generated sections below the agent zone.
