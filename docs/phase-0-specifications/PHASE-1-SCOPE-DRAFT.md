# Phase 1 Scope — Draft Implementation Plan

**Date:** 2026-07-10  
**Status:** DRAFT — awaiting Fix #3 completion + M4 checkpoint gate decisions  
**Purpose:** Map Phase 0 deliverables (D1, D2, D4) → Phase 1 implementation tasks (TDD-first, parallel execution)

---

## Phase 0 → Phase 1 Handoff Model

```
Phase 0 (DONE):
  D1 (PeerObservation spec) → Phase 1.0 tasks (schema landing)
  D2 (Heartbeat spec) → Phase 1.1–1.3 tasks (STM integration)
  D4 (Threat model) → Phase 1.0–1.3 verification gates

Phase 1 (PLANNED):
  1.0: Schema + confidence formula wired (days 1–5)
  1.1: Confidence scoring + TDD Batch 7 (days 5–10)
  1.2: StateTransitionManager + witness quorum (days 10–18)
  1.3: Epoch + T7 monotonic gate (days 18–28)
```

---

## Checkpoint Gate Dependencies (M4-Dependent)

**Checkpoint 1.0 gate criteria:** [USER DECISION NEEDED]
- Soft: Schema compiles + confidence method exists + M1 (ghost-peer) test passes
- Medium: Same, but M1–M3 tests passing
- Firm: All M1–M5 tests passing

**Checkpoint 1.1 gate criteria:** [USER DECISION NEEDED]
- Soft: compute_confidence() wired + test fixtures exist
- Medium: 3/5 TDD tests passing
- Firm: 5/5 TDD tests passing

**Checkpoint 1.2 gate criteria:** [USER DECISION NEEDED]
- Soft: StateTransitionManager class exists + methods defined
- Medium: Promote/demote logic + E1–E5 edge cases pass
- Firm: All E1–E10 edge cases pass

**Checkpoint 1.3 gate criteria:** [USER DECISION NEEDED]
- Soft: T7 monotonic apply guard exists
- Medium: T7 guard + T2 freshness gate pass
- Firm: Full epoch + T7 integration + conflict resolution

---

## Phase 1.0: Schema + Confidence (Days 1–5)

**Checkpoint gate:** 1.0 (user picks: soft/medium/firm)

### Task 1.0.1: PeerObservation Dataclass Implementation

**Spec reference:** D1 § 2 (schema with 20 fields)

**Deliverable:** Python dataclass + validation
```python
@dataclass
class PeerObservation:
    peer_id: str
    epoch: int
    timestamp: float
    proof_score: float  # [0, 1]
    witness_set: List[PeerObservation]  # Recursive; capped at depth 2
    freshness_score: float  # [0, 1]
    observation_type: ObservationType  # REACHABLE | UNREACHABLE
    # ... 14 more fields from D1 § 2
    
    def compute_confidence(self) -> float:
        """Multiplicative gate: proof × freshness × witness."""
        # Implemented in 1.0.2
        pass
```

**Tests (TDD):**
- Immutability: reassign field → error
- Field bounds: proof_score outside [0, 1] → error
- Depth limits: witness_set depth > 2 → error
- Serialization: round-trip JSON → identical

**Estimated time:** 4–6 hours  
**Prerequisites:** None  
**Parallel ready?** Yes

---

### Task 1.0.2: Confidence Formula Implementation

**Spec reference:** D1 § 3 (multiplicative gate)

**Deliverable:** compute_confidence() method
```python
def compute_confidence(self) -> float:
    proof_factor = self.proof_score  # [0, 1]
    freshness_factor = 0.40 + 0.60 * self.freshness_score  # [0.40, 1.00]
    witness_multiplier = self._compute_witness_multiplier()  # [0.50, 1.00]
    
    confidence = proof_factor * freshness_factor * witness_multiplier
    return round(confidence, 2)  # 0.00–1.00
```

**Witness multiplier logic:**
- proof_factor = 0 → confidence = 0 (multiplicative gate: any zero zeros the product)
- witness_multiplier ∈ [0.50, 1.00] based on witness agreement/disagreement

**Tests (TDD Batch 7):**
- M1: Ghost-peer (proof=0) → confidence=0.00 ✅
- M2: High freshness + low proof → confidence depends on proof
- M3: Witnesses disagree → witness_multiplier <1.0 → confidence reduced
- M4: Perfect score (all 1.0) → confidence=1.00
- M5: Edge case (freshness_score=0) → freshness_factor=0.40 → confidence >0 if proof >0

