# Periscope agentsview → periscope rename catalogue (PT memory)

**Date:** 2026-07-28  
**Status:** active — use on every `agentsview` upstream merge into `merged`  
**Canonical in repo:** `periscope/docs/guides/agentsview-to-periscope-rename-catalogue.md`  
**Machine index:** `periscope/docs/guides/agentsview-rename-index.json`

## Context

Periscope maintains an **`agentsview` mirror branch** (kenn-io/agentsview) separate
from product branding **`periscope`** on `merged`. Upstream syncs reintroduce
`agentsview` strings; agents must not confuse mirror naming with product naming.

Indexed snapshot (merged @ `6cf2f38f`, 2026-07-28):

- **96 files**, **514** literal matches (`agentsview|AgentsView|AGENTSVIEW`)
- Largest debt: `build_wheels_test.py`, `desktop-release-setup.md`, `lib.rs`
  sidecar spawn, `README.md`, PG tests, `install.ps1`, CI workflows

## Decision summary

| Signal | Action |
| --- | --- |
| Branch/remote `agentsview` | KEEP |
| Session fixture cwd `/.../agentsview` | KEEP |
| `docs/superpowers/*` historical plans | KEEP |
| Binary, cmd, CI artifact, sidecar file | RENAME → periscope |
| `AGENTSVIEW_*` / `AGENT_VIEWER_DATA_DIR` env | COMPAT — read legacy; prefer PERISCOPE_* |
| `agentsview-*` localStorage keys | MIGRATE — dual-read legacy |

## 2026-07-28 session fixes (PR #11)

| Area | Fix |
| --- | --- |
| Desktop CI smoke | `desktop-artifacts.yml`: `periscope-${target_triple}` path + `periscope dev` grep |
| Workflow tests | `test-desktop-workflows.sh`: `periscope-desktop-linux-arm64` |
| Gitignore | `desktop/src-tauri/.gitignore`: `periscope-*` binaries |

**Lesson:** rename `prepare-sidecar.sh` + `desktop-release.yml` first; always
update `desktop-artifacts.yml` and shell smoke tests in the same pass.

## Related PT / orama memory

- `PERISCOPE_DUAL_PEDIGREE_REANCHOR_2026-07-28.md` — branch topology
- `WORKSPACE_PR_BASE_BRANCHES_2026-07-28.md` — PR base `merged` only
- `lesson_fdb82283644f` — three-branch mirror model
- orama `docs/reference/periscope-cursor-repo-rules.md`

## Discover matches (filename scan only)

```bash
rg -l 'agentsview|AgentsView|AGENTSVIEW' "$PERISCOPE_REPO" \
  --glob '!**/node_modules/**' --glob '!**/Cargo.lock'
```

Use this to find files that may need re-categorization after an upstream sync.
It does **not** write `agentsview-rename-index.json`.

## Regenerate machine index

No checked-in generator exists yet. After discovery, update
`periscope/docs/guides/agentsview-rename-index.json` manually (or via a one-off
script) with:

- `generated_at` — ISO-8601 UTC timestamp of the audit
- `base_ref` — current `merged` tip (for example `git -C "$PERISCOPE_REPO" rev-parse merged`)
- `file_count` / `match_count` — totals from the `rg` scan
- `entries[]` — per-file rows with `path`, `category` (`keep` | `rename` | `compat` | `migrate`), and `match_count`

Re-categorize each path with the decision tree in
`periscope/docs/guides/agentsview-to-periscope-rename-catalogue.md` before
committing the JSON.
