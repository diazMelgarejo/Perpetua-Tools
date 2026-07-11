# Phase 2 Integration Backlog — PR #203 Deferred TODOs

**Date:** 2026-07-11  
**Source:** Codex architectural review of PR #203 blend execution  
**Status:** Ready for Phase 2 planning  
**Confidence:** 4/5

---

## Executive Summary

PR #203 (StateTransitionManager integration) successfully wired G4→G5 and G6 security gates but deferred two architectural gaps that Sonnet's plan underestimated. Neither is a blocker for merge (no concurrent caller path exists yet), but both must be addressed in Phase 2 for production robustness.

---

## TODO #1: Bounded Observation Deduplication

**Issue:** `_seen_observations` cache in Lineage B was declared but never read/written — dead scaffolding.

**Impact:** StateTransitionManager accepts duplicate observations from the same peer+epoch+sequence, risking replay attacks if downstream handlers don't re-check dedup.

**Root Cause:** Sonnet's plan assumed Lineage B's cache implementation was functional; it was actually unused.

**Priority:** Medium (risk lives in injected EquivocationLog, not STM state; concurrent caller can retry idempotently)

**Acceptance Criteria:**
- [ ] Implement bounded observation dedup (max 500 entries, LRU or TTL-based)
- [ ] Dedup key: canonical hash of (peer_id, epoch, sequence, observation_type)
- [ ] Document eviction policy (time-to-live or LRU count)
- [ ] Add 5+ tests covering dedup gate (accept first, reject second, eviction)
- [ ] Verify no memory leak under high-observation rate

**Suggested Approach:**
- Use `functools.lru_cache` with max_size=500 for the digest computation
- OR use OrderedDict with timestamp-based eviction (TTL: 10 minutes)
- Add a bounded cache alongside existing `_seen_observations` set

**Effort:** 2–3 hours (implementation + tests)

---

## TODO #2: Async-Safe Concurrency Model

**Issue:** Sonnet's threading.RLock() doesn't serialize async pipeline (no atomicity across `await` points).

**Impact:** Two concurrent `evaluate_observation` calls on the same peer could race on `_last_applied_key` and `_peer_locks`, leading to out-of-order state transitions or missed dedup checks.

**Root Cause:** Sonnet used a threading primitive (RLock) for async code. In asyncio, locks between `await` points don't guarantee atomicity because the event loop can interleave tasks.

**Priority:** Medium (no concurrent caller path exists yet; future orchestrator must use this)

**Acceptance Criteria:**
- [ ] Replace per-peer asyncio.Lock with a single pipeline lock serializing full `evaluate_observation`
- [ ] Document locking strategy (single global lock vs. per-peer async.Lock with explicit ordering)
- [ ] Add 3+ tests covering concurrent observation races (same peer, different epochs)
- [ ] Verify no deadlock under heavy concurrency
- [ ] Benchmark latency impact (lock contention on high-peer-count deployments)

**Suggested Approach:**
- Add `self._pipeline_lock: asyncio.Lock = asyncio.Lock()` to constructor
- Wrap full `async def evaluate_observation` body: `async with self._pipeline_lock:`
- OR per-peer: `lock = self._peer_locks.setdefault(peer_id, asyncio.Lock())`; current code already does this at line 267

**Effort:** 1–2 hours (refactor + tests)

---

## Why Neither is a Blocker

1. **Dedup risk:** EquivocationLog already deduplicates observations at inject time (if caller doesn't re-check, that's their bug, not STM's)
2. **Concurrency risk:** No caller in the orchestrator exists yet that would invoke `evaluate_observation` concurrently on the same peer
3. **Phase 1b scope:** Original plan was "integrate existing gates," not "harden for production concurrency"

---

## Phase 2 Planning

These TODOs should be:
- Tracked in the gossip board (agent_coordination.py) as Phase 2 tasks
- Prioritized after Phase 1 completion and Phase 2a gates (G2, G3, G7)
- Scoped as "Phase 2b: StateTransitionManager hardening"

**Estimated Phase 2 scope:**
- Phase 2a: G2/G3/G7 gate integration (1 week)
- Phase 2b: STM dedup + concurrency (2–3 days)
- Phase 2c: Full integration tests (2–3 days)

---

## Related

- PR #203: https://github.com/diazMelgarejo/Perpetua-Tools/pull/203
- 2026-07-11-PR203-BLEND-VERDICT.md (contains correction note)
- LESSONS.md (2026-07-11 entry)
- agent_coordination.py (job board)

**Validator:** Codex (GPT-5.5)  
**Confidence Level:** 4/5  
**Decision Rationale:** Codex architectural verification of Lineage B's actual implementation; threading vs. asyncio distinction; current caller coverage analysis.
