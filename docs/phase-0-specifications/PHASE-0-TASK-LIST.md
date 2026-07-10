# Phase 0 Task List (TDD-First)

**Duration:** 17.5 hours over 2–3 weeks
**Approach:** TDD (test specs → design → consensus)
**Checkpoints:** Every 2 days (async design review)
**Total effort:** 17.5 hours across Task Groups A–C, matching the detailed task estimates below.

---

## Task Group A: Deliverable 1 (Peer Observation Model)

### Task A1: Finalize PeerObservation Schema (2h)

**Spec Test:** `test_peer_observation_schema_complete`

```python
from dataclasses import FrozenInstanceError
import pytest

def test_peer_observation_schema_complete():
    """
    GIVEN: PeerObservation dataclass
    WHEN: Instantiate with all required + optional fields
    THEN: Frozen=True (immutable), all fields present, no errors
    """
    # See DELIVERABLE-1-PEER-OBSERVATION-MODEL-EXPANDED.md § 2.2
    # Create 10 example observations (fixtures):
    # 1. Fresh direct connection (confidence 1.00)
    # 2. Stale passive entry (confidence 0.00)
    # 3. Relay claim with partial proof (confidence ~0.209)
    # 4. Timeout (confidence 0.1)
    # 5. Degraded (confidence 0.6)
    # 6. IP migrated (epoch mismatch)
    # 7. Witnessed agreement (witness=2)
    # 8. Witnessed disagreement (witness_disagreement=1)
    # 9. Static seed (route="static_seed")
    # 10. Malicious relay attempt (proof_score=0.0, confidence penalized)

    for fixture in FIXTURES:
        assert fixture.__dataclass_params__.frozen is True
        with pytest.raises(FrozenInstanceError):
            fixture.confidence = 0.0
        assert all(hasattr(fixture, field) for field in REQUIRED_FIELDS)
        assert fixture.confidence <= 1.0 and fixture.confidence >= 0.0
```

**Deliverable:**
- `orchestrator/models/peer_observation.py` with PeerObservation dataclass
- `tests/test_peer_observation_schema.py` with 10 fixtures
- `docs/peer-observation-schema.md` with field explanations + RFC references

**Checklist:**
- [ ] Schema matches § 2.2 of Deliverable 1 (all fields present)
- [ ] Frozen=True enforced (immutable)
- [ ] All 10 fixtures created + validate successfully
- [ ] Docstrings explain RFC semantics (HyParView, endpoint_epoch, witness agreement)
- [ ] Team review: comment on field naming + RFC alignment

---

### Task A2: Confidence Scoring Function (1.5h)

**Spec Test:** `test_confidence_scoring_formula`

```python
def test_confidence_scoring_formula():
    """
    GIVEN: proof_score, freshness_score, witness_agreement
    WHEN: compute_confidence(proof, fresh, witness)
    THEN: confidence = proof × freshness_factor × witness_multiplier
          freshness_factor = 0.40 + 0.60 × freshness_score
          witness_multiplier ∈ [0.50, 1.00] based on agreement/disagreement ratio
    """
    # Test cases from § 3.2 (Deliverable 1):
    # 1. Fresh direct (1.0, 1.0, 2 witnesses) → 1.00
    # 2. Stale unverified (0.0, 0.0, 0 witnesses) → 0.00
    # 3. Partial relay (0.3, 0.7, 0 witnesses) → 0.209
    # 4. Disagreement penalty (1.0, 1.0 but witness_disagree=2) → 0.50

    test_cases = [
        ((1.0, 1.0, 2, 0), 1.00),  # Fresh direct + witnessed
        ((0.0, 0.0, 0, 0), 0.0),   # Stale unverified
        ((0.3, 0.7, 0, 0), 0.209), # Partial proof: 0.3 * 0.82 * 0.85
        ((1.0, 1.0, 0, 2), 0.5),   # Proof high but disagreement penalty
    ]

    for (proof, fresh, agree, disagree), expected in test_cases:
        result = compute_confidence(proof, fresh, agree, disagree)
        assert abs(result - expected) < 0.05  # Within 5%
```

