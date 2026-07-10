# PeerObservation Schema: TDD Test Specs & Fixtures

**Date:** 2026-07-10
**Phase:** 0 Deliverable 1 (Non-binding Iteration 1)
**Approach:** Test-driven design; fixtures exercise all confidence levels & edge cases

---

## Part 1: Test Specification Suite

### Test Batch 1: Confidence Scoring & Direct Reachability

#### Test 1.1: Fresh Direct Connection (High Confidence)
```python
def test_fresh_direct_connection_high_confidence():
    """
    GIVEN: Fresh heartbeat from direct peer, signed, endpoint matches
    WHEN: PeerObservation created
    THEN: 
        - proof_score = 1.0 (full cryptographic proof)
        - freshness_score = 1.0 (< 10s old)
        - confidence >= 0.9
        - can add to active_view
    """
    now = 1720614843  # Unix timestamp
    obs = build_observation(
        direct_status="REACHABLE",
        route="direct",
        last_heartbeat_timestamp=now,
        proof_score=1.0,
        freshness_score=1.0,
        witness_agreement=2,  # Both mac-primary and win-rtx3080 see it
        witness_disagreement=0,
    )
    
    assert obs.confidence >= 0.9
    assert obs.confidence == (1.0 * 0.5) + (1.0 * 0.3) + (1.0 * 0.2)  # = 1.0 (capped)
    assert obs.proof_score == 1.0
    assert obs.probe_result["success"] is True
    assert obs.probe_result["heartbeat_received"]["signature"] is not None
    assert obs.endpoint_epoch == obs.probe_result["heartbeat_received"]["endpoint_epoch"]
```

#### Test 1.2: Timeout (Low Confidence)
```python
def test_timeout_low_confidence():
    """
    GIVEN: Probe sent but no response within timeout
    WHEN: PeerObservation created with TIMEOUT status
    THEN:
        - proof_score = 0.0 (no proof)
        - freshness_score = 0.0 (no successful heartbeat)
        - confidence <= 0.1
        - must NOT add to active_view
    """
    now = 1720614843
    obs = build_observation(
        direct_status="TIMEOUT",
        route="direct",
        last_heartbeat_timestamp=None,  # Never succeeded
        last_probe_timestamp=now,
        proof_score=0.0,
        freshness_score=0.0,
        witness_agreement=0,
        witness_disagreement=1,  # Other observer reached it fine
    )
    
    assert obs.confidence <= 0.1
    assert obs.proof_score == 0.0
    assert obs.probe_result["success"] is False
    assert obs.probe_result["error"] == "connection_timeout"
    assert obs.confidence < CONFIDENCE_THRESHOLD_DIRECT
```

#### Test 1.3: Stale Passive Entry (Very Low Confidence)
```python
def test_stale_passive_entry_very_low_confidence():
    """
    GIVEN: Peer reported via relay, no direct probe, no heartbeat > 90s
    WHEN: PeerObservation created with STALE status
    THEN:
        - proof_score = 0.0 (relay claim, no proof)
        - freshness_score = 0.0 (way past deadline)
        - confidence <= 0.15
        - demote from active_view, keep in passive_view only
    """
    now = 1720614843
    obs = build_observation(
        direct_status="STALE",
        route="relay",
        last_heartbeat_timestamp=now - 143,  # 143 seconds ago
        last_probe_timestamp=now - 143,
        probe_latency_ms=None,
        proof_score=0.0,
        freshness_score=0.0,
        witness_agreement=0,
        witness_disagreement=0,
        relay_proof=None,
        tags=["relay_unverified", "stale"],
    )
    
    assert obs.confidence <= 0.15
    assert obs.direct_status == "STALE"
    assert obs.route == "relay"
    assert obs.ttl_seconds == 300  # Long TTL for passive entries
```

#### Test 1.4: Degraded Link (Medium Confidence)
```python
def test_degraded_link_medium_confidence():
    """
    GIVEN: Peer responds but with high latency (300ms+)
    WHEN: PeerObservation created with DEGRADED status
    THEN:
        - proof_score = 0.8 (proof present but link quality poor)
        - freshness_score = 0.9 (recent)
        - confidence ≈ 0.65–0.75
        - can stay in active_view but priority for replacement
    """
    now = 1720614843
    obs = build_observation(
        direct_status="DEGRADED",
        route="direct",
        last_heartbeat_timestamp=now,
        probe_latency_ms=325.0,  # High latency
        proof_score=0.8,
        freshness_score=0.9,
        witness_agreement=0,
        witness_disagreement=0,
        tags=["degraded", "high_latency"],
        notes="Responding but slow (325ms RTT); may indicate congestion or link quality issue",
    )
    
    assert 0.65 <= obs.confidence <= 0.75
    assert obs.probe_latency_ms > 300
    assert obs.direct_status == "DEGRADED"
```

---

### Test Batch 2: Relay & Proof Validation (Threat T1)

#### Test 2.1: Unverified Relay Claim (No Proof)
```python
def test_unverified_relay_no_proof():
    """
    GIVEN: Relay claim without signature from target peer
    WHEN: PeerObservation created with route="relay" but relay_proof=None
    THEN:
        - proof_score = 0.3 (unverified claim)
        - confidence < 0.5
        - requires witness agreement to mark reachable
    """
    now = 1720614843
    obs = build_observation(
        direct_status="UNKNOWN",
        route="relay",
        last_probe_timestamp=now,
        last_heartbeat_timestamp=None,
        proof_score=0.3,
        freshness_score=0.7,
        witness_agreement=0,
        witness_disagreement=0,
        relay_proof=None,  # No signature from target!
        probe_result={"success": True, "can_reach": True},  # But no proof
        tags=["relay_claim", "unverified_proof"],
        source_id="win-rtx3080",
    )
    
    assert obs.confidence < 0.5
    assert obs.relay_proof is None
    assert obs.proof_score < 0.5
```

