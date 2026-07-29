# Periscope agentsview+periscope — history-preserving synthesis update (2026-07-29)

**Status:** integration branch rebased to history-preserving merge  
**Branch:** `cursor/agentsview-plus-periscope-f559`  
**PR:** [#29](https://github.com/diazMelgarejo/periscope/pull/29)

---

## Policy correction (user mandate)

> All history from all repos merged together must be preserved as much as possible,
> minimize synthetic commits, reuse real historical SHA, conflict resolution in favor
> of implementation plans.

> **Everyday rule still applies elsewhere:** Five-pass matryoshka planning (simulate → classify → plan) remains the normal doctrine for AutoResearch mutations and usual daily code dev. The two-parent merge + `read-tree` overlay below is an **extraordinary exemption** for dual-pedigree public-repo history — never routine practice.

### What changed

| Approach | Verdict |
|----------|---------|
| `synthesis(pass1..5)` synthetic commits on integration branch | **Abandoned** — archived on `cursor/agentsview-plus-periscope-synthetic-pass-f559` |
| Two-parent `git merge` + `read-tree` + Layer overlay | **Adopted** — commit `32d3c281` |

### Merge commit ancestry

```
32d3c281 merge: synthesize purified+PR26 onto merged (history-preserving)
├── 12d23c2e origin/merged (parent 1 — Periscope fork)
└── ff8cd5b3 origin/cursor/agentsview-purified-onto-kenn-f559 (parent 2 — kenn-io + PR #26)
```

All 76 commits on `merged` and 25 commits on `purified` remain reachable with **original SHAs**.

### Tree resolution

1. Base tree = purified (`read-tree` from `ff8cd5b3^{tree}`)
2. Overlay from merged (ARCHITECTURE.md Layer 2+3):
   - `internal/summarize/`, `internal/llm/`
   - `frontend/src/lib/components/context/`
   - `scripts/install*`, `scripts/release.sh`, `scripts/sync-upstream.sh`, dev scripts
   - `jetbrains-plugin/`, `README.md`, `CLAUDE.md`, `AGENTS.md`
   - `.claude/`, `.agents/`, `.codex/` (ECC superset)
3. `CGO_ENABLED=1 go build -tags fts5 ./cmd/periscope` → **pass**

### Lessons graduated

- `lesson_566891328e34` — five-pass matryoshka planning (simulate, classify, plan); "never monolithic" = no bulk manual conflict resolution in one session — **everyday rule**
- `lesson_d8ef5aaa6bf8` — **unusual exemption only:** two-parent merge + read-tree overlay when dual-pedigree SHA preservation is mandatory; never synthetic replay on integration branch

---

## Key principles — do and don't (going forward)

### Do

| Principle | Rationale |
|-----------|-----------|
| **Two-parent `git merge`** when unifying `merged` and `purified` lines | Preserves every original SHA on both sides; graph stays reviewable |
| **`read-tree` purified base + overlay `PERISCOPE_OWNED` from `merged`** | Upstream-modernized tree builds; Layer 2+3 Periscope identity survives |
| **Classify conflicts by matryoshka layer** (`docs/ARCHITECTURE.md`) | 735 symmetric conflicts decompose by ownership, not by "pick a winner" |
| **Merge PR #26 onto purified first**, then synthesize onto `merged` | Correct sequencing: upstream stack lands on modernization line before fork graft |
| **Append PR bodies only** | Never replace upstream stack descriptions |
| **`git add` → `verify-staged-for-commit` → `commit-clean`** on periscope | Blocks message-only synthetic commits |
| **Keep `cursor/agentsview-modernization-3way-f559` as bad-example reference** | Documents what not to do (synthetic SHA replay) |
| **Experiment A (`merged` base) for production**; Experiment B probe only | ARCHITECTURE.md canonical branch is `merged` |
| **Graduate lessons to PT `.agent`** after integrative merges | `lesson_566891328e34`, `lesson_d8ef5aaa6bf8`, `lesson_c4e8f12a9b3d` |

### Don't

| Anti-pattern | Why |
|--------------|-----|
| **Synthetic `synthesis(passN)` replay commits on integration branch** | Replays trees under new SHAs; violates never-synthesize-SHAs policy |
| **Replay upstream kenn-io commits under new SHAs** (PR #17 pattern) | 769 synthetic commits, ancient merge-base, unusable review graph |
| **Monolithic `-X ours/theirs` on whole trees** | Amputates one side's valid intent |
| **Monolithic merge of 700+ conflicts in one session** | Use layer classification first; merge commit + overlay second |
| **Force-merge stale synthesis branches wholesale** | Reset to fresh base; replay harmonized path-scoped delta only |
| **Ship Experiment B** (`purified` ← `merged`) to production | Higher effort; fights fork identity; probe only |
| **Replace PR summaries** when appending CI/synthesis notes | Upstream descriptions are canonical context |
| **Delete bad-example branches** | `cursor/agentsview-modernization-3way-f559` is curriculum |

### Canonical merge recipe (Experiment A)

```bash
git checkout cursor/agentsview-plus-periscope-f559   # from origin/merged
git merge origin/cursor/agentsview-purified-onto-kenn-f559 --no-commit --no-ff
git read-tree --reset -u $(git rev-parse origin/cursor/agentsview-purified-onto-kenn-f559^{tree})
git checkout HEAD -- internal/summarize internal/llm \
  frontend/src/lib/components/context \
  scripts/install.sh scripts/install.ps1 scripts/install_test.sh scripts/release.sh \
  scripts/sync-upstream.sh scripts/desktop-dev.ps1 scripts/dev-backend-build.sh scripts/e2e-server.sh \
  jetbrains-plugin README.md CLAUDE.md AGENTS.md .claude .agents .codex
git status --porcelain   # require no unrelated changes
git add -- internal/summarize internal/llm \
  frontend/src/lib/components/context \
  scripts/install.sh scripts/install.ps1 scripts/install_test.sh scripts/release.sh \
  scripts/sync-upstream.sh scripts/desktop-dev.ps1 scripts/dev-backend-build.sh scripts/e2e-server.sh \
  jetbrains-plugin README.md CLAUDE.md AGENTS.md .claude .agents .codex
bash scripts/git/verify-staged-for-commit.sh
bash scripts/git/commit-clean.sh -m "merge: synthesize purified+PR26 onto merged (history-preserving)"
# commit-clean auto-detects MERGE_HEAD and retains all merge parents (no trailing git commit)
CGO_ENABLED=1 go build -tags fts5 ./cmd/periscope
```

---

## Cross-references

| Doc | Path |
|-----|------|
| Purified integration / never synthesize SHAs | [PERISCOPE_MODERNIZATION_PURIFIED_INTEGRATION_2026-07-29.md](./PERISCOPE_MODERNIZATION_PURIFIED_INTEGRATION_2026-07-29.md) |
| Prior synthesis experiment notes | [PERISCOPE_AGENTSVIEW_PLUS_SYNTHESIS_2026-07-29.md](./PERISCOPE_AGENTSVIEW_PLUS_SYNTHESIS_2026-07-29.md) |
| In-repo merge runbook | `periscope/docs/synthesis/HISTORY_PRESERVING_MERGE.md` |

---

## Next

- [ ] CI on PR #29 (`732720c3`)
- [ ] Append PR body only (do not replace upstream summary)
- [ ] Experiment B (#28) remains probe — do not merge
