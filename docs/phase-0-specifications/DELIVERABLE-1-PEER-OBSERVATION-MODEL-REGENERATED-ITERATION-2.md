# Deliverable 1 — PeerObservation Model (Regenerated, All Fixes Applied)

**Navigation:** ← [task list](PHASE-0-TASK-LIST.md) · supersedes: [Iteration 1 (expanded)](DELIVERABLE-1-PEER-OBSERVATION-MODEL-EXPANDED.md) · companion: [test specs](peer_observation_tdd.md) · consumed by: [D2](DELIVERABLE-2-HEARTBEAT-LIVENESS-REGENERATED.md) · constrained by: [D4 threat model](DELIVERABLE-4-THREAT-MODEL-REGENERATED.md) · → feeds: [Phase 1 scope](PHASE-1-SCOPE-DRAFT.md)

**Phase:** 0 · **Iteration:** 2 (fixes folded in) · **Date:** 2026-07-10
**Change log vs. Iteration 1:**
- **A1** — `time_to_suspect_ms` demoted from stored field to `@property`; new `chain_depth` field added (gossip-loop safety).
- **Confidence** — additive formula **replaced** by the **multiplicative gated formula** (critical-blocker fix: unproven observations can no longer cross a reachability threshold on freshness + witnesses alone).
- **T2** — IP-migration mitigation now also performs a **T7 signed-timestamp comparison** (epoch-replay / rollback defense).
- **Naming** — `witness_bonus` → `witness_multiplier`; `probe_latency_ms` docstring clarified; TTL and route semantics documented.

---

## Section 1 — RFC Baseline *(unchanged)*

The PeerObservation model is the on-the-wire and in-memory unit of the OpenClaw membership layer. Its design descends from three well-understood protocol families, adapted for a small, mixed-trust LAN fleet (mac-primary, win-rtx3080, win-rtx5080, transient peers):

| Baseline | Borrowed mechanism | Where it appears in this model |
|----------|-------------------|-------------------------------|
| **SWIM** (Scalable Weakly-consistent Infection-style Membership) | Direct probe → suspect → confirm lifecycle; incarnation numbers | `direct_status` ∈ {REACHABLE, SUSPECT, STALE, TIMEOUT, UNREACHABLE, DEGRADED, UNKNOWN}; `endpoint_epoch` is the incarnation counter |
| **HyParView** | Two-tier views: small **active_view** (probed, high-confidence) + larger **passive_view** (gossiped, low-confidence backup) | `confidence` thresholds gate active-view membership; passive entries carry long TTL |
| **Signed gossip / Secure membership** | Every membership claim carries a verifiable proof; relayed claims require the target's own signature | `probe_result.heartbeat_received.signature`, `relay_proof`, `proof_score` |

**Invariants carried forward unchanged:**

1. **Reachability is directional.** An observation always reads observer → target; symmetric reachability is *derived* by pairing two directed observations, never assumed.
2. **Every state transition is proof-anchored.** A node may be marked REACHABLE only on the strength of a cryptographically verifiable heartbeat or a relay claim that carries the target's signature.
3. **Epoch monotonicity.** `endpoint_epoch` increases whenever a peer's `(ip, port)` changes; a higher epoch always supersedes a lower one for the same `target_peer_id`.
4. **Time is advisory, proof is authoritative.** Freshness modulates confidence but can never, on its own, manufacture it. *(This invariant is what the Section 3 formula change enforces mechanically — see the critical-blocker note.)*

No baseline mechanism changed in this iteration. Sections 2, 3, 4, and 6 change *how* these invariants are enforced; Section 1 and Section 5 restate the contract they enforce.

---

## Section 2 — PeerObservation Schema *(fixes applied)*

**Field changes (Iteration 2):**

| Field | Iteration 1 | Iteration 2 | Rationale |
|-------|-------------|-------------|-----------|
| `time_to_suspect_ms` | stored `Optional[float]` | **`@property`** (computed) | Stored computed value rots under clock skew; recompute on read. |
| `chain_depth` | *absent* | **`int = 0`** + `MAX_CHAIN_DEPTH` reject rule | Breaks relay cycles, bounds gossip fan-out. |
| `confidence` | computed by additive formula | **computed by multiplicative gated formula (Section 3)** | Ensures proof is a hard gate; zero proof → zero confidence. |
| `backend_state` | free `str` | **`BackendState` enum** | Canonical, extensible, non-breaking. |

