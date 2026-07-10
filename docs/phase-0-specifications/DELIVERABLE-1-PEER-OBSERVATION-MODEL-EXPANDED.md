# Phase 0 Deliverable 1 (Expanded): Peer Observation Model

> **SUPERSEDED** — this is Iteration 1 (additive confidence formula, since
> replaced by the multiplicative gated formula). Kept for research-provenance
> only; do not implement against this version. Current: [Iteration 2](DELIVERABLE-1-PEER-OBSERVATION-MODEL-REGENERATED-ITERATION-2.md).

**Navigation:** ← [task list](PHASE-0-TASK-LIST.md) · companion: [test specs](peer_observation_tdd.md) · → superseded by: [Iteration 2](DELIVERABLE-1-PEER-OBSERVATION-MODEL-REGENERATED-ITERATION-2.md)

**Date:** 2026-07-10  
**Approach:** TDD-first (test specs before schema), P2P RFC compliance (HyParView baseline, Kademlia-migration-ready), production-ready confidence scoring.

---

## § 0 — Executive Summary

Replace the 4-state enum (ISOLATED, VIA_RELAY, DIRECT_1, DIRECT_2+) with a **timestamped peer-observation table** that:

1. **Captures directed reachability** (A→B ≠ B→A) as core data
2. **Tracks confidence + proof validity** to mitigate T1–T6 threats (malicious relay, stale peers, silent hangs)
3. **Enables witness agreement** (2+ observers reduce false positives)
4. **Derives display states** (UI layer) with hysteresis to prevent state flapping
5. **Aligns with HyParView RFC 7946** for seamless PlumTree/Kademlia migration in Phase 2–3

**Key design principle:** Observation table is **ground truth**; display states are **derived & mutable**. This separation lets Phase 1 ship with simple hysteresis, Phase 1b add confidence scoring, Phase 2 upgrade to full PlumTree without schema changes.

---

## § 1 — RFC Baseline: HyParView (RFC 7946)

### What HyParView Gives Us

HyParView (Hybrid Partial View) is a **proven epidemic membership protocol** from 2015 research (Jelasity, Montresor). It defines:

1. **Active view (5–7 peers):** Peers we're connected to right now
2. **Passive view (30+ peers):** Peers we know about but aren't directly connected to
3. **Promotion on failure:** When active peer fails, promote random passive-view candidate (< 1s recovery)
4. **Shuffling:** Periodically exchange view entries with peers (bootstrap)

### Why We Adopt HyParView

- ✅ **Proven in production** (Cassandra, Akka, Riak use it)
- ✅ **Handles network churn** (nodes joining/leaving constantly)
- ✅ **Sub-second failure detection** (with application-level heartbeats)
- ✅ **No centralized discovery** (each node bootstraps from any peer it knows)
- ✅ **Compatible with future DHT** (PlumTree gossip + Kademlia DHT layer on top)

### Where We Extend HyParView

HyParView's original RFC doesn't define:
- **Proof of reachability** (needed for T1: malicious relay mitigation)
- **Confidence scoring** (needed for witness agreement + hysteresis)
- **IP migration detection** (needed for T2: stale peer mitigation)
- **Proof of backend state** (needed for our use-case: "can this peer run Ollama?")

We define these as **opaque fields in the observation table**; HyParView logic stays unchanged.

---

## § 2 — PeerObservation Schema (TDD-First Spec)

### 2.1 Core Definition