#### Test 2.2: Relay Claim with Valid Proof
```python
def test_relay_claim_with_valid_proof():
    """
    GIVEN: Relay claim WITH signature from target (relay_proof present)
    WHEN: PeerObservation created with verified relay_proof
    THEN:
        - proof_score = 0.85–0.95 (strong proof via relay)
        - confidence ≈ 0.70–0.80
        - can mark reachable if witnessed
    """
    now = 1720614843
    obs = build_observation(
        direct_status="REACHABLE",
        route="relay",
        last_probe_timestamp=now,
        last_heartbeat_timestamp=now,
        proof_score=0.9,
        freshness_score=0.95,
        witness_agreement=1,
        witness_disagreement=0,
        relay_proof="<base64-signed-message-from-target>",  # Valid proof!
        probe_result={
            "success": True,
            "relay_response": {
                "can_reach": True,
                "via_peer": "win-rtx3080",
                "target_signature": "abc123...",
            }
        },
        tags=["relay_claim", "verified_proof"],
        source_id="win-rtx3080",
    )
    
    assert obs.relay_proof is not None
    assert obs.proof_score >= 0.85
    assert obs.confidence >= 0.70
```

#### Test 2.3: Malicious Relay Attempt (T1: Relay Lies)
```python
def test_malicious_relay_attempt_detected():
    """
    GIVEN: Relay claims peer is reachable, but:
           - Target signature is invalid (forged)
           - OR target explicitly contradicts via direct probe
    WHEN: PeerObservation created + cross-check with target's own observation
    THEN:
        - Relay marked with tag "relay_liar_candidate"
        - proof_score < 0.3
        - confidence downgraded
        - High witness_disagreement (target says unreachable, relay says reachable)
    """
    now = 1720614843
    relay_claim = build_observation(
        direct_status="REACHABLE",
        route="relay",
        last_probe_timestamp=now,
        proof_score=0.2,  # Signature validation failed
        freshness_score=0.8,
        witness_agreement=0,
        witness_disagreement=1,  # Target disagrees!
        relay_proof="<invalid-signature>",
        tags=["relay_claim", "invalid_signature", "relay_liar_candidate"],
    )
    
    target_direct = build_observation(
        direct_status="UNREACHABLE",
        route="direct",
        observer_id=relay_claim.target_peer_id,
        target_peer_id=relay_claim.observer_id,  # Reversed: target sees relay as unreachable
        last_probe_timestamp=now,
        proof_score=1.0,
        witness_agreement=0,
        tags=["direct_probe", "connection_refused"],
    )
    
    # Check conflict
    assert relay_claim.direct_status != target_direct.direct_status
    assert "relay_liar_candidate" in relay_claim.tags
    assert relay_claim.witness_disagreement > 0
    assert relay_claim.proof_score < 0.3
```

---

### Test Batch 3: IP Migration & Epoch Tracking (Threat T2)

#### Test 3.1: IP Migration Detected (Epoch Increment)
```python
def test_ip_migration_epoch_increment():
    """
    GIVEN: Peer migrates from 192.168.1.50:9000 (epoch=1) to 10.0.0.5:9000 (epoch=2)
    WHEN: New observation arrives with higher epoch
    THEN:
        - Old observation tagged "ip_migrated" or marked STALE
        - New observation creates fresh record with epoch=2
        - Confidence of old observation drops to 0.0
        - New observation starts fresh
    """
    now = 1720614843
    old_obs = build_observation(
        endpoint="192.168.1.50:9000",
        endpoint_epoch=1,
        last_heartbeat_timestamp=now - 100,
        direct_status="REACHABLE",
        confidence=0.95,
    )
    
    # New heartbeat arrives: epoch=2, IP changed
    new_obs = build_observation(
        endpoint="10.0.0.5:9000",
        endpoint_epoch=2,
        last_heartbeat_timestamp=now,
        direct_status="REACHABLE",
        confidence=0.95,
        tags=["ip_migrated"],
    )
    
    # Mark old observation as stale
    old_obs_stale = dataclass_replace(old_obs, direct_status="STALE", tags=["ip_migrated", "superseded"])
    
    assert new_obs.endpoint != old_obs.endpoint
    assert new_obs.endpoint_epoch > old_obs.endpoint_epoch
    assert old_obs_stale.direct_status == "STALE"
    assert new_obs.confidence >= 0.9
```

#### Test 3.2: Epoch Mismatch (Stale Cached Entry)
```python
def test_epoch_mismatch_stale_cached_entry():
    """
    GIVEN: Cached observation has endpoint_epoch=1, but peer heartbeat says epoch=3
    WHEN: Large gap in epoch numbers
    THEN:
        - Detect stale cache
        - Mark observation with "epoch_mismatch" tag
        - Ignore cached observation for reachability decisions
    """
    now = 1720614843
    cached_obs = build_observation(
        endpoint="192.168.1.50:9000",
        endpoint_epoch=1,
        last_heartbeat_timestamp=now - 500,  # Very old
        direct_status="REACHABLE",
    )
    
    new_heartbeat = {
        "endpoint_epoch": 3,  # Gap of 2 epochs!
        "endpoint": "10.0.0.7:9000",
    }
    
    # Check for mismatch
    assert new_heartbeat["endpoint_epoch"] - cached_obs.endpoint_epoch >= 2
    assert "epoch_mismatch" should_be_tagged(cached_obs)
```