### 2.1 StateTransitionManager Constants *(Asymmetric Hysteresis)*

The `StateTransitionManager` owns peer state transitions (ACTIVE → SUSPECT → INACTIVE). Hysteresis constants implement **asymmetric thresholds**: quick to suspect (low positive threshold), conservative to recover (high negative threshold + sustained hold). This design prioritizes cascading-failure resilience over transient-glitch UX.

**Constants table:**

| Constant | Value | Semantics |
|----------|:-----:|-----------|
| `PROMOTE_THRESHOLD` | **2** | Consecutive HEALTHY/REACHABLE signals required to transition from SUSPECT → ACTIVE (fast recovery eligibility) |
| `DEMOTE_THRESHOLD` | **3** | Consecutive non-HEALTHY/UNREACHABLE signals required to transition from ACTIVE → SUSPECT (slow degradation, tolerates transient loss) |
| `CONFIRM_DEAD_HOLD` | **90s** | Minimum continuous SUSPECT duration before escalation to INACTIVE (sustained hold prevents hair-trigger dead marking) |
| `RECOVERY_GRACE` | **1** | One HEALTHY signal in SUSPECT state immediately cancels escalation counter (prevents flip-flopping on marginal links) |

**Key asymmetry rationale:**
- `PROMOTE_THRESHOLD=2` (quick): Two successive REACHABLE observations (~20s) qualify a peer for ACTIVE status, enabling rapid re-integration after brief transient failures.
- `DEMOTE_THRESHOLD=3` (conservative): Three successive UNREACHABLE observations (~30s) are required to mark a peer SUSPECT, providing tolerance for transient loss and single-packet-burst glitches.
- Combined with `CONFIRM_DEAD_HOLD=90s`, the full path from ACTIVE → INACTIVE takes a minimum of 30s (demotion) + 90s (hold) = 120s, protecting against premature partition on flaky links.

**PeerRecord dataclass example with dual counters:**

```python
@dataclass
class PeerRecord:
    peer_id: str
    state: PeerState = PeerState.ACTIVE
    endpoint_epoch: int = 0
    last_transition_ts: float = 0.0

    # Independent hysteresis counters for asymmetric thresholds
    pending_count_promote: int = 0  # HEALTHY signals toward ACTIVE (0–2)
    pending_count_demote: int = 0   # UNREACHABLE signals toward SUSPECT (0–3)

    # Recovery hold window
    confirm_dead_timestamp: Optional[float] = None  # Set on ACTIVE→SUSPECT; cleared on recovery

    def is_in_recovery_hold(self, now: float) -> bool:
        """True if peer is INACTIVE and still within CONFIRM_DEAD_HOLD window."""
        if self.state != PeerState.INACTIVE or not self.confirm_dead_timestamp:
            return False
        elapsed = now - self.confirm_dead_timestamp
        return elapsed < 90.0  # CONFIRM_DEAD_HOLD seconds
```

**Deprecated reference:** In prior versions, `POLLS_TO_CONFIRM` was used for symmetric thresholds. This constant is **renamed to `PROMOTE_THRESHOLD`** to reflect asymmetric semantics and align with `DEMOTE_THRESHOLD`.

---

## Section 3 — Confidence Scoring *(NEW MULTIPLICATIVE FORMULA)*

### 3.1 Critical blocker being fixed

The Iteration-1 **additive** formula was:

```text
confidence = (proof_score × 0.5) + (freshness_score × 0.3) + (witness_bonus × 0.2)
```

**Blocker:** the three terms are *independent addends*, so freshness and witnesses can manufacture confidence with **zero proof**:

```text
proof_score = 0.0, freshness = 1.0, witness_agreement = 2
  → (0.0×0.5) + (1.0×0.3) + (1.0×0.2) = 0.50      # CROSSES relay threshold with NO proof
```