```python
# Canonical schema for Phase 1 + beyond
# All timestamps = Unix seconds (float, subsecond precision OK)
# All IDs = ed25519 public key hex (64 chars)

@dataclass(frozen=True)  # Immutable; create new instances for updates
class PeerObservation:
    """
    One node's snapshot of another node's reachability state at a point in time.
    
    Immutable record = one data point for trend analysis and witness agreement.
    Multiple observations (different timestamps, observers) are compared to derive state.
    """
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # IDENTITY
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    # WHO made this observation
    observer_id: str  # ed25519 pub key hex (64 chars) = "a7f3c9e2d4b1..."
    
    # WHO is being observed
    target_peer_id: str  # ed25519 pub key hex
    
    # WHEN this observation was recorded
    observer_timestamp: float  # Unix seconds when observer created this record
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # REACHABILITY (directed: observer → target)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    direct_status: Literal[
        "REACHABLE",      # Probe succeeded; heartbeat received within deadline
        "TIMEOUT",        # Probe sent; no response within timeout
        "UNREACHABLE",    # Probe sent; connection refused / RST received
        "STALE",          # Previously reachable; no heartbeat since deadline
        "SUSPECT",        # STALE → retrying; state-machine intermediate
        "UNKNOWN",        # Never probed or no recent data
        "DEGRADED",       # Reachable but slow / high latency / flaky
    ]
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ENDPOINT (network address)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    endpoint: str  # "192.168.1.105:9000" or "10.0.0.5:9000"
    
    endpoint_epoch: int  # Increments when peer reports IP change
                         # Use to detect/ignore stale cached entries
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TIMING DATA
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    last_heartbeat_timestamp: Optional[float]  # Last successful probe time
                                               # None if UNKNOWN or never probed
    
    last_probe_timestamp: Optional[float]  # Last probe attempt (success or fail)
    
    probe_latency_ms: Optional[float]  # Observed RTT (only if REACHABLE)
                                       # Use for tie-breaking when confidence tied
    
    time_to_suspect_ms: Optional[float]  # How long until this transitions to SUSPECT
                                         # = max(0, HEARTBEAT_DEADLINE - (now - last_heartbeat))
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ROUTE & METHOD
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    route: Literal[
        "direct",         # TCP direct connection from observer to target
        "relay",          # Via intermediate peer (relay claim)
        "discovered",     # Via discovery (mDNS, TCP scan, seed list)
        "static_seed",    # From OPENCLAW_PEERS config
        "passively_learned",  # From peer's heartbeat payload (observer_reports)
        "unknown",        # Incomplete data; route not yet determined
    ]
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PROOF & VALIDATION (Threat T1: malicious relay)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    probe_result: Optional[Mapping[str, Any]]
        # For REACHABLE:
        #   {
        #     "success": True,
        #     "latency_ms": 12,
        #     "heartbeat_received": {
        #       "node_id": "...",
        #       "endpoint": "...",
        #       "endpoint_epoch": 2,
        #       "backend_state": "MAC_DUAL",
        #       "timestamp": 1720614843,
        #       "signature": "<ed25519(heartbeat_payload)>"  # Proof of liveness
        #     }
        #   }
        #
        # For TIMEOUT:
        #   {
        #     "success": False,
        #     "error": "connection_timeout",
        #     "timeout_ms": 5000
        #   }
        #
        # For UNREACHABLE:
        #   {
        #     "success": False,
        #     "error": "connection_refused",
        #     "errno": 111
        #   }
    
    relay_proof: Optional[str]
        # For relay route: base64-encoded signed message from target
        # = signature_from_target_peer(challenge_from_observer + timestamp + nonce)
        # Proves: target is alive (not just claimed by intermediate)
        # None = unverified relay claim (confidence < 0.5)
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CONFIDENCE & CONSENSUS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    confidence: float  # 0.0 (unproven) to 1.0 (proven + witnessed)
                       # Scoring: see § 3.1
    
    proof_score: float  # Component of confidence (0.0–1.0)
                        # = 0.0 (no proof) | 0.3 (unverified claim) | 0.7 (partial proof) | 1.0 (full proof)
    
    freshness_score: float  # Component of confidence (0.0–1.0)
                            # = 1.0 if last_heartbeat < 10s ago
                            # = 0.5 if < 30s ago
                            # = 0.2 if > 30s ago (SUSPECT)
                            # = 0.0 if > 90s ago (INACTIVE)
    
    witness_agreement: int  # Number of OTHER observers reporting same status
                            # = 0 (only this observer), 1 (1 other), 2+ (consensus)
    
    witness_disagreement: int  # Number of observers reporting DIFFERENT status
                               # High disagreement = low confidence, even if proof_score high
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # BACKEND & CAPABILITIES (our use-case)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    backend_caps: Tuple[str, ...]  # Advertised by peer: ("ollama", "lmstudio")
    
    backend_state: Optional[str]  # Peer's last-reported backend state
                                  # = "MAC_DUAL" | "MAC_OLLAMA_ONLY" | "WIN_LMSTUDIO" | "MAC_NONE" | "OFFLINE"
                                  # None if never learned
    
    backend_state_timestamp: Optional[float]  # When peer last reported this
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # METADATA & LIFECYCLE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    ttl_seconds: int  # How long to trust this observation
                      # = 60 for REACHABLE (fast refresh)
                      # = 120 for SUSPECT (waiting for retry)
                      # = 300 for STALE/DEGRADED
                      # = -1 (no expiry) for static seeds
    
    tags: FrozenSet[str]  # Metadata: {"static_seed", "ip_migrated", "flaky", "relay_liar_candidate"}
                          # Used for debugging, monitoring, and selective trust
    
    notes: str  # Human-readable explanation
               # = "peer reported IP change (epoch 2→3)"
               # = "relay claim unverified; no proof received"
               # = "3 failed relay probes from this peer; trust downgraded"
    
    source_id: str  # If this observation came from another observer's heartbeat,
                    # record who reported it (for circular-reference detection)

    def __post_init__(self) -> None:
        # frozen=True blocks assignment after construction, but callers can still pass mutable
        # containers. Copy and freeze nested structures at the boundary.
        object.__setattr__(self, "probe_result", deep_freeze_mapping(self.probe_result))
        object.__setattr__(self, "backend_caps", tuple(self.backend_caps))
        object.__setattr__(self, "tags", frozenset(self.tags))
```

