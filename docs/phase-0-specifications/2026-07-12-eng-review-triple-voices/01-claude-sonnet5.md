> **Note (added post-hoc):** a separate, more complete Eng-review record — 5 voices (Codex ×2, Kimi, Claude Sonnet, Antigravity), including a caught-and-corrected stale Antigravity pass — was produced concurrently on this same branch and is now the canonical record: [`../2026-07-12-eng-review-voices/00-README.md`](../2026-07-12-eng-review-voices/00-README.md), aggregated into [`../2026-07-12-autoplan-final-approval-gate.md`](../2026-07-12-autoplan-final-approval-gate.md). This file is kept as a supplementary, independently-run pass — its findings directly informed the code fixes committed in `fix(stm): close remaining Eng-review findings from triple-voice review`, cross-verified against current source rather than superseded silently.

# Voice 1 of 3 — Claude Sonnet 5 (medium depth), agentId a0d54e6a35d5d5ae0

**Grounded at:** commit `60636ad5` (before the two mid-flight fix commits below landed).
**Status note (added post-hoc by orchestrating session, 2026-07-12):** this review's finding 1.1 (`_reorder_buffer` outer dict unbounded) was RESOLVED by commit `62b66119` after this review ran. See `00-README.md` for the full resolved/open cross-check against current HEAD (`4f3fb463`).

---

# Engineering Review — PR #205 `phase-2-stm-concurrency-dedup`
### `orchestrator/state_transition_manager.py` + `tests/test_state_transition_manager.py`

Scope: independent engineering-level read of the actual implementation and test suite. No reliance on the prior CEO/Strategist quad-review summary except where explicitly noted as corroboration I re-derived myself from source.

---

## 1. Architecture & Design Correctness

**1.1 — The outer `_reorder_buffer` dict is unbounded across distinct peer_ids (High confidence).** [RESOLVED by commit 62b66119 — see 00-README.md]
`orchestrator/state_transition_manager.py:240` declares `self._reorder_buffer: Dict[str, "OrderedDict[...]"] = {}` — a plain dict, with no LRU wrapper and no `_touch_cache()` call anywhere in `_buffer_observation()` (`state_transition_manager.py:325-357`) or `_flush_reorder_buffer()` (`state_transition_manager.py:359-380`). The *inner* OrderedDict is capped per peer at `reorder_buffer_max` (`state_transition_manager.py:330-345`), and this cap is well tested (`test_reorder_buffer_respects_max_size`, `tests/test_state_transition_manager.py:609-632`). But the *outer* dict entry for a given `peer_id` is only ever removed in one place — `del self._reorder_buffer[peer_id]` at `state_transition_manager.py:379`, which fires only when that peer's buffer fully drains via a successful flush. If an attacker (or just a flaky peer) seeds `_last_applied_key` with one accepted observation per distinct `peer_id`, then sends a single gap-ahead observation for each and never supplies the missing sequence, `_reorder_buffer` grows by one `OrderedDict` key per distinct `peer_id` forever, with no eviction path. This is the same class of unbounded-memory DoS vector that `_peer_locks` (ref-counted eviction, `state_transition_manager.py:135-153`) and `_seen_observations`/`_last_applied_key` (LRU via `_touch_cache`, `state_transition_manager.py:242-248`) were explicitly hardened against — P18's bounded-cache treatment was applied to two of the three growing structures but not to `_reorder_buffer`'s outer dict.

**1.2 — `_last_applied_key` LRU eviction can orphan a `_reorder_buffer` entry (Medium confidence).**
Because `_last_applied_key` is LRU-bounded (`state_transition_manager.py:233`, `247-248`) but `_reorder_buffer` is not, a peer whose `_last_applied_key` entry gets evicted while it still has a buffered gap entry becomes a case the code doesn't reason about together. `_evaluate_locked()` treats a peer absent from `_last_applied_key` as "fresh" (`last is None` branch, `state_transition_manager.py:298-314`), bypassing the buffer-gap check entirely and routing straight to `_apply_observation`. The subsequent `_flush_reorder_buffer` call (`state_transition_manager.py:320`) can then pop a stale buffered entry keyed by coincidence of `(epoch, sequence)` matching the newly-applied key — functionally survivable in the cases I traced, but it is unexercised by any test and the interaction between the two caches' independent eviction policies is not documented or asserted anywhere.

