# vendor/ecc-tools — local-only additions

The submodule gitlink is aligned to **canonical `c9de8f5b`** (origin/main of
ecc-tools, verified 2026-08-14). Four reviewed local overlay paths are preserved here so they
survive `git submodule update`. They are re-applied by
[`ecc-submodule-sync.sh`](ecc-submodule-sync.sh) from
[`ecc-local-additions.patch`](ecc-local-additions.patch). The companion
[`ecc-local-overlay.tsv`](ecc-local-overlay.tsv) is the reviewed intent registry;
the patch is only the portable application artifact.

## What is currently preserved (vs canonical c9de8f5b)

| File | Mode | Lines | What it is |
|------|------|-------|-----------|
| `.agents/skills/frontend-design/agents/openai.yaml` | `new-file` | 7 | Codex/OpenAI agent surface (interface + policy) for the `frontend-design` skill — absent upstream. |
| `.antigravity/ANTIGRAVITY.md` | `new-file` | 48 | "ECC for Gemini CLI" baseline workflow / review standards / security checks (Antigravity target). |
| `.gemini/ANTIGRAVITY.md` | `new-file` | 48 | Same ECC-for-Gemini content, `.gemini/` location. |
| `.env.example` | `additive` | 5 | Empty optional Gemini key placeholders added to the upstream template; no credential value is preserved. |

These four paths are the **entire approved local overlay**. Their intent is
declared in `ecc-local-overlay.tsv`, rather than embedded as a blind snapshot in
the shell script. Everything else found uncommitted in the submodule worktree
remains separately classified until it is reviewed and either promoted through
an upstream-compatible change or discarded from the local checkout. The patch
is add-only: it must not modify an upstream ECC file.

### Runtime hook telemetry is not an overlay

`.claude/hooks/.logs/hook-log.jsonl` is append-only runtime evidence written by
the active hook implementation. It must not be captured in the reviewed patch:
a fixed snapshot becomes stale immediately and blocks otherwise-safe ECC
updates. The sync helper reports it separately, excludes it from overlay
candidates, and offers an explicit local-only ignore command:

```bash
bash scripts/git/ecc-submodule-sync.sh ignore-runtime
```

This command writes only the submodule's local Git exclude file. It does not
modify ECC source, the overlay registry, or the reviewed patch.

## Manual Review Gate

`ecc-submodule-sync.sh` is a developer-maintenance helper, never an application
runtime, startup, hook, CI, or automatic-upgrade mechanism. Its `save` command
cannot replace the tracked patch in one step:

```bash
bash scripts/git/ecc-submodule-sync.sh save --review
# Inspect the printed diff stat and digest. Then, only if it is intentional:
bash scripts/git/ecc-submodule-sync.sh save --approve <sha256-from-review>
```

The script regenerates the candidate during approval and writes the patch only
when its digest matches the reviewed value. It classifies each live difference
against the reviewed intent registry, showing the path, mode, and purpose for
allowed drift. `new-file` permits a local-only file; `additive` permits only
added lines to a named upstream file. It rejects paths outside the registry,
deletions, patch-type mismatches, and unreviewed submodule changes. `update`
and `upgrade` restore the existing reviewed patch but never call `save`
themselves. Restore applies each registered path independently, so an existing
local-only file cannot mask a required `additive` overlay in a different file.
Candidate patches use full blob IDs, so the review gate remains stable across
different Git abbreviation settings.

## 2026-08-14 Revalidation and advancement

The current `origin/main` was fetched and verified at `c9de8f5b`. The reviewed
candidate contains the same four paths and 108 added lines shown above; no new
overlay path or content delta was found. The patch was regenerated against that
current base after review. The earlier `ed387446` anchor remains recorded in
the manifest and the historical section below as provenance, not as the active
canonical target.

The restore workflow is intentionally idempotent: a clean checkout with no
local files is allowed through `upgrade`, even when it is already at
`origin/main`, and the reviewed patch is restored before success is reported.
This protects the local-only overlay from the stale assumption that a current
submodule SHA implies an already-restored worktree.

## 2026-07-15 Reclassification

The older three-way analysis below remains historical evidence. A later audit
confirmed the first three paths plus the additive environment-template entry as the
explicitly preserved overlay. It also separated malformed Markdown fence edits,
lockfile-only resolution drift, and a checkout at an older upstream commit from
this overlay; none of those categories belongs in this patch.

## Provenance (3-way analysis, 2026-06-13)

The submodule worktree had ~115 uncommitted local files on top of the stale gitlink
`4e66b288`, while origin/main had moved **529 commits** forward to `928076c`. Breakdown:

- **71** files — already merged upstream (local edits == canonical). Dropped.
- **43** files — superseded by newer canonical versions (both diverged from base).
  Canonical wins; the stale local versions were discarded.
- **3** files — genuinely local-only at the time (the first three rows above). Kept.

## Recovery

- **Just the approved overlay:** `bash scripts/git/ecc-submodule-sync.sh restore`.
- **Refresh the approved overlay after a deliberate review:** run `save --review`,
  inspect the candidate, then run `save --approve <sha256>`. Only after that use
  `update` or `upgrade`; neither command creates or rewrites the patch.
- **The full pre-canonical local work** (all 115 files, including the 43 superseded):
  salvage branch **`985ee9b`** (`salvage/ecc-local-wip-pre-928076c`) inside the
  submodule's own git. It is local-only (never pushed to ecc-tools) and will be lost
  if the submodule is re-cloned — but its only *unique* content is the 3 files above,
  which are already preserved in the tracked patch. A throwaway full snapshot was also
  written to `/tmp/ecc-local-salvage.patch` (ephemeral; not relied upon).

## Adding more local-only files later

Run the manual review gate above before any submodule update. To propose a new
overlay path, first amend `ecc-local-overlay.tsv` with its human-readable intent
as part of a deliberate review. The script then requires approval of the exact
candidate digest before it rewrites the patch.