### 2.2 Immutability Rationale

`frozen=True` means:
- Every update = new instance (old one kept for trend analysis)
- Can store observations as immutable log
- Time-series analysis natural (sort by timestamp, compute deltas)
- Thread-safe (no mutations race)

`frozen=True` is not enough by itself for nested containers. Phase 1 must normalize mutable constructor inputs before the object escapes:

- `probe_result` is deep-copied and exposed as an immutable mapping
- `backend_caps` is stored as a tuple
- `tags` is stored as a frozenset
- tests mutate the original input dict/list/set after construction and assert the observation does not change

---

## § 3 — Confidence Scoring (TDD Spec)

### 3.1 Scoring Formula

```python
confidence = proof_score × freshness_factor × witness_multiplier

where:
    proof_score ∈ [0.0, 1.0]:
        0.0 = no proof (unverified relay claim, stale heartbeat)
        0.3 = partial proof (relay claim with unsigned response)
        0.7 = strong proof (heartbeat received, signature valid, but older)
        1.0 = full proof (fresh heartbeat, signature valid, endpoint epoch matches)
    
    freshness_factor = 0.40 + 0.60 × freshness_score
    freshness_score ∈ [0.0, 1.0]:
        1.0 if last_heartbeat < 10s ago (ACTIVE)
        0.7 if 10–30s ago (REACHABLE but warming)
        0.5 if 30–90s ago (SUSPECT)
        0.2 if > 90s ago (STALE, demote from active view)
        0.0 if never received (UNKNOWN)
    
    witness_multiplier ∈ [0.50, 1.00]:
        0.50 if witness_disagreement > witness_agreement
        0.85 if witness_agreement == 0
        0.95 if witness_agreement == 1
        1.00 if witness_agreement >= 2
```

### 3.2 Examples

**Example 1: Fresh direct connection**
```python
obs = PeerObservation(
    observer_id="mac-primary",
    target_peer_id="win-rtx5080",
    observer_timestamp=1720614843,
    direct_status="REACHABLE",
    endpoint="192.168.1.105:9000",
    endpoint_epoch=2,
    last_heartbeat_timestamp=1720614843,
    last_probe_timestamp=1720614843,
    probe_latency_ms=12.5,
    route="direct",
    probe_result={
        "success": True,
        "latency_ms": 12.5,
        "heartbeat_received": {
            "node_id": "win-rtx5080",
            "endpoint": "192.168.1.105:9000",
            "endpoint_epoch": 2,
            "backend_state": "WIN_LMSTUDIO",
            "timestamp": 1720614843,
            "signature": "abc123..."
        }
    },
    confidence=1.0,  # 1.0 × 1.0 × 1.0 = 1.0
    proof_score=1.0,   # Full proof: signature valid, epoch matches
    freshness_score=1.0,  # < 10s ago
    witness_agreement=2,  # Both mac-primary and win-rtx3080 see this
    witness_disagreement=0,
    backend_caps=["lmstudio"],
    backend_state="WIN_LMSTUDIO",
    backend_state_timestamp=1720614843,
    ttl_seconds=60,
    tags=[],
    notes="Direct connection, fresh heartbeat, cross-witnessed",
    source_id=None,
)

# Derived: REACHABLE + fresh + witnessed = confidence 1.0, add to active view
```

