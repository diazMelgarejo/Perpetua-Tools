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

- Orama-system#423 CI was still running when this was written.
- The spec's operator decisions 1 to 7 remain open for the operator.
- The `/team-onboarding` guide still awaits its three answers; the Cowork VM image cleanup was
  not run.
