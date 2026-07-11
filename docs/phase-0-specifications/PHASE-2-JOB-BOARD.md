# Phase 2 Integration Job Board

**Created:** 2026-07-11  
**Source:** PR #203 blend completion (Codex review)  
**Status:** Ready for agent assignment

---

## Queued Tasks

### Task 1: Bounded Observation Deduplication

**Task ID:** TODO-stm-observation-dedup  
**Priority:** Medium  
**Effort:** 2–3 hours  
**Status:** ⏳ QUEUED (awaiting agent assignment)

**Description:**
`_seen_observations` cache in StateTransitionManager.py was declared but never read/written — dead scaffolding from Lineage B. Must implement bounded dedup to prevent replay attacks on duplicate observations.

**File:** `orchestrator/state_transition_manager.py`

**Acceptance Criteria:**
- [ ] Implement bounded observation dedup (max 500 entries, LRU or TTL-based)
- [ ] Dedup key: canonical hash of (peer_id, epoch, sequence, observation_type)
- [ ] Document eviction policy (time-to-live or LRU count)
- [ ] Add 5+ tests covering dedup gate (accept first, reject second, eviction cycles)
- [ ] Verify no memory leak under high-observation rate

**Suggested Implementation:**
```python
# Option 1: functools.lru_cache for digest
from functools import lru_cache

@lru_cache(maxsize=500)
def _dedup_digest(peer_id, epoch, seq, obs_type):
    return hash((peer_id, epoch, seq, obs_type))

# Option 2: OrderedDict with TTL
from collections import OrderedDict
from time import time

self._dedup_cache = OrderedDict()
self._dedup_ttl = 600  # 10 minutes
```

**Related Reading:**
- `2026-07-11-PHASE-2-BLOCKERS.md` § TODO #1
- `2026-07-11-state-transition-manager-integration-plan.md` § Execution Flow

**Why Non-Blocking:**
- EquivocationLog already deduplicates at inject time
- Concurrent caller can retry idempotently
- Risk is in injected log, not STM state

---

### Task 2: Async-Safe Concurrency Model

**Task ID:** TODO-stm-concurrency-model  
**Priority:** Medium  
**Effort:** 1–2 hours  
**Status:** ⏳ QUEUED (awaiting agent assignment)

**Description:**
Current per-peer `asyncio.Lock` pattern doesn't serialize the full StateTransitionManager pipeline. Concurrent `evaluate_observation` calls on the same peer can race on `_last_applied_key` and `_peer_locks`, leading to out-of-order state transitions or missed dedup checks. Sonnet's threading.RLock was rejected as unsafe for async.

**File:** `orchestrator/state_transition_manager.py`

**Acceptance Criteria:**
- [ ] Implement single-pipeline asyncio.Lock serializing full `evaluate_observation` method
- [ ] Document locking strategy (choice between single global lock vs. per-peer with explicit ordering)
- [ ] Add 3+ tests covering concurrent observation races (same peer, different epochs)
- [ ] Verify no deadlock under heavy concurrency (load test)
- [ ] Benchmark latency impact (lock contention on high-peer-count deployments)

**Suggested Implementation:**
```python
# Option 1: Single global lock (simplest, most contention)
self._pipeline_lock: asyncio.Lock = asyncio.Lock()

async def evaluate_observation(self, obs, old_status):
    async with self._pipeline_lock:
        return self._evaluate_locked(obs, old_status)

# Option 2: Per-peer lock with explicit ordering (more parallelism)
# Current code already has per-peer locks at line 267
# Verify ordering and serialization across all 5 steps
```

**Related Reading:**
- `2026-07-11-PHASE-2-BLOCKERS.md` § TODO #2
- `2026-07-11-state-transition-manager-integration-plan.md` § Execution Flow (steps [1]–[5])
- Python asyncio docs: `asyncio.Lock` vs. threading.Lock

**Why Non-Blocking:**
- No concurrent caller path exists yet in the orchestrator
- Future phases will add concurrent peer evaluation
- Needed for production robustness, not Phase 1 merge

---

## Timeline

**Phase 2a:** G2/G3/G7 gate integration (1 week)  
**Phase 2b:** STM dedup + concurrency (3–5 hours total, both tasks)  
**Phase 2c:** Full integration tests (2–3 days)

---

## Handoff Notes

1. Both TODOs are **non-blocking for PR #203 merge** but **required for production deployment**
2. Neither has a concurrent caller yet (makes them non-blocking now, urgent later)
3. Dead scaffolding (dedup cache) was discovered via code inspection, not runtime failure
4. Sonnet's threading.RLock was rejected after Codex verified it doesn't serialize async

---

## References

- PR #203: https://github.com/diazMelgarejo/Perpetua-Tools/pull/203
- Blend verdict: `docs/phase-0-specifications/2026-07-11-PR203-BLEND-VERDICT.md`
- Phase 2 blockers: `docs/phase-0-specifications/2026-07-11-PHASE-2-BLOCKERS.md`
- Agent navigator: `docs/phase-0-specifications/README-PR203-BLEND.md`

---

**Last Updated:** 2026-07-11  
**Status:** Ready for Phase 2 agent assignment
