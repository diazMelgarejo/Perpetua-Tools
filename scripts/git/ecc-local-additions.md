# vendor/ecc-tools — local-only additions

The submodule gitlink is pinned to **canonical `928076c`** (origin/main of ecc-tools).
Three files are local-only — not present upstream — and are preserved here so they
survive `git submodule update`. They are re-applied by
[`ecc-submodule-sync.sh`](ecc-submodule-sync.sh) from
[`ecc-local-additions.patch`](ecc-local-additions.patch).

## What is unique (vs canonical 928076c)

| File | Lines | What it is |
|------|-------|-----------|
| `.agents/skills/frontend-design/agents/openai.yaml` | 7 | Codex/OpenAI agent surface (interface + policy) for the `frontend-design` skill — absent upstream. |
| `.antigravity/ANTIGRAVITY.md` | 48 | "ECC for Gemini CLI" baseline workflow / review standards / security checks (Antigravity target). |
| `.gemini/ANTIGRAVITY.md` | 48 | Same ECC-for-Gemini content, `.gemini/` location. |

These three are the **entire** unique delta. Everything else that was sitting
uncommitted in the submodule worktree was not unique.

## Provenance (3-way analysis, 2026-06-13)

The submodule worktree had ~115 uncommitted local files on top of the stale gitlink
`4e66b288`, while origin/main had moved **529 commits** forward to `928076c`. Breakdown:

- **71** files — already merged upstream (local edits == canonical). Dropped.
- **43** files — superseded by newer canonical versions (both diverged from base).
  Canonical wins; the stale local versions were discarded.
- **3** files — genuinely local-only (the table above). Kept.

## Recovery

- **Just the unique 3:** `bash scripts/git/ecc-submodule-sync.sh restore`
  (or `update` to do save → submodule update → restore in one shot).
- **The full pre-canonical local work** (all 115 files, including the 43 superseded):
  salvage branch **`985ee9b`** (`salvage/ecc-local-wip-pre-928076c`) inside the
  submodule's own git. It is local-only (never pushed to ecc-tools) and will be lost
  if the submodule is re-cloned — but its only *unique* content is the 3 files above,
  which are already preserved in the tracked patch. A throwaway full snapshot was also
  written to `/tmp/ecc-local-salvage.patch` (ephemeral; not relied upon).

## Adding more local-only files later

Run `bash scripts/git/ecc-submodule-sync.sh save` before any submodule update — it
re-snapshots every worktree file that differs from the pinned gitlink into the patch.
