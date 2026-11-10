# Native Windows evidence, real Cline run and qualification status (2026-11-10)

Author/actor: Claude Code on the Windows host acting as win-researcher (self-reported,
identity_verified=false). V = run on the Windows host. P = reported by a peer. U = unverified.
Scrubbed: no addresses, host names, workstation paths, tokens or fingerprints. This records events
and lessons; it is not an approval, a qualification or a merge.

## Events

| Event | Evidence | Status |
| --- | --- | --- |
| The Mac took ownership of the three defect areas in orama PR 487 and asked for a write hold on 487 and PT 487, 488, 489; Windows acknowledged and held | LAN files, topics WIN-HOLD-ACK and WIN-CORRECTION | V |
| The Mac resolved the not-sent question: any nonzero exit after launch is `unknown`; only a missing CLI or failed spawn is `not-sent` (orama 487 head 69cb2ea7; 76f096df adds a Cline folder fallback) | Mac answers file | P |
| Windows reran 130 tests on 69cb2ea7 in a throwaway checkout | 130 passed, 1 skipped, hygiene pass | V |
| The Cline session ran the assigned native lock tests (board item CLINE-PICKUP-10) and sent three files to the Mac | file hashes matched; 5 tests rerun by Windows | V |
| Windows added native process tests and a status receipt; orama 488 merged the 487 head (4899d17c); orama PR 489 opened on top (head ba406c77) | 10 native tests pass; mutation checks fail as expected | V |
| Real Cline 3.0.74 through the controller: completes with a pinned model, fails with "model not found" without one | one call each, plan mode, scratch directory | V |
| The Mac pushed four commits to PT 489 (head 6983f740); the episodic gate passes on it | gate output against main and the previous head | V |
| Qualification register H01 to H10 reviewed: Windows is NOT qualified | receipt in orama PR 489 | V |

## Lessons

1. A test is evidence only if it fails when the code is broken. A Cline regression test passed
   with and
   without its fix; the two native test files here fail under mutation (lock forced on: 5 of 5;
   prompt
   routed through the cmd shim: 3 of 5). LIVE: orama PR 489 tests.
2. A misleading error can hide the real one. Cline printed a hook-dispatch error before "model not
   found". Reproduce in a clean context, pin the model, and withdraw a hypothesis as soon as a
   reproduction contradicts it. HISTORY: "likely repository-scope hooks" (withdrawn).
3. Verify a silent tool failure before acting on its result. A patch step run with the Windows Store
   python stub did nothing and an unrevised draft reached a peer. Read an edit back before
   sending; if a
   stale message goes out, send a correction that names what it supersedes.
4. The peer-send sanitizer refuses long token-like strings, including long file names. Describe a
   file;
   quote hashes only in a receipt line.
5. `git worktree add` with a relative path resolves against the worktree you run it from and can
   nest
   the new one. Use absolute paths.
6. "Qualify now" is not a code action. Qualification is a register of physical, human-only and
   account or trust gates. Do the native, bounded parts, keep an honest status table, hand the
   rest to
   the operator.
7. Stack by ancestry without touching a held PR: merge the held PR's head into your own PR branch
   so it
   is an ancestor; never push to the held branch.
8. When a peer owns a rule change, accept it and list what becomes stale (tests, lessons, ledger
   rows)
   instead of re-arguing. The Mac chose "any nonzero exit is unknown".
9. To assign work to a local Cline session, queue a board item with a written brief that states
   the hard
   limits (no pushes to held branches, plan mode unless act mode is authorised, report through the
   send
   script), then verify its evidence yourself (hash, rerun, mutation) before relaying it.
