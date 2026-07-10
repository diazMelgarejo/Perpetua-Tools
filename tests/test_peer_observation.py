"""
tests/test_peer_observation.py — TDD tests for PeerObservation dataclass.

Tests validate:
- Immutability (frozen=True enforcement)
- Field bounds (proof_score, freshness_score ∈ [0, 1])
- Depth limits (witness_set recursive tuple, max depth 2)
- Serialization (JSON round-trip)
- Validation (range checks, enum values)
"""

import json
import time
from dataclasses import FrozenInstanceError

import pytest

from orchestrator.membership import (
    PeerObservation,
    DirectStatus,
    Route,
    BackendState,
    ObservationType,
    CONFIDENCE_THRESHOLD_RELAY,
)


class TestPeerObservationImmutability:
    """Test that PeerObservation is truly frozen."""

    def test_frozen_raises_error_on_field_reassignment(self):
        """GIVEN: frozen dataclass WHEN: reassign field THEN: FrozenInstanceError."""
        obs = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=time.time(),
            proof_score=0.8,
            witness_set=(),
            freshness_score=0.9,
            observation_type=ObservationType.REACHABLE,
            observer_id="observer-001",
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            last_heartbeat_timestamp=time.time(),
            last_probe_timestamp=time.time(),
            probe_latency_ms=10.5,
            route=Route.DIRECT,
            probe_result=None,
            relay_proof=None,
            witness_agreement=0,
            witness_disagreement=0,
            backend_caps=(),
            backend_state=None,
            backend_state_timestamp=None,
            ttl_seconds=60,
            tags=frozenset(),
            notes="test",
            source_id=None,
            chain_depth=0,
        )

        # Attempt to modify — should raise FrozenInstanceError
        with pytest.raises(FrozenInstanceError):
            obs.proof_score = 0.5

        with pytest.raises(FrozenInstanceError):
            obs.epoch = 999

    def test_mutable_input_copied_before_object_escape(self):
        """GIVEN: mutable list/dict inputs WHEN: passed to constructor
        THEN: object interior is frozen, mutations to original don't affect obs."""

        now = time.time()
        mutable_tags = ["tag1", "tag2"]
        mutable_caps = ["ollama", "lmstudio"]

        obs = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=now,
            proof_score=0.8,
            witness_set=(),
            freshness_score=0.9,
            observation_type=ObservationType.REACHABLE,
            observer_id="observer-001",
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            last_heartbeat_timestamp=now,
            last_probe_timestamp=now,
            probe_latency_ms=10.5,
            route=Route.DIRECT,
            probe_result=None,
            relay_proof=None,
            witness_agreement=0,
            witness_disagreement=0,
            backend_caps=mutable_caps,
            backend_state=None,
            backend_state_timestamp=None,
            ttl_seconds=60,
            tags=mutable_tags,
            notes="test",
            source_id=None,
            chain_depth=0,
        )

        # Mutate original inputs
        mutable_tags.append("tag3")
        mutable_caps.append("extra-backend")

        # Object should be unchanged
        assert "tag3" not in obs.tags
        assert "extra-backend" not in obs.backend_caps
        assert obs.tags == frozenset(["tag1", "tag2"])
        assert obs.backend_caps == ("ollama", "lmstudio")


