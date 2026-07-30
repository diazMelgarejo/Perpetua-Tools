# Periscope AgentsView+Periscope synthesis — Experiment A decision (2026-07-29)

**Date:** 2026-07-29  
**Status:** decided — Experiment A is production path; Experiment B is probe only  
**Scope:** periscope `merged` integration; purified upstream replay + PR #26 stack synthesis

---

## Decision

| Item | Outcome |
|------|---------|
| [PR #29](https://github.com/diazMelgarejo/periscope/pull/29) `cursor/agentsview-plus-periscope-f559` | **Production path (Experiment A)** — synthesize purified+PR26 onto `merged` |
| [PR #28](https://github.com/diazMelgarejo/periscope/pull/28) `cursor/purified-plus-merged-f559` | **Probe only** — merge `merged` fork into purified+PR26; do not ship |
| [PR #26](https://github.com/diazMelgarejo/periscope/pull/26) (merged 2026-07-29) | Upstream stack onto purified: #1274 DuckDB + #1251 artifact + #1284 Omnigent |
| Prior decision | See [PERISCOPE_MODERNIZATION_PURIFIED_INTEGRATION_2026-07-29.md](./PERISCOPE_MODERNIZATION_PURIFIED_INTEGRATION_2026-07-29.md) — PR #20 purified over PR #17 bad replay |

**Why Experiment A wins:** Integration base is `merged` (canonical shipping branch with Layer 2+3 Periscope identity). Purified AgentsView ancestry + PR #26 upstream features are replayed *onto* that base — same direction as `scripts/sync-upstream.sh` and matryoshka ownership in `periscope/docs/ARCHITECTURE.md`. Experiment B inverts the base and fights fork identity preservation.

---

## Context

| Layer | Source | Role in synthesis |
|-------|--------|-------------------|
| Layer 1 | `kenn-io/agentsview` @ purified base | Parser, sync, postgres, db — take upstream on conflict |
| Layer 2 | latentsignal-org/periscope features | ContextPage, summarize, guidance, API routes — preserve |
| Layer 3 | diazMelgarejo/periscope identity | Module rename, sync-upstream.sh, CI, JetBrains — preserve |
| PR #26 delta | DuckDB + artifact + Omnigent onto purified | Land after Layer 1, before Layer 3 identity |

**Monolithic merge probe:** `git merge` of purified+PR26 onto `merged` produced **735 symmetric conflicts**. Do not resolve in one pass — use path-scoped integrative merge (oramasys-method; precedent: [PR #25](https://github.com/diazMelgarejo/periscope/pull/25) ECC path-scoped replay, [PERISCOPE_ECC_INTEGRATIVE_REPLAY_2026-07-28.md](./PERISCOPE_ECC_INTEGRATIVE_REPLAY_2026-07-28.md)).

---

## Five-pass planning doctrine (everyday rule — matryoshka-ordered)

> **Exception banner (2026-07-29):** To preserve commit history in **both** pedigrees of a public fork, we made an **extraordinary exemption** for merge *execution* (see [History preservation (2026-07-29 correction) - extraordinary exemption](#history-preservation-2026-07-29-correction---extraordinary-exemption) below). In **AutoResearch mutations** and **usual daily code dev**, the general rule in this section still applies — do not conflate the exemption with everyday practice.

Method: [integrative-merge.md](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/oramasys-method/references/integrative-merge.md) — **synthesize, never amputate**.

**What the five passes are for (planning only):**

1. **Simulation** — `git merge --no-commit --no-ff` → enumerate `U` → `git merge --abort` before touching files
2. **Ownership classification** — map each conflicted path to matryoshka layer via `docs/ARCHITECTURE.md` and `scripts/sync-upstream.sh`
3. **Resolution planning** — decide per-path integrative mode (take upstream, union, preserve fork identity) before any integration-branch commit

Each pass scopes paths to one ownership layer. **Do not** land per-pass integration-branch commits — passes inform a single harmonized outcome (path-scoped delta replay or disposable worktree), not a stack of `synthesis(passN)` SHAs.

### Pass 1 — Layer 1 upstream (parser / sync / postgres)

**Paths (take upstream unless PR #26 explicitly extends):**

- `internal/parser/**`
- `internal/sync/**`
- `internal/postgres/**`
- `internal/db/db.go` (`dataVersion` — take higher)
- `internal/db/sessions.go` (union `IncrementalInfo` fields per ARCHITECTURE.md)

**Checklist:**

- [ ] Simulate merge; list only Pass-1 path conflicts
- [ ] Apply ARCHITECTURE.md Layer 1 table — take upstream for parser/sync/postgres
- [ ] Union struct fields where Periscope added `ModelContextWindowTokens` / `HasModelContextWindowTokens`
- [ ] `go test -tags fts5 ./internal/parser/... ./internal/sync/... ./internal/postgres/...`
- [ ] Record Pass-1 ownership decisions in plan notes (no integration-branch commit)

### Pass 2 — PR #26 features (DuckDB + artifact + Omnigent)

**Paths:** PR #26 diff only — DuckDB integration, artifact handling, Omnigent parser/agent paths (verify against PR #26 file list).

**Checklist:**

- [ ] Cherry-pick or path-copy harmonized blobs from PR #26 tip onto Pass-1 result
- [ ] Do not replay full PR #26 branch if base diverged — path-scoped delta only
- [ ] Run targeted tests for new agent/parser surfaces
- [ ] Verify no Layer 1 regressions from Pass 1
- [ ] Record Pass-2 ownership decisions in plan notes (no integration-branch commit)

### Pass 3 — Fork identity (Layer 3)

**Paths:**

- `go.mod` / module path `github.com/latentsignal-org/periscope`
- `cmd/periscope/**` (binary name, Version var)
- `scripts/sync-upstream.sh`, `scripts/install.sh`
- `.github/workflows/release.yml` (adapt binary/repo names)
- `jetbrains-plugin/**`, `PeriscopeProcessManager.kt`

**Checklist:**

- [ ] Keep `periscope` binary and module identity — never revert to `agentsview` in Layer 3 paths
- [ ] Preserve sync-upstream.sh known-patterns table
- [ ] `make build` produces `periscope` binary
- [ ] Record Pass-3 ownership decisions in plan notes (no integration-branch commit)

### Pass 4 — Frontend synthesize (Layer 2 UI + upstream SPA)

**Paths:**

- `frontend/**` (especially `App.svelte`, `vite.config.ts`, `types/index.ts`)
- `internal/server/server.go` (routes union: context + timing + summarize)
- `internal/summarize/**`, `internal/llm/**`

**Checklist:**

- [ ] `App.svelte`: keep ActivityMinimap + ContextPage tab block; add upstream SessionVitals/snippets
- [ ] `server.go`: union routes — `/context`, `/context/timeline`, `/summarize` AND upstream routes
- [ ] `types/index.ts`: export both `./context.js` and upstream exports
- [ ] `vite.config.ts`: keep `applyDevProxyHeaders` / `getDevProxyTarget`
- [ ] `make frontend && make test-short`
- [ ] Record Pass-4 ownership decisions in plan notes (no integration-branch commit)

### Pass 5 — Docs / ECC / skills union

**Paths:**

- `README.md`, `CLAUDE.md`, `AGENTS.md` — Periscope branding (keep ours)
- `docs/**` (union addenda; update ARCHITECTURE.md if new conflict patterns found)
- `.agents/skills/**`, `.claude/skills/**`, ECC bundles — integrative union per PR #25 precedent

**Checklist:**

- [ ] ECC skill mirrors byte-identical where required (`verify-ecc-skill-mirror.sh`)
- [ ] Union instinct IDs — additive, with `## Related` cross-links where triggers differ
- [ ] Update `docs/ARCHITECTURE.md` conflict table if new patterns discovered
- [ ] Full verification: `go test -tags fts5 ./...`, `make frontend`, `make build`
- [ ] `git diff --name-only --diff-filter=U` empty in disposable worktree before push
- [ ] Land **one** harmonized commit (or follow extraordinary exemption below) — never stack `synthesis(passN)` on the integration branch

---

## Lessons

### PR #26 merge sequencing

PR #26 merged **onto purified** (`cursor/agentsview-purified-onto-kenn-f559`), not onto `merged`. That is correct for upstream replay hygiene (see purified integration doc). Synthesis onto `merged` is a **separate** integrative step — do not assume PR #26 merge implies `merged` is current; replay path-scoped deltas from PR #26 tip after rebasing mental model onto `origin/merged`.

### Path-scoped vs monolithic merge (everyday rule)

| Approach | Result |
|----------|--------|
| Monolithic manual resolution of 700+ conflicts in one session | Unreviewable — **prohibited** in AutoResearch and daily dev |
| 5-pass planning (simulate → classify → plan per layer) | Conflicts partitioned by matryoshka ownership; each layer testable in a disposable worktree |
| Single harmonized path-scoped delta commit onto fresh `origin/merged` | Normal execution path (PR #25 / ECC replay precedent) |
| Two-parent merge + `read-tree` overlay (2026-07-29 only) | **Extraordinary exemption** — see below; not everyday practice |

**Never** resolve 700+ conflicts in one session without path scoping. **Never** force-merge a stale synthesis branch wholesale. "Never monolithic" means **no bulk manual conflict resolution in one session** — it does **not** prohibit a single final merge commit when that commit is the agreed harmonized outcome.

### Symmetric conflict count

735 symmetric conflicts means **both sides changed the same files** for valid reasons (purified upstream modernization + Periscope fork features). High count is expected, not a signal to pick one side. It signals **decompose by layer** using ARCHITECTURE.md ownership and sync-upstream.sh patterns.

### History preservation (2026-07-29 correction) - extraordinary exemption

> **Scope:** This merge-execution procedure is an **unusual exception** made once to preserve real commit history in **both** public-repo pedigrees (`merged` fork line + `kenn-io/agentsview` purified line). Path-scoped five-pass **planning** is still the doctrine we would normally choose for execution — but that path would erase reachable upstream SHAs on the integration graph. **Do not** treat this exemption as the default for AutoResearch mutations or usual daily code dev.

**Do not** land synthetic `synthesis(passN)` commits on the integration branch — that replays trees under new SHAs and violates the never-synthesize-SHAs policy (see purified integration doc).

**Unusual procedure adopted for PR #29** — single two-parent merge (`32d3c281`):

1. `git merge purified --no-commit --no-ff` (retain both parent SHAs)
2. `git read-tree --reset -u purified^{tree}` (upstream-modernized base tree)
3. Overlay `PERISCOPE_OWNED` paths from `merged` (Layer 2+3) — path-scoped, not whole-tree `-X ours/theirs`
4. Require clean worktree; stage only intended overlay paths; run `verify-staged-for-commit` then `commit-clean` (auto-detects `MERGE_HEAD` parents for a single merge commit)

Synthetic pass experiments archived on `cursor/agentsview-plus-periscope-synthetic-pass-f559` only. See `PERISCOPE_HISTORY_PRESERVING_SYNTHESIS_2026-07-29.md` and `lesson_d8ef5aaa6bf8`.

---

## Cross-references

| Doc | Path |
|-----|------|
| Purified integration decision | [PERISCOPE_MODERNIZATION_PURIFIED_INTEGRATION_2026-07-29.md](./PERISCOPE_MODERNIZATION_PURIFIED_INTEGRATION_2026-07-29.md) |
| ECC path-scoped replay | [PERISCOPE_ECC_INTEGRATIVE_REPLAY_2026-07-28.md](./PERISCOPE_ECC_INTEGRATIVE_REPLAY_2026-07-28.md) |
| Matryoshka layers | `periscope/docs/ARCHITECTURE.md` |
| Integrative merge doctrine | orama `integrative-merge.md` |
| Path-scoped PR replay card | orama `path-scoped-pr-replay-reference-card.md` |
| PR #26 docs / git / FM8 session | [PERISCOPE_PR26_DOCS_GIT_AFRP_SESSION_2026-07-29.md](./PERISCOPE_PR26_DOCS_GIT_AFRP_SESSION_2026-07-29.md) |

---

## Recall

```bash
python .agent/tools/recall.py "periscope agentsview synthesis experiment A path-scoped matryoshka 735 conflicts"
```