**Deliverable:**
- `orchestrator/confidence.py` with `compute_confidence()` function
- `tests/test_confidence_scoring.py` with 10+ test cases
- `docs/confidence-scoring-spec.md` with formula explanation + decision thresholds

**Checklist:**
- [ ] Formula matches § 3.1 (proof-gated multiplicative confidence)
- [ ] Witness multiplier computed from agreement/disagreement ratio
- [ ] Disagreement penalty applied (witness_multiplier = 0.50 if disagree > agree)
- [ ] All test cases pass (10+ cases covering extremes)
- [ ] Team review: scoring formula reasonable? Weights correct?

---

### Task A3: Derive Display States from Observations (1.5h)

**Spec Test:** `test_derive_topology_state_from_observations`

```python
def test_derive_topology_state_from_observations():
    """
    GIVEN: List of PeerObservations (1–N)
    WHEN: derive_topology_state(observations)
    THEN: TopologyState ∈ {SOLO, PAIR, FLEET, RELAY, PARTITIONED, STALE, SUSPECT, OFFLINE, DEGRADED}
          with metadata (peers, confidence, recovery_time_s)
    """
    # Test cases:
    # 1. 2+ direct peers (confidence >= 0.7), cross-reachable → FLEET
    # 2. 2+ direct peers, NOT cross-reachable → PARTITIONED
    # 3. 1 direct peer → PAIR
    # 4. 0 direct, 1+ relay (confidence >= 0.5) → RELAY
    # 5. 0 reachable, 1+ SUSPECT (confidence >= 0.3) → SUSPECT
    # 6. 0 reachable, 1+ STALE → STALE
    # 7. 0 reachable, 0 suspect → SOLO
    # 8. No local backend → OFFLINE

    test_cases = [
        ([direct1, direct2_cross_reachable], TopologyState.FLEET, 0.93),
        ([direct1, direct2_not_cross], TopologyState.PARTITIONED, 0.85),
        ([direct1], TopologyState.PAIR, 0.95),
        ([relay1], TopologyState.RELAY, 0.50),
        ([suspect1, suspect2], TopologyState.SUSPECT, 0.35),
        ([stale1], TopologyState.STALE, 0.1),
    ]

    for obs_list, expected_state, expected_conf in test_cases:
        state, meta = derive_topology_state(obs_list)
        assert state == expected_state
        assert abs(meta["confidence"] - expected_conf) < 0.1
```

**Deliverable:**
- `orchestrator/topology.py` with `derive_topology_state()` function
- `tests/test_derive_topology_state.py` with 10+ test cases
- `docs/topology-derivation-spec.md` with decision tree + examples

**Checklist:**
- [ ] All 9 states reachable (SOLO, PAIR, FLEET, RELAY, PARTITIONED, STALE, SUSPECT, OFFLINE, DEGRADED)
- [ ] Decision tree matches § 4 of PHASE-0-DESIGN-SPECIFICATION.md
- [ ] Hysteresis NOT yet implemented (just derive latest state)
- [ ] All test cases pass
- [ ] Team review: state names correct? Decision logic sound?

---

## Task Group B: Hysteresis + State Transitions

### Task B1: State Transition Manager with Hysteresis (2h)

**Spec Test:** `test_state_transition_hysteresis_prevents_flapping`

