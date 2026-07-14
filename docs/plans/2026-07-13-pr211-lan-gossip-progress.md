---
title: PR211 LAN Gossip Bridge Remediation Progress
status: review-ready
created: 2026-07-13
pr: 211
branch: kimi-lan-peer-job-board
---

# PR211 LAN Gossip Bridge Remediation Progress

This document tracks the final CodeRabbit remediation pass for PR #211.

## Scope

PR #211 extends the intra-host GossipBus job board to opt-in LAN peers.

The remediation pass follows [`2026-07-13-branch-local-pattern-remediation-card.md`](2026-07-13-branch-local-pattern-remediation-card.md): cluster by failure class, fix the owning abstraction, add tests, and keep all writes on the PR branch.

## Failure classes

| Class | Status | Owner files | Resolution |
|---|---:|---|---|
| F1: Global event identity | Done | `orchestrator/gossip_bus.py`, `orchestrator/lan_gossip_bridge.py`, `tests/test_lan_gossip_bridge.py` | Added UUID-backed event identity, idempotent replay, bridge UUID forwarding, and UUID-dedup tests. |
| F2: Canonical DB initialization | Done | `orchestrator/gossip_bus.py`, `orchestrator/fastapi_app.py` | `GossipBus()` now resolves canonical `.state/perpetua_core.db` and lazily initializes before public reads/writes, covering FastAPI fallback and first-request paths. |
| F3: Gossip endpoint auth | Done | `orchestrator/fastapi_app.py`, `orchestrator/lan_gossip_bridge.py`, `tests/test_lan_gossip_bridge.py` | Existing endpoint guard remains; bridge now forwards `X-Gossip-Secret` when `GOSSIP_SHARED_SECRET` is configured. |
| F4: Peer concurrency/logging | Already satisfied | `orchestrator/lan_gossip_bridge.py` | Existing code uses `asyncio.gather(..., return_exceptions=True)` and `logger.debug` for peer failures. |
| F5: Bridge init API | Already satisfied | `orchestrator/lan_gossip_bridge.py` | `LanGossipBridge.init_db()` delegates to `self.local.init_db()`. |

## Implementation notes

- Logical event identity is `uuid` / `event_uuid`.
- Local SQLite ordering identity is still `row_id`.
- LAN merge key is `uuid`.
- Sort order remains `(ts, row_id)` descending.
- The bridge forwards UUID both as top-level `uuid` and as private payload envelope `_gossip_uuid` for compatibility with endpoint models that ignore unknown top-level fields.
- `GossipBus` strips `_gossip_uuid` before persistence, so transport metadata does not pollute stored/searchable event payloads.

## Constraints observed

- Work stayed on PR branch `kimi-lan-peer-job-board`.
- PR remains unmerged for human review.
- A full-file FastAPI replacement was not repeated after the connector blocked it because the file includes sensitive control-plane auth plumbing. The canonical initialization guarantee was instead pushed down into `GossipBus`, the owning storage abstraction.

## Validation checklist

- [x] PR #211 head branch identified.
- [x] CodeRabbit threads classified by failure class.
- [x] Already-fixed gather/debug/init comments verified as already satisfied.
- [x] UUID dedup fixed at storage and bridge layers.
- [x] Gossip auth header forwarding added to peer client.
- [x] Canonical DB/lazy init fixed at storage boundary.
- [x] Regression tests updated for UUID dedup, auth forwarding, and forwarded UUID stripping.
- [ ] CI green on final branch head.
- [ ] Human review completed.
- [ ] PR merged by operator, not agent.

## Suggested local validation

```bash
python -m pytest tests/test_lan_gossip_bridge.py -q
python -m pytest tests/test_lan_gossip_bridge.py::test_bridge_tail_deduplicates_by_uuid_with_distinct_row_ids -q
python -m pytest tests/test_lan_gossip_bridge.py::test_gossip_bus_strips_forwarded_uuid_from_stored_payload -q
```

Run broader CI before merge if local checks pass.
