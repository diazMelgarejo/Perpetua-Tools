# Heartbeat vs. Log Liveness Gap — 2026-07-18

## Status

Fixed on my (Claude/`claude-sonnet-g7-impl`) side. Recording here so the
mechanism is documented, not just the fix.

## What happened

Codex posted a HIGH-priority board question asking all agents to disclose
private/off-board worktrees, and separately flagged, correctly, that
`claude-sonnet-g7-impl` was showing as **STALLED** (not dead — stalled) on
the coordination board despite having posted numerous substantive `log()`
updates across the session (PR review findings, sync status, memory
graduations, worktree reports).

## Root cause

`log()` and `heartbeat pulse()` are two different GossipBus event kinds.
Liveness/stall detection only looks at `pulse()` events. Posting frequent,
detailed `log()` messages does not refresh liveness state — an agent can be
actively working and communicating substantively, and still read as stalled
to every peer agent watching the board, purely because it never called
`heartbeat pulse <agent_id>` as its own explicit action.

This is not obvious from the CLI's own naming — `log` reads like the
general-purpose "post something" verb, and it's easy to assume it also
counts as presence. It doesn't.

## Fix

```bash
python3 scripts/agent_coordination.py heartbeat pulse <agent_id>
```

Called directly, independent of whatever `log()` posting is already
happening. Confirmed cleared the stalled state.

## Durable lesson

Recorded as `lesson_e8c57f92b1b9` in `.agent/memory/semantic/lessons.jsonl`:

> On the GossipBus coordination board, `log()` events and `heartbeat
> pulse()` events are tracked separately by liveness detection. Posting
> frequent log() status updates does NOT keep an agent's heartbeat fresh —
> an agent can be actively working, posting substantive updates via
> log(), and still show as STALLED (not DEAD, but stalled) to peer agents
> if it never calls `heartbeat pulse <agent_id>` directly. Call heartbeat
> pulse periodically as its own explicit action, independent of whatever
> log() posting is already happening.

## For future agents (any harness, not just Claude)

If you're posting `log()` updates on a long session and haven't separately
called `heartbeat pulse` in a while, do it now — don't assume communication
activity substitutes for liveness signaling. The two are unrelated
mechanisms on this board.

Related, not duplicate: `lesson_f139b30f67df` (post the same status through
every distinct channel — board log, PR comment, heartbeat — since a partner
may not be actively polling any single one). That lesson is about
redundancy across channels for a given piece of news. This one is about a
structural gap between two specific event kinds on the same channel.
