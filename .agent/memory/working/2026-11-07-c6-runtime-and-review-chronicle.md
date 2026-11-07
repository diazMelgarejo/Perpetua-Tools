# C6 Runtime, Verified-Feed and Review Chronicle (2026-11-07)

**Latest outcome:** the operator accepted the Mac receipt and local logical
commits; see the closing addendum. Earlier pending states below are retained
history, not the current qualification status. Windows and new-head C3d
remain separate; no C6 publication or activation is claimed.

## Scope and Attribution

Author/actor: codex-reviewer, self-reported identity. Claude authored the
original C6 controls/profile and the November 7 plan review. An independent
read-only agent review (Franklin, instance
`01a1b2b9-05b9-7b00-8af5-8f0f0b9b78c0`) found three additional implementation
issues. Do not convert their analysis or these tests into human approval.

This record delivers the verified-local portion of queued K6,
`closure-CLOSURE-K6-C6-verified-chronicle-lessons-domain-knowledge-20261107-bce450d0`.
The operator subsequently requested this chronicle, lessons and domain record
on the existing PT PR. The original K4 dependency and future qualification
addendum remain gated: no task-complete event or operator evidence is invented.

Earlier history remains in
`2026-11-06-closure-k1-k4-chronicle.md` and
`WEEKLY_DURABLE_FIXES_2026-11-02_TO_2026-11-05.md`; neither is rewritten.
Existing review lanes are PT #481 and orama-system #477. This record is authored
before its own publication; the final Gossip closeout supplies publication SHAs.

## Runtime and Design Sequence

1. The supplied Mac APFS runs at Oramasys `89da844c` missed first-try and p99
   budgets; run 2 also missed final-error budget. No-refresh control A had zero
   failures/800, whereas one-sender control B still failed during refresh.
2. The profile attributed 769 signature verifications to one refresh: three
   passes over 256 event signatures plus the state signature. In-lock crypto
   was supported by the profile, not initially a direct lock-hold measurement.
   A convoy was only a hypothesis; FULL/fsync was not the demonstrated cause.
3. Exa/Firecrawl research was checked against primary SQLite transaction,
   busy-handler, WAL and synchronous documentation. WAL still permits one
   writer, longer timeouts do not cure lock cycles, and NORMAL is not a neutral
   durability change. Research never authorized a new authority model.
4. The old Python 3.13.0 embedded SQLite 3.45.3. A separate patched CLI did not
   change that Python library, nor did a loader-path experiment. An isolated
   Python 3.11 build proved a patched runtime existed, then the operator chose
   the latest available Python 3.13 distribution instead.
5. The selected Astral build was Python 3.13.18 with SQLite 3.53.1, source ID
   `2026-05-05 10:34:17 c88b22011a54b4f6fbd149e9f8e4de77658ce58143a1af0e3785e4e6475127e9`.
   A temporary WAL/FULL integrity smoke passed. That was not C6 qualification.
6. Claude F1-F6 refined the plan: unmodified baseline first; actual-serving
   SQLite evidence because the production store already uses WAL; direct
   writer-hold spans; a safety floor rather than exact-version rejection; cold
   versus steady refresh; explicit no-refresh control behavior.
7. Installing isolated pinned dependencies enabled the UNMODIFIED 2400-send
   baseline on the patched library. It still produced seven final errors,
   p99 412.79 ms and refresh p95 1007.49 ms. The WAL-reset fix was necessary
   correctness work, not the contention fix.

## Implementation and Adversarial Review

- Oramasys candidate base remains
  `89da844c5c62d3e91e78ffa3a7865598fab759f2`; the final staged tree is
  `ef6d27c165626cb36900369b7a924bdc641c9435`, NOT a new commit SHA.
- Full detached-feed authentication stays outside write locks. A private,
  bounded, success-only exact event verifier feeds the existing trusted store
  port. Public ingest SQL, duplicate signatures, fork/gap/anchor refusals and
  acknowledgement-before-freshness ordering were retained.
- Previous snapshots are authenticated outside locks too. Exact-byte changes
  after preparation refuse instead of silently replaying under the write lock.
  No public verified flag, bulk-prefix bypass or new proof authority was added.
