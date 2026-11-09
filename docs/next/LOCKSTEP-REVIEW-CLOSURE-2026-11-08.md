# PT / Orama lockstep review closure

AFRP: Type C | Expert | Mode 2. This is the executable review ledger for PT
[#484](https://github.com/diazMelgarejo/Perpetua-Tools/pull/484) and Orama
[#481](https://github.com/diazMelgarejo/orama-system/pull/481), not deployment approval.
Keep the existing PRs, signed history, local-first policy and serving-off boundary.

## Evidence and synthesis

The two reported Orama CI jobs fail seven tests because spawn dispatch imports
`orchestrator.gossip_bus` solely for state-directory discovery, indirectly requiring
`aiosqlite`. Rich local environments masked that dependency. The repair separates
lightweight state discovery from async gossip rather than installing unrelated
runtime services just to find a path. Clean-environment tests must execute a mocked
dispatch, not merely import the guard.

Four older local containment failures have a different cause: killed grandchildren
remain zombies under an inert container PID 1. A zombie-only `/proc` scan cannot
prove that hidden live members are absent. Preserve conservative production
containment and use an explicit orphan-reaping test launcher; do not count a skip,
weakened assertion or inaccessible process as contained.

The review identifies one shared vertical contract: canonical policy and exact
effect identity -> private durable claim -> public/direct/fan-out callers -> replay
transport -> observable failure. Repair this contract as a pair, not as isolated
line edits. PT owns authority; Orama adapts it. Memory corrections remain audited,
append-only, provisional/retracted and separate from approval.

## Consolidated finding map

| Review comments | Intended invariant and proof |
| --- | --- |
| PT 4504116603 | Direct provider aliases cannot bypass canonical model governance; effect is never invoked on denial. |
| PT 4504116628 | Trusted symlink ancestors work; ownership, writable ancestors and resolved targets still fail closed. |
| PT 4504116629 | Reconciled HTTP replay accepts an explicit new scope; omitted scope preserves existing identity. |
| PT 4504116631, 4504116633, 4504116637 | Upgrade/default scope is stable; authorization and identity describe the actual model; each legacy provider effect is guarded, including private fan-out leaves. |
| PT dispatch nitpick | Vary job and session IDs separately: neither bypasses same-envelope deduplication. |
| Orama 4504108275 | A cached local `orchestrator` persona package cannot shadow PT authority; do not evict another package globally. |
| Orama 4504108278, 4504108282 | Portal/CLI return actionable rejection and duplicate errors; CLI exposes an explicit reconciled scope. |
| Orama 4504108269, 4504108284, 4504108286 | Test/release/local setup uses one immutable PT producer; credentials are not persisted into imported code. |
| PT 4504116594 | Search results preserve current lesson status and visible retraction, including FTS and fallback. |
| PT 4504116596, 4504116598 | Reused and identical correction retries validate the entire audit without duplicate publication. |
| PT 4504116601 | Both locked native appenders preserve a complete final JSON object lacking newline; malformed history still refuses. |
| PT retraction nitpick | Successful retraction and identical retry retain semantic and rendered retracted state. |
| PT 4504116605 | Implicit models skip model-specific planning; independently verify model and required approval before dispatch. |
| PT 4504116613, 4504116615, 4504116620 | Validate the actual configured interpreter; link corrected evidence; separate preflight from reviewed-experiment qualification. |
| PT 4504116622, 4504116626 | Protect child stderr locally and attempt a FAIL receipt even when cleanup fails or times out. |
| PT preflight CI nitpick | Run preflight self-tests in CI, including overwrite refusal and failure evidence. |
| PT SSRF nitpick | Exercise default-session construction with ambient proxies isolated and actual pinned validation intact. |
| PT follow-up 4504125537 | Unwanted commits stop publication until an approved history-preserving remedy is complete. |
| Orama startup nitpick (review 5815507104) | No-admin configuration validates, starts and succeeds with initially closed ports; no host listener race. |

## Execution and publication

1. Pin the current remote tips and compile inline, nested, review-level and nitpick
   findings. Preserve original reports and distinguish verified defects from claims.
2. Assign disjoint ownership, reproduce failures, and consolidate each component's
   changes before review. Do not repeatedly chase individual line suggestions.
3. Run regressions, complete affected suites and full paired suites under the
   documented interpreter/reaping harness. Check docstrings, mirrored bytes,
   historical JSONL prefixes and candidate immutability.
4. Commit logical batches: memory integrity; PT authority/replay/adapters; Orama
   adapter and pinned test contract; Windows evidence and test debt. Finalize PT's
   immutable producer SHA before committing the Orama test pin.
5. Inspect every unpublished commit and the final trees. If unwanted commits are
   found, STOP. Use only an explicitly approved remedy preserving signed history;
   no unauthorized amend, rebase, force-push or publication hiding the problem.
6. Publish each repository once for this batch, PT first so its immutable object is
   reachable before Orama CI. Reuse the two PRs. Reply in every bot inline thread
   with its verified disposition and evidence: for a fixed finding, cite the actual fixing
   commit as `@BotName we fixed this in commit FULL_SHA`; for a withdrawn, already
   correct, or unresolved finding, explain the disposition without claiming a fix.
   Include any bounded disagreement.
   Report review-level nitpicks separately when no inline root exists.
7. Recheck exact-head CI and new review feedback. Do not merge red or pending work.
   Source success does not activate serving or close host qualification.

## Remaining operational boundaries

Physical POSIX and Windows evidence precedes C9/R6 independent review, C10/R7
operator pin and C11/R8 separate activation/canary/expiry/rollback. PT stays manual;
compatibility shims remain. The experimental SQLite preflight is not the required
reviewed locking experiment, and GitHub-hosted Windows CI is not service-identity
or power-loss qualification. Record final results and fixing SHAs in PR follow-ups
and the downloadable handoff; never silently overwrite this dated plan as evidence.

For separate Git directories, stop all old and new dispatch processes before
upgrading or changing `PT_STATE_DIR`. An existing legacy `.state` location is
retained; a fresh layout uses the Git common directory. If both locations exist,
dispatch refuses until an operator reconciles the ledgers. Do not copy, delete,
or select between competing claims without an approved reconciliation procedure.
Mixed-version processes cannot coordinate location selection safely.
An existing legacy parent `.state` can also be shared by independent separate
Git directories under that parent; it does not identify its owning repository.
Keep dispatch stopped until an operator has established ownership and explicitly
selected or reconciled the ledger. Git discovery failures and parent-repository
discovery remain open authority-resolution risks; passing inherited Git settings
through without validation is not a safe substitute for an explicit design.

## Local verification receipt — 2026-11-08 UTC

- PT, Python 3.12.14: `python -m pytest -q tests/`
  `docs/next/windows-dryrun-20261108/test_sqlite_lock_preflight.py`:
  **3,264 passed, 76 skipped, 12 warnings**, 161.85 seconds.
- Orama, paired PT roots configured, Python 3.12.14:
  `python scripts/ci/run_with_subreaper.py python -m pytest -q tests/`:
  **3,405 passed, 94 skipped, 3 warnings, 21 subtests passed**, 148.33 seconds.
- Touched Python documentation: PT **681/681**, Orama **241/241**. Markdown
  checks, whitespace checks and three mirrored endpoint/containment files pass.
- Both structured histories and original candidates retain their published bytes.
  This batch repairs tooling/search behavior; it does not edit historical JSONL.
- Warnings remain visible, including old async resource-lifecycle/deprecation
  warnings; zero failing tests is not a claim of zero warning debt.

Independent review drove the nested-symlink and empty-effective-model regressions.
The current Cursor selector is checked, not falsely treated as an implicit model;
unsupported policy selections refuse. Unverifiable legacy composite dispatch
requires an adapter upgrade; the marked paired implementation retains guarded
fan-out. The Windows experiment remains experimental with no physical-host result.
Publication and exact-head remote CI receipts follow in the PR discussion.