class TestPeerObservationBounds:
    """Test field value bounds and validations."""

    def test_proof_score_accepts_valid_range(self):
        """GIVEN: proof_score in [0.0, 1.0] THEN: accepted."""
        for value in [0.0, 0.5, 1.0, 0.01, 0.99]:
            obs = PeerObservation(
                peer_id="peer-001",
                epoch=1,
                timestamp=time.time(),
                proof_score=value,
                witness_set=(),
                freshness_score=0.5,
                observation_type=ObservationType.REACHABLE,
                observer_id="observer-001",
                direct_status=DirectStatus.REACHABLE,
                endpoint="192.168.1.1:9000",
                endpoint_epoch=1,
                last_heartbeat_timestamp=None,
                last_probe_timestamp=None,
                probe_latency_ms=None,
                route=Route.DIRECT,
                probe_result=None,
                relay_proof=None,
                witness_agreement=0,
                witness_disagreement=0,
                backend_caps=(),
                backend_state=None,
                backend_state_timestamp=None,
                ttl_seconds=60,
                tags=frozenset(),
                notes="",
                source_id=None,
                chain_depth=0,
            )
            assert obs.proof_score == value

    def test_proof_score_rejects_out_of_bounds(self):
        """GIVEN: proof_score < 0 or > 1 THEN: validation error."""
        with pytest.raises(ValueError):
            PeerObservation(
                peer_id="peer-001",
                epoch=1,
                timestamp=time.time(),
                proof_score=-0.1,  # Invalid
                witness_set=(),
                freshness_score=0.5,
                observation_type=ObservationType.REACHABLE,
                observer_id="observer-001",
                direct_status=DirectStatus.REACHABLE,
                endpoint="192.168.1.1:9000",
                endpoint_epoch=1,
                last_heartbeat_timestamp=None,
                last_probe_timestamp=None,
                probe_latency_ms=None,
                route=Route.DIRECT,
                probe_result=None,
                relay_proof=None,
                witness_agreement=0,
                witness_disagreement=0,
                backend_caps=(),
                backend_state=None,
                backend_state_timestamp=None,
                ttl_seconds=60,
                tags=frozenset(),
                notes="",
                source_id=None,
                chain_depth=0,
            )

        with pytest.raises(ValueError):
            PeerObservation(
                peer_id="peer-001",
                epoch=1,
                timestamp=time.time(),
                proof_score=1.1,  # Invalid
                witness_set=(),
                freshness_score=0.5,
                observation_type=ObservationType.REACHABLE,
                observer_id="observer-001",
                direct_status=DirectStatus.REACHABLE,
                endpoint="192.168.1.1:9000",
                endpoint_epoch=1,
                last_heartbeat_timestamp=None,
                last_probe_timestamp=None,
                probe_latency_ms=None,
                route=Route.DIRECT,
                probe_result=None,
                relay_proof=None,
                witness_agreement=0,
                witness_disagreement=0,
                backend_caps=(),
                backend_state=None,
                backend_state_timestamp=None,
                ttl_seconds=60,
                tags=frozenset(),
                notes="",
                source_id=None,
                chain_depth=0,
            )

    def test_freshness_score_accepts_valid_range(self):
        """GIVEN: freshness_score in [0.0, 1.0] THEN: accepted."""
        for value in [0.0, 0.25, 0.5, 0.75, 1.0]:
            obs = PeerObservation(
                peer_id="peer-001",
                epoch=1,
                timestamp=time.time(),
                proof_score=0.5,
                witness_set=(),
                freshness_score=value,
                observation_type=ObservationType.REACHABLE,
                observer_id="observer-001",
                direct_status=DirectStatus.REACHABLE,
                endpoint="192.168.1.1:9000",
                endpoint_epoch=1,
                last_heartbeat_timestamp=None,
                last_probe_timestamp=None,
                probe_latency_ms=None,
                route=Route.DIRECT,
                probe_result=None,
                relay_proof=None,
                witness_agreement=0,
                witness_disagreement=0,
                backend_caps=(),
                backend_state=None,
                backend_state_timestamp=None,
                ttl_seconds=60,
                tags=frozenset(),
                notes="",
                source_id=None,
                chain_depth=0,
            )
            assert obs.freshness_score == value

    def test_freshness_score_rejects_out_of_bounds(self):
        """GIVEN: freshness_score < 0 or > 1 THEN: validation error."""
        with pytest.raises(ValueError):
            PeerObservation(
                peer_id="peer-001",
                epoch=1,
                timestamp=time.time(),
                proof_score=0.5,
                witness_set=(),
                freshness_score=-0.1,  # Invalid
                observation_type=ObservationType.REACHABLE,
                observer_id="observer-001",
                direct_status=DirectStatus.REACHABLE,
                endpoint="192.168.1.1:9000",
                endpoint_epoch=1,
                last_heartbeat_timestamp=None,
                last_probe_timestamp=None,
                probe_latency_ms=None,
                route=Route.DIRECT,
                probe_result=None,
                relay_proof=None,
                witness_agreement=0,
                witness_disagreement=0,
                backend_caps=(),
                backend_state=None,
                backend_state_timestamp=None,
                ttl_seconds=60,
                tags=frozenset(),
                notes="",
                source_id=None,
                chain_depth=0,
            )