**Example 2: Stale passive entry**
```python
obs = PeerObservation(
    observer_id="mac-primary",
    target_peer_id="win-unknown-peer",
    observer_timestamp=1720614843,
    direct_status="STALE",
    endpoint="192.168.1.200:9000",  # Claimed by win-rtx3080
    endpoint_epoch=1,
    last_heartbeat_timestamp=1720614700,  # 143 seconds ago
    last_probe_timestamp=1720614700,
    probe_latency_ms=None,
    route="relay",
    probe_result=None,  # No direct probe yet
    relay_proof=None,   # Never got proof from relay
    confidence=0.0,  # 0.0 proof gate forces confidence to 0.0
    proof_score=0.0,   # No proof: relay claim unverified
    freshness_score=0.0,  # Way past deadline
    witness_agreement=0,  # Only this observer
    witness_disagreement=0,
    backend_caps=[],
    backend_state=None,
    backend_state_timestamp=None,
    ttl_seconds=300,
    tags=["relay_unverified", "stale"],
    notes="Peer reported this via relay; no direct probe; no proof received",
    source_id="win-rtx3080",
)

# Derived: STALE + unverified = confidence 0.0, keep only as diagnostic/passive evidence
```

**Example 3: Relay claim with partial proof**
```python
obs = PeerObservation(
    observer_id="mac-primary",
    target_peer_id="win-rtx5080",
    observer_timestamp=1720614843,
    direct_status="UNKNOWN",  # Never direct-probed
    endpoint="192.168.1.105:9000",
    endpoint_epoch=2,
    last_heartbeat_timestamp=None,
    last_probe_timestamp=1720614833,  # Relay probe 10s ago
    probe_latency_ms=None,
    route="relay",
    probe_result={
        "success": True,
        "relay_response": {
            "can_reach": True,
            "via_peer": "win-rtx3080",
            # NO PROOF of actual reachability (no signed heartbeat from target)
        }
    },
    relay_proof=None,  # No signature from target
    confidence=0.123,  # 0.3 × (0.40 + 0.60 × 0.7) × 0.50
    proof_score=0.3,   # Partial proof: relay claim + response, no target signature
    freshness_score=0.7,  # 10s ago (fresh-ish)
    witness_agreement=0,
    witness_disagreement=1,  # win-rtx3080 directly reaches this peer, we don't
    backend_caps=[],
    backend_state=None,
    backend_state_timestamp=None,
    ttl_seconds=60,
    tags=["relay_claim", "unverified_proof"],
    notes="win-rtx3080 claims it can reach; no proof from target; don't trust alone",
    source_id="win-rtx3080",
)

# Derived: confidence 0.123 < 0.5 threshold, don't mark REACHABLE yet
# Requires ≥2 observers to promote this to reachable
```

### 3.3 Decision Thresholds

```python
# State transitions based on confidence
CONFIDENCE_THRESHOLD_DIRECT = 0.7   # Minimum to add to active_view
CONFIDENCE_THRESHOLD_RELAY = 0.5    # Minimum for VIA_RELAY (needs witness agreement)
CONFIDENCE_THRESHOLD_PROMOTED = 0.6  # Minimum to promote from passive_view
CONFIDENCE_THRESHOLD_DEMOTE = 0.3   # Below this = remove from active_view

# Witness requirements
WITNESS_THRESHOLD_MARK_REACHABLE = 1  # At least 1 other observer agrees
WITNESS_THRESHOLD_MARK_SOLO = 2        # 2+ observers agree it's unreachable

# Disagreement = low confidence even if proof_score high
if witness_disagreement > witness_agreement:
    witness_multiplier = 0.50  # Penalty for conflict
```

---

## § 4 — Test Specifications (TDD: Write Tests Before Code)

All tests are **integration-level**; they test PeerObservation creation, confidence scoring, and state derivation. No mocking; use real timestamps and ed25519 keys.