- Initial RED probes observed locked crypto and locked old-snapshot replay.
  The first candidate eliminated final errors but still missed scheduled p95:
  62.47 ms versus the 50 ms budget. This justified the plan's bounded next step.
- Lookup clock observation and decision now share one FULL transaction. Forward
  observations commit before stale/trust/callback refusals propagate. This is
  not in-memory clock authority or group commit.
- Independent review caught quadratic multi-key resolver reads, prewarm
  refusals bypassing observation, and missing failed/delayed refresh samples.
  All three were reproduced RED and fixed. Another RED test showed retirement
  inside the approval callback could allow a lookup; final trust sampling
  now refuses. Key sampling is not an atomic external trust-generation service.
- The harness uses absolute arrival schedules, all-outcome denominators,
  queue/service latency, per-refresh schedules/outcomes, safe SQLite codes and
  writer wait/hold envelopes. Cold initialization remains separate.

## Bounded Verification Evidence

| Final local check | Result |
| --- | --- |
| Oramasys real-producer suite | 3214 passed, 2 skipped |
| Isolated Phylax-free suite | 3087 passed, 2 skipped |
| Runtime/interop subset | 120 passed |
| Historical producer contract subsets | 9 passed on each of a7211df and b2edfe9 |
| Ruff, network-authority guard, staged whitespace | passed |
| Changed Python docstrings and annotations | 180 definitions, no omissions |

The expected skips are ownership-registry and clean-installed deployment
evidence. An extra optional LangChain skip was traced and restored using the
canonical oracle pin 1.0.7, not suppressed. This is local Python 3.13 evidence,
not hosted CI, the full Python 3.11/3.12 matrix or native Windows qualification.

| Same-harness diagnostic | Original adapter | Final candidate |
| --- | ---: | ---: |
| Sends | 2400 | 2400 |
| Scheduled p95 / p99 | 93.00 / 625.48 ms | 47.55 / 209.29 ms |
| First-try unavailable | 26 | 2 |
| Final errors | 7 | 0 |
| Refresh p95 | 1016.57 ms | 622.52 ms |
| Cache writer-hold maximum | 592.58 ms | 6.87 ms |

Both final agent controls had zero failures: A had 800 sends/no refresh,
p95/p99 45.29/52.55 ms; B had 600 sends/seven refreshes, p95/p99
19.85/203.04 ms. APFS device matching, sample uniqueness/counts, artifact
digests and exact runtime-fingerprint equality were independently checked.
Synthetic event-verify median was 0.7491 ms over 50 samples.

These are AGENT diagnostics. Zero errors/2400 has an approximately 0.1247%
one-sided 95% binomial upper bound, not a population guarantee <=0.1%; temporal
correlation adds another limitation. No operator-run pass is claimed here.

## Subsequent Independent Repetition (Gossip Row 6359)

Claude reported independent verification of the exact staged tree by exporting
it into a scratch Git repository: producer 3214/2 skipped and producer-free
3087/2 skipped. An initial export without Git metadata produced 25 false test
failures; restoring the repository precondition resolved them. This is reported
independent evidence, not a new Codex-run suite or human acceptance.

Claude's separate 2400-send AGENT diagnostic had no first-try/final failures,
cache hold max 6.65 ms and refresh p95 about 634 ms, BUT successful-call p95
53.3 ms and scheduled p95 57.7 ms both exceeded 50 ms. The single Codex pass
above is therefore not repeatable qualification. Both latency definitions must
be retained; their authoritative threshold binding remains an operator decision.
Neither runtime changes nor changed scheduling/denominators alone explain an
apparent old/new p95 comparison without a controlled baseline.

The eight review lessons are retained across the domain reference and native
lessons: inspect the actual embedded engine; falsify hypotheses with controls;
measure lock holds directly; profile before redesigning; do not inflate the
deliberate 100 ms deadlock-avoidance timeout; include serving SQLite in C7/C8;
do not silently migrate metric definitions; preserve Git preconditions in test
exports. Claude's producer-code inspection covered 1d2f2bb only; the separate
Codex historical-producer test receipts above remain separately attributed.

