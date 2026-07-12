# Eng Review — Codex GPT-5.5, run 1 of 2

**Note:** this run initially appeared stalled (33 min elapsed, near-zero CPU) and was force-killed — but it had already finished writing this output moments before the kill signal landed. Recovered intact, not a partial/truncated capture (has a full Verdict section). A second run (`02-codex-run2.md`) was launched afterward with stdin explicitly closed (`< /dev/null`) to rule out a stdin-inheritance block as the cause of the apparent stall.

---

**1. Architecture & Design Correctness**

- **High confidence:** Dedup correctness is fragile because `StateTransitionManager` uses `obs.to_json()` as the dedup key before monotonic checks, but `PeerObservation._to_dict()` omits `sequence` and `observer_provenance`. Evidence: `orchestrator/state_transition_manager.py:294-296`, `orchestrator/membership.py:151`, `orchestrator/membership.py:404-434`. Two distinct observations with same serialized fields but different sequence can be rejected as `DUPLICATE` before the monotonic gate sees them.

- **High confidence:** The reorder buffer is capped per peer, but the outer `peer_id -> buffer` map is unbounded. Evidence: `orchestrator/state_transition_manager.py:238-240`, `orchestrator/state_transition_manager.py:330-347`. An attacker can avoid the per-peer cap by sending one buffered gap per many peer IDs.

- **Medium confidence:** The per-peer lock/ref-count model is correct only for a single asyncio event loop; the code’s safety comment explicitly depends on single-threaded asyncio semantics, but the manager is stored on FastAPI app state and has no guard against cross-thread/cross-loop use. Evidence: `orchestrator/state_transition_manager.py:142-146`, `orchestrator/state_transition_manager.py:267-279`, `src/perpetua_tools/orchestrator.py:123-129`.

- **High confidence:** `_touch_cache()` implements ordinary LRU eviction correctly for insert/update: assign, `move_to_end`, then `popitem(last=False)` when over size. Evidence: `orchestrator/state_transition_manager.py:242-248`. I do not see a local LRU implementation defect.

**2. Code Quality & Maintainability**

- **Medium confidence:** The module-level production posture is misleading: it documents caller behavior and “existing caller” compatibility, while the referenced docs record zero production callers. Evidence: `orchestrator/state_transition_manager.py:14-16`, `orchestrator/state_transition_manager.py:116-117`, `docs/phase-0-specifications/PATTERN-SYNTHESIS.md:287-292`, `docs/phase-0-specifications/2026-07-11-state-transition-manager-integration-plan.md:641`.

- **Low confidence:** The `else` branch assigning `new_status = decision_type.value` is unreachable in `_apply_observation()` because all rejecting gates return earlier and the local decision type is only `APPROVED` or `SYBIL_FLAGGED`. Evidence: `orchestrator/state_transition_manager.py:415-440`, `orchestrator/state_transition_manager.py:449-464`.

- **Medium confidence:** Error handling is entirely result-code based; dependency failures from audit, reputation, k-bucket, or equivocation are not caught or wrapped. Evidence: direct calls at `orchestrator/state_transition_manager.py:394`, `orchestrator/state_transition_manager.py:403`, `orchestrator/state_transition_manager.py:465-471`, `orchestrator/state_transition_manager.py:484`.

**3. Test Coverage & Correctness**

- **High confidence:** The concurrency tests do not actually prove lock contention. `evaluate_observation()` awaits only at `async with entry.lock`, then runs a synchronous core, so `asyncio.gather()` can complete one call before the other meaningfully contends; the tests only assert final outcomes. Evidence: `orchestrator/state_transition_manager.py:270-271`, `orchestrator/state_transition_manager.py:286-290`, `tests/test_state_transition_manager.py:533-541`, `tests/test_state_transition_manager.py:723-730`.

- **High confidence:** The tests knowingly work around the dedup-key omission instead of catching it. Comments say `to_json()` does not include sequence and vary timestamp so tests reach stale/weighted paths. Evidence: `tests/test_state_transition_manager.py:310-319`, `tests/test_state_transition_manager.py:386-396`, plus serialization omission at `orchestrator/membership.py:404-434`.

- **Medium confidence:** The reorder-buffer max-size test verifies only a single peer’s cap, not the outer-dict DoS case. Evidence: `tests/test_state_transition_manager.py:608-632`, implementation outer map at `orchestrator/state_transition_manager.py:238-240`.

- **Medium confidence:** The LRU test verifies insertion-order eviction for `_last_applied_key`, but not refresh semantics for an existing key and not the identity of `_seen_observations` evictions. Evidence: `tests/test_state_transition_manager.py:637-657`, `_touch_cache()` refresh behavior at `orchestrator/state_transition_manager.py:242-248`.

**4. Production Readiness / Operational Risk**

- **High confidence:** If wired tomorrow, valid higher-sequence observations can be false-duplicate rejected when only sequence changes, because sequence is absent from serialization and dedup runs first. Evidence: `orchestrator/state_transition_manager.py:294-296`, `orchestrator/membership.py:151`, `orchestrator/membership.py:404-434`.

- **High confidence:** Buffered observations are intentionally unaudited and have no log/metric path in this module, so persistent sequence gaps could be operationally invisible unless every caller inspects returned `BUFFERED` results. Evidence: `orchestrator/state_transition_manager.py:325-357`, imports with no logging/metrics at `orchestrator/state_transition_manager.py:24-29`.

- **Medium confidence:** Terminal decisions are auditable, but operational observability is limited to the in-memory audit object; there are no counters for duplicate/stale/buffered/equivocation/quorum outcomes. Evidence: audit appends at `orchestrator/state_transition_manager.py:465-476` and `orchestrator/state_transition_manager.py:590-596`, no logging/metrics imports at `orchestrator/state_transition_manager.py:24-29`.

**Verdict: BLOCK**

The implementation is close structurally, but I would not approve this as engineering-ready until the dedup key includes sequence-relevant identity and the reorder buffer has an outer/global bound or eviction policy. Those are correctness and DoS issues in the exact code path under review. The test suite is broad, but it currently works around the dedup bug and does not prove the claimed concurrency or cross-peer buffer bounds.