### Test 1: Fresh Direct Connection

```python
# test_peer_observation_fresh_direct.py

def test_fresh_direct_connection_high_confidence():
    """
    GIVEN: Fresh heartbeat from direct peer
    WHEN: PeerObservation created with valid signature, epoch matches
    THEN: confidence >= 0.9, proof_score = 1.0, freshness_score = 1.0
    """
    now = time.time()
    mac_key = ed25519.Ed25519PrivateKey.generate()
    win_key = ed25519.Ed25519PrivateKey.generate()
    
    # Create signed heartbeat
    heartbeat = {
        "node_id": win_key.public_key().hex(),
        "endpoint": "192.168.1.105:9000",
        "endpoint_epoch": 2,
        "backend_state": "WIN_LMSTUDIO",
        "timestamp": now,
    }
    heartbeat["signature"] = sign_ed25519(win_key, heartbeat)
    
    # Create observation
    obs = PeerObservation(
        observer_id=mac_key.public_key().hex(),
        target_peer_id=win_key.public_key().hex(),
        observer_timestamp=now,
        direct_status="REACHABLE",
        endpoint="192.168.1.105:9000",
        endpoint_epoch=2,
        last_heartbeat_timestamp=now,
        last_probe_timestamp=now,
        probe_latency_ms=12.5,
        route="direct",
        probe_result={"success": True, "latency_ms": 12.5, "heartbeat_received": heartbeat},
        confidence=compute_confidence(1.0, 1.0, 2),  # proof=1.0, fresh=1.0, witnessed
        proof_score=1.0,
        freshness_score=1.0,
        witness_agreement=2,
        witness_disagreement=0,
        backend_caps=("lmstudio",),
        backend_state="WIN_LMSTUDIO",
        backend_state_timestamp=now,
        ttl_seconds=60,
        tags=frozenset(),
        notes="",
        source_id=None,
    )
    
    assert obs.confidence >= 0.9
    assert obs.proof_score == 1.0
    assert obs.freshness_score == 1.0
    # Can add to active view
    assert obs.confidence >= CONFIDENCE_THRESHOLD_DIRECT
```

### Test 2: Signature Validation (Threat T1)

```python
def test_relay_claim_requires_proof_signature():
    """
    GIVEN: Relay claim without signature from target
    WHEN: PeerObservation created with relay route but no relay_proof
    THEN: proof_score < 0.5, confidence < 0.5
    """
    now = time.time()
    mac_key = ed25519.Ed25519PrivateKey.generate()
    win3080_key = ed25519.Ed25519PrivateKey.generate()
    unknown_key = ed25519.Ed25519PrivateKey.generate()
    
    obs = PeerObservation(
        observer_id=mac_key.public_key().hex(),
        target_peer_id=unknown_key.public_key().hex(),
        observer_timestamp=now,
        direct_status="UNKNOWN",
        endpoint="192.168.1.200:9000",
        endpoint_epoch=1,
        last_heartbeat_timestamp=None,
        last_probe_timestamp=now,
        probe_latency_ms=None,
        route="relay",
        probe_result={"success": True, "can_reach": True},  # No signature
        relay_proof=None,  # No proof!
        confidence=compute_confidence(0.3, 0.7, 0),  # proof=0.3 (unverified)
        proof_score=0.3,
        freshness_score=0.7,
        witness_agreement=0,
        witness_disagreement=0,
        backend_caps=[],
        backend_state=None,
        backend_state_timestamp=None,
        ttl_seconds=60,
        tags=["relay_claim", "unverified"],
        notes="",
        source_id=win3080_key.public_key().hex(),
    )
    
    assert obs.proof_score < 0.5
    assert obs.confidence < 0.5
    # Don't mark as reachable without witness agreement
    assert obs.confidence < CONFIDENCE_THRESHOLD_RELAY
    assert obs.witness_agreement < 2
```

### Test 3: IP Migration (Threat T2)

