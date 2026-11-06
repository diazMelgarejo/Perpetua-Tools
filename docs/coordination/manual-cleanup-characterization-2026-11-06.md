# Manual stale-claim cleanup: v1 characterization (2026-11-06)

Closure row C2, Perpetua-Tools part. Canonical register: Orama
`docs/v2/MASTER-CLOSURE-AND-IMPLEMENTATION-PLAN-2026-11-06.md`. This record
describes current behavior. It does not change it, approve it, or specify the
v2 claim contract, which belongs to Oramasys under Orama doc 68.

Decisions applied: D1 keeps PT manual. Automatic expiry and release belong to
the v2 Controller only, so this repository adds no daemon, scheduler, or
automatic cleanup. D2 retains the compatibility shims; removing callers is a
separate later decision.

Pinned by `tests/test_coordination_manual_cleanup_characterization.py`. Those
tests pass on current code by design. They record behavior, including the known
gaps listed below; they do not endorse it.

## Owners and call path

| Step | Owner | Notes |
| --- | --- | --- |
| `heartbeat cleanup` CLI leaf | `orchestrator/coordination/cli.py` | One of seven one-shot heartbeat leaves; no `daemon` leaf exists |
| `_heartbeat_cleanup(bus)` | `orchestrator/coordination/liveness.py` | Calls `cleanup_stale_claims(bus)` with defaults, prints, returns `None` |
| `cleanup_stale_claims(bus, max_age_seconds=1800)` | `orchestrator/heartbeat_monitor.py` | Legacy `agent_claim` sweep, then the queue sweep |
| `cleanup_stale_queue_claims(bus, dead_agent_ids)` | `orchestrator/coordination/task_queue.py` | Releases `task_claims` rows held by dead agents |
| `release_claim_with_event(...)` | `task_queue.py` | `BEGIN IMMEDIATE`, conditional delete and event in one transaction |
| `current_worktree_label()` | `orchestrator/coordination/paths.py` | Producer label on emitted events (see C4) |

The August 23 draft's `orchestrator/coordination/heartbeat.py` and its
`heartbeat_cleanup(bus, stale_threshold_sec=...)` call do not exist. Neither
does `daemon.py`.

## Behavior

Liveness classification:

- `find_agent_heartbeats` folds `agent_register`, `agent_claim`,
  `agent_release`, `agent_killed` and `agent_pulse` events. The newest event
  sets the activity timestamp. DEAD means more than 1800 s since that event, or
  an explicit kill not followed by a register or pulse.
- An agent with no such events is unknown, not DEAD. If it holds a queue claim
  (for example, from a direct `try_atomic_claim` with no presence pulse), cleanup
  never releases that claim.
- `max_age_seconds` is accepted but unused. Only the fixed thresholds apply.

Legacy `agent_claim` sweep:

- Releases claims held by agents classified as DEAD. Each release is a plain
  `agent_release` append with `auto_released: true`, the reason
  `"agent dead for 30+ min"`, the original holder's `agent_id`, and the claim's
  label copied from the claim (`None` when the claim had none).
- Atomicity: none across the sweep. Liveness is read once, before any release.
  The release is not conditional on the holder's latest heartbeat, so a pulse
  landing between classification and release does not prevent the release
  (time-of-check/time-of-use).
- Failure: an emit error raises `GossipBusError` and stops the sweep. Releases
  already appended stay; the list of released tasks is lost to the caller.
- Running it again does nothing more, because the first run closed the claims.
- `heartbeat kill` releases nothing by itself. A separate `heartbeat cleanup` is
  required, and it then releases even recent claims of the killed agent.

Queue `task_claims` sweep:

- Selects rows held by the dead set, then releases each one through
  `release_claim_with_event(..., expected_agent_id=<holder>)`. The delete is
  conditional on the holder inside `BEGIN IMMEDIATE`. If the row changed hands
  after the select, the result is `LOST_RACE` and the new holder's row stays.
- Lock contention is retried three times with short backoff. A final
  `CONTENTION` is silently skipped: it is neither reported nor raised.
- Each released task gets a `task_failed` event with status `queued`,
  `assigned_agent: null` and the note `Auto-released: agent <id> dead; task
  returned to queue`. `retry_count` is copied unchanged and not compared with
  `max_retries`. This is the resurrection gap recorded in
  `lesson_8e8d5636d1c8`.
- Holder liveness is not rechecked inside the transaction; there is no lease,
  expiry, version or fencing token.

Read and failure surface:

- CLI: prints `released: a, b` or `no stale claims released`. The exit code is
  0 in both cases. `GossipBusError` (for example, a corrupt database detected at
  initialization) prints `ERROR:` on stderr and exits 1.
- In-process: liveness reads use raw SQL through `bus.connect()`. A store error
  after initialization surfaces as `sqlite3.Error` (through `aiosqlite`), not as
  `GossipBusError`.
- With `GOSSIP_PEERS` set, the CLI builds a `LanGossipBridge`. Release events are
  stored locally first, then forwarded best effort. The sweep reads local state
  only.

## Known in-repo callers

A repository search lists known callers only. It cannot enumerate external
installations, private scripts, or operator habits, so D2 keeps every shim.

| Caller | Kind |
| --- | --- |
| `scripts/agent_coordination.py`, `agent_coordination_core.py`, `agent_coordination_legacy.py`, `agent_coordination_phases.py` | Compatibility shims re-exporting `orchestrator.coordination.cli` |
| `orchestrator/coordination/cli.py` (`heartbeat cleanup`) | Only production call site of `_heartbeat_cleanup` |
| `orchestrator/heartbeat_monitor.py` | Only production call site of `cleanup_stale_queue_claims` |
| `tests/test_agent_coordination_heartbeat.py`, `test_task_queue_presence_pulse.py`, `test_agent_coordination_cli_contract.py`, this characterization suite | Tests |
| `PHASE_TRACKING.md`, `docs/heartbeat-monitoring.md`, `.agents/skills/agent-coordination-heartbeat/SKILL.md` | Operator instructions (manual invocation) |
| Orama `bin/orama-system/skills/hermes-harness/scripts/coord_comms_board.ps1` | Cross-repository script that calls `scripts/agent_coordination.py` |

No caller in Oramasys or Perpetua Core was found in the reference checkouts
searched on 2026-11-06. That result covers those checkouts, not every
deployment.

## Implications for the v2 contract

These gaps are inputs to the v2 claim contract. They are not PT work items under
D1:

1. Staleness is read outside the release transaction. v2 must check expiry and
   the current claim version inside the authoritative transaction.
2. There is no fencing: a late or partitioned v1 worker can still act after its
   claim was released.
3. Requeue ignores retry exhaustion and uncertain external effects.
4. Contention outcomes are silently dropped.

Live, multi-host and crash evidence for v1 cleanup is owner-held. None of the
tests above is live evidence.
