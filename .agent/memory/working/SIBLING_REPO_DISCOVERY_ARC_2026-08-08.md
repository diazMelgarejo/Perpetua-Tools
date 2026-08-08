# Arc: Sibling-Repo Discovery (Fixing Guessed Paths With Real Crawls)

**Date:** 2026-08-07 → 2026-08-08
**Parent essay:** `SESSION_BIRDSEYE_TRUST_INFRASTRUCTURE_2026-08-08.md`
**Repos:** orama-system canonical; PT consumes the generic crawler + adds
its own reverse-direction resolver

## The bug shape (found twice, unrelated code paths)

Both bugs are the same root cause: **a fixed relative-depth assumption
breaks the moment a sibling repo is nested one level deeper than
expected.** PT lives at `<mother>/perplexity-api/Perpetua-Tools`, not
`<mother>/Perpetua-Tools` — a naming/layout quirk from before this repo's
rename, still live on this exact machine.

1. `scripts/git/check-guard-sync-divergence.sh --workspace` globbed
   `$WORKSPACE_ROOT/*` (one level) to find sibling repos to check — silently
   skipped PT, reported `PASS`, and would have kept doing so indefinitely.
2. Six PT scripts (`cloud-bootstrap.sh`, `lib-normalize-cloud-paths.sh`,
   `install-user-git-environment.sh`, `session-apply-git-guards.sh`,
   `sync-private-attribution-from-home.sh`, `check_docs_v2_pointer_sync.sh`)
   defaulted `ORAMA_SYSTEM_PATH` to `$REPO_ROOT/../orama-system` — resolves
   to a directory that does not exist on this machine.

Orama already had a working, non-naive discovery function
(`resolve_pt_root()` in `bin/orama-system/skills/hermes-harness/scripts/
resolve_perp_harness.sh`) for the *other* direction — env-var override
(fail-closed if set-but-invalid) → `.paths` cache check → depth-N crawl
from the workspace mother directory, validated by a marker file
(`orchestrator/fastapi_app.py`) rather than a hardcoded depth. PT had no
equivalent for finding orama.

## What got built

**`scripts/git/resolve_sibling_git_repo.sh`** (new, canonical in orama,
synced byte-identical to PT) — extracted the generic shape of
`resolve_pt_root()`'s crawler into marker-parameterized primitives
(`sibling_repo_is_git_root`, `sibling_repo_crawl_collect`,
`sibling_repo_finalize`, `sibling_repo_check_env_override`) so the *same*
file can discover PT from orama, orama from PT, or "any git repo at all"
(empty marker) for the divergence-check's own `--workspace` scan — one
canonical crawler, three call sites, instead of three copies.

- `resolve_perp_harness.sh` refactored to a thin wrapper over the generic
  crawler — public function name/behavior unchanged, all 13 pre-existing
  tests pass unmodified.
- **`Perpetua-Tools/scripts/resolve_orama_root.sh`** (new) — the mirror,
  discovering orama via the same crawler, marker `bin/orama-system/
  SKILL.md`, env vars `ORAMA_SYSTEM_PATH` / `ORAMA_SYSTEM_ROOT` /
  `ORAMA_ROOT` in that order, same fail-closed-on-invalid-override
  semantics, memoized cache.
- The six PT sites fixed to call the resolver instead of guessing,
  preserving each file's own existing fallback/error shape on resolution
  failure (deliberately conservative — these are Cursor-cloud-specific
  bootstrap scripts, and a resolution failure there might be *expected* in
  a cloud sandbox with a different layout).
- `check-guard-sync-divergence.sh --workspace` now does a depth-2 crawl
  via the same primitive instead of a flat glob — confirmed live: it now
  correctly finds PT, where it previously silently skipped it.

## Division of labor across agents (worth remembering the pattern, not just the result)

This arc's two directions were built by two different dispatched agents
(codex for the PT-side resolver + the six-site fix, working independently
against the orama-side crawler this session had already written) and
verified before trusting either: content diff against canonical for
byte-identical sync, the full attribution test suite re-run (94 passed) on
the PT side, `check-guard-sync-divergence.sh` re-run to confirm parity —
not just "the dispatched agent said it ran tests."

## Cross-references

- `SESSION_BIRDSEYE_TRUST_INFRASTRUCTURE_2026-08-08.md` — the "guessed
  path" bug shape as a recurring gold nugget.
- `HALLUCINATION_PREVENTION_ARC_2026-08-08.md` — shares the same generic
  crawler for `find_stranded_work.sh`'s repo discovery.
- `GUARD_SYNC_HARMONIZATION_ARC_2026-08-08.md` — how the new crawler file
  itself got added to the formal sync manifest.