**1.3 — The per-peer `asyncio.Lock` is not currently load-bearing (High confidence, empirically verified).**
The class docstring (`state_transition_manager.py:183-192`) and the "Synchronous core" comment (`state_transition_manager.py:281-284`) both note that `_evaluate_locked()` and everything it calls (`equivocation_log`, `k_bucket`, `audit_log`, `reputation`) are fully synchronous — there is **no `await` anywhere inside the critical section**. CPython's `asyncio.Lock.acquire()` fast path (uncontended case) does not suspend to the event loop; combined with a zero-`await` critical section, this means two `evaluate_observation()` calls for the same `peer_id` cannot interleave with or without the lock, because asyncio only switches tasks at genuine suspension points and none exist here. I verified this empirically: replacing `entry.lock` with a true no-op async context manager and re-running the exact scenario from `test_concurrent_calls_same_peer_serialize_correctly` (`tests/test_state_transition_manager.py:524-541`) still produces `accepted=1, duplicate=1` — identical to the real-lock result. The `_RefCountedLock` machinery is therefore defensive/future-proofing for a scenario (an async dependency call inside the pipeline) that does not exist in this PR, not a currently-necessary correctness mechanism. This isn't a bug, but it means the concurrency-safety claim in the docstring is untested by anything that could actually fail if the lock were removed today.

**1.4 — `_touch_cache()` LRU logic is correct (High confidence).** `state_transition_manager.py:242-248`: assignment + `move_to_end` + conditional `popitem(last=False)` correctly implements LRU-bounded insert/refresh/evict, and is verified by `test_seen_observations_and_last_applied_key_are_lru_bounded` (`tests/test_state_transition_manager.py:637-657`), which asserts eviction targets the least-recently-used entry specifically, not just cache size. No issue found here.

**1.5 — No deadlock risk identified (Medium confidence).** Only one lock is ever held at a time, per-peer, non-reentrant, released deterministically via `async with`; no nested lock acquisition or cross-peer lock ordering exists in the code. Given finding 1.3, this is somewhat moot today, but the design itself (single per-peer lock, no lock-ordering dependency) would not deadlock even once real awaits are introduced.

---

## 2. Code Quality & Maintainability

**2.1 — Dead branch in `_apply_observation` (High confidence).** `state_transition_manager.py:461-464`:
```python
if decision_type in (DecisionType.APPROVED, DecisionType.SYBIL_FLAGGED):
    new_status = obs.observation_type.value
else:
    new_status = decision_type.value
```
The comment immediately above (`state_transition_manager.py:454-460`) states outright: "the only two reachable here, since every rejecting gate above already returned." `decision_type` is initialized to `APPROVED` at `state_transition_manager.py:449` and only ever reassigned to `SYBIL_FLAGGED` at `state_transition_manager.py:451`; every other `DecisionType` value causes an early `return` before this point. The `else` branch is therefore unreachable dead code. Low severity, but worth a comment-only cleanup since it currently implies a code path that cannot occur.

**2.2 — Naming and structure are otherwise clean (Medium confidence).** Method decomposition is cohesive, each function has a single responsibility, and all public dataclasses are frozen — consistent with immutability conventions. File is 609 lines, within the common 800-line ceiling but past the 400-line "typical" guideline; the pipeline-step helpers are extractable into a separate module if this file grows further, but not urgent at current size.

**2.3 — Module docstring implies production readiness the code doesn't back up (High confidence, independently re-derived).** `state_transition_manager.py:1-19` describes the module as "the *security decision* layer" that "callers decide how to apply" — worded as an actively-consumed component. I independently confirmed via `grep -rn "evaluate_observation"` across the repo (excluding tests and worktree copies) that the only calls to `evaluate_observation()` exist in `tests/test_state_transition_manager.py`. `src/perpetua_tools/orchestrator.py:123-129` constructs a `StateTransitionManager` and assigns it to `app.state.state_transition_manager`, but nothing in that file (or anywhere else searched) ever calls `.evaluate_observation()` on it — the wiring stops at construction. This matches finding (1) from the referenced prior review but I reached it independently from the grep evidence above, not by trusting the earlier summary.

**2.4 — Error handling is adequate for what's here, but narrow (Medium confidence).** `InvalidObservationError` (`state_transition_manager.py:40-41`) is declared but never raised anywhere in this file. No `try`/`except` exists anywhere in `state_transition_manager.py`; every dependency call is trusted to never raise. Given `_apply_observation` mutates `_seen_observations`/`_last_applied_key` *before* calling `self._k_bucket.update()`, an exception from `k_bucket.update()` would leave the dedup/monotonic state committed but the k-bucket routing table not updated for that observation — a partial-write inconsistency with no rollback. No test exercises a dependency-raises-mid-pipeline scenario.

---

## 3. Test Coverage & Correctness

**3.1 — 767-line test file is broad and well-organized** (per-gate unit tests, integration tests, property-based tests via `hypothesis`, and a dedicated Phase-2 section for reorder buffer/bounded caches/lock cleanup/audit naming). Fixtures use real dependency instances rather than mocks, which is the right call for this kind of pipeline-integrity code.