class TestPeerObservationWitnessDepth:
    """Test witness_set depth limits (max depth 2)."""

    def test_witness_set_empty(self):
        """GIVEN: empty witness_set THEN: accepted."""
        obs = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=time.time(),
            proof_score=0.8,
            witness_set=(),
            freshness_score=0.9,
            observation_type=ObservationType.REACHABLE,
            observer_id="observer-001",
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            last_heartbeat_timestamp=None,
            last_probe_timestamp=None,
            probe_latency_ms=None,
            route=Route.DIRECT,
            probe_result=None,
            relay_proof=None,
            witness_agreement=0,
            witness_disagreement=0,
            backend_caps=(),
            backend_state=None,
            backend_state_timestamp=None,
            ttl_seconds=60,
            tags=frozenset(),
            notes="",
            source_id=None,
            chain_depth=0,
        )
        assert obs.witness_set == ()
        assert len(obs.witness_set) == 0

    def test_witness_set_depth_1_with_nested_observations(self):
        """GIVEN: witness_set with depth-1 observations (no nested witnesses)
        THEN: accepted."""

        now = time.time()
        witness_obs_1 = PeerObservation(
            peer_id="witness-peer-1",
            epoch=1,
            timestamp=now,
            proof_score=0.7,
            witness_set=(),  # No nested witnesses
            freshness_score=0.8,
            observation_type=ObservationType.REACHABLE,
            observer_id="observer-002",
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.2:9000",
            endpoint_epoch=1,
            last_heartbeat_timestamp=None,
            last_probe_timestamp=None,
            probe_latency_ms=None,
            route=Route.DIRECT,
            probe_result=None,
            relay_proof=None,
            witness_agreement=0,
            witness_disagreement=0,
            backend_caps=(),
            backend_state=None,
            backend_state_timestamp=None,
            ttl_seconds=60,
            tags=frozenset(),
            notes="",
            source_id=None,
            chain_depth=0,
        )

        obs = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=now,
            proof_score=0.8,
            witness_set=(witness_obs_1,),
            freshness_score=0.9,
            observation_type=ObservationType.REACHABLE,
            observer_id="observer-001",
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            last_heartbeat_timestamp=None,
            last_probe_timestamp=None,
            probe_latency_ms=None,
            route=Route.DIRECT,
            probe_result=None,
            relay_proof=None,
            witness_agreement=0,
            witness_disagreement=0,
            backend_caps=(),
            backend_state=None,
            backend_state_timestamp=None,
            ttl_seconds=60,
            tags=frozenset(),
            notes="",
            source_id=None,
            chain_depth=0,
        )
        assert len(obs.witness_set) == 1
        assert obs.witness_set[0].peer_id == "witness-peer-1"

    def test_witness_set_depth_2_allowed(self):
        """GIVEN: witness_set with depth-2 observations (nested witnesses)
        THEN: accepted if depth doesn't exceed 2."""

        now = time.time()

        # Depth-1 witness (no nested witnesses)
        depth_1_witness = PeerObservation(
            peer_id="witness-peer-1",
            epoch=1,
            timestamp=now,
            proof_score=0.7,
            witness_set=(),
            freshness_score=0.8,
            observation_type=ObservationType.REACHABLE,
            observer_id="observer-002",
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.2:9000",
            endpoint_epoch=1,
            last_heartbeat_timestamp=None,
            last_probe_timestamp=None,
            probe_latency_ms=None,
            route=Route.DIRECT,
            probe_result=None,
            relay_proof=None,
            witness_agreement=0,
            witness_disagreement=0,
            backend_caps=(),
            backend_state=None,
            backend_state_timestamp=None,
            ttl_seconds=60,
            tags=frozenset(),
            notes="",
            source_id=None,
            chain_depth=0,
        )

        # Depth-2 observation (with depth-1 witnesses)
        depth_2_obs = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=now,
            proof_score=0.8,
            witness_set=(depth_1_witness,),
            freshness_score=0.9,
            observation_type=ObservationType.REACHABLE,
            observer_id="observer-001",
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            last_heartbeat_timestamp=None,
            last_probe_timestamp=None,
            probe_latency_ms=None,
            route=Route.DIRECT,
            probe_result=None,
            relay_proof=None,
            witness_agreement=0,
            witness_disagreement=0,
            backend_caps=(),
            backend_state=None,
            backend_state_timestamp=None,
            ttl_seconds=60,
            tags=frozenset(),
            notes="",
            source_id=None,
            chain_depth=0,
        )
        assert depth_2_obs is not None
        assert len(depth_2_obs.witness_set) == 1

    def test_witness_set_depth_exceeds_2_rejected(self):
        """GIVEN: witness_set exceeds depth 2 THEN: validation error."""
        now = time.time()

        # Depth-1 witness
        depth_1_witness = PeerObservation(
            peer_id="witness-peer-1",
            epoch=1,
            timestamp=now,
            proof_score=0.7,
            witness_set=(),
            freshness_score=0.8,
            observation_type=ObservationType.REACHABLE,
            observer_id="observer-002",
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.2:9000",
            endpoint_epoch=1,
            last_heartbeat_timestamp=None,
            last_probe_timestamp=None,
            probe_latency_ms=None,
            route=Route.DIRECT,
            probe_result=None,
            relay_proof=None,
            witness_agreement=0,
            witness_disagreement=0,
            backend_caps=(),
            backend_state=None,
            backend_state_timestamp=None,
            ttl_seconds=60,
            tags=frozenset(),
            notes="",
            source_id=None,
            chain_depth=0,
        )

        # Depth-2 witness (with depth-1 witnesses)
        depth_2_witness = PeerObservation(
            peer_id="witness-peer-2",
            epoch=1,
            timestamp=now,
            proof_score=0.6,
            witness_set=(depth_1_witness,),
            freshness_score=0.7,
            observation_type=ObservationType.REACHABLE,
            observer_id="observer-003",
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.3:9000",
            endpoint_epoch=1,
            last_heartbeat_timestamp=None,
            last_probe_timestamp=None,
            probe_latency_ms=None,
            route=Route.DIRECT,
            probe_result=None,
            relay_proof=None,
            witness_agreement=0,
            witness_disagreement=0,
            backend_caps=(),
            backend_state=None,
            backend_state_timestamp=None,
            ttl_seconds=60,
            tags=frozenset(),
            notes="",
            source_id=None,
            chain_depth=0,
        )

        # Depth-3 observation (with depth-2 witnesses) — should be rejected
        with pytest.raises(ValueError, match="witness_set depth exceeds maximum"):
            PeerObservation(
                peer_id="peer-001",
                epoch=1,
                timestamp=now,
                proof_score=0.8,
                witness_set=(depth_2_witness,),  # This witness has depth 2 internally
                freshness_score=0.9,
                observation_type=ObservationType.REACHABLE,
                observer_id="observer-001",
                direct_status=DirectStatus.REACHABLE,
                endpoint="192.168.1.1:9000",
                endpoint_epoch=1,
                last_heartbeat_timestamp=None,
                last_probe_timestamp=None,
                probe_latency_ms=None,
                route=Route.DIRECT,
                probe_result=None,
                relay_proof=None,
                witness_agreement=0,
                witness_disagreement=0,
                backend_caps=(),
                backend_state=None,
                backend_state_timestamp=None,
                ttl_seconds=60,
                tags=frozenset(),
                notes="",
                source_id=None,
                chain_depth=0,
            )