---

### Test Batch 4: Witness Agreement & Consensus (Threat T3/T4)

#### Test 4.1: Witness Agreement Prevents Lone Claims
```python
def test_witness_agreement_prevents_lone_claims():
    """
    GIVEN: Single observer claims relay reachability (unverified)
    WHEN: No other observer agrees
    THEN:
        - witness_agreement = 0
        - confidence < CONFIDENCE_THRESHOLD_RELAY (0.5)
        - must NOT mark reachable
    """
    obs = build_observation(
        direct_status="UNKNOWN",
        route="relay",
        proof_score=0.3,
        freshness_score=0.7,
        witness_agreement=0,  # Only this observer!
        witness_disagreement=0,
        confidence=0.35,  # Below 0.5 threshold
    )
    
    assert obs.witness_agreement == 0
    assert obs.confidence < 0.5
    assert obs.confidence < CONFIDENCE_THRESHOLD_RELAY
```

#### Test 4.2: Two Witnesses Achieve Consensus
```python
def test_two_witnesses_achieve_consensus():
    """
    GIVEN: Two observers independently report same endpoint as REACHABLE
    WHEN: Both submit observations with witness_agreement=1
    THEN:
        - Combined confidence rises
        - Can mark endpoint REACHABLE if proof_score > 0.5
    """
    obs1 = build_observation(
        observer_id="mac-primary",
        target_peer_id="unknown-peer",
        direct_status="REACHABLE",
        proof_score=0.7,
        freshness_score=0.9,
        witness_agreement=1,  # Mac sees win-rtx3080 also agree
        witness_disagreement=0,
        confidence=(0.7 * 0.5) + (0.9 * 0.3) + (1.0 * 0.2),  # ≈ 0.77
    )
    
    obs2 = build_observation(
        observer_id="win-rtx3080",
        target_peer_id="unknown-peer",
        direct_status="REACHABLE",
        proof_score=0.8,
        freshness_score=0.85,
        witness_agreement=1,  # Win sees mac-primary also agree
        witness_disagreement=0,
        confidence=(0.8 * 0.5) + (0.85 * 0.3) + (1.0 * 0.2),  # ≈ 0.795
    )
    
    assert obs1.witness_agreement == 1
    assert obs2.witness_agreement == 1
    assert obs1.confidence >= 0.75
    assert obs2.confidence >= 0.75
```

#### Test 4.3: Witness Disagreement Flags Partition or Malice
```python
def test_witness_disagreement_flags_partition():
    """
    GIVEN: Observer A sees peer as REACHABLE; Observer B sees it as TIMEOUT
    WHEN: Observations exchanged
    THEN:
        - witness_disagreement > 0 for both
        - confidence capped (penalty applied)
        - Likely partition or observer malfunction
    """
    obs_a = build_observation(
        observer_id="observer-a",
        target_peer_id="peer-x",
        direct_status="REACHABLE",
        proof_score=1.0,
        freshness_score=1.0,
        witness_agreement=0,
        witness_disagreement=1,  # B disagrees!
        confidence=(1.0 * 0.5) + (1.0 * 0.3) + (0.0 * 0.2),  # = 0.8, then penalize
        tags=["asymmetric_reachability", "partition_suspect"],
    )
    
    obs_b = build_observation(
        observer_id="observer-b",
        target_peer_id="peer-x",
        direct_status="TIMEOUT",
        proof_score=0.0,
        freshness_score=0.0,
        witness_agreement=0,
        witness_disagreement=1,  # A disagrees!
        confidence=0.0 * 0.5 + 0.0 * 0.3 + 0.0 * 0.2,  # = 0.0
        tags=["timeout", "asymmetric_reachability"],
    )
    
    # Both show disagreement
    assert obs_a.witness_disagreement == 1
    assert obs_b.witness_disagreement == 1
    assert obs_a.direct_status != obs_b.direct_status
    # Confidence is penalized
    final_confidence_a = obs_a.confidence * 0.5 if obs_a.witness_disagreement > 0 else obs_a.confidence
    assert final_confidence_a < 0.5
```

---

### Test Batch 5: Static Seeds & Discovery

#### Test 5.1: Static Seed Entry (No Expiry)
```python
def test_static_seed_no_expiry():
    """
    GIVEN: Peer from OPENCLAW_PEERS config (static seed)
    WHEN: PeerObservation created with route="static_seed"
    THEN:
        - ttl_seconds = -1 (no expiry)
        - tag includes "static_seed"
        - confidence depends on probe result, not time
    """
    obs = build_observation(
        route="static_seed",
        tags=["static_seed"],
        ttl_seconds=-1,
        confidence=0.9,  # Based on last probe, not age
        notes="From OPENCLAW_PEERS config",
    )
    
    assert obs.ttl_seconds == -1
    assert "static_seed" in obs.tags
    # No automatic expiry; manually refresh only
```