```python
def test_state_transition_hysteresis_prevents_flapping():
    """
    GIVEN: State oscillates DIRECT_1 → SUSPECT → DIRECT_1 (jitter)
    WHEN: StateTransitionManager(POLLS_TO_CONFIRM=2, dwell_time_min_s=5)
    THEN: State stays DIRECT_1 until 2 consecutive SUSPECT polls (10s)
    """
    manager = StateTransitionManager(
        POLLS_TO_CONFIRM=2,
        dwell_time_min_s=5,
    )

    # Simulate 10 polls over 100s (10s each)
    states_input = [
        "DIRECT_1",    # Poll 0
        "SUSPECT",     # Poll 1 (jitter)
        "DIRECT_1",    # Poll 2 (jitter clears)
        "DIRECT_1",    # Poll 3
        "SUSPECT",     # Poll 4 (real degradation)
        "SUSPECT",     # Poll 5 (still suspect)
        "SUSPECT",     # Poll 6 (still suspect)
        "DIRECT_1",    # Poll 7 (recovery)
        "DIRECT_1",    # Poll 8
        "DIRECT_1",    # Poll 9
    ]

    outputs = []
    for i, input_state in enumerate(states_input):
        time.sleep(10)  # or mock time
        output_state = manager.update(input_state)
        outputs.append(output_state)

    # Expected: state changes only after 2 stable polls
    # DIRECT_1 (0–2), DIRECT_1 (3–4), SUSPECT after poll 5, DIRECT_1 after poll 8
    assert outputs[0:3] == ["DIRECT_1", "DIRECT_1", "DIRECT_1"]  # Hysteresis suppresses jitter
    assert outputs[4] == "DIRECT_1"  # Still previous; not enough polls yet
    assert outputs[5] == "SUSPECT"  # 2 consecutive SUSPECT polls, transition
    assert outputs[6:8] == ["SUSPECT", "SUSPECT"]  # Wait for 2 DIRECT_1 polls to recover
    assert outputs[8:] == ["DIRECT_1", "DIRECT_1"]
```

**Deliverable:**
- `orchestrator/state_transition.py` with StateTransitionManager class
- `tests/test_state_transition_hysteresis.py` with detailed flapping test
- `docs/hysteresis-spec.md` with timing diagram + examples

**Checklist:**
- [ ] Class constructor: POLLS_TO_CONFIRM, dwell_time_min_s parameters
- [ ] update(state) returns current state, possibly updates on transitions
- [ ] Hysteresis: require N consecutive polls before transition
- [ ] Dwell time: never transition faster than min dwell
- [ ] Test case: jitter suppression works (flapping scenario)
- [ ] Team review: dwell timing reasonable (5s for LAN)?

---

### Task B2: Heartbeat Deadline Strategy + Peer Health State Machine (1h)

**Spec Test:** `test_peer_health_state_machine`

```python
def test_peer_health_state_machine():
    """
    GIVEN: Peer's last_heartbeat_timestamp and an injectable clock/deadline strategy
    WHEN: Update health state with jitter-aware fixed deadlines
    THEN: Transition ACTIVE → SUSPECT → INACTIVE based on time
    """
    HEARTBEAT_INTERVAL = 10
    HEARTBEAT_DEADLINE = 30
    SUSPICION_TIMEOUT = 90

    clock = FakeClock(now)
    deadlines = DeadlineStrategy(
        heartbeat_deadline_s=HEARTBEAT_DEADLINE,
        suspicion_timeout_s=SUSPICION_TIMEOUT,
        jitter_budget_s=2,
    )
    peer = {"node_id": "...", "last_heartbeat": now}

    # At now: ACTIVE
    assert health_state(peer, clock.now(), deadlines) == "ACTIVE"

    # At now + 25s: still ACTIVE (< deadline)
    clock.advance_to(now + 25)
    assert health_state(peer, clock.now(), deadlines) == "ACTIVE"

    # At now + 30s: SUSPECT (deadline reached)
    clock.advance_to(now + 30)
    assert health_state(peer, clock.now(), deadlines) == "SUSPECT"

    # At now + 60s: still SUSPECT (< suspicion timeout)
    clock.advance_to(now + 60)
    assert health_state(peer, clock.now(), deadlines) == "SUSPECT"

    # At now + 90s: INACTIVE (demote from active view)
    clock.advance_to(now + 90)
    assert health_state(peer, clock.now(), deadlines) == "INACTIVE"

    # Deadline math is fixed; send jitter changes heartbeat scheduling, not the deadline window.
    assert deadlines.next_send_interval(base_s=10, jitter_s=2) in range(8, 13)
```

**Deliverable:**
- `orchestrator/failure_detection.py` with `health_state()` function + timeout constants
- `tests/test_health_state_machine.py` with state machine tests
- `docs/failure-detection-spec.md` with timeout hierarchy + rationale