```python
def test_ip_migration_epoch_mismatch_detected():
    """
    GIVEN: Peer migrates IP (epoch 1 → 2)
    WHEN: Observation receives heartbeat with new epoch
    THEN: Old observation (epoch=1) marked stale; new observation (epoch=2) created
    """
    now = time.time()
    mac_key = ed25519.Ed25519PrivateKey.generate()
    win_key = ed25519.Ed25519PrivateKey.generate()
    
    # Old observation: epoch 1, IP 192.168.1.50
    old_obs = PeerObservation(
        observer_id=mac_key.public_key().hex(),
        target_peer_id=win_key.public_key().hex(),
        observer_timestamp=now - 100,
        direct_status="REACHABLE",
        endpoint="192.168.1.50:9000",
        endpoint_epoch=1,
        last_heartbeat_timestamp=now - 100,
        # ... (other fields)
    )
    
    # New heartbeat arrives: epoch 2, IP 10.0.0.5
    new_heartbeat = {
        "node_id": win_key.public_key().hex(),
        "endpoint": "10.0.0.5:9000",
        "endpoint_epoch": 2,
        "timestamp": now,
        "signature": "...",
    }
    
    new_obs = PeerObservation(
        observer_id=mac_key.public_key().hex(),
        target_peer_id=win_key.public_key().hex(),
        observer_timestamp=now,
        direct_status="REACHABLE",
        endpoint="10.0.0.5:9000",
        endpoint_epoch=2,
        last_heartbeat_timestamp=now,
        # ... (other fields)
    )
    
    # Old observation should be marked stale
    assert old_obs.endpoint_epoch < new_obs.endpoint_epoch
    superseded = supersede_observation(old_obs, new_obs)
    assert old_obs.direct_status == "REACHABLE"  # immutable historical record is not mutated
    assert superseded.direct_status == "STALE"
    assert "ip_migrated" in superseded.tags
    assert new_obs.endpoint != old_obs.endpoint
```

### Test 4: Witness Agreement Reduces False Positives

```python
def test_witness_agreement_prevents_lone_claim():
    """
    GIVEN: Single relay claim (unverified) from one observer
    WHEN: No other observer agrees
    THEN: confidence < 0.5, not marked REACHABLE
    """
    # Observer 1 claims via relay
    obs1 = PeerObservation(
        # ... (relay route, unverified, witness_agreement=0)
        confidence=compute_confidence(0.3, 0.7, 0, 0),
    )
    
    assert obs1.confidence < CONFIDENCE_THRESHOLD_RELAY
    
    # Now Observer 2 also claims
    obs2 = PeerObservation(
        # ... (same relay route, witness_agreement=1)
        confidence=compute_confidence(0.3, 0.7, 1, 0),
    )
    
    # Combine via the real aggregation path, which verifies provenance and quorum.
    aggregate = aggregate_witness_confidence([obs1, obs2])
    assert aggregate.witness_agreement == 1
    assert aggregate.confidence < CONFIDENCE_THRESHOLD_RELAY
    assert aggregate.reason == "insufficient_proof_or_quorum"
```

### Test 5: Partition Detection

```python
def test_partition_detection_asymmetric_reachability():
    """
    GIVEN: Network partition (A→B works, B→A times out)
    WHEN: A and B exchange observations
    THEN: A sees B=REACHABLE, B sees A=TIMEOUT, partition flag set
    """
    now = time.time()
    a_key = ed25519.Ed25519PrivateKey.generate()
    b_key = ed25519.Ed25519PrivateKey.generate()
    
    # A's view: B is reachable
    a_sees_b = PeerObservation(
        observer_id=a_key.public_key().hex(),
        target_peer_id=b_key.public_key().hex(),
        direct_status="REACHABLE",
        confidence=0.95,
        # ...
    )
    
    # B's view: A is unreachable
    b_sees_a = PeerObservation(
        observer_id=b_key.public_key().hex(),
        target_peer_id=a_key.public_key().hex(),
        direct_status="TIMEOUT",
        confidence=0.1,
        witness_disagreement=1,  # A claims reachable, but B disagrees
        # ...
    )
    
    # Detect partition
    observations = [a_sees_b, b_sees_a]
    partition_likely = detect_partition(observations)
    assert partition_likely == True
    all_tags = {tag for obs in observations for tag in obs.tags}
    assert {"PARTITIONED", "ASYMMETRIC"} & all_tags
```

### Test 6: Hysteresis Prevents Flapping