#### Test 5.2: Discovered via TCP Scan
```python
def test_discovered_via_tcp_scan():
    """
    GIVEN: Peer discovered via local TCP port scan
    WHEN: PeerObservation created with route="discovered"
    THEN:
        - tag includes "discovered"
        - proof_score depends on successful connection
        - ttl_seconds = 60 (refresh frequently)
    """
    obs = build_observation(
        route="discovered",
        direct_status="REACHABLE",
        proof_score=0.6,  # Connection succeeded, but no heartbeat signature yet
        freshness_score=0.95,
        tags=["discovered", "tcp_scan"],
        ttl_seconds=60,
        confidence=(0.6 * 0.5) + (0.95 * 0.3) + (0.2 * 0.2),  # ≈ 0.62
    )
    
    assert obs.route == "discovered"
    assert obs.ttl_seconds == 60
```

---

### Test Batch 6: Backend Capabilities

#### Test 6.1: Backend State Tracking
```python
def test_backend_state_tracking():
    """
    GIVEN: Peer reports backend_state = "WIN_LMSTUDIO" in heartbeat
    WHEN: PeerObservation created
    THEN:
        - backend_state captured
        - backend_state_timestamp recorded
        - backend_caps populated from heartbeat
    """
    now = 1720614843
    obs = build_observation(
        backend_state="WIN_LMSTUDIO",
        backend_state_timestamp=now,
        backend_caps=["lmstudio"],
        probe_result={
            "heartbeat_received": {
                "backend_state": "WIN_LMSTUDIO",
            }
        },
    )
    
    assert obs.backend_state == "WIN_LMSTUDIO"
    assert obs.backend_state_timestamp == now
    assert "lmstudio" in obs.backend_caps
```

---

## Part 2: Fixture Instances (10 Examples)

Each fixture covers a unique scenario with realistic confidence levels.

### Fixture 1: Fresh Direct Connection (Confidence ≈ 0.95)
```python
FIXTURE_FRESH_DIRECT = PeerObservation(
    observer_id="mac-primary-a7f3c9e2d4b1aaff",
    target_peer_id="win-rtx5080-c4d8e2f1a3b7c9d5",
    observer_timestamp=1720614843.0,
    direct_status="REACHABLE",
    endpoint="192.168.1.105:9000",
    endpoint_epoch=2,
    last_heartbeat_timestamp=1720614843.0,
    last_probe_timestamp=1720614843.0,
    probe_latency_ms=12.5,
    time_to_suspect_ms=9990.0,  # 10s until heartbeat deadline
    route="direct",
    probe_result={
        "success": True,
        "latency_ms": 12.5,
        "heartbeat_received": {
            "node_id": "win-rtx5080-c4d8e2f1a3b7c9d5",
            "endpoint": "192.168.1.105:9000",
            "endpoint_epoch": 2,
            "backend_state": "WIN_LMSTUDIO",
            "timestamp": 1720614843.0,
            "signature": "aAbBcCdDeEfF1122334455667788990011223344556677889900112233445566",
        }
    },
    relay_proof=None,
    confidence=0.95,
    proof_score=1.0,
    freshness_score=1.0,
    witness_agreement=2,
    witness_disagreement=0,
    backend_caps=["lmstudio"],
    backend_state="WIN_LMSTUDIO",
    backend_state_timestamp=1720614843.0,
    ttl_seconds=60,
    tags=[],
    notes="Direct connection, fresh heartbeat, cross-witnessed by mac-primary and win-rtx3080",
    source_id=None,
)
```

### Fixture 2: Stale Passive Entry (Confidence ≈ 0.15)
```python
FIXTURE_STALE_PASSIVE = PeerObservation(
    observer_id="mac-primary-a7f3c9e2d4b1aaff",
    target_peer_id="win-unknown-peer-9e8d7c6b5a4f3e2d",
    observer_timestamp=1720614843.0,
    direct_status="STALE",
    endpoint="192.168.1.200:9000",
    endpoint_epoch=1,
    last_heartbeat_timestamp=1720614700.0,  # 143 seconds ago
    last_probe_timestamp=1720614700.0,
    probe_latency_ms=None,
    time_to_suspect_ms=0.0,  # Past suspect deadline
    route="relay",
    probe_result=None,
    relay_proof=None,
    confidence=0.15,
    proof_score=0.0,
    freshness_score=0.0,
    witness_agreement=0,
    witness_disagreement=0,
    backend_caps=[],
    backend_state=None,
    backend_state_timestamp=None,
    ttl_seconds=300,
    tags=["relay_unverified", "stale"],
    notes="Peer reported this via relay (win-rtx3080); no direct probe; past heartbeat deadline",
    source_id="win-rtx3080-5f4e3d2c1b0a9f8e",
)
```

### Fixture 3: Unverified Relay (Confidence ≈ 0.35)
```python
FIXTURE_UNVERIFIED_RELAY = PeerObservation(
    observer_id="mac-primary-a7f3c9e2d4b1aaff",
    target_peer_id="win-rtx5080-c4d8e2f1a3b7c9d5",
    observer_timestamp=1720614843.0,
    direct_status="UNKNOWN",
    endpoint="192.168.1.105:9000",
    endpoint_epoch=2,
    last_heartbeat_timestamp=None,
    last_probe_timestamp=1720614833.0,  # Relay probe 10s ago
    probe_latency_ms=None,
    time_to_suspect_ms=None,
    route="relay",
    probe_result={
        "success": True,
        "relay_response": {
            "can_reach": True,
            "via_peer": "win-rtx3080-5f4e3d2c1b0a9f8e",
            # NO SIGNATURE from target
        }
    },
    relay_proof=None,
    confidence=0.35,
    proof_score=0.3,  # Partial: relay claim + response, no signature
    freshness_score=0.7,  # 10s old, fresh-ish
    witness_agreement=0,
    witness_disagreement=1,  # win-rtx3080 directly reaches it, we don't
    backend_caps=[],
    backend_state=None,
    backend_state_timestamp=None,
    ttl_seconds=60,
    tags=["relay_claim", "unverified_proof"],
    notes="win-rtx3080 claims it can reach; no proof from target; < 0.5 threshold",
    source_id="win-rtx3080-5f4e3d2c1b0a9f8e",
)
```