**Checklist:**
- [ ] Constants defined: HEARTBEAT_INTERVAL=10, DEADLINE=30, SUSPICION=90 (seconds)
- [ ] health_state() accepts injectable clock/deadline strategy for deterministic tests
- [ ] Deadline strategy keeps heartbeat send jitter separate from detection deadlines
- [ ] health_state() returns one of ACTIVE, SUSPECT, INACTIVE
- [ ] Transition happens at exact boundaries (not off-by-one)
- [ ] Test covers all 4 state transitions
- [ ] Team review: timeout values reasonable? Should they vary per network?

---

## Task Group C: Discovery + Bootstrap

### Task C1: Discovery Fallback Chain Config + Test (1.5h)

**Spec Test:** `test_discovery_fallback_chain_order`

```python
def test_discovery_fallback_chain_order():
    """
    GIVEN: All discovery methods available (seeds, mDNS, TCP scan)
    WHEN: Discover peers (static seeds first, then mDNS, then TCP)
    THEN: First available method returns peers; later methods skipped

    GIVEN: First method fails
    WHEN: Retry next method
    THEN: Chain continues until success or exhausted
    """
    # Scenario 1: Static seeds available
    config = {
        "discovery": {
            "static_seeds": ["192.168.1.50:9000"],
        }
    }
    peers = discover_peers(config)
    assert len(peers) > 0
    assert peers[0]["route"] == "static_seed"

    # Scenario 2: Seeds empty, multicast available
    config["discovery"]["static_seeds"] = []
    peers = discover_peers(config)  # Fall back to mDNS
    assert all(p["route"] == "mdns" for p in peers)

    # Scenario 3: mDNS blocked, TCP scan fallback
    config["discovery"]["enable_mdns"] = False
    peers = discover_peers(config)
    assert all(p["route"] == "tcp_scan" for p in peers)

    # Scenario 4: All fail
    config["discovery"]["static_seeds"] = []
    config["discovery"]["enable_mdns"] = False
    config["discovery"]["enable_tcp_scan"] = False
    peers = discover_peers(config)
    assert len(peers) == 0  # Degraded state
```

**Deliverable:**
- `orchestrator/discovery.py` with `discover_peers()` function
- `orchestrator/config_schema.py` with discovery config schema (YAML)
- `tests/test_discovery_fallback.py` with 4 fallback chain tests
- `docs/discovery-config-spec.md` with flowchart + examples

**Checklist:**
- [ ] Fallback order: static seeds → mDNS → TCP scan → manual → degraded
- [ ] Config schema matches PHASE-0-DESIGN-SPECIFICATION.md
- [ ] Each fallback tested independently + in sequence
- [ ] Timeout per method: seeds 0s, mDNS 1s, TCP scan 60s (total)
- [ ] Team review: order correct? Timeouts reasonable?

---

## Task Group D: Integration Tests + E2E Validation

### Task D1: Integration Test: Observation Table CRUD (1h)

**Spec Test:** `test_observation_table_crud_operations`

```python
def test_observation_table_crud_operations():
    """
    GIVEN: Empty ObservationTable
    WHEN: Create, update, retrieve observations
    THEN: Operations succeed; table maintains consistency
    """
    table = ObservationTable()

    # CREATE: Add observation
    obs = PeerObservation(
        observer_id="mac-primary",
        target_peer_id="win-rtx5080",
        # ... (fields)
    )
    table.add(obs)

    # RETRIEVE: Get by (observer, target) pair
    result = table.get(observer_id="mac-primary", target_peer_id="win-rtx5080")
    assert result is not None
    assert result.confidence == obs.confidence

    # UPDATE: Add newer observation (same pair, newer timestamp)
    obs2 = PeerObservation(
        observer_id="mac-primary",
        target_peer_id="win-rtx5080",
        observer_timestamp=obs.observer_timestamp + 10,  # 10s newer
        confidence=0.92,  # Updated
    )
    table.add(obs2)

    # Latest should be obs2
    result = table.get(observer_id="mac-primary", target_peer_id="win-rtx5080", latest=True)
    assert result.confidence == 0.92

    # LIST: Query all observations
    all_obs = table.list(observer_id="mac-primary")
    assert len(all_obs) >= 1  # At least obs1 and obs2 for this observer

    # TIME-SERIES: Get all observations for target (trend analysis)
    trend = table.trend(target_peer_id="win-rtx5080", limit=10)
    assert len(trend) >= 2
    assert trend[0].observer_timestamp < trend[1].observer_timestamp  # Chronological
```

