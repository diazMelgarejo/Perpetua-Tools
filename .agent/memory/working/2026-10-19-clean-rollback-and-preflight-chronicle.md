# 2026-10-19 chronicle: a corrected suggestion, a chain-event fix and a hardened preflight

**Status:** working record for the 24 hours to 2026-10-19 UTC. It extends
`2026-10-18-stacked-pr-c2-no-change-required-chronicle.md`, which holds the 2026-10-18 detail.
Facts were re-checked against live GitHub and git state while writing.

**Current next actions (Addendum 2; read first, repeated at the end).**

1. Operator: answer D1 (push both slice-1 branches and open one PR per repository), D2 (delete the
   stale remote branch on merged PR 421) and D3 (pin promotion, still gated on evidence and
   approval).
2. Codex: finish its review of the Oramasys consumer; its issuer-slice verdict is already
   APPROVE_WITH_SCOPE.
3. Claude: after D1, push each branch once as a fast-forward and open its single PR.
4. Nobody pushes the slice-1 branches or enables serving; `ORAMA_GRANT_SERVING` stays unset.

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

- Gemini CLI exited with an ineligible-tier error. Per the maintainers' 2026-06-18 notice, access
  ended for free, Google AI Pro and Google AI Ultra individual accounts; enterprise Code Assist
  licences and API-key authentication were stated as unaffected. The operator confirmed Antigravity
  replaced it for this account. The observed headless `agy` shell command was auto-denied, so the
  diff was inlined with tools forbidden; this was a command-permission failure, not a general
  workspace file-read restriction.
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
| `lesson_4641b912197a` | Headless `agy` needs the diff inlined; superseded by `lesson_8458726d8699`, then `lesson_e552b1994a46`, which scopes the observed limitation to shell-command permission while retaining the individual-account Gemini CLI claim |
| `lesson_ac036153c85a` | Check merged state first; superseded by `lesson_0744027558a8` (a push to a merged branch does not update main) |
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
   inlined when the requested shell command lacks permission.
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

## Addendum 2: the verify-everything round

**Current next actions (Addendum 2; read first, repeated at the end).**

1. Operator: answer D1 (push both slice-1 branches and open one PR per repository), D2 (delete the
   stale remote branch on merged PR 421) and D3 (pin promotion, still gated on evidence and
   approval).
2. Codex: finish its review of the Oramasys consumer; its issuer-slice verdict is already
   APPROVE_WITH_SCOPE.
3. Claude: after D1, push each branch once as a fast-forward and open its single PR.
4. Nobody pushes the slice-1 branches or enables serving; `ORAMA_GRANT_SERVING` stays unset.

### A9. Outcomes

| Item | State |
| --- | --- |
| Phylax issuer branch | `2026-10-19-e1-c2-issuer-slice1`, head `f0b73c8`, 12 commits on `origin/main`, not pushed |
| Oramasys consumer branch | `2026-10-19-e1-c2-consumer-slice1`, head `812e0f3`, 8 commits on `origin/main`, not pushed |
| Tests | Phylax 397 passed at 91.6 percent coverage (14 warnings, the baseline); Oramasys 171 target tests, 1622 in the whole suite minus two files that need an uninstalled package |
| Interop with real Ed25519ph | 7 of 7 scenarios, including a validly signed permit for another ledger refused and a rolled-back issuer refused as a fork |
| Independent verdicts | Codex APPROVE_WITH_SCOPE (issuer slice, head `fdafdbf`); Agnes APPROVE_SCOPED (both tracks); neither approves serving, T3 or a pin |

Every subagent result was re-verified by the orchestrator: suites re-run, the code read against the
ratified rules, and its own mutation tests run, including guards the subagent had not listed.

### A10. What two parallel audits found, and how each was decided

* **Issuer (4 minor):** adopted the permit `R_p` floor on a stored-finalization retry and DDL-text
  schema
  validation; declined to refuse a stored retry after key rotation (a lost-response retry must not
  be
  stranded) and pinned that with a test; check order left alone.