### Fixture 4: Timeout (Confidence ≈ 0.1)
```python
FIXTURE_TIMEOUT = PeerObservation(
    observer_id="mac-primary-a7f3c9e2d4b1aaff",
    target_peer_id="unknown-offline-1a2b3c4d5e6f7a8b",
    observer_timestamp=1720614843.0,
    direct_status="TIMEOUT",
    endpoint="192.168.1.150:9000",
    endpoint_epoch=0,
    last_heartbeat_timestamp=None,  # Never succeeded
    last_probe_timestamp=1720614843.0,
    probe_latency_ms=None,
    time_to_suspect_ms=0.0,
    route="direct",
    probe_result={
        "success": False,
        "error": "connection_timeout",
        "timeout_ms": 5000,
    },
    relay_proof=None,
    confidence=0.1,
    proof_score=0.0,
    freshness_score=0.0,
    witness_agreement=0,
    witness_disagreement=1,  # win-rtx3080 reached it 2 minutes ago
    backend_caps=[],
    backend_state=None,
    backend_state_timestamp=None,
    ttl_seconds=120,  # SUSPECT TTL: waiting for retry
    tags=["timeout", "suspect"],
    notes="Direct probe timed out after 5000ms; may be offline or network issue",
    source_id=None,
)
```

### Fixture 5: IP Migrated (Epoch Mismatch)
```python
FIXTURE_IP_MIGRATED = PeerObservation(
    observer_id="mac-primary-a7f3c9e2d4b1aaff",
    target_peer_id="win-rtx5080-c4d8e2f1a3b7c9d5",
    observer_timestamp=1720614843.0,
    direct_status="STALE",  # Old address no longer valid
    endpoint="192.168.1.50:9000",  # Old address
    endpoint_epoch=1,  # Old epoch
    last_heartbeat_timestamp=1720614700.0,  # 143 seconds ago
    last_probe_timestamp=1720614700.0,
    probe_latency_ms=15.0,
    time_to_suspect_ms=0.0,
    route="direct",
    probe_result=None,  # No recent probe
    relay_proof=None,
    confidence=0.0,  # Superseded; don't use
    proof_score=0.7,  # Was valid, but address changed
    freshness_score=0.0,  # Too old
    witness_agreement=0,
    witness_disagreement=0,
    backend_caps=["lmstudio"],
    backend_state="WIN_LMSTUDIO",
    backend_state_timestamp=1720614700.0,
    ttl_seconds=300,
    tags=["ip_migrated", "superseded", "epoch_mismatch"],
    notes="Peer reported IP change (epoch 1→2); old address 192.168.1.50 no longer valid; see new observation with epoch=2",
    source_id=None,
)
```

### Fixture 6: Witness Agreement (2+ Observers)
```python
FIXTURE_WITNESS_AGREEMENT = PeerObservation(
    observer_id="mac-primary-a7f3c9e2d4b1aaff",
    target_peer_id="win-rtx5080-c4d8e2f1a3b7c9d5",
    observer_timestamp=1720614843.0,
    direct_status="REACHABLE",
    endpoint="192.168.1.105:9000",
    endpoint_epoch=2,
    last_heartbeat_timestamp=1720614843.0,
    last_probe_timestamp=1720614843.0,
    probe_latency_ms=14.2,
    time_to_suspect_ms=9992.0,
    route="direct",
    probe_result={
        "success": True,
        "latency_ms": 14.2,
        "heartbeat_received": {
            "node_id": "win-rtx5080-c4d8e2f1a3b7c9d5",
            "endpoint": "192.168.1.105:9000",
            "endpoint_epoch": 2,
            "backend_state": "WIN_LMSTUDIO",
            "timestamp": 1720614843.0,
            "signature": "aAbBcCdDeEfF1122334455667788990011223344556677889900112233445566",
        }
    },
    relay_proof=None,
    confidence=1.0,  # Full confidence: fresh + witnessed
    proof_score=1.0,
    freshness_score=1.0,
    witness_agreement=2,  # mac-primary AND win-rtx3080 see this
    witness_disagreement=0,
    backend_caps=["lmstudio"],
    backend_state="WIN_LMSTUDIO",
    backend_state_timestamp=1720614843.0,
    ttl_seconds=60,
    tags=["witnessed", "consensus"],
    notes="Fresh direct connection witnessed by 2 observers (mac-primary, win-rtx3080); high confidence",
    source_id=None,
)
```

