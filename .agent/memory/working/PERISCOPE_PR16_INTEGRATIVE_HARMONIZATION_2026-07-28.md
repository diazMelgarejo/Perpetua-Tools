# Periscope PR #16 integrative harmonization

**Date:** 2026-07-28  
**Status:** completed — head rewritten on GitHub  
**Scope:** [periscope #16](https://github.com/diazMelgarejo/periscope/pull/16) ECC bundle vs `origin/merged`

## Situation

| Item | Detail |
|------|--------|
| PR | #16 — `ecc-tools[bot]` auto ECC bundle |
| Base | `merged` |
| Pre-harmonization head | `f7fdef69` (11-path wholesale regen) |
| `origin/merged` | Already carries integrative ECC from PRs #10/#12 @ `44593b77` |

## Problem

Wholesale PR #16 would **regress** merged ECC:

- Thinner `SKILL.md` (89 vs 115 lines)
- Wrong naming instinct (PascalCase vs kebab-case frontend reality)
- Lost `ecc-tools.json` security-evidence score (14 → 0)
- Amputated PR #10/#12 dependency workflow pair and alias notes

## Technique — additive path-scoped replay (same as PR #12 card)

1. Reset branch to fresh `origin/merged`
2. Replay **only** harmonized unique paths — not the full 11-file bundle
3. **Synthesize** PR #16 insights into merged superset (never one-side-only)
4. Skip timestamp-only `ecc-tools.json` / `identity.json` churn unless intentional

### Paths replayed

```text
.agents/skills/periscope/SKILL.md
.claude/skills/periscope/SKILL.md
.claude/homunculus/instincts/inherited/periscope-instincts.yaml
```

## Integrative content preserved + added

| Source | Kept / added |
|--------|----------------|
| PR #10/#12 on `merged` | Full SKILL workflows, dependency instinct pair, alias notes, security evidence metadata |
| PR #16 (additive) | `periscope-arch-type-based`; `periscope-workflow-update-integration-analysis-doc` |
| Layer-2 evidence | `docs:` / `fix(frontend):` commit examples; expanded length averages (55–68 chars) |
| SKILL | `/update-integration-analysis` workflow section; mirrored agents ↔ claude byte-identical |

## Result

| Field | Value |
|-------|-------|
| Branch | `ecc-tools/periscope-1785246953340` |
| Head | `0544ccf4` |
| Delta vs `merged` | +107 / −10 on 3 paths |
| Push | `git push --force-with-lease` (replaced `f7fdef69`) |

## Related (not in this PR)

- **PR #15** / `merged-local-rebased-on-origin` @ `e5affe8c` — layer-2 docs + frontend delta; separate merge to `merged`
- **PT PR #295** @ `fdc42b0f` — periscope adapter prune + supervisor tests + synthesis memory

## Recreate safely

1. Read `.agent/memory/working/PERISCOPE_ECC_INTEGRATIVE_REPLAY_2026-07-28.md`
2. Confirm base = `merged`; never replay onto `main`
3. Compare instinct IDs: union only; reject duplicate naming regressions
4. Verify SKILL mirror: `diff .agents/skills/periscope/SKILL.md .claude/skills/periscope/SKILL.md`