**3.2 — The same-peer concurrency test does not prove what it claims (High confidence — see finding 1.3).** `test_concurrent_calls_same_peer_serialize_correctly` (`tests/test_state_transition_manager.py:524-541`) is the only test exercising the per-peer lock under real contention, and I empirically demonstrated it passes identically with the lock's serialization behavior removed entirely (see 1.3). This is a test that would still pass if the underlying locking logic were subtly wrong as long as the pipeline stayed synchronous — it is testing asyncio's scheduling guarantees, not the lock's own correctness.

**3.3 — Reorder-buffer outer-dict growth is untested (High confidence — gap corresponding to finding 1.1).** [RESOLVED — see `test_reorder_buffer_outer_peer_map_is_lru_bounded` added by commit `62b66119`, per 00-README.md] `TestReorderBuffer` (`tests/test_state_transition_manager.py:552-632`) covers: gap buffered not rejected, flush on gap fill, multi-buffer flush ordering, and per-peer buffer max. No test constructs multiple distinct `peer_id`s with abandoned (never-filled) gaps and asserts a bound — or absence of a bound — on `len(manager._reorder_buffer)`.

**3.4 — LRU-eviction/reorder-buffer interaction (finding 1.2) is untested.** No test combines `max_cache_size` eviction with an in-flight `_reorder_buffer` entry for the evicted peer.

**3.5 — Property-based test is appropriately shaped.** `test_audit_invariant_one_entry_per_call` (`tests/test_state_transition_manager.py:456-477`) uses `hypothesis` over 1-20 calls with distinct peer_ids, asserting exactly one audit entry per call — a real invariant test that would catch a broken audit-on-every-terminal-decision guarantee. Good use of property-based testing here, not just example-based.

**3.6 — `test_audit_appended_for_acceptance` has a vacuous fallback assertion (Low confidence, minor).** `tests/test_state_transition_manager.py:294`: `assert result.audit_hash if hasattr(result, "audit_hash") else result.audit_entry.hash` — since `StateTransitionResult` has no `audit_hash` field, this always evaluates the `else` branch, and any truthy hash string satisfies it. Harmless but leftover defensive code that doesn't test anything the `hasattr` branch was presumably meant to guard.

---

## 4. Production Readiness / Operational Risk

**4.1 — Zero logging in the module (High confidence).** `grep -n "^import logging\|logging\.\|logger\." orchestrator/state_transition_manager.py` returns nothing. Every terminal decision — including security-relevant rejections (EQUIVOCATION, INSUFFICIENT_QUORUM, SYBIL_FLAGGED) — is only recorded into the in-memory `AuditLog` and returned to the caller. If this pipeline were wired into a real caller tomorrow, an operator watching application logs would see nothing when a peer is flagged for equivocation or Sybil correlation.

**4.2 — `AuditLog` is in-memory only, no persistence (High confidence).** `orchestrator/audit_log.py:114-115`: `self._entries: list[AuditEntry] = []` — a plain Python list, never written to disk, DB, or any external sink. Combined with 4.1, the entire G8 "forensics" audit trail evaporates on process restart.

**4.3 — No metrics/observability hooks (High confidence).** No counter for decision-type distribution, no timing/latency instrumentation, and no gauge for `_peer_locks`/`_reorder_buffer`/`_seen_observations` sizes. An operator would have no signal that the reorder-buffer DoS vector (1.1) was in progress until memory pressure became visible at the process level.

**4.4 — Concrete failure mode if wired in tomorrow.** [Partially mitigated by 62b66119, see 00-README.md] Given 1.1 + 4.1 + 4.3 together: a caller feeding real observations through `evaluate_observation()` has (a) no lock-safety issue in practice per 1.3, (b) a genuine unbounded-memory growth path via abandoned reorder-buffer gaps per 1.1, and (c) no logging or metrics that would surface (b) before it manifests as OOM.

**4.5 — `InvalidObservationError` is unused (Low confidence, minor).** Declared but never raised.

---

## Verdict: **APPROVE WITH CHANGES**

The implementation is careful, well-commented, and the two bounded-cache mechanisms it does apply are correctly implemented and well tested. However, two concrete issues should be addressed before or shortly after this lands into a real caller: (1) the outer `_reorder_buffer` dict has no bound across distinct `peer_id`s [since resolved]; and (2) the module has zero logging and zero durable audit persistence. Neither is a correctness blocker in the module's current unwired state, but both should be fixed — or explicitly tracked as follow-up tickets — before this pipeline is connected to a live caller. The per-peer lock's current lack of load-bearing effect (finding 1.3) is not something that needs fixing now, but the test suite should either add a genuinely interleaving scenario or the docstring should note the concurrency-safety claim is currently unfalsified by any test that would fail without it.