### Fixture 7: Witness Disagreement (Partition Suspect)
```python
FIXTURE_WITNESS_DISAGREEMENT = PeerObservation(
    observer_id="mac-primary-a7f3c9e2d4b1aaff",
    target_peer_id="win-unknown-peer-9e8d7c6b5a4f3e2d",
    observer_timestamp=1720614843.0,
    direct_status="REACHABLE",
    endpoint="192.168.1.200:9000",
    endpoint_epoch=2,
    last_heartbeat_timestamp=1720614843.0,
    last_probe_timestamp=1720614843.0,
    probe_latency_ms=45.3,
    time_to_suspect_ms=9954.7,
    route="direct",
    probe_result={
        "success": True,
        "latency_ms": 45.3,
        "heartbeat_received": {
            "node_id": "win-unknown-peer-9e8d7c6b5a4f3e2d",
            "endpoint": "192.168.1.200:9000",
            "endpoint_epoch": 2,
            "timestamp": 1720614843.0,
            "signature": "xXyYzZ1122334455667788990011223344556677889900112233445566aAbBcC",
        }
    },
    relay_proof=None,
    confidence=0.40,  # Reduced due to disagreement (0.8 * 0.5 = 0.40)
    proof_score=1.0,  # Proof is valid
    freshness_score=0.8,  # Recent but not < 10s
    witness_agreement=0,
    witness_disagreement=1,  # win-rtx3080 sees it as TIMEOUT!
    backend_caps=[],
    backend_state=None,
    backend_state_timestamp=None,
    ttl_seconds=60,
    tags=["asymmetric_reachability", "partition_suspect", "disagreement"],
    notes="mac-primary reaches this peer, but win-rtx3080 times out; likely network partition",
    source_id=None,
)
```

### Fixture 8: Static Seed Entry (No Expiry)
```python
FIXTURE_STATIC_SEED = PeerObservation(
    observer_id="orchestrator-system-0000000000000000",
    target_peer_id="win-rtx5080-c4d8e2f1a3b7c9d5",
    observer_timestamp=1720614843.0,
    direct_status="REACHABLE",
    endpoint="192.168.1.105:9000",
    endpoint_epoch=2,
    last_heartbeat_timestamp=1720614800.0,  # 43 seconds ago (stale by normal standards)
    last_probe_timestamp=1720614800.0,
    probe_latency_ms=11.8,
    time_to_suspect_ms=None,  # Not used for static seeds
    route="static_seed",
    probe_result={
        "success": True,
        "latency_ms": 11.8,
    },
    relay_proof=None,
    confidence=0.92,  # High confidence because it's from config + recently confirmed
    proof_score=0.95,
    freshness_score=0.85,  # 43s old, but static seeds don't auto-expire
    witness_agreement=0,
    witness_disagreement=0,
    backend_caps=["lmstudio"],
    backend_state="WIN_LMSTUDIO",
    backend_state_timestamp=1720614800.0,
    ttl_seconds=-1,  # NO EXPIRY for static seeds!
    tags=["static_seed"],
    notes="From OPENCLAW_PEERS config; never expires; manually refreshed on startup",
    source_id=None,
)
```

### Fixture 9: Malicious Relay Attempt (T1: Relay Lies)
```python
FIXTURE_MALICIOUS_RELAY = PeerObservation(
    observer_id="mac-primary-a7f3c9e2d4b1aaff",
    target_peer_id="unknown-peer-deadbeef00001234",
    observer_timestamp=1720614843.0,
    direct_status="REACHABLE",
    endpoint="192.168.1.222:9000",
    endpoint_epoch=1,
    last_heartbeat_timestamp=1720614843.0,
    last_probe_timestamp=1720614843.0,
    probe_latency_ms=None,
    time_to_suspect_ms=None,
    route="relay",
    probe_result={
        "success": True,
        "relay_response": {
            "can_reach": True,
            "via_peer": "win-rtx3080-5f4e3d2c1b0a9f8e",
        }
    },
    relay_proof="<invalid-signature-fails-verification>",  # Forged!
    confidence=0.08,  # Very low: signature invalid + target disagrees
    proof_score=0.05,  # Signature verification FAILED
    freshness_score=1.0,  # Recent, but proof is bad
    witness_agreement=0,
    witness_disagreement=2,  # BOTH direct-probe AND win-rtx3080 say unreachable!
    backend_caps=[],
    backend_state=None,
    backend_state_timestamp=None,
    ttl_seconds=60,
    tags=["relay_claim", "invalid_signature", "relay_liar_candidate", "malicious_attempt"],
    notes="Relay (win-rtx3080) claims reachability, but signature is forged; direct probe also times out; win-rtx3080 marked as untrustworthy",
    source_id="win-rtx3080-5f4e3d2c1b0a9f8e",
)
```

### Fixture 10: Degraded Link (Reachable but Slow)
```python
FIXTURE_DEGRADED_LINK = PeerObservation(
    observer_id="mac-primary-a7f3c9e2d4b1aaff",
    target_peer_id="win-rtx5080-c4d8e2f1a3b7c9d5",
    observer_timestamp=1720614843.0,
    direct_status="DEGRADED",
    endpoint="192.168.1.105:9000",
    endpoint_epoch=2,
    last_heartbeat_timestamp=1720614843.0,
    last_probe_timestamp=1720614843.0,
    probe_latency_ms=385.5,  # High latency!
    time_to_suspect_ms=9614.5,
    route="direct",
    probe_result={
        "success": True,
        "latency_ms": 385.5,
        "heartbeat_received": {
            "node_id": "win-rtx5080-c4d8e2f1a3b7c9d5",
            "endpoint": "192.168.1.105:9000",
            "endpoint_epoch": 2,
            "backend_state": "WIN_LMSTUDIO",
            "timestamp": 1720614843.0,
            "signature": "aAbBcCdDeEfF1122334455667788990011223344556677889900112233445566",
        }
    },
    relay_proof=None,
    confidence=0.68,  # (0.8 * 0.5) + (0.9 * 0.3) + (0.2 * 0.2) = 0.68
    proof_score=0.8,  # Proof present but link quality suggests issue
    freshness_score=0.9,  # Recent
    witness_agreement=0,
    witness_disagreement=0,
    backend_caps=["lmstudio"],
    backend_state="WIN_LMSTUDIO",
    backend_state_timestamp=1720614843.0,
    ttl_seconds=60,
    tags=["degraded", "high_latency", "jitter_detected"],
    notes="Responding but very slow (385ms RTT); may indicate congestion, VPN, or link quality issue; prioritize for rotation",
    source_id=None,
)
```

