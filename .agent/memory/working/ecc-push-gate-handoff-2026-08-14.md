# ECC Push-Gate Fix — Handoff

Date: 2026-08-14

## Source

`~/code/oramasys/tools/ECC+GitHub-push-analysis-2026-08-14.md` — PT branch
`fix/ecc-overlay-idempotency-20260814` (HEAD `f4d0761d`, working tree clean)
was blocked locally by a false positive in the guard-sync divergence gate.

## What actually happened (in order)

1. Diagnosed two real bugs matching the analysis doc's "Required Correction":
   the pre-push trigger was directory-wide (`^scripts/git/`) instead of
   manifest-exact, and `check-guard-sync-divergence.sh`'s `CANON_ROOT`
   self-nominated whenever invoked from a downstream checkout.
2. Implemented both fixes **directly in this PT worktree** — wrong. Both
   files are canonical-managed (`GUARD_SYNC_EXECUTABLES` in
   `scripts/git/guard-sync-manifest.sh`); PT's copy must stay a
   byte-identical mirror. Caught via AskUserQuestion before committing.
3. Multi-agent coordination board (GossipBus, query in
   `.agent/memory/semantic/LESSONS.md` lesson `20234c4410fd`) ruled: fix in
   orama-system, not PT. Reverted the PT hand-edits with `git checkout --`.
4. Re-implemented both fixes on orama-system PR #311
   (`docs/contract-migration-vertical-slice-20260814`, worktree
   `/private/tmp/orama-contract-migration-20260814`) — the existing
   guard-hardening draft, per a live coordination-board decision after the
   owner verified it was the right vehicle.
5. Hit and fixed two test-design bugs along the way (both now recorded as
   separate lessons — `fb41758b35af` BASH_SOURCE self-detection isolation,
   `9c02865055b4` vacuous negative-assertion pattern).
6. Committed + pushed twice to PR #311 (`cd614bdd`, then `f04515b3`). Both
   pushes triggered the real (fixed) hook for real against every actual
   sibling worktree on this machine and passed clean —
   `guard-sync-divergence: PASS` — real-world confirmation beyond the 13
   synthetic unit tests.
7. A manual human review flagged one real medium bug in my first PR 311
   commit (record 1343): the degraded fallback (manifest file missing)
   only matched `scripts/git/` paths, not `.githooks/`, even though the
   manifest governs both — a manifest-managed githook change could have
   silently skipped divergence validation. Fixed, tested, pushed as
   `f04515b3`.

## Current state (end of this session)

- **orama-system PR #311**: pushed, `f04515b3`, 13/13 tests green,
  review item resolved. **Still under manual human review — not merged.**
- **PT** (`fix/ecc-overlay-idempotency-20260814`): genuinely clean,
  `HEAD f4d0761d`, matches origin. No guard-file changes here — correct,
  per the ruling. Nothing to push yet.

## Next step (do not skip ahead)

Per coordination record 1343: **"PT remains untouched; do not sync until
this review item is resolved and PR 311 merges normally."** The review
item is resolved (this session); the merge is not done. Once PR #311
merges into orama-system `main`:

1. Sync the generated mirrors onto `fix/ecc-overlay-idempotency-20260814`
   via the canonical sync tooling (`sync-attribution-guard-scripts.sh` or
   equivalent) — never hand-copy/hand-edit.
2. Push that single PT branch — this was the actual, original blocked
   push the whole analysis doc exists to unblock.
3. Confirm the real push now succeeds without a bypass
   (no `--no-verify`, no `GUARD_SYNC_SKIP_DIVERGENCE_CHECK=1`).

## Related

- Lessons: `20234c4410fd` (ownership boundary), `fb41758b35af` (test
  isolation), `9c02865055b4` (vacuous assertions) — all in
  `.agent/memory/semantic/LESSONS.md`.
- Coordination board: GossipBus records 1339-1343 (query via
  `orchestrator.coordination.paths.canonical_db_path()`), agent
  `codex-primary-orchestrator`.