**Deliverable:**
- `orchestrator/observation_table.py` with ObservationTable class (CRUD operations)
- `tests/test_observation_table.py` with CRUD tests
- `docs/observation-table-api.md` with method signatures + examples

**Checklist:**
- [ ] Create/add() operation adds new observation
- [ ] Retrieve/get() with (observer, target, latest) filters
- [ ] Update: newer observation with same (observer, target) replaces old
- [ ] List/all() queries for trend analysis (time-series)
- [ ] TTL expiration: old observations evicted after ttl_seconds
- [ ] Team review: API ergonomic? Queries efficient?

---

### Task D2: E2E Test: Derive State from Real-World Observations (1.5h)

**Spec Test:** `test_e2e_derive_state_realistic_scenario`

```python
def test_e2e_derive_state_realistic_scenario():
    """
    GIVEN: Realistic 3-node cluster (Mac + Win3080 + Win5080)
    WHEN: Simulate 10 heartbeat cycles (100s real time)
    THEN: Topology state transitions match expected scenarios
    """
    # Scenario: Gradual failure + recovery
    scenario = [
        # T=0–30s: All direct, cross-reachable → FLEET
        {
            "mac": {"direct": [win3080, win5080], "confidence": 0.95},
            "win3080": {"direct": [mac, win5080], "confidence": 0.95},
            "win5080": {"direct": [mac, win3080], "confidence": 0.95},
            "expected": "FLEET",
        },
        # T=30–60s: Win5080 starts timing out; Mac & Win3080 still direct
        {
            "mac": {"direct": [win3080], "timeout": [win5080], "confidence": 0.7},
            "win3080": {"direct": [mac], "timeout": [win5080], "confidence": 0.7},
            "win5080": {"timeout": [mac, win3080], "confidence": 0.0},
            "expected": "PAIR",  # Mac ↔ Win3080 direct, Win5080 isolated
        },
        # T=60–90s: Win5080 recovers, back to FLEET
        {
            "mac": {"direct": [win3080, win5080], "confidence": 0.95},
            "win3080": {"direct": [mac, win5080], "confidence": 0.95},
            "win5080": {"direct": [mac, win3080], "confidence": 0.95},
            "expected": "FLEET",
        },
    ]

    for step in scenario:
        observations = build_observations_from_scenario(step)
        state, meta = derive_topology_state(observations)
        assert state == TopologyState[step["expected"]]
        print(f"✓ {step['expected']} (confidence {meta['confidence']})")
```

**Deliverable:**
- `tests/test_e2e_realistic_scenarios.py` with 5–10 scenarios
- Scenario library: cluster configurations (3-node LAN, 2-node isolated, etc.)
- Documentation: scenario playbook + expected state transitions

**Checklist:**
- [ ] Scenario 1: All direct, cross-reachable → FLEET
- [ ] Scenario 2: 1 peer fails, others still direct → PAIR
- [ ] Scenario 3: Network partition (A ↔ B, both ↔ C broken) → PARTITIONED
- [ ] Scenario 4: Gradual degradation (jitter, high latency) → DEGRADED or SUSPECT
- [ ] Scenario 5: Recovery (all come back) → back to FLEET
- [ ] Team review: scenarios cover real failures? Transitions smooth?

---

## Task Group E: Team Review + Consensus

### Task E1: Checkpoint Review (Async, 1h per checkpoint × 3) = 3h total

**Checkpoint 1.0 (Deliverables A1–A3):** Schema + Scoring + Derivation

