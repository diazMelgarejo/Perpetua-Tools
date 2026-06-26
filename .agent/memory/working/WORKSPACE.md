# Workspace (live task state)

Last updated: 2026-06-26 by cursor-agent (agentic-stack union-merge doc 41)

## Current task
None active. Doc 41 + install-agentic-stack.sh + memory on `main`.

## Completed 2026-06-26 — agentic-stack union-merge doctrine

| Item | Outcome | Ref |
|------|---------|-----|
| CI: `test_skill_md_has_frontmatter` | ✅ Move `<!-- lint-ignore LINT-013 -->` after frontmatter `---` | `bin/orama-system/SKILL.md` |
| CI: repo_hygiene LINT-006 | ✅ ecc-migration-rules.md — no `/Users/<name>/` literal | already clean on main; defensive rephrase |
| CodeRabbit r3480506247 | ✅ `patch_models_yml` loopback guard + `LM_STUDIO_WIN_ENDPOINT` regex fix | `scripts/discover.py` |
| discover hash/runtime split | ✅ documented in DECISIONS; lessons `lesson_0314ada4d630`, `lesson_e7d62d7a5ed9` | PR #108 review |
| agentic-stack union-merge doc 41 | ✅ orama `docs/v2/41-*`; PT `install-agentic-stack.sh` | lessons `9a8236d2f51f`, `959ddd42ff01` |
| orama PR #108 CI + vendor move | ✅ prior session `b4f0e4b` / `d13cd57` | see below |

## Completed 2026-06-26 — orama PR #108 closeout + agentic-stack vendor (prior)

### orama-system PR #107

| Commit | What |
|--------|------|
| `e898d41` | Wire Hermes to PT hardware policy SSoT; pt-hardware-policy skill |
| `f3cd6e5` | workspace-path-resolution.md; platform/windows paths |
| `ee4bf80` | Coauthor guard; start.sh env discovery; AGY save-first |

### Integration invariant (AFRP)

One policy file → one API → one CLI → launcher gates on each harness.

## Next session start

1. `python .agent/tools/recall.py "discover hash runtime IP split"`
2. `python .agent/tools/recall.py "agentic-stack vendor submodule"`
3. `bash scripts/git/agentic-stack-submodule-sync.sh status`
4. Verify orama CI green on main after push
