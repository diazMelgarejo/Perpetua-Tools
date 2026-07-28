# Periscope merged-local salvage → integrative synthesis (layer 1 + layer 2)

**Date:** 2026-07-28  
**Status:** completed and published to GitHub  
**Scope:** `diazMelgarejo/periscope` — recovering a diverged local `merged` line after
`origin/merged` dual-pedigree reanchor, without replaying stale history wholesale

**Doctrine:** orama-system `integrative-merge.md` + `git-history-surgery` SKILL
(path-scoped replay, tree-twin reanchor, not ahead/behind counts)

---

## Situation (what happened)

1. Local `merged` had **20 first-parent commits** above tree twin `852b8e38` while
   `origin/merged` had moved forward **537 commits** via dual-pedigree reanchor
   (`6cf2f38f`) + integrative PRs (#10–#14).
2. A naive `git reset --hard origin/merged` **discarded the local line** unless
   salvaged from reflog first.
3. Graph metrics looked catastrophic (`596 behind / 20 ahead`) but **tree diff**
   was only **44 paths** — mostly content already on `origin/merged` under different SHAs.

---

## Published branches (recovery layers)

| Branch | SHA (tip at publish) | Role |
|--------|----------------------|------|
| `origin/merged` | `44593b77` | Canonical integrative integration line |
| `origin/merged-local-reanchored` | `bec3eeb9` | **Layer 1** — salvaged pre-reset local tip; tree-twin graft onto `852b8e38` |
| `origin/merged-local-rebased-on-origin` | `e5affe8c` | **Layer 2** — integrative synthesis on current `origin/merged` + L4 docs + frontend fixes |

Canonical clone (v2 workspace): `$OPENCLAW_ROOT/periscope` (or `$REPO_ROOT` when set) — branch `merged` tracks `origin/merged`.

**Safety tags (local):** `backup/merged-local-salvage-*`, `backup/merged-local-reanchored-*`

**Disposable worktrees used:**

- `periscope-reanchor-merged-local` — layer 1 cherry-pick replay
- `periscope-recovery-layer2` — layer 2 synthesis

---

## Layer 1 — tree-twin salvage (`merged-local-reanchored`)

### Salvage before reset

```bash
cd "${OPENCLAW_ROOT:-$REPO_ROOT}/periscope"
PRE_TIP=$(git rev-parse merged@{1})   # reflog before reset
git branch merged-local "$PRE_TIP"
git tag backup/merged-local-salvage-$(date +%Y%m%d-%H%M%S) merged-local
```

### Deepest tree twin

- **Merge-base** with `origin/merged`: `17673c28` (misleading — dual pedigree)
- **Byte-identical anchor:** `852b8e381ead918dc70e64c25233c124b8ecb5e1`
- **20 first-parent commits** above twin with **no tree match** in `origin/merged`

### Correct reanchor (NOT plain `git rebase`)

```bash
# WRONG — replays ~78 commits (merge second-parent history); conflicts immediately
git rebase --onto 852b8e38 852b8e38 merged-local

# RIGHT — first-parent cherry-pick; -m 1 for the upstream merge commit
git checkout -B merged-local-reanchored 852b8e38
for c in $(git rev-list --first-parent --reverse 852b8e38..merged-local); do
  if [ "$(git rev-list --parents -n 1 "$c" | wc -w)" -gt 2 ]; then
    git cherry-pick -m 1 "$c"
  else
    git cherry-pick "$c"
  fi
done
```

**Proof:** `tree(merged-local-reanchored) == tree(merged-local)` — byte-identical tips.

---

## Layer 2 — integrative synthesis (`merged-local-rebased-on-origin`)

### Wrong approach

- Blind `git rebase origin/merged` on layer 1 → mass conflicts on commit 1 (duplicate upstream merge).
- Cherry-picking all 19 non-merge commits → mostly empty/conflicting; `ARCHITECTURE.md` add/add.

### Right approach — harmonize, don't amputate

**Base:** `origin/merged` (superset of local tree — **0 files only on local line**).

| Mode | What | Resolution |
|------|------|------------|
| superset | ECC bundle, attribution guards, rename catalogue, cursor rules | Keep `origin/merged` |
| architecturally-correct | Desktop `sidecar("periscope")`, PR #14 | Keep origin; local `agentsview` stems = stale residue |
| union | `AGENTS.md` Cursor Cloud section | Keep origin |
| synthesize | `frontend/package.json` | `marked` in `dependencies` @ `18.0.3` + `svelte` `^5.55.9` |
| union | `docs/ARCHITECTURE.md` | Origin + L4 integration cross-link |
| additive | `docs/INTEGRATION-ORAMASYS-STACK-PLAN.md` | New |
| architecturally-correct | `App.svelte` ActivityMinimap | Remove dead block (upstream deleted component) |
| architecturally-correct | Context viz TS | Fix strictness so `svelte-check` passes |

### Layer-2 delta vs `origin/merged` (8 paths)

Docs: integration plan, synthesis analysis, ARCHITECTURE link  
Package: `marked` / `svelte` harmonization + lockfile  
Frontend: minimap removal, `ContextWindowBlocks`, `ContextTimeline` types

In-repo analysis card: `periscope/docs/INTEGRATION-SYNTHESIS-LAYER2-ANALYSIS.md`

---

## Verification gates (all passed before publish)

| Gate | Result |
|------|--------|
| `go test -tags fts5 ./...` | ✅ all packages ok (~65s) |
| `npm ci` + `npm run check` | ✅ 0 errors (4 pre-existing warnings) |
| `npm test` (vitest) | ✅ 1127 tests, 64 files (~15s) |
| `reanchor_scan.sh . origin/merged heads` | Use for branch classification, not as sole verdict |

**Insight:** Baseline `origin/merged` already had **9 svelte-check errors** with same deps;
layer 2 fixed stale minimap + context TS — do not assume docs-only branches skip frontend CI.

---

## L4 orchestration (PT hook — unchanged)

- Periscope = **L4 read-only** observability; PT owns `orchestrator/periscope_adapter.py` → OpenClaw JSONL.
- v1: optional (`PERISCOPE_AUTOSTART=0`); v2 oramasys: obligatory.
- Plan: `periscope/docs/INTEGRATION-ORAMASYS-STACK-PLAN.md`
- Revalidation draft: `.agent/memory/working/PERISCOPE_L4_REVALIDATION_DRAFT_2026-07-28.md`

---

## Tips for future agents

### Git / history

1. **Never trust ahead/behind after a rewrite** — run tree-twin scan (`reanchor_scan.sh`) and `git diff --stat` between tips.
2. **Salvage before `reset --hard`** — `git branch salvage-name merged@{1}` + backup tag.
3. **Dual-pedigree `merged` is not Case B single-lineage reanchor** — see
   `PERISCOPE_DUAL_PEDIGREE_REANCHOR_2026-07-28.md`; do not rebase one mirror onto the other blindly.
4. **Plain `git rebase` on a merge commit replays second-parent history** — use **first-parent cherry-pick** with `-m 1` for merge commits.
5. **`git cherry -v origin/merged <tip> <twin>`** lists patch-ids missing by history — not proof of missing *semantic* work after integrative reanchor.
6. **Publish recovery layers as named branches** — do not force-push over `merged`; use `merged-local-reanchored` (history artifact) vs `merged-local-rebased-on-origin` (integration candidate).

### Integrative merge

7. **Synthesize; never amputate** — when local and origin differ, classify paths by mode table (superset / union / synthesize / architecturally-correct) before editing.
8. **If local tree is subset of origin** — layer 2 is almost always "origin + thin harmonized delta", not replay of N commits.
9. **Stale rename residue** — `agentsview` binary/sidecar names on a `periscope` fork are regressions; prefer `origin/merged` for desktop/CI naming.
10. **Path-scoped replay card** applies when PR branch conflicts because base already landed overlapping content (ECC PR #12 after #10).

### Periscope repo policy

11. Agent PR **base = `merged`**, never `main` (`main` = latentsignal mirror only).
12. Canonical v2 clone path: `$OPENCLAW_ROOT/periscope` (branch `merged`).
13. After meaningful periscope changes: `go test -tags fts5 ./...` + `npm --prefix frontend run check` + `npm test`.

### Worktree hygiene

14. Use **disposable worktrees** for reanchor probes — `git worktree add ../periscope-recovery-layer2 -b <branch> <start-point>`.
15. Do not write absolute workstation paths into periscope docs (repo guard may block); use env vars and repo-relative paths.

---

## Reflection

- **Tree identity (%T) ≠ graph health** — both proofs matter; dual-pedigree repair fixed graph while preserving tree.
- **Alternate integration histories can converge to the same product tree** — the 20 local commits were a *story*, not necessarily unique *content*, once dual-pedigree reanchor landed.
- **Integrative synthesis is faster and safer than conflict archaeology** when one side is already the superset: start from `origin/merged`, diff paths, harmonize only what adds intent.
- **Frontend dead code** (`ActivityMinimap`) can linger after upstream deletes — `svelte-check` is a good gate before claiming "docs-only" PRs.

---

## Related memory

| Doc | Topic |
|-----|--------|
| `PERISCOPE_DUAL_PEDIGREE_REANCHOR_2026-07-28.md` | Dual-pedigree `ours` + `read-tree` recovery |
| `PERISCOPE_ECC_INTEGRATIVE_REPLAY_2026-07-28.md` | Path-scoped ECC fusion (PR #12) |
| `PERISCOPE_AGENTSVIEW_RENAME_CATALOGUE_2026-07-28.md` | Rename index for upstream merges |
| `PERISCOPE_L4_REVALIDATION_DRAFT_2026-07-28.md` | PT adapter / openclaw_dirs contract |
| `WORKSPACE_PR_BASE_BRANCHES_2026-07-28.md` | Integration bases for agent PRs |

## Recall

```bash
python .agent/tools/recall.py "periscope merged-local integrative synthesis tree-twin"
```