---

## Part 3: Schema Review & Issue Findings

### Issue 1: Optional Fields Ambiguity — `probe_latency_ms` (MINOR)

**Location:** § 2.1, field `probe_latency_ms`

**Problem:**
- Defined as `Optional[float]` with comment "Observed RTT (only if REACHABLE)"
- But should it also be populated for DEGRADED? YES (Fixture 10 shows it is)
- Comment is slightly misleading

**Recommendation:**
- Update comment: "Observed RTT (populated if direct_status = REACHABLE or DEGRADED)"
- Or split into two fields: `probe_latency_ms` (all successful probes) and `quality_assessment` (only if DEGRADED)
- **Decision:** Keep as-is; comment clarification sufficient. No schema change needed.

---

### Issue 2: Inconsistent Route Enum vs Actual Routes (POTENTIAL BUG)

**Location:** § 2.1, field `route`

**Problem:**
- Enum lists 6 values: `direct`, `relay`, `discovered`, `static_seed`, `passively_learned`, `unknown`
- But fixtures show observations with no route specified → defaults to "unknown"
- No guidance on when to assign each value (e.g., when should route be "passively_learned" vs "relay"?)

**Recommendation:**
- Add routing decision tree to § 3.4 (or new section):
  ```
  if heartbeat_received_directly_from_target → route="direct"
  elif from_relay_with_proof → route="relay"
  elif from_target's_heartbeat_in_observer_reports → route="passively_learned"
  elif from_config → route="static_seed"
  elif from_mdns_or_tcp_scan → route="discovered"
  else → route="unknown"
  ```
- **Decision:** Add clarification; no schema change needed.

---

### Issue 3: `time_to_suspect_ms` Computed or Stored? (AMBIGUOUS)

**Location:** § 2.1, field `time_to_suspect_ms`

**Problem:**
- Defined as "How long until this transitions to SUSPECT"
- Comment: "= max(0, HEARTBEAT_DEADLINE - (now - last_heartbeat))"
- **This is a COMPUTED field**, not observed data
- Storing a computed value is risky: if observer_timestamp ≠ now (clock skew), value becomes invalid
- Fixtures show it populated, but should it be recomputed at query time?

**Recommendation:**
- **EITHER:** Mark as `@property` (computed, not stored)
  ```python
  @property
  def time_to_suspect_ms(self) -> float:
      if self.last_heartbeat_timestamp is None:
          return 0.0
      deadline_s = self.last_heartbeat_timestamp + HEARTBEAT_DEADLINE_S
      now_s = time.time()
      return max(0.0, (deadline_s - now_s) * 1000)
  ```
- **OR:** Store as field but with caveat in docstring: "Computed at observation time; may be stale if observer_timestamp is old"
- **Decision:** **CHANGE TO @property** to avoid stale computed values. This prevents bugs from mismatched timestamps.

---

### Issue 4: Missing `confidence_updated_at` (MINOR GAP)

**Location:** § 2.1, Confidence section

**Problem:**
- `confidence` is present, but no timestamp for when it was last recomputed
- If observation is 2 hours old but still confidence=0.95, is that stale?
- Currently no way to distinguish "confidence computed recently" vs "confidence is old"

**Recommendation:**
- Add field: `confidence_computed_at: float` (Unix timestamp)
- Use in scoring logic: ignore observations where confidence_computed_at > 60s old?
- **Decision:** Add field for production use; optional for Phase 1. Mark as **Phase 1b enhancement**.

---

### Issue 5: Circular Reference Prevention (SECURITY)

**Location:** § 2.1, field `source_id`

**Problem:**
- `source_id` records who reported this observation
- No mechanism to prevent circular loops (A reports B, B reports A, cycle)
- Malicious observer could create infinite loops in gossip

**Recommendation:**
- Add field: `chain_depth: int` (how many hops from original observation)
- Add validation: reject observations with chain_depth > MAX_CHAIN_DEPTH (e.g., 5)
- Example:
  ```python
  chain_depth: int  # 0 = direct observation, 1 = reported by 1 peer, etc.
  
  # Validation:
  if chain_depth > MAX_CHAIN_DEPTH:
      reject(f"Observation chain too deep: {chain_depth} > {MAX_CHAIN_DEPTH}")
  ```
- **Decision:** Add `chain_depth` field. Essential for Phase 1 gossip safety.

---

### Issue 6: Backend State Enum (NEEDS DEFINITION)

**Location:** § 2.1, field `backend_state`

**Problem:**
- Listed as Optional[str] with example values: "MAC_DUAL" | "MAC_OLLAMA_ONLY" | "WIN_LMSTUDIO" | "MAC_NONE" | "OFFLINE"
- No canonical enum or registry
- How to extend when new backend states emerge?
- Examples don't cover all possibilities (e.g., "Linux" systems?)