Claude also reported prior acceptance of PT 66c4af6d and queued K7 for runtime
adoption. The live PR was independently checked at 022bf51a before this batch.
The operator's current direct one-push instruction authorizes these review and
memory updates, NOT acceptance of their future new heads. Renew exact-head
review after publication; do not perform K7 global/runtime changes from a board
claim, erase the accepted history or waive the C6 hold.

## Current Review Remediation

### Subsequent Operator Amendment and K8

On 2026-11-07 the operator directly re-ratified p95 at 60 ms, applied to
both scheduled latency and successful-call send latency. Scheduled p99
at most 250 ms and every other budget remain unchanged. Claude's prior
diagnostic meets the amended p95 limits but remains agent evidence, not
one of the three operator passes. Historical 50 ms comparisons above
are preserved as measurements against their then-applicable target.

K8 was claimed through the native queue and completed by updating only
the C6 runbook and budget proposal, preserving the historical budget row.
Markdown lint, staged whitespace and no-unstaged-change checks passed.
The new frozen tree is `5f35692ad7af891965e85e5b0bd0bce8b66ebc6d`,
superseding `ef6d27c165626cb36900369b7a924bdc641c9435`. The harness
and implementation are unchanged. Operator passes must use the new tree;
no commit, push, qualification or activation follows from K8 completion.

### Publication Batch

Before operator passes, Franklin's read-only K5 delta audit found two
remaining documentation inaccuracies: holds were described as keyed by
`run_id` rather than integer-keyed and tagged by `run_id`; the JSONL
ledger's lock was described as process-wide rather than per instance.
Codex claimed K5, corrected the disposition row and source documentation,
and proved the executable AST unchanged. All 35 ledger tests passed;
changed-module docstrings were 9/9 and Markdown/whitespace checks passed.
The final staged C6 tree is `c63581c508a92675b01d8e441b13fa993b1482c6`,
superseding the intermediate K8 tree above. No operator pass, C6 commit
or publication is claimed. K9 remained absent from the canonical search
and queue; clarification was requested rather than inventing ownership.

The operator requested consolidation into one existing PR per repository,
one final push each, inline fixing-SHA replies, and a Gossip closeout.

- Orama review 5798928745: bind CI to tested commit/base/head/tree rather than
  label a synthetic merge as exact-head CI; remove the stale push hold while
  retaining the merge barrier.
- PT review 5802274772: move all async identity/collision discovery off the
  loop without caching its result; redact exact known branch tokens and reject
  residual labels anywhere in derived recall/export; isolate unit-test sibling
  discovery and subprocess cwd/PYTHONPATH; close SQLite fixtures after commit.
- Known complete branch tokens are private even if they resemble ordinary
  words. Larger identifiers and surrounding prose stay intact; structured
  branch/ref references retain their coverage. No raw history is rewritten.
- An older ADR-pointer thread refers to the companion generator's previous
  format. Orama `9ecdf955d6edfaf542a1bd535f044f1afae85ee2` already synchronizes
  the split-line format; complete-file checking against PT succeeds.

Publication and inline replies are subsequent events, not fabricated by this
pre-commit record. The C6 code worktree remains staged/unpublished; this PT
memory record does not waive its three-operator-run commit gate, exact-head
C3d, Windows qualification, deployment, trust or serving barriers.

## Durable References

Native-writer graduated lessons: `lesson_8c6d41c0759b` (linear prepared trust),
`lesson_4ed064cdd5d9` (durable prewarm refusal), `lesson_16f1df978247`
(residual topology), `lesson_6578cb464163` (off-loop identity), and
`lesson_64abeaf88a4f` (tested-tree CI binding), `lesson_4c5caf9ba844`
(Git metadata in candidate exports), and `lesson_fe2edf12886b` (explicit
latency populations and dated threshold amendments). Their episode and graduation
records retain append-only lineage; the attribution-envelope episode binds
the batch to its self-reported actor without rewriting historical rows.

- `semantic/C6_SQLITE_AND_VERIFIED_FEED_DOMAIN_KNOWLEDGE_2026-11-07.md`
- Gossip plan `7d013071c04f48ea93189a24e3ae44b9`; Claude review
  `f8eaae63ae0548939dcac949bdd024ba`.
