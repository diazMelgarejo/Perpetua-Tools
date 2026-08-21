# Tier-5 Ledger Bug Hunt: Method, Rigor, and Luck (2026-08-21)

**Context:** PT PR #359, CodeRabbit review #4983381866, `orchestrator/tier5_budget.py` +
`orchestrator/tiered_pipeline.py`. Six real findings fixed, one bonus bug caught that wasn't
in the review at all. This doc records *how* each was found, not just what was wrong, so the
method is repeatable next time — not luck alone.

## The method, in order

1. **Read the full review before touching code.** Both the CodeRabbit review body and a
   separately-provided local brief (`perpetua-359.md`) were read in full first — not just the
   nitpick summary, which under-represented the real findings. The "actionable comments"
   section (7 items) contained 3 findings the nitpick list (4 items) didn't mention at all
   (`explicit_cap` vs `remaining`, `release_pre_dispatch`'s missing state guard, connection
   leaks). **Rigor, not luck**: skimming the nitpick summary alone would have missed half the
   real bugs.
2. **Group into logical batches before writing any fix**, via `/oramasys-method`'s AFRP gate +
   5-stage discipline: Batch A (ledger correctness), Batch B (trace-ID identity), Batch C (doc
   Mermaid/reconciliation). This is what made it possible to commit and verify each batch
   independently instead of one undifferentiated diff.
3. **Verify every finding against the actual current code before fixing it**, not just the
   review's diff suggestion. Two of CodeRabbit's own proposed diffs were checked against the
   file as it currently stood (not the version CodeRabbit reviewed) before applying — the file
   had moved since the review ran.
4. **Fix, then write a test that would have caught the exact bug**, one test per finding, named
   for the behavior it locks in.
5. **Retroactively enforce RED before GREEN** (`docs/TDD.md` Pre-Commit Checklist item 1) via
   `git stash push --keep-index -- <code files only>` — reverts production code, keeps the new
   tests, confirms all 8 new/changed assertions fail for the *right* reason against the old
   code, then `git stash pop` to restore and confirm green. This is what turned "I wrote a
   fix and a test" into an actually-verified claim instead of an assumed one.
6. **Re-run the FULL local suite, not just the touched files, before every commit.** This is
   where the bonus bug surfaced — see below.

## Bug-by-bug: how each was actually found

### 1. `busy_timeout_ms` unvalidated
**Source:** CodeRabbit nitpick, explicit.
**Rigor:** None required beyond reading the finding and confirming the failure mode (`TypeError`
three calls deep at connect time instead of `ValueError` at construction) by tracing the call
path in the current file.

### 2. `mark_dispatch` not idempotent, no state guard, no error mapping
**Source:** CodeRabbit nitpick, explicit — but the nitpick text bundled *three* distinct bugs
into one comment. Reading past the summary line to the full "Three gaps exist here" list was
necessary to not silently fix only one of the three.

### 3. `explicit_cap_microusd` not bounded by `remaining`
**Source:** CodeRabbit's "actionable comments" block, **not** the nitpick summary. This is the
one most likely to have been missed on a skim — it wasn't flagged as a standalone comment on a
line range the way the others were, just a paragraph in the aggregated AI-agent prompt block.
**Rigor:** worked out the exact numeric scenario by hand (9,500,000 reserved of 10,000,000,
600,000 requested against a 5,000,000 explicit cap with only 500,000 truly remaining) before
writing the test, to be certain the fix's boundary condition was right, not just "looks safer."

### 4. `release_pre_dispatch` missing state predicate
**Source:** CodeRabbit nitpick + actionable block (mentioned in both, worth cross-checking
that both descriptions agreed on the exact fix before implementing).
**Rigor:** required tracing what happens to a `SETTLED` run's `held_microusd`/`settled_microusd`
if this bug fired in production — confirmed it would zero out `held_microusd` on a run whose
spend was already recorded via `settled_microusd`, silently under-counting the daily total.
That's *why* it's a real bug and not just tidiness, and why the test asserts settled_microusd
survives the failed release attempt, not just that release raises.