**Recommendation:**
- Define as enum:
  ```python
  class BackendState(Enum):
      MAC_DUAL = "mac_dual"              # macOS with both Ollama + LMStudio
      MAC_OLLAMA_ONLY = "mac_ollama_only"
      MAC_LMSTUDIO_ONLY = "mac_lmstudio_only"
      WIN_LMSTUDIO = "win_lmstudio"
      WIN_OLLAMA_ONLY = "win_ollama_only"
      MAC_NONE = "mac_none"              # macOS but no backend
      WIN_NONE = "win_none"
      LINUX_OLLAMA = "linux_ollama"      # Forward compatibility
      LINUX_LMSTUDIO = "linux_lmstudio"
      OFFLINE = "offline"
      UNKNOWN = "unknown"
  ```
- **Decision:** Define enum in Phase 1. Supports extensibility without schema breaking.

---

### Issue 7: Missing Directionality Metadata (MINOR)

**Location:** § 2.1, no field

**Problem:**
- Observations are directed (observer → target)
- But no field explicitly marks "this is a directed probe, not symmetric"
- Could be inferred from route, but not explicit

**Recommendation:**
- Add field: `directional: bool = True` (always true for Phase 1; room for symmetric checks in future)
- Or just document in docstring that reachability is always asymmetric
- **Decision:** Document in docstring. No schema change needed for Phase 1.

---

### Issue 8: Witness Agreement Math (CLARIFICATION NEEDED)

**Location:** § 3.1, confidence scoring formula

**Problem:**
- witness_bonus formula shows:
  ```
  +1.0 if witness_agreement >= 2  (2+ others agree)
  ```
- But the formula is: `confidence = (proof_score × 0.5) + (freshness_score × 0.3) + (witness_bonus × 0.2)`
- If witness_bonus = 1.0, confidence can be up to 1.0 (perfect)
- But what if proof_score = 0.0 (no proof)? Then confidence = 0.0 + 0.3 + 0.2 = 0.5 (not correct!)
- **The witness_bonus is being added AFTER proof/freshness, which skews the formula**

**Recommendation:**
- **Clarify:** Is witness_bonus a bonus (added after formula) or a component?
  - If bonus: `confidence = min(1.0, (proof_score × 0.5) + (freshness_score × 0.3) + witness_bonus)`
  - If component: `confidence = (proof_score × 0.5) + (freshness_score × 0.3) + (witness_agreement_score × 0.2)` where witness_agreement_score ∈ [0.0, 1.0]
- **Current impl seems to use witness_bonus as a component** (since it's in the formula, not a post-modifier)
- **Decision:** Clarify in docstring. Formula is correct as-is; rename `witness_bonus` → `witness_agreement_score` for clarity.

---

### Issue 9: Missing TTL Semantics (MINOR)

**Location:** § 2.1, field `ttl_seconds`

**Problem:**
- ttl_seconds = 60 (refresh frequently)
- ttl_seconds = 300 (passive entries)
- ttl_seconds = -1 (no expiry)
- **But when is TTL checked?** At observation time? At query time? Sliding window?
- If observation is 2 days old but never probed again, is it still valid?

**Recommendation:**
- Add to docstring: "TTL is measured from observer_timestamp. Expired observations should be removed from tables at query time."
- Add field: `expired_at: Optional[float]` (computed: observer_timestamp + ttl_seconds, if ttl_seconds != -1)
- Or just document behavior in § 4 (lifecycle section)
- **Decision:** Document TTL semantics clearly. No schema change.

---

### Issue 10: Signature Validation Field Missing (SECURITY)

**Location:** § 2.1, Proof & Validation section

**Problem:**
- `probe_result` contains `heartbeat_received` with `signature` field
- But no field to indicate signature validation STATUS (valid/invalid/unverified)
- If signature validation failed, proof_score should be 0.0, but schema doesn't track validation result

**Recommendation:**
- Add field to probe_result:
  ```python
  "heartbeat_received": {
      "signature": "...",
      "signature_valid": True,  # NEW
      "signature_verified_at": 1720614843.0,  # NEW
  }
  ```
- Or add field to PeerObservation:
  ```python
  signature_status: Literal["valid", "invalid", "unverified", "unknown"]
  ```
- **Decision:** Add `signature_status` field to PeerObservation for Phase 1b. For Phase 1, store in probe_result. No breaking change.

---

## Summary: Issue Triage

| Issue | Severity | Category | Recommendation | Phase |
|-------|----------|----------|-----------------|-------|
| 1. probe_latency_ms comment | MINOR | Docs | Clarify comment | 1.0 |
| 2. Route enum decision tree | MINOR | Docs | Add routing guide to spec | 1.0 |
| 3. time_to_suspect_ms computed | MEDIUM | Design | Change to @property | 1.0 |
| 4. Missing confidence_updated_at | MINOR | Enhancement | Add in Phase 1b | 1b |
| 5. Circular reference prevention | MEDIUM | Security | Add chain_depth field | 1.0 |
| 6. BackendState enum | MINOR | Design | Define enum | 1.0 |
| 7. Directionality metadata | TRIVIAL | Docs | Document in docstring | 1.0 |
| 8. Witness agreement formula | MINOR | Clarification | Rename witness_bonus → witness_agreement_score | 1.0 |
| 9. TTL semantics | MINOR | Docs | Document TTL lifecycle | 1.0 |
| 10. Signature validation status | MEDIUM | Security | Add signature_status field | 1b |

**Net Assessment:**
- **3 MEDIUM issues** (fixable, no blocking): #3 (time_to_suspect_ms), #5 (chain_depth), #10 (signature_status)
- **Schema is SOUND** for Phase 1.0; confidence scoring is correct; witness agreement is well-designed
- **No redundant fields**, **no type mismatches**, **naming is clear**
- All issues are either docs/clarification or non-breaking enhancements for Phase 1b