- Resume `fe75f7a9a26a47779047c79d027fd3e6`; progress
  `cde3318360be458ba8be1c2032c21959`, `561d4938f2be475eba78c85f217a0b6b`,
  `be892e1f0ef640148c7e6695ba14e6b7`.
- Verified-local handoff `f52d1558c4074895a70620a6de3794fa`.
- Local evidence uses the configurable `$REFERENCE_ROOT` directory and dated
  C6 plan, review, execution ledger, computed verification receipt and raw
  diagnostic artifacts; concrete workstation mappings remain node-local.

## Operator-Directed Runs, Acceptance and Local Commits

K9 added Claude's Windows handoff to the same C6 candidate. Its final frozen
tree was `30ec3c74b87d2fcc6797c1c9905072a59278b7ae`, superseding all
intermediate tree identifiers above. The operator explicitly allowed Codex
execution while retaining explicit receipt acceptance as a separate step.

The runner preflight first stopped before any benchmark cell because the
selected uv environment had no pip. Its files were preserved. Offline uv
freeze targeting the explicit interpreter produced a byte-identical inventory
without installing or changing anything. Seven helper preflight tests passed.
The helper creates exclusive 0700 evidence/temp directories, rejects receipt
collisions, counts failed receipt writes, uses the selected interpreter for
judging, records helper digests and checks the tree at completion. The old
shared 0755 temporary directory was not changed or reused.

| Cell | Sends | Scheduled p95 ms | Successful-call p95 ms | Scheduled p99 ms | Refresh p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| No-refresh control | 800 | 37.09 | 31.20 | 57.37 | N/A |
| One-sender control | 600 | 16.74 | 11.93 | 209.08 | 645.79 |
| Trial 1 | 2,400 | 51.26 | 42.60 | 143.59 | 633.21 |
| Trial 2 | 2,400 | 45.83 | 38.76 | 219.64 | 654.47 |
| Trial 3 | 2,400 | 40.98 | 35.29 | 146.40 | 685.09 |

All cells had zero first-attempt unavailability, zero final errors and zero
refresh failures. An independent raw audit checked 8,600 unique sends,
absolute pacing, monotonic samples, outcome accounting, raw percentiles,
refresh stages including the control, runtime/dependency identity, APFS,
private permissions, code/helper digests and the frozen tree. It did not
pool controls and trials into an unsupported long-run guarantee. Per-trial
zero/2,400 still has an approximately 0.1247% upper 95% binomial bound.

The operator directly answered: "Accept Mac receipt; make local logical
commits only." The accepted raw receipt SHA-256 is
`606cecf7a8a693241378adead2a31f6f2a679e7d9251d04b0a147b4dfdc9ec9f`.
Acceptance was saved separately; the original pending receipt was not edited.
Four local Oramasys commits preserve dependency order and self-reported agent
trailers: `078823a1` runtime, `22194657` harness, `22c62db5` adapter and
`9dc38569d22745d54b3e09718f254ad8889e2e37` documentation. The final committed
tree exactly equals the measured tree and the worktree is clean. Standard
Git commits were used because this repository has no commit wrapper; no
hooks were bypassed. Post-commit real-producer suite: 3,214 passed;
Phylax-free suite: 3,087 passed, each with two explicit deployment skips.
Focused safety/ledger: 143 passed. Changed-file
docstrings: 195/195; Ruff and Markdown checks passed.

K4's local implementation/measurement scope is complete. Native Windows,
longer confidence runs, fresh-auth exact-new-head C3d, publication, merge,
deployment and serving activation remain separate. PR #95 was independently
verified unchanged at `89da844c`. Claude retains K10 on existing Orama #478.

K6 now follows its completed K4 dependency locally on the existing PT #481
line; no additional push is authorized. New single-incident candidates
`73d79fbe6645` (pip-free inventory) and `02c827dbcb5f` (runner integrity)
are staged through native tools for later recurrence review, not falsely
graduated. Existing accepted lessons and episodic history are preserved.