### 5. Five leaked `sqlite3.Connection` objects
**Source:** CodeRabbit's actionable block: "each `sqlite3.Connection` should be explicitly
closed."
**Rigor + a real near-miss:** while extracting the shared `_transaction()` helper to fix this,
the explicit `db.execute("BEGIN IMMEDIATE")` was initially dropped as "redundant with `with
db:`" — it is not (Python's sqlite3 defaults to *deferred* transactions; `with db:` never emits
its own BEGIN). This would have silently reopened the exact TOCTOU race the ledger's atomicity
depends on, with **no test failure**, because the existing test suite is single-threaded and
never exercises the race window. Caught by re-reading the diff before committing, not by any
test — this is the one place pure code review, not TDD, was the safety net. Fixed by moving
`BEGIN IMMEDIATE` *into* `_transaction()` so every call site gets it automatically instead of
needing to remember it.

### 6. `load_pipeline_approval` trusts the artifact's embedded `trace_id`
**Source:** CodeRabbit's actionable block, `tiered_pipeline.py` line 194.
**Rigor:** read the full function to understand the actual attack shape (file looked up by
filename = requested trace_id, but the *returned object's* `.trace_id` field came from the
file's own JSON content) before writing the fix, then wrote a test that directly demonstrates
the divergence (register under one trace_id, hand-edit the artifact's embedded field to a
different value, confirm rejection) rather than a test that only checks the happy path still
works.

### 7. `TRACE_ID_MIN_LENGTH` duplicated as a literal (8 in FastAPI, 1 in `validate_trace_id`)
**Source:** CodeRabbit's actionable block.
**Rigor:** this one had a real regression risk on fix — bumping the shared minimum to 8 broke
an *existing, unrelated* test (`test_load_malformed_approval_raises`, which used the 3-character
trace_id `"bad"`). Caught immediately by running the full `test_tiered_pipeline*.py` suite
after the fix, not assumed safe. Fixed the test fixture (longer trace_id), not the code — the
code was correct, the old test's fixture just predated the stricter shared constant.

### 8. The bonus bug: `ipaddress.is_global` reports multicast as globally routable
**Source:** genuinely not in the review at all. Found by re-running the **full** local suite
(`test_ssrf_fetch_policy.py` included) as a matter of course before committing the tier5 batch,
even though that file wasn't touched this session.
**Luck, honestly:** a `hypothesis`-generated random 32-bit integer happened to land on
`224.0.0.0` (the multicast network's own base address) in this run. It could just as easily
not have — this property test had presumably passed on every prior run since the module was
written, purely because hypothesis hadn't sampled a multicast value in that exact code path
yet. **The rigor that turned luck into a real fix:** once it failed, confirmed the failure
was a real stdlib quirk (not a flaky assertion) by directly checking `is_global` against four
different multicast addresses in isolation, established that *all* multicast addresses share
this property (not just the network base), and fixed the test's ground-truth oracle rather than
either the production code (which was already correct) or dismissing the failure as noise.

## What made this repeatable, not a one-off

- Reading full review bodies, not summaries — the nitpick/actionable split hid real severity.
- Verifying against *current* code, since review diffs go stale the moment a branch moves.
- One test per finding, named for the behavior, not the line number.
- Retroactive RED/GREEN via selective `git stash` when fix-and-test were written together.
- Full-suite re-run before every commit, regardless of which files were "supposed" to be
  touched — this is what caught bug #8, and it would have caught a regression from bug #7's
  fix if the fix itself had been wrong instead of the test fixture.
- Treating a caught near-miss (the dropped `BEGIN IMMEDIATE`) as worth writing down with the
  same weight as a review-sourced bug, not a private embarrassment to skip past.

## Cross-references

- Individual atomic lessons: `lesson_cf3a7adb55d3` (connection leak), `lesson_3d9cc9f3ef55`
  (BEGIN IMMEDIATE regression), `lesson_a045e9f02292` (is_global multicast quirk),
  `lesson_516cedc1d6f1` (explicit-cap-vs-remaining pattern), `lesson_8466d1718c00`
  (git-stash TDD verification technique).
- Fix commits: `1d56a095` (Batch A, ledger), pending (Batch B trace-ID, Batch C doc, Batch D
  ssrf-policy test oracle).
- Canonical TDD discipline this session adopted going forward: `docs/TDD.md`
  (orama-system canonical, PT `docs/TDD.md` pointer).
