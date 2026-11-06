# Closure K1-K4 chronicle (2026-11-06)

## Provenance and publication

Author/actor: codex-reviewer (self-reported identity). Contributions preserve
Claude's review proposals, AGY/Cline inventories and remediation, and the
GPT-6.1 Terra medium builders Darwin, Kierkegaard and Raman. Test results are
bounded evidence, not operator approval, deployment or all-agent endorsement.

Existing PRs only: Orama477 `cf87c340`, PT481 `66c4af6d`, Oramasys95 `89da844c`.
All three live heads passed hosted checks when freshly read during closeout.
One initial push per repository was followed by one explicitly authorized
Oramasys-only corrective push. No merge, force-push, deployment or activation.

## K1-K3 fixes and review receipts

- Orama wrapper `8ddd9144` detects linked worktrees and ignores inherited Git
  location variables during discovery. Its real worktree regression proves
  actual pointer checking and drift refusal, not a successful skip.
- Canonical pointer format may use two lines. Never hand-edit downstream
  pointers. Orama CI uses an explicit immutable PT peer pin because the paired
  branches have different names. Explicit checkout failure cannot fall back to
  unrelated main. Land Orama477 before PT481 and rerun main parity afterward.
- PT `d75d3671` skips bare root/home redaction fragments while preserving full
  legacy-label redaction. `2eb26264` reports broken process barriers;
  `57eb3412` stops reader threads even when producer futures fail.
- Oramasys `f52a3ed` rejects unhashable failure classes with an audited 400;
  `b23a678` distinguishes a normal not-running worker from an unexpected
  RuntimeError that must produce failed state. `e964fde` removes the test race
  between a background recovery sweep and a competing manual sweep.
- `d79182a` preserves resolver outages as unavailable instead of swallowing an
  exception and allowing after transient recovery. None/not-found remains
  distinct. `7cb054f` asserts the specific refusal, not any exception.
- Outbox integrity documentation, ledger hold/cap scope, async JSONL adapter
  incompatibility, per-instance writer locking, controller status and the
  trusted-matcher/D6-validation distinction were corrected against code.
- All13 Claude items received dispositions;16 new inline comments received
  exact-SHA replies. Root IDs and detailed receipts remain on the PRs and the
  canonical GossipBus, not in mutable convenience snapshots.

## Optional-dependency CI lesson

The first complete local run used the real producer and passed3185 tests with
2 skips, but hosted base/oracle jobs found7 benchmark-test setup errors because
the new test file imported optional Phylax APIs from the base-test directory.
The R3 candidate jobs and inert rehearsal passed; production dependencies were
not missing by accident and must not be expanded to hide the placement error.

Correction `89da844c` moves those tests into the existing `r3_interop` lane.
With Phylax blocked,3079 passed and2 skipped. With the real required producer,
3185 passed and2 skipped. Seven focused benchmark tests pass; a missing required
producer still fails collection. The base remains Phylax-free. Always test both
dependency modes before publication, not only the richest developer environment.

PT validation:319 passed. Changed-PR Python function/class docstrings:
PT194/194, Oramasys409/409, Orama10/10. Ruff, changed-doc lint, pointer and map
parity passed. Local results are not native Windows qualification.

## Operator policy and boundaries

The six J1 decisions are directly confirmed. D1 keeps PT coordination manual;
automatic expiry belongs to the separate v2 Controller. Keep shims, raw history
node-local and LAN exports sanitized. No legacy Core Doc69 retrofit.

C3d needs the operator, not a second human. The operator personally performs a
fresh interactive GitHub login and accepts exact final heads and review scope.
An agent cannot perform or sign that ceremony. Existing tokens prove neither
freshness nor review. Future independent-reviewer configuration is backlog,
initially operator-only, not a fictitious implemented runtime policy flag.
Independent Release R6 deployment review is a different gate and was not waived.

Serving remains off, the grant-serving environment flag unset and library
default `governed=False`. No actor may infer activation from green CI or C3d.

## C6 measurements and K4 handoff

Claude's supplied Mac APFS runs at89da844c missed the approved first-try and
p99 budgets; one also missed final-error budget. Control A, no refresh during
800 sends, had zero unavailable/final errors and p99 about50ms. Control B,
one sender with refresh, still had failures and p99 about397ms. The evidence
implicates refresh interference; a convoy is an inference, not a proven cause.

Profile evidence reports triple signature verification per refresh, including
the complete already-stored feed inside cache/store write locks. Fsync alone
is not established as the bottleneck. Keep failures fail-closed while reducing
duplicate work; never widen timeout or disable durable-clock checks blindly.

The benchmark now preserves configured feed size, counts snapshot failures,
refuses unfinished refresh threads and preflights descriptor capacity without
changing host limits. Fixed-size refresh does not model newly appended events.
Synthetic CI smoke is not physical-filesystem qualification. Measure scheduled
latency to avoid coordinated omission; retain exact error-rate bounds rather
than treating zero errors in2400 sends as proof of a0.1 percent upper bound.

K4 starts in a NEW worktree/branch from89da844c. Preserve the accepted PR95 head.
Revised priority: incremental digest-prefix ingest, then trust-bound verification
reuse only if needed; lock/WAL restructuring is later. No read-only lookup or
group-committed clock without a separate security decision. Public ingest must
retain signature, fork, gap, anchor and rollback refusals. Freshness commits last.

K4 commit gate: RED regressions, full producer/base suites, security checks and
THREE operator-run Mac C6 passes at every approved threshold plus controls.
Until then, no K4 commit, push, new PR or merge. The resulting new head requires
its own operator C3d acceptance. Native Windows follows the final lock design;
do not qualify a design twice or infer Windows success from Mac evidence.

## Source records

Gossip topics: `CLOSURE_K1_K3_TERRA61_DISPATCH_20261106`,
`CLOSURE_FINAL_CI_OPTIONAL_DEPENDENCY_CORRECTION_20261106`,
`CLOSURE_ORAMASYS95_CORRECTIVE_PUSH_AUTHORIZED_PUBLISHED_20261106`.
K4 queue task suffix: `4928923b` (board6335).
K5 delta-review follow-up suffix: `c732720b`, dependent on completed K1-K3.
The queued review source has SHA256
`476ac6cd8db54b2eacfa23de1d78afa3bcb96f5c85013049f72a9961aaafafc9`.
K4's first security analysis rejects a plain caller-asserted preverified flag:
the store's public duplicate-signature contract must remain intact. No K4 code
or commit was made merely to satisfy a performance hypothesis. A scoped verifier
on the existing trusted port is a candidate for review, not ratified authority.
Off-repo references are named, not copied with private absolute paths:
`2026-11-06-review-fix-proposals-for-codex.md`,
`2026-11-06-k1-k3-final-review-and-c6-handoff.md`,
`2026-11-06-c6-debug-and-next-iteration-design.md`,
`2026-11-06-c6-control-a-no-refresh.txt`,
`2026-11-06-c6-control-b-one-sender.txt`.