**Estimated time:** 3–4 hours  
**Prerequisites:** Task 1.0.1  
**Parallel ready?** After 1.0.1 done

---

### Task 1.0.3: Integration with PeerRecord Display State

**Spec reference:** D1 § 2.3 (display state derivation)

**Deliverable:** Compute display_state from PeerObservation.confidence
```python
def compute_display_state(peer: PeerRecord, confidence: float) -> PeerDisplayState:
    """Derive UI/user-visible state from confidence."""
    if confidence == 0.0:
        return UNKNOWN  # Ghost peer or recent failure
    elif confidence < 0.30:
        return SUSPECT
    elif confidence < 0.70:
        return DEGRADED
    else:
        return HEALTHY
```

**Tests:**
- Boundary transitions (0→UNKNOWN, 0.3→SUSPECT, 0.7→DEGRADED, 1→HEALTHY)
- Hysteresis (consecutive calls same confidence → same state)

**Estimated time:** 2–3 hours  
**Prerequisites:** Task 1.0.2  
**Parallel ready?** After 1.0.2 done

---

### Checkpoint 1.0 Re-Review (Day 5)

**Gate:** PeerObservation dataclass + confidence formula + display state working end-to-end.

**Cline re-review focus:** Schema soundness, confidence formula correctness, no floating-point surprises.

**Decision:** Proceed to Phase 1.1? 
- If soft gate (method exists): YES, start 1.1 in parallel
- If medium gate (3/5 tests): YES if M1–M3 pass
- If firm gate (5/5 tests): YES only if M1–M5 all pass

---

## Phase 1.1: Confidence Wired + TDD Regression (Days 5–10)

**Checkpoint gate:** 1.1 (user picks: soft/medium/firm)

### Task 1.1.1: Wire Confidence Into PeerRecord Update Loop

**Spec reference:** D1 § 6 (Integration Checkpoints)

**Deliverable:** PeerRecord computes & caches confidence on every update
```python
class PeerRecord:
    def update_from_observation(self, obs: PeerObservation):
        # Validate obs (T2, T3, T7 gates)
        # Increment witness counters (for 1.2 hysteresis)
        # Compute confidence
        self.last_confidence = obs.compute_confidence()
        self.last_confidence_timestamp = now()
        # Update display_state
        self.display_state = compute_display_state(self, self.last_confidence)
```

**Tests:**
- Multiple updates → confidence changes
- Stale observations (T2 gate) → confidence not updated
- Duplicate observations (T3 gate) → confidence stable

**Estimated time:** 3–5 hours  
**Prerequisites:** Task 1.0.3  
**Parallel ready?** Day 5+

---

### Task 1.1.2: Batch 7 Regression Tests (M1–M5)

**Spec reference:** D1 § 4 (TDD Batch 7)

**Deliverable:** pytest fixtures + 5 regression tests
```python
@pytest.mark.parametrize("scenario", [
    pytest.param(M1, id="ghost_peer_proof_zero"),
    pytest.param(M2, id="high_freshness_low_proof"),
    pytest.param(M3, id="witness_disagreement"),
    pytest.param(M4, id="perfect_score"),
    pytest.param(M5, id="zero_freshness_nonzero_proof"),
])
def test_confidence_regression(scenario):
    obs = scenario.make_observation()
    assert obs.compute_confidence() == scenario.expected
```

**Edge case handling:**
- Floating-point precision (round to 2 decimals)
- Division by zero (witness_set empty)
- Recursion depth (witness_set depth > 2)

**Estimated time:** 4–6 hours  
**Prerequisites:** Task 1.0.2  
**Parallel ready?** Yes (independent of 1.1.1)

---

### Checkpoint 1.1 Re-Review (Day 10)

**Gate:** All TDD Batch 7 regression tests passing.

**Cline re-review focus:** Test comprehensiveness, edge case coverage, floating-point correctness.

**Decision:** Proceed to Phase 1.2?
- If soft gate: YES, start 1.2
- If medium gate (3/5 pass): YES if M1–M3 pass
- If firm gate (5/5 pass): YES only if all pass

---

## Phase 1.2: StateTransitionManager + Witness Quorum (Days 10–18)

**Checkpoint gate:** 1.2 (user picks: soft/medium/firm)

### Task 1.2.1: StateTransitionManager Class + State Machine

**Spec reference:** D2 § 5.3 (STM Integration) + Fix #3 Tasks 3.2 pseudocode