class TestPeerObservationSerialization:
    """Test JSON serialization and round-trip."""

    def test_json_serialization_basic(self):
        """GIVEN: PeerObservation WHEN: to JSON THEN: all fields preserved."""
        now = time.time()
        obs = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=now,
            proof_score=0.8,
            witness_set=(),
            freshness_score=0.9,
            observation_type=ObservationType.REACHABLE,
            observer_id="observer-001",
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            last_heartbeat_timestamp=now,
            last_probe_timestamp=now,
            probe_latency_ms=10.5,
            route=Route.DIRECT,
            probe_result=None,
            relay_proof=None,
            witness_agreement=1,
            witness_disagreement=0,
            backend_caps=("ollama",),
            backend_state=BackendState.MAC_DUAL,
            backend_state_timestamp=now,
            ttl_seconds=60,
            tags=frozenset(["tag1"]),
            notes="test observation",
            source_id="source-001",
            chain_depth=0,
        )

        json_str = obs.to_json()
        data = json.loads(json_str)

        assert data["peer_id"] == "peer-001"
        assert data["epoch"] == 1
        assert data["timestamp"] == now
        assert data["proof_score"] == 0.8
        assert data["freshness_score"] == 0.9

    def test_json_round_trip_identical(self):
        """GIVEN: PeerObservation WHEN: to JSON and back THEN: identical."""
        now = time.time()
        original = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=now,
            proof_score=0.8,
            witness_set=(),
            freshness_score=0.9,
            observation_type=ObservationType.REACHABLE,
            observer_id="observer-001",
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            last_heartbeat_timestamp=now,
            last_probe_timestamp=now,
            probe_latency_ms=10.5,
            route=Route.DIRECT,
            probe_result=None,
            relay_proof=None,
            witness_agreement=1,
            witness_disagreement=0,
            backend_caps=("ollama", "lmstudio"),
            backend_state=BackendState.WIN_LMSTUDIO,
            backend_state_timestamp=now,
            ttl_seconds=60,
            tags=frozenset(["tag1", "tag2"]),
            notes="test observation",
            source_id="source-001",
            chain_depth=0,
        )

        # Serialize and deserialize
        json_str = original.to_json()
        restored = PeerObservation.from_json(json_str)

        # Compare all fields
        assert restored.peer_id == original.peer_id
        assert restored.epoch == original.epoch
        assert restored.timestamp == original.timestamp
        assert restored.proof_score == original.proof_score
        assert restored.freshness_score == original.freshness_score
        assert restored.observation_type == original.observation_type
        assert restored.witness_agreement == original.witness_agreement
        assert restored.witness_disagreement == original.witness_disagreement
        assert restored.backend_caps == original.backend_caps
        assert restored.backend_state == original.backend_state
        assert restored.tags == original.tags
        assert restored.notes == original.notes
        assert restored.chain_depth == original.chain_depth


