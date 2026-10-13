# AlphaClaw bind-host lesson provenance — 2026-09-28

## Purpose

This record remediates the evidence link for the accepted PT semantic lesson
[`lesson_1bbee93ff11e`](../semantic/LESSONS.md) without changing its claim, original
evidence timestamp, or September 28, 2026 acceptance date.

## Historical lesson and evidence ID

- **Lesson:** AlphaClaw Express defaults to a loopback bind on bare metal and uses
  `0.0.0.0` only in Docker or when `ALPHACLAW_BIND_HOST` is explicitly set.
- **Candidate:** [`1bbee93ff11e`](../candidates/graduated/1bbee93ff11e.json)
- **Original evidence ID / staged timestamp:** `2026-09-28T09:14:56.898944+00:00`
- **Acceptance timestamps (recorded in two places, which differ; both preserved unchanged):**
  - Candidate `1bbee93ff11e.json` `accepted_at`: `2026-09-28T09:14:57.155274+00:00`
  - Both `lesson_1bbee93ff11e` rows in `semantic/lessons.jsonl` `accepted_at`:
    `2026-09-28T09:14:57.115805+00:00`
  - The roughly 40 ms difference is historical. Neither record was rewritten.

The preserved live episodic log and the available September 28 archive did not
contain a row at the original evidence ID. They therefore could not prove the
candidate's historical reference by themselves.

## Independently verified implementation source

The underlying implementation exists in the local AlphaClaw worktree at
`$HOME/code/OpenClaw/AlphaClaw`:

- **Branch:** `subagent/mac-orchestrator/alphaclaw-bind-host`
- **Commit:** `55d06572b2ebb9f9a5350eead962ba97db43d6b4`
- **Commit timestamp:** `2026-09-28T17:10:48+08:00`
- **Subject:** `fix(server): loopback bind on bare metal, 0.0.0.0 in Docker`
- **Changed implementation/tests:** `lib/platform.js`,
  `lib/server/init/server-lifecycle.js`, and `tests/server/platform.test.js`

The commit implements and tests the loopback/Docker/`ALPHACLAW_BIND_HOST` behavior
described by the lesson. At the time of verification, the source commit was not an
ancestor of local `main`, `origin/main`, or `upstream/main`; it is local-only
implementation evidence, not evidence of a merged or published AlphaClaw change.

## Additive remediation

On October 12, 2026, the PT audit integration appended one
`evidence-reconstruction:lesson_1bbee93ff11e` event to
[`AGENT_LEARNINGS.jsonl`](../episodic/AGENT_LEARNINGS.jsonl). Its timestamp is the
lesson's original evidence ID so the reference resolves exactly once. The event is
explicitly marked as a reconstruction recorded during the audit integration and
contains the source branch, commit, commit time, changed paths, and local-only
publication status. It is not represented as a recovered contemporaneous runtime
event.

The semantic JSONL receives an append-only update for the same lesson ID, preserving
the original `accepted_at` date while recording this remediation rationale. The
derived `LESSONS.md` is regenerated from that structured source.