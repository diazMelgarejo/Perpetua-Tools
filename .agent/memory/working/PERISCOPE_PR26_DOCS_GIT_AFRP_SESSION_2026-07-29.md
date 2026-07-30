# Periscope PR #26 docs CI + git guards + AFRP FM8 — session card (2026-07-29)

**Date:** 2026-07-29  
**Status:** operational evidence — tips for future agents  
**Scope:** periscope PR #26 CI/docs, orama-system PR #238 git guards + AFRP FM8, spec vs implementation truth

---

## Situation summary

| PR | Branch | Role |
|----|--------|------|
| [periscope #26](https://github.com/diazMelgarejo/periscope/pull/26) | `cursor/periscope-pr23-duckdb-f559` | Upstream PR #23 stack onto purified + CI/doc fixes |
| [orama-system #238](https://github.com/diazMelgarejo/orama-system/pull/238) | `cursor/agentsview-purified-lessons-f559` | AFRP FM8 synthetic SHA replay + commit-clean staging guards |
| [Perpetua-Tools #296](https://github.com/diazMelgarejo/Perpetua-Tools/pull/296) | `cursor/periscope-l4-adapter-f559` | Memory + L4 adapter line (continues #295) |

**Remote tips (session end):** periscope PR #26 post-docs/git fixes; orama #238 `abe2f685`; PT #296 this commit.

---

## 1. Docs CI — absolute paths and stale spec filenames

### Bad pattern (breaks `check_built_site.py` / Zensical link resolution)

Markdown links that use a **developer-absolute filesystem path** in the `href`, e.g. a path under a local clone root like `…/dev/periscope/docs/v1-ui-spec.md` instead of a repo-relative target.

Machine-local absolute paths are not repo-relative. CI treats them as broken links (GitHub Actions job: docs / `check_built_site.py`).

### Fix

When both files live in `docs/`, use **`v1-ui-spec.md`** or **`./v1-ui-spec.md`**.

### `context-session-visualizer-spec.md` does not exist

Renamed to **`periscope-spec.md`** in periscope commit `bc0c13ae` (2026-04-18). Still referenced in:

- `docs/context-visualizer-ui-recommendation.md`
- `docs/context-session-visualizer-roadmap.md`
- `docs/context-session-visualizer-mvp-plan.md`

**Fix:** point all links to **`./periscope-spec.md`**. Grep the repo:

```bash
rg 'context-session-visualizer-spec' docs/
rg '\]\(/' docs/ README.md   # inspect hrefs — reject developer-absolute paths
```

### Agent tips

- Docs failures are often **missing renamed files**, not missing frontmatter.
- When upstream docs reference a spec, verify the file exists with `git ls-files`, not grep text alone.
- Planning docs (`*-mvp-plan.md`, `*-roadmap.md`) can lag renames — fix links even when content is draft.
- **Portable memory:** never paste literal home-directory paths into PT `.agent/` files — hooks block them (use placeholders or repo-relative examples only).

---

## 2. Product spec vs UI spec vs implementation (PR #26)

| Document | Role | Fully implemented on PR #26? |
|----------|------|------------------------------|
| **`periscope-spec.md`** (was `context-session-visualizer-spec.md`) | Full product spec V1 + V2 | **No** — V2 guidance APIs/UI largely absent |
| **`v1-ui-spec.md`** | UI design exploration (Options A–D) | **Partial** — V1 core shipped; not literal Option C layout |

### V1 implemented (PR #26 tip)

- Route `/context/:sessionId` + embedded session tab (`ContextPage` in `App.svelte`)
- APIs: `GET /api/v1/sessions/{id}/context`, `GET .../context/timeline`
- Components: `ContextSummaryCard`, `ContextTimeline`, composition via **`ContextWindowBlocks`** (not `ContextCompositionChart` on the page)
- SSE live refresh via `watchSession` on `ContextPage`
- Post-compaction trim (`compaction_trimmed` + user warnings in `internal/server/context.go`)

### Not V1-complete / V2 leaked early

- `GET .../context/branch-points`, `.../recommendation`, `.../analyze`, `.../guidance` — **not** on server
- `RewindSignalBanner`, `CompactSignalBanner`, summarize controls — **V2-ish** vs strict V1 “descriptive only”
- `ContextCompositionChart.svelte` exists but **`ContextPage` uses `ContextWindowBlocks`** (aligns with Option B+ in `context-visualizer-ui-recommendation.md`, not v1-ui-spec Option C primary)

### Agent tips

- Do not assume planning doc filenames match disk — check `git ls-files docs/`.
- “Spec fully implemented” requires separating **V1 scope** from **V2** and checking **routes + UI actually wired**.
- UI recommendation doc may be the better MVP truth than v1-ui-spec Option C prose.

---

## 3. Git guard bundle — `commit-clean.sh` + regression harness

### Mandatory workflow (orama + periscope forks)

```bash
git add <paths>                    # commit-clean does NOT auto-stage
bash scripts/git/verify-staged-for-commit.sh
bash scripts/git/commit-clean.sh -m "type(scope): summary"
git show --stat --oneline HEAD     # confirm before push
```

**Failure Mode 9:** running `commit-clean.sh` without staging → silent empty or message-only commits; CI fixes stay unstaged while remote keeps broken workflows.

### `commit_clean_test.sh` must test **copied** scripts

Harness installs helpers into `$tmp/scripts/git/`. Tests must invoke:

```bash
bash "$tmp/scripts/git/commit-clean.sh" ...
bash "$tmp/scripts/git/verify-staged-for-commit.sh"
```

**Not** `$SCRIPT_DIR/commit-clean.sh` — that validates the source tree, not the bundle agents sync into sibling repos.

Bootstrap init commit via `commit-clean.sh` too (not raw `git commit`), so the harness exercises the full guard path.

### `sync-attribution-guard-scripts.sh` — worktree detection

Bare repos and gitlinks: do not rely on exit code alone.

```bash
if [[ "$(git -C "$target" rev-parse --is-inside-work-tree 2>/dev/null)" != "true" ]]; then
  echo "skip: not a git repo: $target" >&2
  exit 0
fi
```

### `set -u` + empty `verify_args` in `commit-clean.sh`

```bash
if ((${#verify_args[@]} > 0)); then
  bash "$SCRIPT_DIR/verify-staged-for-commit.sh" "${verify_args[@]}"
else
  bash "$SCRIPT_DIR/verify-staged-for-commit.sh"
fi
```

Without this, bash 5+ with `set -u` fails: `verify_args[@]: unbound variable`.

### Cancel-path test lesson (PT #295)

Async `sup.cancel` + await integration test hung in pytest. Prefer **`test_maybe_emit_periscope_job_cancelled_literal_wiring`** — direct `_maybe_emit_periscope_job(spec, assistant_text="cancelled")` mirrors `_run_worker` branch without flaky task timing.

### Agent tips

- After syncing guards from orama, run `bash scripts/git/commit_clean_test.sh` locally before pushing doc-only PRs that touch workflows.
- Duplicate push race: if remote already has your SHA, `cannot lock ref … expected X but is at Y` means **another push succeeded** — verify with `git ls-remote`, do not force-push blindly.

---

## 4. AFRP Failure Mode 8 — synthetic SHA replay (orama PR #238)

**Trigger:** Replaying hundreds of upstream commits under **new SHAs** when `kenn-io/agentsview` / `origin/agentsview` already has originals.

| Bad (PR #17 pattern) | Good (PR #20 / purified pattern) |
|----------------------|----------------------------------|
| ~769 replayed commits, 2k+ file PR | Inherit upstream @ `#1283`; 9 fork-unique commits |
| Same tip **tree**, unusable graph | Byte-identical tree, reviewable graph |

### Recovery commands — use documented refs

**Wrong:** `git cherry -v upstream-kenn/main <tip>` — ref does not exist on typical fork setups.

**Right:**

```bash
git fetch origin agentsview    # fork tracks kenn-io/agentsview
git cherry -v origin/agentsview <tip>
```

Base on real upstream tip; cherry-pick **fork-unique** commits only; preserve bad branch as anti-pattern reference; close bad PR.

### Tree-equivalence check (path-scoped card)

**Wrong:**

```bash
# git rev-parse HEAD^{tree} == modernization-tip^{tree}
```

`==` is passed to `git rev-parse` as an argument — command fails.

**Right:**

```bash
test "$(git rev-parse HEAD^{tree})" = "$(git rev-parse modernization-tip^{tree})"
```

### CIDF / curriculum cross-refs

After FM8, AFRP pointers should be **§6–8** (CONFLICTING PR, proxy conclusion, synthetic SHA replay) — not §6–7 only.

Canonical orama paths:

- `bin/orama-system/afrp/failure-modes.md` §8
- `bin/orama-system/cidf/references/integrative-editing-examples.md` §10
- `bin/orama-system/skills/git-history-surgery/references/path-scoped-pr-replay-reference-card.md`

### Relation to periscope synthesis

FM8 is the **history graph** side of the same policy as `lesson_d8ef5aaa6bf8` (two-parent merge + read-tree overlay). Path-scoped replay is for **ECC/docs deltas**; not for replaying entire upstream lineages.

See also: [PERISCOPE_HISTORY_PRESERVING_SYNTHESIS_2026-07-29.md](./PERISCOPE_HISTORY_PRESERVING_SYNTHESIS_2026-07-29.md), [PERISCOPE_AGENTSVIEW_PLUS_SYNTHESIS_2026-07-29.md](./PERISCOPE_AGENTSVIEW_PLUS_SYNTHESIS_2026-07-29.md).

---

## 5. ECC harmonization (PR #16) — quick recall

Wholesale ecc-tools bot PRs can **regress** merged ECC. Replay only 3 paths onto fresh `origin/merged`. See [PERISCOPE_PR16_INTEGRATIVE_HARMONIZATION_2026-07-28.md](./PERISCOPE_PR16_INTEGRATIVE_HARMONIZATION_2026-07-28.md).

---

## Verification commands

```bash
# Periscope docs (in docs/ with uv)
bash scripts/check-docs.sh

# Git guards
bash scripts/git/commit_clean_test.sh
bash scripts/git/verify-git-guards.sh

# Periscope ECC mirror (when paths exist)
# orama: scripts/periscope/verify-ecc-skill-mirror.sh
```

---

## Recall

```bash
python .agent/tools/recall.py "periscope docs absolute path periscope-spec commit-clean FM8 synthetic SHA"
```