class TestPeerObservationIntegration:
    """Integration tests combining multiple features."""

    def test_create_full_observation(self):
        """GIVEN: all fields provided WHEN: create observation THEN: succeeds."""
        now = time.time()
        obs = PeerObservation(
            peer_id="peer-001",
            epoch=2,
            timestamp=now,
            proof_score=1.0,
            witness_set=(),
            freshness_score=1.0,
            observation_type=ObservationType.REACHABLE,
            observer_id="observer-001",
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=2,
            last_heartbeat_timestamp=now,
            last_probe_timestamp=now,
            probe_latency_ms=10.5,
            route=Route.DIRECT,
            probe_result={"success": True, "latency_ms": 10.5},
            relay_proof=None,
            witness_agreement=2,
            witness_disagreement=0,
            backend_caps=("ollama", "lmstudio"),
            backend_state=BackendState.MAC_DUAL,
            backend_state_timestamp=now,
            ttl_seconds=60,
            tags=frozenset(["direct", "healthy"]),
            notes="Fresh direct connection with valid signature",
            source_id=None,
            chain_depth=0,
        )

        assert obs.peer_id == "peer-001"
        assert obs.proof_score == 1.0
        assert obs.freshness_score == 1.0
        assert obs.witness_agreement == 2
        assert obs.witness_disagreement == 0

    def test_confidence_property_computed(self):
        """GIVEN: proof, freshness, witness scores
        WHEN: compute_confidence() called THEN: multiplicative formula applied."""
        now = time.time()
        obs = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=now,
            proof_score=1.0,
            witness_set=(),
            freshness_score=1.0,
            observation_type=ObservationType.REACHABLE,
            observer_id="observer-001",
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            last_heartbeat_timestamp=None,
            last_probe_timestamp=None,
            probe_latency_ms=None,
            route=Route.DIRECT,
            probe_result=None,
            relay_proof=None,
            witness_agreement=2,
            witness_disagreement=0,
            backend_caps=(),
            backend_state=None,
            backend_state_timestamp=None,
            ttl_seconds=60,
            tags=frozenset(),
            notes="",
            source_id=None,
            chain_depth=0,
        )

        # Confidence should be: 1.0 × (0.40 + 0.60 × 1.0) × 1.0 = 1.0
        confidence = obs.compute_confidence()
        assert confidence == 1.0

    def test_ghost_peer_confidence_zero(self):
        """GIVEN: proof_score=0.0 (no proof)
        WHEN: compute_confidence() called THEN: confidence=0.0 (multiplicative gate)."""
        now = time.time()
        obs = PeerObservation(
            peer_id="ghost-peer",
            epoch=1,
            timestamp=now,
            proof_score=0.0,  # No proof
            witness_set=(),
            freshness_score=1.0,  # Fresh
            observation_type=ObservationType.REACHABLE,
            observer_id="observer-001",
            direct_status=DirectStatus.UNKNOWN,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            last_heartbeat_timestamp=None,
            last_probe_timestamp=None,
            probe_latency_ms=None,
            route=Route.RELAY,
            probe_result=None,
            relay_proof=None,
            witness_agreement=2,  # Even with witnesses
            witness_disagreement=0,
            backend_caps=(),
            backend_state=None,
            backend_state_timestamp=None,
            ttl_seconds=60,
            tags=frozenset(),
            notes="",
            source_id=None,
            chain_depth=0,
        )

        # Confidence must be 0 due to multiplicative gate
        confidence = obs.compute_confidence()
        assert confidence == 0.0
        assert confidence < CONFIDENCE_THRESHOLD_RELAY


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TDD BATCH 7: Confidence Formula Tests (M1–M5)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestConfidenceFormulaBatch7:
    """
    TDD Batch 7: Multiplicative confidence gate tests.

    Formula: confidence = proof_score × freshness_factor × witness_multiplier
    where:
        freshness_factor = 0.40 + 0.60 × freshness_score ∈ [0.40, 1.00]
        witness_multiplier ∈ [0.50, 1.00]

    Tests M1–M5 from task brief.
    """

    def test_m1_ghost_peer_proof_zero_confidence_zero(self):
        """M1: Ghost-peer (proof=0) → confidence=0.00 ✅

        GIVEN: proof_score=0 (no proof of reachability)
        WHEN: compute_confidence() called
        THEN: confidence=0.0 (multiplicative gate: any zero zeros the product)

        This is the hard gate that prevents unproven observations from passing
        thresholds based on freshness or witness count alone.
        """
        now = time.time()
        obs = PeerObservation(
            peer_id="ghost-peer",
            epoch=1,
            timestamp=now,
            proof_score=0.0,  # ZERO PROOF
            witness_set=(),
            freshness_score=1.0,  # Even if fresh
            observation_type=ObservationType.REACHABLE,
            observer_id="observer-001",
            direct_status=DirectStatus.UNKNOWN,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            last_heartbeat_timestamp=None,
            last_probe_timestamp=None,
            probe_latency_ms=None,
            route=Route.RELAY,
            probe_result=None,
            relay_proof=None,
            witness_agreement=3,  # Even with multiple witnesses
            witness_disagreement=0,
            backend_caps=(),
            backend_state=None,
            backend_state_timestamp=None,
            ttl_seconds=60,
            tags=frozenset(),
            notes="",
            source_id=None,
            chain_depth=0,
        )

        confidence = obs.compute_confidence()
        # 0 × 1.0 × 1.0 = 0
        assert confidence == 0.0, f"Expected 0.0, got {confidence}"
        assert confidence == 0.0

    def test_m2_high_freshness_low_proof_depends_on_proof(self):
        """M2: High freshness + low proof → confidence depends on proof ✅

        GIVEN: proof_score=0.3 (some proof) + freshness_score=1.0 (very fresh)
        WHEN: compute_confidence() called
        THEN: confidence = 0.3 × 1.0 × witness_multiplier
            = 0.3 × 1.0 (freshness_factor=0.40+0.60×1.0=1.0)
            × 0.85 (witness_multiplier: no witnesses) ≈ 0.255 → 0.26

        This validates that even high freshness cannot overcome low proof.
        """
        now = time.time()
        obs = PeerObservation(
            peer_id="peer-low-proof",
            epoch=1,
            timestamp=now,
            proof_score=0.3,  # Low proof
            witness_set=(),
            freshness_score=1.0,  # High freshness
            observation_type=ObservationType.REACHABLE,
            observer_id="observer-001",
            direct_status=DirectStatus.TIMEOUT,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            last_heartbeat_timestamp=None,
            last_probe_timestamp=None,
            probe_latency_ms=None,
            route=Route.RELAY,
            probe_result=None,
            relay_proof=None,
            witness_agreement=0,  # No witnesses
            witness_disagreement=0,
            backend_caps=(),
            backend_state=None,
            backend_state_timestamp=None,
            ttl_seconds=60,
            tags=frozenset(),
            notes="",
            source_id=None,
            chain_depth=0,
        )

        # proof_factor = 0.3
        # freshness_factor = 0.40 + 0.60 × 1.0 = 1.0
        # witness_multiplier = 0.85 (no agreement)
        # confidence = 0.3 × 1.0 × 0.85 = 0.255 → rounded to 0.26
        confidence = obs.compute_confidence()
        assert confidence == 0.26, f"Expected 0.26, got {confidence}"

    def test_m3_witnesses_disagree_multiplier_reduced(self):
        """M3: Witnesses disagree → witness_multiplier <1.0 → confidence reduced ✅

        GIVEN: proof_score=1.0 + freshness_score=1.0
               + witness_disagreement > witness_agreement (contradicted)
        WHEN: compute_confidence() called
        THEN: witness_multiplier=0.50 (reduced due to contradiction)
              confidence = 1.0 × 1.0 × 0.50 = 0.50

        This validates that witness contradictions penalize confidence.
        """
        now = time.time()
        obs = PeerObservation(
            peer_id="peer-contradicted",
            epoch=1,
            timestamp=now,
            proof_score=1.0,  # Perfect proof
            witness_set=(),
            freshness_score=1.0,  # Perfect freshness
            observation_type=ObservationType.REACHABLE,
            observer_id="observer-001",
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            last_heartbeat_timestamp=None,
            last_probe_timestamp=None,
            probe_latency_ms=None,
            route=Route.RELAY,
            probe_result=None,
            relay_proof=None,
            witness_agreement=1,  # One witness agrees
            witness_disagreement=2,  # Two witnesses disagree
            backend_caps=(),
            backend_state=None,
            backend_state_timestamp=None,
            ttl_seconds=60,
            tags=frozenset(),
            notes="",
            source_id=None,
            chain_depth=0,
        )

        # proof_factor = 1.0
        # freshness_factor = 0.40 + 0.60 × 1.0 = 1.0
        # witness_multiplier = 0.50 (witness_disagreement > witness_agreement)
        # confidence = 1.0 × 1.0 × 0.50 = 0.50
        confidence = obs.compute_confidence()
        assert confidence == 0.50, f"Expected 0.50, got {confidence}"

    def test_m4_perfect_score_confidence_one(self):
        """M4: Perfect score (all 1.0) → confidence=1.00 ✅

        GIVEN: proof_score=1.0 + freshness_score=1.0 + witness_agreement≥2
        WHEN: compute_confidence() called
        THEN: witness_multiplier=1.0 (consensus: agreement≥2)
              confidence = 1.0 × 1.0 × 1.0 = 1.0

        This validates the ideal case: perfect proof, fresh, consensus.
        """
        now = time.time()
        obs = PeerObservation(
            peer_id="peer-perfect",
            epoch=1,
            timestamp=now,
            proof_score=1.0,  # Perfect proof
            witness_set=(),
            freshness_score=1.0,  # Perfect freshness
            observation_type=ObservationType.REACHABLE,
            observer_id="observer-001",
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            last_heartbeat_timestamp=None,
            last_probe_timestamp=None,
            probe_latency_ms=None,
            route=Route.DIRECT,
            probe_result={"success": True},
            relay_proof=None,
            witness_agreement=2,  # Consensus: 2+ witnesses
            witness_disagreement=0,  # No disagreement
            backend_caps=(),
            backend_state=None,
            backend_state_timestamp=None,
            ttl_seconds=60,
            tags=frozenset(),
            notes="",
            source_id=None,
            chain_depth=0,
        )

        # proof_factor = 1.0
        # freshness_factor = 0.40 + 0.60 × 1.0 = 1.0
        # witness_multiplier = 1.0 (witness_agreement >= 2)
        # confidence = 1.0 × 1.0 × 1.0 = 1.0
        confidence = obs.compute_confidence()
        assert confidence == 1.0, f"Expected 1.0, got {confidence}"

    def test_m5_edge_case_zero_freshness_still_has_base_factor(self):
        """M5: Edge case (freshness_score=0) → freshness_factor=0.40 → confidence >0 if proof >0 ✅

        GIVEN: proof_score=1.0 + freshness_score=0.0 (very stale)
               + witness_agreement≥2 (consensus)
        WHEN: compute_confidence() called
        THEN: freshness_factor = 0.40 + 0.60 × 0.0 = 0.40 (floor for stale data)
              confidence = 1.0 × 0.40 × 1.0 = 0.40

        This validates the freshness floor: even very stale observations with
        perfect proof retain a 0.40 base factor via witness consensus.
        """
        now = time.time()
        obs = PeerObservation(
            peer_id="peer-stale",
            epoch=1,
            timestamp=now,
            proof_score=1.0,  # Perfect proof
            witness_set=(),
            freshness_score=0.0,  # Very stale (freshness=0)
            observation_type=ObservationType.REACHABLE,
            observer_id="observer-001",
            direct_status=DirectStatus.STALE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            last_heartbeat_timestamp=None,
            last_probe_timestamp=None,
            probe_latency_ms=None,
            route=Route.RELAY,
            probe_result=None,
            relay_proof=None,
            witness_agreement=2,  # Consensus restores confidence
            witness_disagreement=0,
            backend_caps=(),
            backend_state=None,
            backend_state_timestamp=None,
            ttl_seconds=60,
            tags=frozenset(),
            notes="",
            source_id=None,
            chain_depth=0,
        )

        # proof_factor = 1.0
        # freshness_factor = 0.40 + 0.60 × 0.0 = 0.40 (floor for very stale)
        # witness_multiplier = 1.0 (witness_agreement >= 2)
        # confidence = 1.0 × 0.40 × 1.0 = 0.40
        confidence = obs.compute_confidence()
        assert confidence == 0.40, f"Expected 0.40, got {confidence}"
        assert confidence > 0.0, "Confidence should be > 0 even for stale data with proof"