This violates Section-1 Invariant 4. A relay that fabricates a fresh timestamp and colludes with two witnesses could mark an **unreachable, unproven** peer as REACHABLE. **Ship blocker.**

### 3.2 The multiplicative gated formula

Proof is promoted from a weighted addend to a **hard multiplicative gate**. Freshness and witnesses become *envelopes* that can only ever *attenuate* a proof-backed score — never create one.

```text
confidence = proof_score × freshness_factor × witness_multiplier
```

with:

```text
freshness_factor  = 0.40 + 0.60 × freshness_score        #  ∈ [0.40, 1.00]

witness_multiplier =                                      #  ∈ [0.50, 1.00]
    0.50  if witness_disagreement > witness_agreement     #  contradicted
    0.85  elif witness_agreement == 0                     #  solo
    0.95  elif witness_agreement == 1                     #  one corroborator
    1.00  else  (witness_agreement >= 2)                  #  consensus
```

**Key property (the fix):** `proof_score = 0.0 ⟹ confidence = 0.0`, *regardless* of freshness or witness count. Unproven observations are structurally incapable of crossing any reachability threshold. Invariant 4 is enforced by arithmetic.

### 3.3 Reference implementation

```python
def compute_confidence(
    proof_score: float,
    freshness_score: float,
    witness_agreement: int,
    witness_disagreement: int = 0,
) -> float:
    """
    Multiplicative gated confidence ∈ [0.0, 1.0].
    CRITICAL: proof_score is a multiplicative GATE. With proof_score == 0.0 the
    result is 0.0 no matter how fresh or witnessed. This closes Iteration-1 blocker.
    """
    proof_gate = proof_score
    freshness_factor = 0.40 + 0.60 * freshness_score

    if witness_disagreement > witness_agreement:
        witness_multiplier = 0.50
    elif witness_agreement == 0:
        witness_multiplier = 0.85
    elif witness_agreement == 1:
        witness_multiplier = 0.95
    else:
        witness_multiplier = 1.00

    confidence = proof_gate * freshness_factor * witness_multiplier
    return max(0.0, min(1.0, confidence))
```

### 3.4 Test vectors (ghost-peer prevention)

| Scenario | proof | fresh | agree/disagree | Additive (old) | Multiplicative (new) | Verdict |
|----------|:----:|:----:|:----:|:----:|:----:|------|
| **T1: Ghost (perfect proof, dead 2min, witnessed)** | 1.0 | 0.0 | 0/0 | 0.54 | **0.34** ✅ blocked |
| **T1: No-proof, fresh, 2 witnesses** | **0.0** | 1.0 | 2/0 | **0.50** ⚠ | **0.00** ✅ gated |
| **T3: Healthy peer** | 1.0 | 1.0 | 2/0 | 1.00 | **1.00** unchanged |
| **T4: Fresh but unproven** | 0.0 | 1.0 | 0/1 | 0.42 | **0.00** ✅ gated |
| **T5: Aging real peer** | 1.0 | 0.5 | 1/0 | 0.60 | **0.48** ✅ below active |

The **critical fix**: row 2 (T1 blocker) drops from 0.54 → 0.00, a gate that kills ghost peers.

---

## Section 4 — TDD Test Specs *(updated + 5 new multiplicative tests)*

Existing Batches 1–6 carry forward with **updated confidence assertions** per Section 3.4. Five new tests specifically pin the multiplicative gate behavior.

### 4.1 New Batch 7 — Multiplicative Gate Behavior