```python
def test_hysteresis_requires_2_stable_polls():
    """
    GIVEN: State transitions DIRECT_1 → SUSPECT → DIRECT_1 over 3 polls
    WHEN: Hysteresis dwell=2 polls (10 seconds each = 20s min)
    THEN: State stays DIRECT_1 (no flap) until 2 consecutive SUSPECT polls
    """
    dwell_manager = StateTransitionManager(POLLS_TO_CONFIRM=2, dwell_time_min_s=5)
    
    # Poll 1: DIRECT_1 (stable)
    state1 = dwell_manager.update([obs_direct_1])
    assert state1 == TopologyState.DIRECT_1
    
    # Poll 2: Jitter causes SUSPECT
    state2 = dwell_manager.update([obs_suspect])
    # Hysteresis: candidate_polls = 1, doesn't transition yet
    assert state2 == TopologyState.DIRECT_1  # Still previous state
    
    # Poll 3: Jitter clears, back to DIRECT_1
    state3 = dwell_manager.update([obs_direct_1])
    # Candidate state changed again; counter resets
    assert state3 == TopologyState.DIRECT_1
```

---

## § 5 — P2P Migration Path (Kademlia/PlumTree Compatibility)

### 5.1 Phase 1 (Current): HyParView + Custom Probes

```text
PeerObservation table + HyParView membership
Custom heartbeat probes (HTTP GET /health)
Custom relay probe (HTTP POST /api/relay-probe)
No cryptographic proof yet (optional Phase 1b)
```

### 5.2 Phase 2: PlumTree Integration

```text
Keep PeerObservation table UNCHANGED
Replace custom relay probes with PlumTree gossip repair
- relay_proof field now populated by PlumTree-verified source
- witness_agreement updated via gossip (passive-view shuffling includes observations)
```

### 5.3 Phase 3: Kademlia DHT

```text
Keep PeerObservation table UNCHANGED
Add Kademlia DHT query layer on top
- route="relay" observations may become route="discovered" with discovery_method="dht"
- endpoint_epoch helps DHT detect stale entries
- Confidence scoring unchanged; DHT results feed into table as normal observations
```

**Key point:** Schema is stable across all phases. Only the *source* of observations changes (custom probes → PlumTree → DHT).

---

## § 6 — Integration Checkpoints (Non-Locking)

### Checkpoint 1.0: Schema Only (No Scoring)

**Deliverable:** PeerObservation dataclass + sample instances

**Phase 1 Task 1–2:** Implement schema, create 100 sample observations (test fixtures), load into table

**Test:** Parse observations, store, retrieve; no confidence scoring yet

**Rollback:** Trivial; just classes + data structures

---

### Checkpoint 1.1: Basic Confidence Scoring

**Deliverable:** compute_confidence() function + 3 test cases

**Phase 1 Task 3:** Implement scoring formula, wire into detection loop

**Test:** Test 1–3 from § 4 pass

**Rollback:** Simple math function; can swap out formula

---

### Checkpoint 1.2: Witness Agreement + Hysteresis

**Deliverable:** Witness agreement logic + StateTransitionManager

**Phase 1 Task 4–6:** Implement multi-observer tracking, hysteresis dwell

**Test:** Test 4–6 from § 4 pass

**Rollback:** Hysteresis is optional; can disable (just go with latest observation)

---

### Checkpoint 1.3: Full Observation Table + API

**Deliverable:** ObservationTable class + `/api/topology-state` endpoint

**Phase 1 Task 7–9:** CRUD operations, endpoint serialization, sample queries

**Test:** API returns correct observations, hydration of observations, filtering

**Rollback:** API is new; no existing code depends on it

---

---

## Conclusion: Production-Ready Foundation

This Deliverable 1 design:

1. ✅ **Captures ground truth** (directed reachability with proof)
2. ✅ **Mitigates known threats** (T1–T6) via proof + witness agreement
3. ✅ **Aligns with RFC standards** (HyParView baseline, migration path to PlumTree/Kademlia)
4. ✅ **TDD-ready** (test specs written; code follows)
5. ✅ **Non-locking** (4 checkpoints; can pause/pivot at any)
6. ✅ **Extensible** (confidence formula, threshold tuning in Phase 1b)

---

**Phase 0 next: Finalize this spec with team. Estimated: 4–6 hours. Target completion: 2026-07-12.**
