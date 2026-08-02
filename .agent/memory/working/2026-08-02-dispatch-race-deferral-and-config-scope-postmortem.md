# Dispatch-Race Deferral Consistency + Config-Scope Investigation — Postmortem (2026-08-02)

> Continuation of the same day's CI tool-version/gitleaks retrospective.
> Covers the orama PR #260 review-remediation arc from that point forward:
> the deferral-date internal-inconsistency bug, the duplicate-fallback +
> cancellation-safety fixes in the dispatch-race code, and the markdown
> config-scope investigation that surfaced 1032 pre-existing violations.

## Part 1 — A deferral extension that was internally inconsistent with itself

### What happened

An automated CI-autofix branch simultaneously (a) pushed a race-leg
deferral date further into the future in a tracked log file, and (b)
changed the dispatch-race function's racer dictionary from a single
`direct-lmstudio-win` entry to two new entries (`cursor`,
`hermes-lmstudio-win`). Merging that branch's content in caused a
previously-cleanly-`SKIPPED` test to start failing.

### Root cause

The test in question is explicitly gated: it only runs "while deferred"
(checking that same log file's date against today), and asserts the
*old*, single-racer behavior. The two changes bundled into that one
branch contradicted each other: extending the deferral says "the new
race legs aren't ready yet," while simultaneously wiring those new race
legs into the dispatch function says the opposite. Whichever commit
introduced both changes never actually ran the deferred-state test
against its own new racer dictionary before landing.

### The fix, and why it wasn't just "restore the newer branch's version"

Extended the deferral date further out (matching the actual ask: enough
runway for a larger, unrelated piece of work to land first), and
correspondingly kept the racer dictionary at its old, single-entry state
— consistent with an active deferral. Restoring the branch's racer
dictionary as originally written, even with the extended date, would
have reintroduced the exact same contradiction, just with a different
number in the log file.

### The lesson (Part 1)

When two changes in the same commit are meant to work together (a
feature flag and the feature it gates, a deferral date and the behavior
that respects it), verify they're actually consistent with each other
by running the specific test that exercises that consistency — not just
each change's own isolated test coverage. A change that extends a
deferral without checking what depends on that deferral being real can
silently ship a contradiction.

## Part 2 — Duplicate work and unsafe cancellation in the same race function

### Duplicate fallback

The "Hermes leg" of the race had its own internal fallback: on timeout
or failure, it called the same direct-dispatch function the race's own
top-level fallback-of-last-resort also calls when every racer fails.
Once a second race leg (Hermes) exists alongside the direct one, this
meant a single failed Hermes attempt could trigger two independent
direct-dispatch calls racing each other — the internal one and the
top-level one — genuine duplicate work, not defense in depth.

Fixed by keeping fallback handling in exactly one layer (the top-level
race function) and removing the internal fallback from the leg function
entirely.

### A related, second duplicate that the first fix's own edge case revealed

Removing the internal fallback naively (deleting the top-level
last-resort fallback branch too, to "avoid duplication" in one sweep)
would have broken a *different*, already-passing test — the top-level
last-resort fallback is intentional and necessary for the case where two
*other* legs (not the direct one) both fail; it's a duplicate only in
the specific case where the direct leg is *itself* one of the racers
that already failed. Fixed by making the top-level fallback conditional
on the direct leg not already being among the failed racers, rather than
removing it outright — the narrower, correct fix instead of the
broader, convenient one.

### Cancellation safety

The Hermes leg didn't handle `asyncio.CancelledError` explicitly while
awaiting its subprocess. When a sibling racer won and this leg got
cancelled mid-flight, its subprocess could be left running, unreaped.
Fixed by explicitly catching the cancellation, killing and awaiting the
subprocess's exit, then re-raising. The top-level race function's own
cancellation of losing racers had the same gap in the other direction —
it fired `.cancel()` on pending tasks without ever awaiting the
cancellation to actually complete, meaning the function could return
before the underlying subprocesses were actually torn down. Fixed by
awaiting all cancelled tasks via a gather-with-exceptions-suppressed
call in a `finally` block before returning.

### The lesson (Part 2)

A concurrency fix that "removes duplication" is not automatically
correct just because it removes the offending call — the same call site
can serve two different purposes depending on which specific state the
code is in, and removing it everywhere fixes one bug while introducing
a different regression. And a cancellation-related fix needs proof, not
inspection alone: the correct test doesn't just check that a value
comes back right, it checks that the *process being cancelled* is
verifiably no longer running by the time the caller gets control back.

## Part 3 — A precise config fix that reveals more than it fixes

### What was investigated

A code-review comment asked for a broad file-pattern exemption in a
markdown-lint config to be narrowed to only the specific rule it needed
to disable, rather than exempting an entire class of files from every
rule. The narrower, more precise version was built and verified to work
correctly against the real, CI-pinned linter version.

### What it actually surfaced

Running the narrower config against every file the broad pattern used
to cover revealed just over a thousand pre-existing violations across
roughly two hundred files — none introduced by the change under review,
all previously invisible because the broad exemption hid them
entirely, not just the one rule it was meant to relax.

### The decision, and why it wasn't automatic

Adopting the narrower, more "correct" config immediately would have
either failed CI on a large volume of unrelated pre-existing content, or
required absorbing a large, unplanned cleanup pass into an unrelated
PR's scope. Neither is the right trade against a review comment that
itself said "if possible and feasible." Kept the broader, working
exemption, but didn't just silently decline the suggestion either —
documented the verified narrower config directly in the file as a
comment, so the actual investigation (which config works, exactly how
many violations it surfaces, across how many files) doesn't have to be
redone by whoever eventually picks up that cleanup pass.

### The lesson (Part 3)

"More precise" and "correct to adopt right now" are different
questions. Investigating whether a stricter config is *technically*
achievable is worth doing and worth being honest about once done — but
whether to *actually adopt* it depends on the blast radius of what it
newly exposes, which can only be known by actually running it, not by
reasoning about it in the abstract. When the honest answer is "not yet,
and here's exactly why," recording that finding where the next person
will actually see it is more useful than either silently adopting a
config that will fail CI or silently declining the suggestion with no
trace of having checked.

## Part 4 — A large "test suite regression" that was entirely environmental

### What was reported

A prior session's retrospective noted a large number of test failures
as a pre-existing, out-of-scope issue, verified only by a before/after
comparison (same failures with and without the session's own changes
present) — correctly establishing that the changes weren't the cause,
but not investigating the actual root cause at the time.

### What the root cause actually was

Systematically installing each missing dependency one at a time and
re-running: the failure count dropped by an order of magnitude after
the first missing package, then continued dropping with each subsequent
one. All but two of the original failures were resolved by installing
already-declared-but-not-installed dependencies. The remaining two were
also environmental, not code bugs: one test's permission-denial
assertion doesn't hold when the process running it has elevated
privileges that bypass the restriction being tested; another test's
mocked absence of a system tool doesn't actually hide that tool when
it's genuinely present system-wide.

### The lesson

"Confirmed pre-existing, not caused by my changes" is a necessary check
before moving on, but it's not the same as understanding *why* the
failures exist, and stopping at that first check leaves a large,
alarming-looking number sitting in the record unexplained. Where
time allows, finishing the diagnosis (what specifically is missing or
different, verified by fixing it and watching the count drop) turns a
vague "pre-existing, unrelated" note into an actual, actionable
description -- in this case, confirming the gap was a one-time
environment-setup issue with zero project-level fix needed, rather than
something that might have looked, to a future reader, like it needed
investigation all over again.