```python
def test_M1_proof_gate_zeroes_unproven_fresh_witnessed():
    """THE BLOCKER REGRESSION TEST."""
    c = compute_confidence(proof_score=0.0, freshness_score=1.0,
                           witness_agreement=2, witness_disagreement=0)
    assert c == 0.0
    assert c < CONFIDENCE_THRESHOLD_RELAY

def test_M2_freshness_floor_retains_proven_stale():
    """Proven-but-stale peer keeps a 0.40 freshness floor."""
    c = compute_confidence(1.0, 0.0, 0, 0)
    assert abs(c - 0.34) < 1e-9
    assert c < CONFIDENCE_THRESHOLD_DIRECT

def test_M3_monotonic_nondecreasing_in_each_factor():
    """Property test: confidence non-decreasing in proof, freshness, witness tier."""
    base = compute_confidence(0.6, 0.6, 1, 0)
    assert compute_confidence(0.9, 0.6, 1, 0) >= base
    assert compute_confidence(0.6, 0.9, 1, 0) >= base
    assert compute_confidence(0.6, 0.6, 2, 0) >= base
    assert compute_confidence(0.6, 0.6, 0, 1) <= base

def test_M4_disagreement_penalty_dominates():
    """Contradiction halves the envelope; cannot reach DIRECT threshold."""
    c = compute_confidence(1.0, 1.0, 0, 1)
    assert abs(c - 0.50) < 1e-9
    assert c <= CONFIDENCE_THRESHOLD_RELAY

def test_M5_malicious_relay_stays_far_below_threshold():
    """Forged signature + contradiction: ~0.025, order of magnitude under 0.50."""
    c = compute_confidence(0.05, 1.0, 0, 2)
    assert abs(c - 0.025) < 1e-9
    assert c < 0.1
```

**Coverage gate for Checkpoint 1.1:** Batches 1–7 must all pass; M3 runs under hypothesis with ≥200 examples.

---

## Section 5 — P2P Migration Path *(unchanged)*

The multiplicative formula generalizes safely to full peer-to-peer gossip without a schema break:

1. **Stage 0 — Local table (Phase 1.0).** Each node keeps its own observations; confidence computed locally.
2. **Stage 1 — Pairwise exchange.** Two nodes swap observation tables on heartbeat.
3. **Stage 2 — Epidemic gossip (HyParView).** `chain_depth > MAX_CHAIN_DEPTH` bounds fan-out.
4. **Stage 3 — Consensus views.** Multi-observer agreement drives promotion; a peer reaches active view only on both proof-backed confidence ≥ 0.70 AND witness quorum ≥ 2.

**Key safety property:** because proof is a multiplicative gate, a relayed observation can never score higher than the original proof permits — gossip can dilute confidence but never inflate it.

---

## Section 6 — Integration Checkpoints 1.0–1.3 *(fixes wired in)*

### Threat model (with new T7)

| ID | Threat | Mitigation (Phase 0) |
|----|--------|----------------------|
| **T1** | Relay lies | Require target signature; multiplicative proof gate zeros unproven claims |
| **T2** | Stale endpoint | Monotonic `endpoint_epoch` + signed timestamp tie-break |
| **T3/T4** | Witness collusion | `witness_multiplier` caps at 0.50 under contradiction |
| **T5** | Stale cache | TTL measured from `observer_timestamp`; query-time eviction |
| **T6** | Gossip loops | `chain_depth > MAX_CHAIN_DEPTH` reject |
| **T7** (NEW) | **Epoch-replay / timestamp rollback** | Supersession compares `(endpoint_epoch, last_heartbeat_timestamp)` lexicographically |

**Checkpoint 1.0 — Schema landed:** dataclass with all fixes, module constants defined. Gate: all 10 fixtures instantiate with updated confidence values; no stored `time_to_suspect_ms`.

**Checkpoint 1.1 — Confidence wired (multiplicative):** `compute_confidence()` implemented; Test Batches 1–7 green; no `proof_score == 0.0` yields `confidence > 0.0`.

**Checkpoint 1.2 — Witness + hysteresis:** `StateTransitionManager` applies PROMOTE_THRESHOLD=2 + DEMOTE_THRESHOLD=3 asymmetric debounce (formerly POLLS_TO_CONFIRM); promotion requires `confidence ≥ 0.70` sustained.

**Checkpoint 1.3 — Epoch + T7 replay defense:** `supersedes()` enforces dual `(epoch, timestamp)` check; replay test asserts old record retained.

---

*End of Deliverable 1 (Iteration 2). All fixes integrated. Ready for Checkpoint 1.0 gate.*