* **Drift (2 major, 5 minor):** adopted the consumer ledger binding and a revocation port that can
  express approval-chain and issuer revocation; persisted a rule 5 fork after the rollback (only a
  signed finalization can reach that path); consumer lifetime caps; ASCII-only timestamps and
  classified
  wire errors on both sides.
* **Cline's code review (6 findings):** none held. After a literal proof rule it checked each with
  `wc -l` and `grep -n` and retracted all six. Across its two reviews none of its nine findings
  identified a defect, while its mechanical jobs (withdrawal, push disable, checklist, retraction)
  were
  accurate once the instructions were literal.
* **A stale peer branch** was not opened as a PR: a trial merge into current main conflicted and
  defined
  the registry twice.

### A11. Open items and gaps

* D1 to D3 await the operator. An auditor's note asked agents not to push until Codex finishes and
  the
  operator answers; that is advice, and it matches the commitment already posted on the board.
* Slice 1 still omits attested abandon and successor, operator lookup and authentication, the
  consumer
  client rules, request-side and catch-up validators, the v2 grant parser and the revocation and
  cascade event body shapes.
* The manifest lists `t3-implementation` and `production-pin-promotion` as disabled; enabling them
  is an
  explicit operator-approved change.

### A13. Warnings fixed and the interop proof moved into both repositories

* The 14 baseline warnings were `ResourceWarning: unclosed database` from verification stores that
  tests opened and dropped without `close()`. An autouse test fixture now closes them; the Phylax
  suite is 397 passed with no warnings and product code needed no change.
* The interop probe now lives in both repositories at `src/tests/interop/c2_interop_probe.py`
  (byte-identical; CI compares the copies). Each repository checks the other out at a one-line pin
  file and runs the probe with only PyNaCl; Oramasys product code stays free of any crypto import.
* Pins are bumped as part of pin promotion, and the checklist records the step. A mutation of the
  issuer's lifetime in a pinned clone made the probe fail, so the guard catches drift.

### A12. Lessons graduated in this addendum

| Lesson | Topic |
| --- | --- |
| `lesson_7abca1f63f8e` | Literal instructions plus a proof rule make compliance checkable; verify with git |
| `lesson_fad63c66c85c` | A reviewer proves each finding with `wc -l` and `grep -n`; spec-required behaviour is not a finding |
| `lesson_85d99b949d74` | Reject a stale peer branch by trial-merging it in a throwaway worktree |
| `lesson_91ee41fa2d80` | ASCII-only regexes and classified wire errors on both sides |
| `lesson_51e864040865` | Validate a persisted schema by its DDL text, not by names |
| `lesson_3a8f4e9f0578` | Audit consumer-versus-issuer drift and every identity and port the consumer must bind |
| `lesson_15164c58cd51` | Prove interop with a probe kept outside both repositories |
| `lesson_9bc31664e7a4` | A free-text queue dependency makes a task unclaimable; enqueue a replacement |
| `lesson_e8c02dec5c0b` | A stale tracking ref is not a remote; use `ls-remote` |
| `lesson_78ee5ae76aa5` | sqlite3's context manager does not close; superseded by `lesson_3629269b36c1`, `lesson_56388c966812`, then `lesson_57abee3ce829` |
| `lesson_57abee3ce829` | Preserve transaction and close semantics with `closing` as the outer context or a close-always helper; the context manager is a no-op with Python 3.12+ `autocommit=True`, while Python 3.11 `isolation_level=None` only disables implicit transaction opening |
| `lesson_74187a494b5f` | Trace a hold to its source; your own posted commitment is the binding one |

**Current next actions (repeated).**

1. Operator: answer D1 (push both slice-1 branches and open one PR per repository), D2 (delete the
   stale remote branch on merged PR 421) and D3 (pin promotion, still gated on evidence and
   approval).
2. Codex: finish its review of the Oramasys consumer; its issuer-slice verdict is already
   APPROVE_WITH_SCOPE.
3. Claude: after D1, push each branch once as a fast-forward and open its single PR.
4. Nobody pushes the slice-1 branches or enables serving; `ORAMA_GRANT_SERVING` stays unset.

