# Independent Verification of PR #357 and PR #6 Recovery Claims (2026-09-13)

**Relationship to existing memory:** additive companion to
`ORAMA_PR357_PR_BODY_INTEGRITY_FALSE_POSITIVE_AND_RECOVERY_2026-09-13.md`
and `PERPETUA_CORE_PR6_RECOVERY_ARCHITECTURE_AND_REVIEW_LESSONS_2026-09-13.md`.
Those two documents record the incident and recovery from the perspective of
the session that introduced and fixed the bug. This document records a
*different* thing: the methodology a separate session used to independently
verify those recovery claims before trusting or building on them, since the
two are not the same activity and neither substitutes for the other.

## What was verified, and how, not just what was claimed

Given three job URLs and no prior context, the verification sequence was:

1. **Fetch the actual job logs**, not the job's rendered summary page (which
   requires authentication to show logs at all) — via
   `GET /repos/{owner}/{repo}/actions/jobs/{job_id}/logs`, not by reading a
   GitHub UI page.
2. **Resolve each run to its exact head SHA and branch** via
   `GET /repos/{owner}/{repo}/actions/runs/{run_id}` before assuming which
   commit a job's failure applied to — two of the three given URLs shared a
   head SHA, one didn't; this was not obvious from the URLs alone.
3. **Read the actual failing assertion text** from the log, not just the
   check-run's pass/fail status, to form an independent hypothesis about
   root cause before reading any other agent's own diagnosis of it.
4. **Reproduce the suspected mechanism directly**, isolated from the real
   script: a standalone bash snippet simulating exactly the write-then-
   readback sequence (`printf '%s\n'` then a round-trip through `$(cat ...)`
   command substitution), checked byte-for-byte with `od`, before touching
   the real script at all. This confirmed the hypothesis was mechanistically
   sound, not merely plausible.
5. **Apply the fix, then verify real RED-then-GREEN** against the actual
   script and actual test file: `git stash` the fix, confirm the exact same
   failure reproduces locally; `git stash pop`, confirm both tests pass.
6. **Run the full test suite**, not just the two directly-relevant tests, and
   independently investigate every other failure rather than assume they're
   related — three unrelated failures were found, checked against the
   pre-fix state (identical failures, confirming pre-existing), and traced
   to a missing `jq` binary in the local sandbox specifically, not a real CI
   condition.
7. When a separate agent's own retrospective was later provided, **treat it
   as a claim to check, not a fact to inherit** — independently reproduced
   its central technical claim (the exact byte-count mismatch, 12 vs 11
   bytes) before citing it as established, and cross-referenced its cited
   commit SHAs and file sizes against the live repository rather than
   quoting them uncritically.

## Why this is a distinct, reusable pattern

The two companion documents are rich with what went wrong and how it was
fixed. This addendum is about a different failure mode entirely: **trusting
a relayed or self-reported recovery without independently checking any of
it.** A retrospective that is well-written, detailed, and internally
consistent is still a claim about the world, not a substitute for checking
the world. The check that matters most is the one already established
earlier this session as `lesson_d7a13d8bc5fb` (the four integrity levels)
applied one level up: a *narrative* about local validity, a write, and a
remote check is not itself proof that the narrative's own claims are
accurate — it deserves the same fetch-and-verify treatment as any single
claimed fact within it.

## Durable pattern for future agents inheriting another session's incident report

When handed a detailed incident/recovery report from another agent or
session, before building on it or citing it as settled:

- [ ] Fetch the actual current state of every artifact the report claims to
  have fixed (file content, blob SHA, byte count, CI status) — independently,
  not by trusting the report's own citation of those values.
- [ ] Where the report makes a technical/mechanistic claim (a chunk-size
  math, an encoding boundary, a race condition), reproduce it directly with
  minimal, isolated code before treating it as established.
- [ ] Where the report cites commit SHAs, PR numbers, or CI run IDs, resolve
  each one against the live API and confirm it says what the report claims.
- [ ] Distinguish, in whatever you write next, what you personally verified
  from what you are relaying on the strength of the other report alone —
  the same provenance discipline already established for reconstructing an
  unreachable session's work applies equally to a reachable one whose claims
  simply haven't been checked yet.

## Evidence references

- Independently reproduced trailing-newline mismatch: 12 bytes (local,
  `printf '%s\n'`) vs. 11 bytes (round-tripped through `$(cat ...)`),
  confirmed with `od -c`.
- Independently verified real RED (`git stash`, exact CI failure text
  reproduced locally) and real GREEN (`git stash pop`, both tests pass).
- Independently confirmed 3 unrelated local test failures were pre-existing
  (identical with and without the fix) and environment-specific (missing
  `jq`), not related to the incident under investigation.
- Independently confirmed `oramasys/perpetua-core` PR #6's final merged head
  (`a7a6624092a747538094f3d07779a0fa09fb8da9`) and current `main`'s
  `requirements/test-agate-compat.txt` content match the companion
  document's account exactly, before citing that document's architecture
  section as accurate.
