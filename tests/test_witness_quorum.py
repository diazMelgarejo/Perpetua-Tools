"""
tests/test_witness_quorum.py — Comprehensive tests for witness quorum validation (T4 Sybil Defense).

Test coverage:
- T1: Threshold met (2 distinct observers, 2 distinct provenances) → quorum passes
- T2: Threshold not met (1 observer repeated) → quorum fails
- T3: Provenance dedup (same provenance) → counted as one provenance → quorum fails
- T4: Edge case (empty witness_set) → quorum fails
- T5: Edge case (single witness) → quorum fails
- E1: Three witnesses (2 distinct observers, 2 provenances) → quorum passes
- E2: Mixed provenance (unknown + known) → counts as distinct
- E3: All same observer, different provenances → quorum fails (observer_id dedup enforced)
- E4: All same provenance, different observers → quorum fails (provenance dedup enforced)
- E5: Exactly 2 witnesses, matching observer_id and provenance → quorum fails
"""

import pytest
from orchestrator.membership import PeerObservation, ObservationType, DirectStatus, Route
from orchestrator.witness_quorum import validate_witness_quorum


class TestWitnessQuorumBasic:
    """Basic witness quorum validation tests."""

    def test_empty_witness_set_fails_quorum(self):
        """T4: Empty witness_set → quorum fails (need ≥2)."""
        obs = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=1000.0,
            observer_id="observer-a",
            observer_provenance="ASN-001",
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            witness_set=(),  # Empty
        )
        assert validate_witness_quorum(obs) is False

    def test_single_witness_fails_quorum(self):
        """T5: Single witness → quorum fails (need ≥2)."""
        witness_a = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=999.0,
            observer_id="observer-b",
            observer_provenance="ASN-002",
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.2:9000",
            endpoint_epoch=1,
        )
        obs = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=1000.0,
            observer_id="observer-a",
            observer_provenance="ASN-001",
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            witness_set=(witness_a,),  # Only 1 witness
        )
        assert validate_witness_quorum(obs) is False

    def test_two_distinct_observers_two_provenances_passes(self):
        """T1: 2 distinct observers, 2 distinct provenances → quorum passes."""
        witness_a = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=999.0,
            observer_id="observer-b",
            observer_provenance="ASN-002",
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.2:9000",
            endpoint_epoch=1,
        )
        witness_b = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=998.0,
            observer_id="observer-c",
            observer_provenance="ASN-003",
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.3:9000",
            endpoint_epoch=1,
        )
        obs = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=1000.0,
            observer_id="observer-a",
            observer_provenance="ASN-001",
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            witness_set=(witness_a, witness_b),
        )
        assert validate_witness_quorum(obs) is True


class TestWitnessQuorumObserverDedup:
    """Tests for observer_id deduplication (Sybil prevention)."""

    def test_repeated_observer_id_fails_quorum(self):
        """T2: Same observer_id repeated → observer dedup fails → quorum fails."""
        same_observer = "observer-b"
        witness_a = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=999.0,
            observer_id=same_observer,  # Same observer
            observer_provenance="ASN-002",
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.2:9000",
            endpoint_epoch=1,
        )
        witness_b = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=998.0,
            observer_id=same_observer,  # Same observer again
            observer_provenance="ASN-003",  # Different provenance doesn't matter
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.3:9000",
            endpoint_epoch=1,
        )
        obs = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=1000.0,
            observer_id="observer-a",
            observer_provenance="ASN-001",
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            witness_set=(witness_a, witness_b),
        )
        assert validate_witness_quorum(obs) is False

    def test_same_observer_different_provenances_fails(self):
        """E3: Same observer_id with different provenances → fails (observer dedup enforced)."""
        same_observer = "observer-b"
        witness_a = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=999.0,
            observer_id=same_observer,
            observer_provenance="ASN-002",
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.2:9000",
            endpoint_epoch=1,
        )
        witness_b = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=998.0,
            observer_id=same_observer,
            observer_provenance="ASN-999",  # Different provenance
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.99:9000",
            endpoint_epoch=1,
        )
        obs = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=1000.0,
            observer_id="observer-a",
            observer_provenance="ASN-001",
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            witness_set=(witness_a, witness_b),
        )
        assert validate_witness_quorum(obs) is False


class TestWitnessQuorumProvenanceDedup:
    """Tests for observer_provenance deduplication (network provenance Sybil defense)."""

    def test_same_provenance_fails_quorum(self):
        """T3: Same provenance repeated → provenance dedup fails → quorum fails."""
        same_provenance = "ASN-002"
        witness_a = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=999.0,
            observer_id="observer-b",
            observer_provenance=same_provenance,  # Same provenance
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.2:9000",
            endpoint_epoch=1,
        )
        witness_b = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=998.0,
            observer_id="observer-c",
            observer_provenance=same_provenance,  # Same provenance again
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.3:9000",
            endpoint_epoch=1,
        )
        obs = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=1000.0,
            observer_id="observer-a",
            observer_provenance="ASN-001",
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            witness_set=(witness_a, witness_b),
        )
        assert validate_witness_quorum(obs) is False

    def test_all_same_provenance_different_observers_fails(self):
        """E4: All same provenance, different observers → fails (provenance dedup enforced)."""
        same_provenance = "ASN-002"
        witness_a = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=999.0,
            observer_id="observer-b",
            observer_provenance=same_provenance,
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.2:9000",
            endpoint_epoch=1,
        )
        witness_b = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=998.0,
            observer_id="observer-c",  # Different observer
            observer_provenance=same_provenance,  # But same provenance
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.3:9000",
            endpoint_epoch=1,
        )
        obs = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=1000.0,
            observer_id="observer-a",
            observer_provenance="ASN-001",
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            witness_set=(witness_a, witness_b),
        )
        assert validate_witness_quorum(obs) is False


