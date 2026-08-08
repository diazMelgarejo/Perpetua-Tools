# Arc: Guard-Sync Harmonization (`.githooks/commit-msg` Drift)

**Date:** 2026-08-07 → 2026-08-08
**Parent essay:** `SESSION_BIRDSEYE_TRUST_INFRASTRUCTURE_2026-08-08.md`
**Repos:** orama-system canonical, PT synced; AlphaClaw explicitly excluded

## The drift, verified before touching anything

orama's `.githooks/commit-msg` chained `check_commit_message.sh` →
`check_tdd_commit.sh`. PT's own version independently chained
`ensure_hooks_installed.sh` → coauthor-stripping → `check_commit_message.
sh` — different structure, same underlying intent, drifted apart because
each repo added what it needed at the time without the other repo's
addition round-tripping back.

Two scripts (`ensure_hooks_installed.sh`, `check_tdd_commit.sh`) already
existed byte-identically in both repos — confirmed with `diff` before
assuming — but were never actually *in* the formal `guard-sync-manifest.
sh` list. They matched by coincidence (someone copied them by hand once),
not because the sync system was keeping them in sync. That is a real,
if quiet, zero-fragmentation gap: the moment either file needed a real
fix, nothing would have propagated it.

## What got built

One harmonized `.githooks/commit-msg`, existence-guarding every optional
step (`[[ -x "$ROOT/scripts/git/check_tdd_commit.sh" ]] && ...`) so the
*same file* is correct whether or not a given repo has that script — PT
doesn't need `check_tdd_commit.sh`'s web/src/ TDD gate to make sense of
having it (it self-guards to a no-op on any repo without a `web/src/`
tree), so shipping it everywhere is safe, not just "harmless."

- `guard-sync-manifest.sh` gained a new `GUARD_SYNC_GITHOOKS` array
  (currently just `commit-msg`) alongside the existing `GUARD_SYNC_
  EXECUTABLES` / `GUARD_SYNC_DATA_FILES`, plus `ensure_hooks_installed.sh`
  and `check_tdd_commit.sh` promoted into the executables list.
- `sync-attribution-guard-scripts.sh` and `check-guard-sync-divergence.sh`
  both generalized to handle a path *prefix* (`scripts/git/` or
  `.githooks/`) instead of a hardcoded one, and the `.githooks/` sync path
  is explicitly gated on the target already having a `.githooks/`
  directory — **never forces the hooks system onto a repo that hasn't
  opted in.**
- The one genuine divergence the anti-clobber guard caught (PT's own
  `.githooks/commit-msg` had real structure absent from canonical history)
  was a deliberate promotion decision, not an accidental clobber — the new
  canonical file already incorporated PT's `ensure_hooks_installed.sh` +
  coauthor-strip steps by design, so applying it directly (bypassing the
  automated gate for this one reviewed case) was the correct call, not a
  bypass of the safety the gate exists for.

## Why the manifest header comment matters here

`guard-sync-manifest.sh`'s own header used to say "single source of truth
for attribution-guard distribution" — read narrowly, that could have been
a reason to *not* add a general-purpose crawler or a commit-msg hook file
to it. Precedent check first: the manifest already carried non-attribution
tooling (itself, the sync script, the divergence checker) before this
session touched anything, so adding `resolve_sibling_git_repo.sh` and the
`.githooks/` entries is consistent with existing practice, not scope
creep — worth the explicit check rather than assuming either way.

## A self-inflicted near-miss, corrected in the same session

A commit message claimed `resolve_sibling_git_repo.sh` was "added to
`GUARD_SYNC_EXECUTABLES`" when only a header comment had actually changed
— see `HALLUCINATION_PREVENTION_ARC_2026-08-08.md` for the full incident;
this is the arc where it actually happened, mid-build, on this exact
manifest file.

## Explicitly not done

AlphaClaw was never synced any of this session's new files. It has no
`.githooks/` directory at all and no `core.hooksPath` configured — a
bigger, separate gap than "commit-msg drifted," and out of scope per the
standing instruction that AlphaClaw (a mirror of an external upstream,
`chrysb/alphaclaw`) is not this session's engineering surface.

## Cross-references

- `SESSION_BIRDSEYE_TRUST_INFRASTRUCTURE_2026-08-08.md`
- `HALLUCINATION_PREVENTION_ARC_2026-08-08.md` — the new checks this arc's
  harmonized hook file wires in.
- `SIBLING_REPO_DISCOVERY_ARC_2026-08-08.md` — the crawler file this arc
  formally added to the sync manifest.
- `ALPHACLAW_OSSF1_AUDIT_2026-08-08.md` — why AlphaClaw stayed untouched
  even though it shares the same underlying guard-script lineage.
