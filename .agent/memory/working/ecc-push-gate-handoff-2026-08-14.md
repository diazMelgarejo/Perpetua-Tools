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

8. Manual human review approved PR #311; merged normally as `ce1d260d`.
   Another agent (Codex) synced the mirrors into PT
   (`61600dff`) and ran the focused guard suite (59 passed) — but that
   surfaced two *more* real bugs, found and fixed entirely by that other
   agent, not me:
   - **Linked-worktree false positive** (orama PR #312): the divergence
     scanner treated linked git worktrees of the canonical repo itself
     (this session used several, for parallel PR work) as independent
     downstream siblings, producing false-positive divergence failures.
     Fixed via `git -C <root> rev-parse --git-common-dir` comparison —
     two roots sharing a common dir are worktrees of one repo, not
     siblings. Lesson `ecf446018e17`.
   - **`GIT_DIR` leakage from the hook's own environment** (orama PR
     #313): once actually invoked as a real pre-push hook (not just
     tested standalone), `GIT_DIR` was already exported and silently
     rebound every `git -C <sibling>` call back to the pushing repo,
     letting a genuinely independent sibling be skipped. Fixed by
     clearing every name from `git rev-parse --local-env-vars` before
     the first cross-repo `git` call. Lesson `e6771ac33caa`.
   Both synced into PT as `0f9472f6` and `ef80f9a5`.
9. **The original blocked push succeeded.** PT's
   `fix/ecc-overlay-idempotency-20260814` now has a remote tracking ref;
   local `HEAD` (`ef80f9a5`) matches `origin/fix/ecc-overlay-idempotency-20260814`
   exactly — confirmed directly, not just from the board. Independently
   re-ran `check-guard-sync-divergence.sh --workspace` myself (with an
   explicit `GUARD_SYNC_CANON_ROOT`, since several orama-system worktrees
   exist on this machine right now and the resolver correctly refuses to
   guess among them) and the local guard test suite: both pass clean,
   no bypass used anywhere in the whole sequence.

## Current state (end of this session) — RESOLVED

- **orama-system**: PR #311 merged (`ce1d260d`), PR #312 and PR #313
  (follow-up fixes) also landed.
- **PT** (`fix/ecc-overlay-idempotency-20260814`): `HEAD ef80f9a5`,
  matches `origin/fix/ecc-overlay-idempotency-20260814` exactly. Contains
  the real ECC overlay-idempotency work (the original deliverable),
  the full canonical guard-tooling mirror, and this session's memory
  commits. **Pushed successfully with no bypass — the original problem
  the analysis doc exists to solve is fixed end to end.**

## Related

- Retrospective / reflections / recommendations: [`ecc-push-gate-retrospective-2026-08-14.md`](ecc-push-gate-retrospective-2026-08-14.md)
- Domain knowledge (stable architecture): [`DOMAIN_KNOWLEDGE.md`](../semantic/DOMAIN_KNOWLEDGE.md) § Guard-sync architecture
- Lessons: `20234c4410fd` (ownership boundary), `fb41758b35af` (test
  isolation), `9c02865055b4` (vacuous assertions), `ecf446018e17`
  (linked-worktree scope), `e6771ac33caa` (GIT_DIR leakage),
  `f5a3139114c2` (coordination-board pattern) — all in
  `.agent/memory/semantic/LESSONS.md`.
- Coordination board: GossipBus records 1339-1353 (query via
  `orchestrator.coordination.paths.canonical_db_path()`), agents
  `codex-primary-orchestrator` and `codex-reviewer`.