class TestWitnessQuorumEdgeCases:
    """Edge cases and boundary conditions."""

    def test_two_witnesses_same_observer_and_provenance_fails(self):
        """E5: Exactly 2 witnesses, same observer_id and provenance → fails."""
        witness_a = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=999.0,
            observer_id="observer-b",
            observer_provenance="ASN-002",
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.2:9000",
            endpoint_epoch=1,
        )
        witness_b = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=998.0,
            observer_id="observer-b",  # Same observer
            observer_provenance="ASN-002",  # Same provenance
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.2:9000",
            endpoint_epoch=1,
        )
        obs = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=1000.0,
            observer_id="observer-a",
            observer_provenance="ASN-001",
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            witness_set=(witness_a, witness_b),
        )
        assert validate_witness_quorum(obs) is False

    def test_three_witnesses_two_distinct_observers_passes(self):
        """E1: 3 witnesses, 2 distinct observers (one repeated), 2 distinct provenances → passes."""
        witness_a = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=999.0,
            observer_id="observer-b",
            observer_provenance="ASN-002",
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.2:9000",
            endpoint_epoch=1,
        )
        witness_b = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=998.0,
            observer_id="observer-b",  # Same observer
            observer_provenance="ASN-003",  # Different provenance
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.3:9000",
            endpoint_epoch=1,
        )
        witness_c = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=997.0,
            observer_id="observer-c",  # Different observer
            observer_provenance="ASN-004",
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.4:9000",
            endpoint_epoch=1,
        )
        obs = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=1000.0,
            observer_id="observer-a",
            observer_provenance="ASN-001",
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            witness_set=(witness_a, witness_b, witness_c),
        )
        assert validate_witness_quorum(obs) is True

    def test_empty_provenance_string_treated_as_distinct(self):
        """E2: Empty provenance strings are distinct from each other and other provenances."""
        witness_a = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=999.0,
            observer_id="observer-b",
            observer_provenance="",  # Empty provenance
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.2:9000",
            endpoint_epoch=1,
        )
        witness_b = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=998.0,
            observer_id="observer-c",
            observer_provenance="ASN-003",  # Non-empty provenance
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.3:9000",
            endpoint_epoch=1,
        )
        obs = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=1000.0,
            observer_id="observer-a",
            observer_provenance="ASN-001",
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            witness_set=(witness_a, witness_b),
        )
        # Empty "" and "ASN-003" are distinct → should pass
        assert validate_witness_quorum(obs) is True

    def test_many_witnesses_satisfies_quorum(self):
        """Verify quorum works with many witnesses (5+)."""
        witnesses = [
            PeerObservation(
                peer_id="peer-001",
                epoch=1,
                timestamp=999.0 - i,
                observer_id=f"observer-{i}",
                observer_provenance=f"ASN-{100 + i}",
                observation_type=ObservationType.REACHABLE,
                direct_status=DirectStatus.REACHABLE,
                endpoint=f"192.168.1.{i+2}:9000",
                endpoint_epoch=1,
            )
            for i in range(5)
        ]
        obs = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=1000.0,
            observer_id="observer-a",
            observer_provenance="ASN-001",
            observation_type=ObservationType.REACHABLE,
            direct_status=DirectStatus.REACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            witness_set=tuple(witnesses),
        )
        assert validate_witness_quorum(obs) is True
        assert len(obs.witness_set) == 5  # Verify test setup


class TestWitnessQuorumUnreachable:
    """Tests with UNREACHABLE observations to ensure quorum logic is observation-type agnostic."""

    def test_quorum_passes_for_unreachable_observations(self):
        """Quorum validation should work regardless of observation_type (REACHABLE vs UNREACHABLE)."""
        witness_a = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=999.0,
            observer_id="observer-b",
            observer_provenance="ASN-002",
            observation_type=ObservationType.UNREACHABLE,  # Note: UNREACHABLE
            direct_status=DirectStatus.UNREACHABLE,
            endpoint="192.168.1.2:9000",
            endpoint_epoch=1,
        )
        witness_b = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=998.0,
            observer_id="observer-c",
            observer_provenance="ASN-003",
            observation_type=ObservationType.UNREACHABLE,  # Note: UNREACHABLE
            direct_status=DirectStatus.UNREACHABLE,
            endpoint="192.168.1.3:9000",
            endpoint_epoch=1,
        )
        obs = PeerObservation(
            peer_id="peer-001",
            epoch=1,
            timestamp=1000.0,
            observer_id="observer-a",
            observer_provenance="ASN-001",
            observation_type=ObservationType.UNREACHABLE,
            direct_status=DirectStatus.UNREACHABLE,
            endpoint="192.168.1.1:9000",
            endpoint_epoch=1,
            witness_set=(witness_a, witness_b),
        )
        assert validate_witness_quorum(obs) is True