**Deliverable:** Python state machine (ACTIVE, SUSPECT, INACTIVE states)
```python
class StateTransitionManager:
    def __init__(self):
        self.state = ACTIVE
        self.pending_count_promote = 0
        self.pending_count_demote = 0
        self.confirm_dead_timestamp = None
    
    def apply_observation(self, obs: PeerObservation) -> StateChange | None:
        """
        Returns StateChange if threshold crossed, else None.
        Implements asymmetric hysteresis (PROMOTE=2, DEMOTE=3).
        """
        # Validation gates (T2, T3, T7)
        # Counter logic (pseudocode from Fix #3 Task 3.2)
        # State transitions
        # Recovery logic (CONFIRM_DEAD_HOLD window)
        pass
```

**Tests (edge cases E1–E5):**
- E1: Empty observation batch → no state change
- E2: Out-of-order observations (newer then older) → older ignored (T7)
- E3: Multiple observations in batch → threshold checks run per-observation
- E4: Threshold hit mid-batch → state changes, 3rd obs applied to new state
- E5: Flapping (fast alternation) → counters reset, no change if thresholds not hit

**Estimated time:** 8–10 hours  
**Prerequisites:** Fix #3 Task 3.2 complete  
**Parallel ready?** No (depends on Fix #3)

---

### Task 1.2.2: Witness Quorum Gate (T4 Sybil Defense)

**Spec reference:** D4 § T4 (Sybil Witnesses) + D1 § 3 (witness_multiplier)

**Deliverable:** Witness independence scoring
```python
def validate_witness_quorum(observation: PeerObservation) -> bool:
    """
    Quorum gate: ≥2 independent witnesses required for observation to count.
    Independence = distinct observer_id AND distinct network provenance.
    """
    if len(observation.witness_set) < 2:
        return False
    
    # Dedup by observer_id
    unique_observers = set(w.observer_id for w in observation.witness_set)
    if len(unique_observers) < 2:
        return False
    
    # Dedup by provenance (ASN, subnet, origin IP)
    unique_provenances = set(w.observer_provenance for w in observation.witness_set)
    if len(unique_provenances) < 2:
        return False
    
    return True
```

**Tests:**
- Threshold met (2 distinct observers) → quorum passes
- Threshold not met (1 observer repeated) → quorum fails
- Provenance dedup (same ASN) → counted as one provenance

**Estimated time:** 3–4 hours  
**Prerequisites:** Task 1.0.1 (witness_set field)  
**Parallel ready?** Yes

---

### Task 1.2.3: Edge Cases E6–E10 (if firm gate chosen)

**Spec reference:** D2 § 5.3 (edge cases from Fix #3 Task 3.2)

**Deliverable:** Test cases + implementation refinements
- E6: Clock skew (future timestamp) → T2 gate rejects
- E7: Conflict (same epoch, seq, different nonce) → deterministic winner
- E8: Sybils (5 observers) → quorum gate enforced
- E9: Recovery after CONFIRM_DEAD_HOLD expiry → transition to ACTIVE
- E10: Bootstrap (peer first appearance) → start at ACTIVE, demote counter=1

**Estimated time:** 6–8 hours (if included)  
**Prerequisites:** Task 1.2.1  
**Parallel ready?** No

---

### Checkpoint 1.2 Re-Review (Day 18)

**Gate:** StateTransitionManager passing E1–E5 (or E1–E10 if firm gate).

**Cline re-review focus:** State machine correctness, race conditions, recovery logic.

---

## Phase 1.3: Epoch + T7 Monotonic Gate (Days 18–28)

**Checkpoint gate:** 1.3 (user picks: soft/medium/firm)

### Task 1.3.1: Monotonic Apply Gate (T7)

**Spec reference:** D4 § T7 (Out-of-Order Observations) + D2 § 5.3 (pseudocode)

**Deliverable:** Observation ordering enforcement
```python
def is_observation_newer(current: PeerObservation, new: PeerObservation) -> bool:
    """
    Monotonic ordering key: (epoch, sequence, timestamp).
    Sequence is canonical causality; timestamp advisory (±30s skew tolerance).
    """
    if new.epoch > current.epoch:
        return True
    if new.epoch == current.epoch:
        if new.sequence > current.sequence:
            return True
        if new.sequence == current.sequence:
            # Same epoch, sequence; use timestamp (allow ±30s skew)
            return new.timestamp > current.timestamp + 30  # seconds
    return False
```

**Tests:**
- Newer epoch → observation accepted
- Same epoch, higher sequence → observation accepted
- Same epoch, lower sequence → observation rejected (monotonic gate)
- Clock skew (timestamp future by <30s) → sequence wins, observation may be accepted

**Estimated time:** 5–7 hours  
**Prerequisites:** Task 1.0.1 (epoch, sequence fields)  
**Parallel ready?** Yes

---

### Task 1.3.2: Reorder Buffer + Watermark

**Spec reference:** D4 § T7 (Reorder buffer with watermark)

**Deliverable:** Buffering for transient multi-path skew
```python
class ReorderBuffer:
    def __init__(self, window_size_seconds=30):
        self.buffer = {}  # key=(epoch, sequence) → observation
        self.watermark = (epoch=0, sequence=0)
    
    def add_observation(self, obs: PeerObservation) -> List[PeerObservation]:
        """
        Add observation to buffer; release observations that clear watermark.
        Returns list of observations ready to apply (in order).
        """
        # Add to buffer if not stale
        # Check if watermark advances
        # Release ready observations in canonical order
        pass
```

**Tests:**
- Multi-path skew (newer arrives, then older) → buffer holds, releases in order
- Watermark advances → held observations released
- Window expiry → held observations released or dropped

**Estimated time:** 4–6 hours  
**Prerequisites:** Task 1.3.1  
**Parallel ready?** No

---

### Checkpoint 1.3 Re-Review (Day 28)

**Gate:** T7 monotonic gate + reorder buffer passing tests.

**Cline re-review focus:** Order-independence verification, edge cases on clock boundaries.

**Decision:** Phase 1 complete? Ship or defer Phase 1b enhancements?

---

## Phase 1 Task Dependency Graph

```
1.0.1 (PeerObservation dataclass)
  ↓
1.0.2 (Confidence formula)
  ↓
1.0.3 (Display state derivation)
  ↓
[Checkpoint 1.0 Gate] ← user decision on gate criteria
  ↙                  ↘
1.1.1                1.1.2
(Wire confidence)    (Batch 7 tests)
  ↓                    ↓
  ↘                  ↙
[Checkpoint 1.1 Gate]
  ↓
1.2.1 (StateTransitionManager) ← depends on Fix #3
  ↓
1.2.2 (Witness quorum) [parallel-ready]
  ↓
1.2.3 (E6–E10 edge cases) [optional]
  ↓
[Checkpoint 1.2 Gate]
  ↓
1.3.1 (T7 monotonic gate) [parallel-ready]
  ↓
1.3.2 (Reorder buffer)
  ↓
[Checkpoint 1.3 Gate]
  ↓
Phase 1 COMPLETE
```

---

## Timeline Summary

| Phase | Tasks | Days | Parallel Slots | Dependencies |
|-------|-------|------|---|---|
| **1.0** | 1.0.1, 1.0.2, 1.0.3 | 1–5 | 1 (sequential) | None |
| **1.1** | 1.1.1, 1.1.2 | 5–10 | 2 (parallel after 1.0.2) | Fix #3 (optional) |
| **1.2** | 1.2.1, 1.2.2, 1.2.3 | 10–18 | 2 (1.2.1 serial; 1.2.2 parallel) | Fix #3 REQUIRED |
| **1.3** | 1.3.1, 1.3.2 | 18–28 | 1 (sequential) | None |

**Estimated Phase 1 duration:** 28 days (with gate criteria soft/medium) or 35–40 days (firm gates with all edge cases)

---

## Blockers & Risks

| Risk | Impact | Mitigation | Owner |
|---|---|---|---|
| Fix #3 delayed | 1.2.1 blocked | Cline executing now | Agent adb14943312a788de |
| M4 gate decisions missing | Scope ambiguous | User decision on checkpoints (30 min) | User |
| Witness quorum spec unclear (M2) | 1.2.2 implementation uncertain | User pick Option A/B for M2 | User |
| Epoch overflow (M1) | 1.3.1 correctness risk | User pick Option A for M1 (uint32 safe) | User |
| Discovery not implemented | Integration SLA at risk | M5 decision defers to 1b; Phase 1 assumes discovery works | Planning |

---

## Next Steps

1. **User decisions needed (30 min):**
   - M4: Checkpoint gate criteria (soft/medium/firm per checkpoint)
   - M1, M2, M5: Key decisions affecting 1.3.1, 1.2.2 scope
   
2. **Fix #3 completion (Cline, ~2–3h):**
   - Unblocks 1.2.1 task sizing
   
3. **Phase 1 task assignment (after decisions):**
   - 1.0.1–1.3.2 ready for developer handoff
   - Task breakdown cards can be filed in backlog with exact requirements