**Review Checklist (see § 7 below):**
- [ ] Schema complete + RFC-aligned?
- [ ] Scoring formula weights reasonable?
- [ ] Derivation logic sound (all 9 states reachable)?
- [ ] Test coverage adequate (20+ tests)?
- [ ] Any blockers for Phase 1?

**Checkpoint 1.1 (Deliverables B1–B2):** Hysteresis + Failure Detection

**Review Checklist:**
- [ ] Hysteresis prevents flapping (test passes)?
- [ ] Timeout values realistic (10s/30s/90s)?
- [ ] State machine correct (4 transitions)?
- [ ] Integration with heartbeat clear?

**Checkpoint 1.2 (Deliverables C1 + D1):** Discovery + Observation Table

**Review Checklist:**
- [ ] Discovery fallback chain logical?
- [ ] Table API sufficient for Phase 1?
- [ ] TTL expiration + retention strategy clear?

---

### Task E2: Finalize All 6 Deliverables (2h)

**Deliverables:**
1. ✅ **Peer Observation Model** (Tasks A1–A3, § 1 of this doc)
2. ⏳ **Heartbeat + Failure Detector** (Tasks B1–B2, § 2 of PHASE-0-DESIGN-SPECIFICATION.md)
3. ⏳ **Recovery SLA Spec** (Manual review of § 3 of PHASE-0-DESIGN-SPECIFICATION.md)
4. ⏳ **Threat Model** (Manual review of § 4 of PHASE-0-DESIGN-SPECIFICATION.md)
5. ⏳ **Bootstrap + Discovery Fallback** (Tasks C1, § 5 of PHASE-0-DESIGN-SPECIFICATION.md)
6. ⏳ **Blocker Resolution Checklist** (Synthesize all 5 into checklist; § 6 of PHASE-0-DESIGN-SPECIFICATION.md)

**Actions:**
- [ ] Incorporate team review feedback from Checkpoints 1.0–1.2
- [ ] Resolve any conflicts or open questions
- [ ] Finalize all 6 deliverables + get team sign-off
- [ ] Update main Phase 0 spec document (PHASE-0-DESIGN-SPECIFICATION.md)
- [ ] Publish to team: "Phase 0 Design Complete"

---

## Task Group F: Phase 1 Readiness

### Task F1: Generate Phase 1 Implementation Plan (0.5h)

**Output:** Phase 1 tasks derived from Phase 0 design

**From Phase 0 Deliverables → Phase 1 Tasks:**

| Deliverable | Phase 1 Task | Effort |
|---|---|---|
| Observation Model | L1.1: Implement PeerObservation class + table | 3h |
| " | L1.2: Wire into heartbeat probe loop | 2h |
| " | L1.3: Implement derive_topology_state() | 2h |
| Failure Detector | L1.4: Heartbeat probes (10s interval) | 3h |
| " | L1.5: Hysteresis + state transitions | 2h |
| Discovery | L1.6: Static seed loading | 1h |
| " | L1.7: TCP scan fallback (discover.py integration) | 2h |
| Tests | L1.8: E2E validation (realistic scenarios) | 3h |

**Total Phase 1:** 18h (within 16–20h estimate)

---

## Summary: Phase 0 Timeline

| Week | Days | Tasks | Effort | Checkpoint |
|------|------|-------|--------|-----------|
| **W1** | 7/10–7/11 | A1–A3 (Observation model) | 5h | ✓ 1.0 (Schema + Scoring) |
| **W1** | 7/12–7/13 | B1–B2 (Hysteresis) | 3h | ✓ 1.1 (State transitions) |
| **W2** | 7/14–7/15 | C1 + D1 (Discovery + Table) | 2.5h | ✓ 1.2 (Integration) |
| **W2** | 7/16–7/17 | E1–E2 (Reviews + Finalization) | 3h | **Phase 0 Complete** |
| **Total** | 7/10–7/24 | All 6 deliverables | **17.5h** | Ready for Phase 1 |

**Phase 1 start: 2026-07-24 (1 week buffer for refinement)**

---

**Ready to start Task A1?**
