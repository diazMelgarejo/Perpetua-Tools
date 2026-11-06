# Concurrency and replication coverage (2026-11-06)

Closure row C5, Perpetua-Tools part. Canonical register: Orama
`docs/v2/MASTER-CLOSURE-AND-IMPLEMENTATION-PLAN-2026-11-06.md` ("Part 3 review
and revised scope", items 5 and 6). Tests:
`tests/test_coordination_concurrency_replication.py`. The tests cover existing
behavior; no runtime code changed for C5.

## Evidence labels

All results are **simulated-local**: one host, temporary SQLite files, asyncio
tasks or local OS processes, and respx-mocked peers. No live LAN, crash or
multi-host evidence was collected. That evidence is owner-held.

## Covered

| Concern | Result |
| --- | --- |
| Ten-worker claim race (coroutines and ten spawned OS processes) | Exactly one `won`; every outcome is in `{won, lost_race, contention}`; one `task_claims` row and one `task_claim` event, both naming the winner. Loser outcomes are not counted per type. |
| Ten workers at `queue claim` level | One success line; nine errors, each from the known message set |
| Bounded lock handling | With a write lock held, claim and release return `contention` after exactly `_LOCK_RETRIES` (3) attempts. Neither leaves a row change or an event. |
| Duplicate events | The same event UUID, sent directly or in the `_gossip_uuid` envelope, is stored once and reported as not newly inserted |
| Shuffled, duplicated replay to a replica | The replica holds exactly the source's UUID set: nothing dropped, nothing duplicated |
| Acknowledgement | `LanGossipBridge.emit` returns a UUID only after the local commit. Peer 500 or connection errors do not change it. A failed local write raises and contacts no peer. Fifty concurrent emits: every returned UUID is stored. |

## Characterized gaps (not fixed in PT under D1)

- **Replica order:** v1 folds claim state in local arrival order. A replica that
  receives a release before its claim reports the claim as open. Replicated
  gossip is therefore not claim authority, consistent with doc 68.
- **Reorder buffer capacity:** `ReorderBuffer` has no capacity bound and no
  refusal. The test buffers 2000 out-of-order claims to show the absence of a
  bound; it does not set a limit. Duplicates keep the first buffered claim.
  Claims below the watermark are dropped without any signal.
- **Drain after a gap:** a forced `buffer drain` jumps the watermark past the
  gap, and a gap claim that arrives later is then dropped silently.
- **Peer acknowledgement:** peers are fire-and-forget. There is no delivery
  receipt and no retry, so a peer can miss an event the local log holds.

Each gap is an input to the v2 contract or an owner decision. None is a PT
daemon or protocol change under D1.
