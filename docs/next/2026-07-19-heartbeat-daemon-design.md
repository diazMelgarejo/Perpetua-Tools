# Multi-worktree heartbeat daemon — design scoping (not implemented)

Status: DESIGN ONLY, per explicit instruction — scope now, build later.
Origin: item (c) of `Coordination-Consolidation Part 3: plan next steps-87099ab9`
("multi-worktree heartbeat daemon"), the one item from that task that isn't
already done or already satisfied (see the board note on that task_id for
(a)/(b)'s resolution).

## Two separable problems, don't conflate them

Investigating this surfaced a concrete bug distinct from the "daemon" ask.
Splitting them avoids over-building: the bug has a five-line fix; the daemon
is a real design question that deserves its own decision, not inheritance
from the bug's urgency.

### Problem 1 (bug, not scoped here as a daemon): stale `Worktree:` field

**Root cause, verified by reading the code, not guessed:**
`orchestrator/heartbeat_monitor.py::find_agent_heartbeats()` builds each
agent's display record from folded heartbeat events. It updates
`last_registration` (which the `Worktree:` field in `heartbeat check`/
`heartbeat list` reads from) **only on an `agent_register` event** — never
on `agent_pulse`, even though `agent_pulse` events already carry their own
fresh `worktree: current_worktree_label()` field (confirmed: both
`register_agent()` in `claims.py` and the pulse-emit call in `cli.py`'s
`_heartbeat_pulse` stamp `worktree` the same way, at call time). If an agent
registers once, then later moves to a different worktree and just calls
`heartbeat pulse` (no re-register), every subsequent `heartbeat check`
still reports the FIRST worktree, forever.

**This is not hypothetical** — hit it twice this session with
`codex-primary-orchestrator`: registered against
`docs/coordination-consolidation-plan-20260717` (2026-07-17, `pr258-coordination-review`
agent-type), never re-registered, and every `heartbeat check` since kept
reporting that stale location even while its actual work (verified via
board `agent_note` timestamps) had moved to
`coordination-consolidation-part2-20260719` days later. Cost real
investigation time twice to confirm it was stale metadata, not a second
live worktree.

**Fix** (small, not a daemon): in `find_agent_heartbeats()`, also update a
`current_worktree` field (separate from `last_registration`, which should
stay a true historical snapshot) whenever ANY event for that agent carries
a `worktree` key — register or pulse, whichever is more recent. Display
layer (`_heartbeat_check`/`_heartbeat_list` in `cli.py`) reads
`current_worktree` instead of `last_registration.worktree`. No new
infrastructure, no new event kind, no daemon — the data already exists on
the wire, it's just not being read.

Not implemented in this doc per the "scope now, build later" instruction,
but flagging: this is a five-line, low-risk, immediately-actionable fix
that doesn't need daemon design work first. Worth doing standalone,
whenever the depth call for it is made.

### Problem 2 (the actual "daemon" scoping)

What would a standing background process add that the fixed
`find_agent_heartbeats()` (problem 1) doesn't already give you on-demand?

**What already exists, on-demand, no daemon:**
- `heartbeat check <agent>` / `heartbeat list` / `heartbeat dashboard` —
  pull-based, computed fresh from the GossipBus event log every call.
- `heartbeat cleanup` — releases claims held by agents classified DEAD,
  but only when explicitly invoked (confirmed this session:
  `lesson_4b5e00553026` — it does NOT run automatically, and does not
  cover job-queue claims at all, only the legacy claim/release table).
- Liveness thresholds already defined: ACTIVE <60s, IDLE <300s, STALLED
  <1800s, DEAD >=1800s (`heartbeat_monitor.py:26-28`).

**What a daemon would add — three genuinely distinct capabilities, worth
deciding on independently rather than bundling into one "daemon" project:**

1. **Proactive DEAD-agent alerting.** Right now, nobody learns an agent
   went DEAD until someone happens to run `heartbeat check`/`dashboard`.
   A daemon could poll on an interval and post a board `agent_note` (or an
   external notification) the moment an agent crosses the DEAD threshold
   with an unreleased claim — turning today's "discover by accident" into
   "told proactively." This is the capability most directly motivated by
   this session's own pattern (discovering Codex's dead claim only because
   the user separately reported it out-of-band).

2. **Automatic stale-claim cleanup**, i.e. `heartbeat cleanup` running on
   its own schedule instead of requiring manual invocation. Lower-risk than
   it sounds since `cleanup_stale_claims()` already exists and is already
   scoped to a `max_age_seconds` threshold (default 1800) — a daemon here
   is mostly "call this existing function on a timer," not new logic. Real
   design question: does an automatically-released claim need its own
   distinct board event (so it's visually distinguishable from a
   human/agent-initiated cleanup), and what's the right interval (too
   short risks racing a genuinely-still-working agent whose last pulse
   just hasn't landed yet; too long defeats the point).

3. **Cross-worktree/cross-repo dashboard aggregation.** Today, `heartbeat
   list` only sees whatever GossipBus DB the CALLING worktree resolves to
   (canonical per-repo via `git rev-parse --git-common-dir`, per this
   session's own verified finding on GossipBus DB-path resolution) — so a
   single call never shows PT and orama-system's boards together, and
   never shows a different machine's board without the separate LAN-gossip
   bridge. A daemon COULD poll multiple DBs/machines and merge a unified
   view. This is the most speculative of the three and the least
   motivated by anything actually observed as a pain point this session —
   flagging it as the lowest-priority of the three, not a given.

**Open design questions if/when this gets built** (not answered here,
deliberately — these are the actual decisions, not implementation detail):
- Where does it run — a real background process (launchd/systemd-style,
  matching the `com.orama.network-watch` precedent already used for LAN
  discovery), or a lightweight check invoked from each skill's own
  preamble (no standing process, cheaper, but only as fresh as the last
  invocation of anything)?
- Does it need its own event kind on the bus (e.g. `daemon_alert`), or
  does it just call the existing `log`/`agent_note` mechanism?
- Single daemon per machine (covers every worktree of every repo via the
  canonical git-common-dir resolution already established) vs. per-repo?
  Per-machine seems right given the DB is already keyed that way, but
  worth confirming against how PT vs. orama-system boards are actually
  used in practice.
- Failure mode: if the daemon itself dies, does anything notice? (Same
  class of problem it's meant to solve for other agents — worth explicitly
  deciding rather than accidentally recursing.)

## Recommendation

Do Problem 1's fix on its own — it's small, isolated, high-confidence, and
already proven valuable (would have saved real investigation time twice
this session). Treat Problem 2 as three separable proposals, not one
"daemon" ticket — capability 1 (proactive DEAD alerting) has the clearest,
most-recently-demonstrated motivation; capability 3 (cross-repo dashboard)
is speculative and shouldn't be built on the strength of this session's
evidence alone.
