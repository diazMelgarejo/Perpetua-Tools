# 2026-10-19 chronicle: a corrected suggestion, a chain-event fix and a hardened preflight

**Status:** working record for the 24 hours to 2026-10-19 UTC. It extends
`2026-10-18-stacked-pr-c2-no-change-required-chronicle.md`, which holds the 2026-10-18 detail.
Facts were re-checked against live GitHub and git state while writing.

## 1. Achievements, last 24 hours

| Item | State |
| --- | --- |
| oramasys stack #64 (#63 digest and permit guards, #62 ruff cleanup) | Recorded in the 2026-10-18 chronicle; #62 re-seated by the operator's lease-pinned push |
| orama-system#419 finalization rollback floor (`221a51f5`) | Merged to `main`; closed the rollback-before-request case |
| Residual rollback gap after #419 | Found by modelling, corrected, shipped in orama-system#423 (`edfe65b0`) |
| Dispatcher binary preflight (#423) | Hardened PATH lookup, `cline` and `kimi` registered, plan doc corrected (`f1921369`, `1f7ea599`) |
| PT memory | 10 lessons on 2026-10-18 (PR #449, merged) and 10 more here |

## 2. The headline: my own suggestion was wrong

After fixing #419 I suggested attaching the digest of the issuer's event at `R_f` to the
finalization. Modelling a hash-chained issuer showed it fails: a clean snapshot restore has the
same history up to its own point, so a digest of an event that already exists matches. An
independent side note said the same while the model was being built.

| Rollback timing | merged floors | digest at `R_f` | finalization as chain event |
| --- | --- | --- | --- |
| none | accept | accept | accept |
| before the request | refuse at 4.2f | refuse at 4.2f | refuse at 4.2f |
| after the request, consumer then acks lost events | accept | accept | refuse at 4.3 |
| consumer never sees the lost events | accept | accept | accept |

The fix makes the finalization itself a hash-chained issuer event (15 fields). After a restore the
issuer's next event takes a version the consumer holds with a different digest, so the fork is
visible without clocks. Honest limits: the last row is invisible to the consumer and stays with
the issuer recovery witness (E1 section 8.2); finalizations now advance the issuer counter, which
is recorded as operator decision 7; the first wording over-claimed and an `agy` reviewer corrected
it (scalar floors do catch the before-request case).

## 3. Preflight review (orama-system#423)

Findings 1 to 7 from the review were fixed: `~` and relative-pathname behaviour stated, bare names
resolved on PATH only (a Windows working-directory hit is refused, empty entries are not
trusted, quoted entries are cleaned, an unset PATH falls back to the default), `cline` and `kimi`
registered with a registry, test and README drift check, both override routes tested, the CLI
unknown-agent message stated, and Windows coverage described as simulated (CI is Linux only). Two
`agy` rounds found a vacuous test, a wrong rule citation, an over-strong "no round trip" claim and
the unset-PATH edge; all fixed. One finding, to split the spec change into its own PR, was
declined at the operator's direction: one PR per repository.

## 4. Process notes

- Gemini CLI exited with an ineligible-tier error; the operator confirmed it was replaced by
  Antigravity. Headless `agy` is denied shell reads, so the diff was inlined with tools forbidden.
- My first simulation fed rule 3 the wrong request's ack and refused the healthy flow; fixed and
  re-run before any claim was made.
- A dangerous-command hook blocked a scratch cleanup; a worktree removal avoided any bypass.
- The first verdict that the PR was open was stale: orama-system#419 had merged before the
  follow-up review, so the spec was read from `main`.

## 5. Lessons graduated

| Lesson | Topic |
| --- | --- |
| `lesson_876a00234865` | Simulate a fix before offering it |
| `lesson_365e8915febd` | Make the confirming act a chain event so a rollback forks visibly |
| `lesson_ecc2f51852bb` | State a defense's scope by timing; write the residual case down |
| `lesson_0bf7efca186f` | Re-read which request's field each rule compares when modelling |
| `lesson_b2efa4c9db15` | Resolve a bare command on PATH only; clean quotes; default when unset |
| `lesson_bd36bf00dbdc` | An alternation-matching negative test passes vacuously |
| `lesson_4641b912197a` | Headless `agy` needs the diff inlined; Gemini CLI is retired |
| `lesson_ac036153c85a` | Check merged state first; extend the one open PR |
| `lesson_7839a778bb36` | Do not bypass a destructive-command hook; use the safe equivalent |
| `lesson_78858a5b8a70` | Verify a side agent's note against your own model |

## 6. Open items

- Orama-system#423 CI is green on `1481bc58`; the reviewer's exact-head review and the operator's
  ratification remain.
- The spec's operator decisions 1 to 7 remain open for the operator.
- The `/team-onboarding` guide still awaits its three answers; the Cowork VM image cleanup was
  not run.

## Addendum: the review saga and the hybrid parallel workflow

**Next actions (read first; repeated at the end).**

1. Independent reviewer: a final re-review of orama-system#423 head `1481bc58`.
2. Operator: ratify the spec by exact commit if that is clean (decision 9 is confirmed,
   section A5).
3. Merge #423: CI is green on `1481bc58` (27 of 27 checks).
4. After the merge, claim the queued oramasys and Phylax conformance task, tests failing first.
5. Later and separate: the operator's pin promotion, only on conformance evidence.

### A1. Outcomes

| Item | State |
| --- | --- |
| orama-system#423 | Head `1481bc58`: spec, dispatcher hardening, three reviewer commits (authorship kept), CI fix |
| Perpetua-Tools#450 | Open; this record and 27 lesson entries for 2026-10-19 (one supersedes another) |
| Operator decisions 1 to 9 | Recorded in the spec; decision 3 confirmed as the scoped reading |
| oramasys conformance task | Queued, unclaimed; the merged helper has no `attempt_id`, sees only live permits, has no finalization or abort |

### A2. The review saga

| Round | Who found what | What changed |
| --- | --- | --- |
| 1 | A model disproved the digest at `R_f` | Finalization became a hash-chained event |
| 2 | Reviewer: unrelated events forced permit replacement | Permit kept across a higher ack; two-grant test |
| 3 | Spec gap: ambiguity with no `permit_id` yet | Durable `attempt_id`; four ambiguity states |
| 4 | Reviewer: abort race; refusal proves no absence; retry identity | One unique row; claim withdrawn; retry rules pinned |
| 5 | Reviewer: fence vs 4.3; circular release prerequisite; one deadline | Row-lock serialization; prerequisite fixed; deadlines split |
| 6 | Three parallel analysts and `agy` passes | Lock order; abandon vs successor contradiction; retention |
| 7 | Reviewer's three local commits | Integrated by cherry-pick; one union conflict |

Round numbers are approximate groupings of about seven rounds. In every round the author's own
new text contained defects that the next review found.

### A3. The hybrid parallel workflow

1. Run read-only analysts in parallel, each on a distinct lens, plus `agy` passes with the diff
   inlined (headless `agy` is denied shell reads).
2. Give every finding to ONE writer, who applies all edits sequentially.
3. Lint, run the tests, then mutation-check the new guards.
4. Push fast-forward only. Analysts report; they never edit shared files.
5. The same pattern wrote this record: three drafting agents in parallel, one writer, then scans.

### A4. Numbers

| Measure | Value |
| --- | --- |
| Review rounds | About 7 |
| Local tests, dispatcher and bridge | 50 passed, 1 skipped |
| Mutation check on the PATH guard | 2 tests fail when it is broken |
| CI on #423 head `1481bc58` | 27 of 27 checks passed (an earlier head failed two tests, see A7) |

### A5. Decision 9 confirmation

The spec recorded decision 9 (Codex coordinates Phylax release evidence, Claude reviews it
independently, the operator approves the pin) from the reviewer's board note, which said the
operator had decided it. The orchestrating session flagged that it had no direct confirmation and
asked. The operator then confirmed it directly in this session. The record is now first-hand.
This is the case that `lesson_2e745462a494` describes.

### A7. The two late events

**Event 1: CI failed on #423 after a green run.** The head `48fbeaef` failed two simulated-Windows
tests on Linux CI. They passed on macOS. Candidate file names had been built from a case-folded
`PATHEXT`, which matches on case-insensitive filesystems and misses on case-sensitive ones. The
independent reviewer found the same cause and committed its own local fix. The two fixes were
combined: the reviewer's finding and intent, the orchestrator's structure (one function for the
configured spelling that builds names, one case-folded function that only compares), a
filesystem-independent test that records the names tried, and a reproduction on a case-sensitive
volume where the old code failed three tests and the fix passed 51. Spec rule 5 was pinned to
the canonical event object in the same commit (`1481bc58`, reviewer credited). Lessons:
`lesson_fc158090bf07` (case-insensitive hosts hide case-sensitive failures) and
`lesson_a0ffc2a1a316` (CI status belongs to one exact head).

**Event 2: a review found an overclaim in one of today's lessons.** CodeRabbit's review of #450
noted that `lesson_c6f5aa0d3de1` said a single writer means "no merge conflicts arise", while the
same session had a cherry-pick conflict. The claim was narrowed append-only: a superseding lesson
`lesson_90cf6d66e79f` now limits the guarantee to concurrent writes, and `LESSONS.md` strikes the
old claim. The general lesson is `lesson_0c28899229c2`: check a lesson's generalization against
the same day's counterexamples before graduating it.

### A8. Remaining gaps

- The reviewer's exact-head review of `1481bc58` and the operator's ratification by exact commit
  are outstanding.
- The queued conformance task's notes predate the final spec (single-row `aborted` state,
  `attempt_id`, abandon and successor request, recovery timeouts after the deadline). Queue
  notes cannot be edited, so implementers must follow spec section 5a and its freeze list.
- Not yet frozen, by design: canonical bytes beyond the finalization event, field types and
  limits, the refusal vocabulary, key selection and resource bounds.
- Left as signed-policy values and unmeasured: the catch-up bound, the throughput ceiling, the
  checkpoint interval and recovery-call timeouts. Decision 8 numbers are starting values.
- CI has no Windows runner, so Windows branches are simulated; case sensitivity is now covered by
  a host-independent test, other Windows behaviour is still unproven.
- The command-blocking hook still false-positives on `rm -rf` of scratch paths; it was not
  bypassed, and `lesson_7839a778bb36` records the rule.
- Carried over, unrelated to this work: the `/team-onboarding` answers, the Cowork VM cleanup.

### A6. Lessons graduated in this addendum

| Lesson | Topic |
| --- | --- |
| `lesson_c2fd21bf87e1` | One unique key, not lookup then write |
| `lesson_2c84b1ae8801` | Fake-store tests need a real-engine and terminal-history test |
| `lesson_f7d2c3a83789` | Re-read every touched rule; review your own text hard |
| `lesson_a765a3393eea` | No authorization that requires what it grants |
| `lesson_5e3f64a7692c` | Recovery stays callable after the deadline, without authority |
| `lesson_7016b327376a` | Durable attempt id before the first external call |
| `lesson_15e5e5d7f8d0` | Compute expiry; fence and consumer share one row lock |
| `lesson_7778729dffe1` | A signed refusal proves nothing about absence |
| `lesson_d341f33a7714` | Test an instruction's premise; ask before rewriting history |
| `lesson_c6f5aa0d3de1` | Parallel analysts, one writer |
| `lesson_055f0f81d60b` | Cherry-pick a reviewer's local commits with authorship |
| `lesson_6676e3109515` | Next actions at the head and the tail |
| `lesson_2e745462a494` | Operator-confirmed only after the operator confirms |

| `lesson_fc158090bf07` | Case-insensitive hosts hide case-sensitive failures; reproduce on a case-sensitive volume |
| `lesson_a0ffc2a1a316` | CI status belongs to one exact head |
| `lesson_0c28899229c2` | Check a lesson's generalization against the day's counterexamples |
| `lesson_90cf6d66e79f` | Supersedes `lesson_c6f5aa0d3de1`: a single writer prevents concurrent writes, not merge conflicts |

One drafted candidate was dropped: a push that prints "Everything up-to-date" after a
hook-rejected commit is already covered by `lesson_18f5ca481f90`.

**Next actions (repeated).**

1. Independent reviewer: a final re-review of orama-system#423 head `1481bc58`.
2. Operator: ratify the spec by exact commit if that is clean (decision 9 is confirmed,
   section A5).
3. Merge #423: CI is green on `1481bc58` (27 of 27 checks).
4. After the merge, claim the queued oramasys and Phylax conformance task, tests failing first.
5. Later and separate: the operator's pin promotion, only on conformance evidence.
