"""
tests/test_display_state.py — TDD tests for display_state computation.

Tests validate:
- Boundary transitions (thresholds 0.0, 0.30, 0.70)
- State coverage (UNKNOWN, SUSPECT, DEGRADED, HEALTHY)
- Edge cases (floating-point precision, epsilon boundaries)
- Hysteresis (deterministic: same confidence → same state)
- Integration with PeerObservation.compute_confidence()

Reference: D1 § 2.3 (display state derivation)
"""

import time

import pytest

from orchestrator.display_state import (
    PeerDisplayState,
    compute_display_state,
    compute_display_state_from_peer,
)
from orchestrator.membership import (
    PeerObservation,
    DirectStatus,
    Route,
    ObservationType,
)


class TestPeerDisplayStateEnum:
    """Test PeerDisplayState enum basics."""

    def test_enum_values_exist(self):
        """GIVEN: PeerDisplayState enum THEN: all 4 states defined."""
        assert hasattr(PeerDisplayState, "UNKNOWN")
        assert hasattr(PeerDisplayState, "SUSPECT")
        assert hasattr(PeerDisplayState, "DEGRADED")
        assert hasattr(PeerDisplayState, "HEALTHY")

    def test_enum_is_string_enum(self):
        """GIVEN: PeerDisplayState THEN: string values."""
        assert PeerDisplayState.UNKNOWN.value == "UNKNOWN"
        assert PeerDisplayState.SUSPECT.value == "SUSPECT"
        assert PeerDisplayState.DEGRADED.value == "DEGRADED"
        assert PeerDisplayState.HEALTHY.value == "HEALTHY"

    def test_enum_count(self):
        """GIVEN: PeerDisplayState THEN: exactly 4 members."""
        assert len(list(PeerDisplayState)) == 4


class TestComputeDisplayStateBoundaries:
    """Test boundary transitions between display states."""

    def test_confidence_exactly_zero_returns_unknown(self):
        """GIVEN: confidence = 0.0 THEN: UNKNOWN."""
        state = compute_display_state(0.0)
        assert state == PeerDisplayState.UNKNOWN

    def test_confidence_near_zero_returns_unknown(self):
        """GIVEN: confidence ≈ 0 (e.g., 1e-10) THEN: not UNKNOWN, depends on value."""
        # 1e-10 is > 0.0, so should be SUSPECT
        state = compute_display_state(1e-10)
        assert state == PeerDisplayState.SUSPECT

    def test_confidence_just_above_zero_returns_suspect(self):
        """GIVEN: confidence > 0 but small (0.01) THEN: SUSPECT."""
        state = compute_display_state(0.01)
        assert state == PeerDisplayState.SUSPECT

    def test_confidence_just_below_threshold_30_returns_suspect(self):
        """GIVEN: confidence < 0.30 (e.g., 0.299) THEN: SUSPECT."""
        state = compute_display_state(0.299)
        assert state == PeerDisplayState.SUSPECT

    def test_confidence_exactly_threshold_30_returns_degraded(self):
        """GIVEN: confidence = 0.30 THEN: DEGRADED (boundary is inclusive on lower)."""
        state = compute_display_state(0.30)
        assert state == PeerDisplayState.DEGRADED

    def test_confidence_just_above_threshold_30_returns_degraded(self):
        """GIVEN: confidence > 0.30 (e.g., 0.301) THEN: DEGRADED."""
        state = compute_display_state(0.301)
        assert state == PeerDisplayState.DEGRADED

    def test_confidence_mid_range_returns_degraded(self):
        """GIVEN: confidence in [0.30, 0.70) (e.g., 0.5) THEN: DEGRADED."""
        state = compute_display_state(0.50)
        assert state == PeerDisplayState.DEGRADED

    def test_confidence_just_below_threshold_70_returns_degraded(self):
        """GIVEN: confidence < 0.70 (e.g., 0.699) THEN: DEGRADED."""
        state = compute_display_state(0.699)
        assert state == PeerDisplayState.DEGRADED

    def test_confidence_exactly_threshold_70_returns_healthy(self):
        """GIVEN: confidence = 0.70 THEN: HEALTHY."""
        state = compute_display_state(0.70)
        assert state == PeerDisplayState.HEALTHY

    def test_confidence_just_above_threshold_70_returns_healthy(self):
        """GIVEN: confidence > 0.70 (e.g., 0.701) THEN: HEALTHY."""
        state = compute_display_state(0.701)
        assert state == PeerDisplayState.HEALTHY

    def test_confidence_exactly_one_returns_healthy(self):
        """GIVEN: confidence = 1.0 THEN: HEALTHY."""
        state = compute_display_state(1.0)
        assert state == PeerDisplayState.HEALTHY


class TestComputeDisplayStateFloatingPoint:
    """Test edge cases involving floating-point precision."""

    def test_confidence_with_floating_point_error(self):
        """GIVEN: confidence from arithmetic with float error
        THEN: correct state (e.g., 0.7 from 0.35 * 2.0)."""
        # Simulate floating-point: 0.35 * 2.0 might not be exactly 0.70
        confidence = 0.35 * 2.0
        state = compute_display_state(confidence)
        assert state == PeerDisplayState.HEALTHY

    def test_confidence_rounded_to_two_decimals(self):
        """GIVEN: confidence rounded to 2 decimals (as per compute_confidence)
        THEN: correct state."""
        # Simulate rounded confidence value
        confidence = round(0.3499999, 2)  # 0.35
        state = compute_display_state(confidence)
        assert state == PeerDisplayState.DEGRADED

    def test_confidence_with_many_decimal_places(self):
        """GIVEN: confidence with many decimal places
        THEN: correct state based on actual value."""
        confidence = 0.696969696969
        state = compute_display_state(confidence)
        assert state == PeerDisplayState.DEGRADED

    def test_confidence_at_boundary_with_many_decimals(self):
        """GIVEN: confidence very close to boundary (0.300001)
        THEN: correct state (DEGRADED)."""
        confidence = 0.300001
        state = compute_display_state(confidence)
        assert state == PeerDisplayState.DEGRADED


class TestComputeDisplayStateHysteresis:
    """Test deterministic behavior: same confidence → same state."""

    def test_same_confidence_returns_same_state_multiple_calls(self):
        """GIVEN: compute_display_state called multiple times with same value
        THEN: always returns same state."""
        confidence = 0.55
        state1 = compute_display_state(confidence)
        state2 = compute_display_state(confidence)
        state3 = compute_display_state(confidence)
        assert state1 == state2 == state3

    def test_deterministic_for_each_state(self):
        """GIVEN: representative confidence for each state
        THEN: consistent results across multiple calls."""
        test_cases = [
            (0.0, PeerDisplayState.UNKNOWN),
            (0.15, PeerDisplayState.SUSPECT),
            (0.50, PeerDisplayState.DEGRADED),
            (0.85, PeerDisplayState.HEALTHY),
        ]

        for confidence, expected_state in test_cases:
            for _ in range(3):
                state = compute_display_state(confidence)
                assert state == expected_state

    def test_threshold_crossing_monotonic(self):
        """GIVEN: increasing confidence values
        THEN: display state monotonically improves (or stays same)."""
        values = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        states = [compute_display_state(v) for v in values]

        # Map states to numeric order (for monotonicity check)
        state_order = {
            PeerDisplayState.UNKNOWN: 0,
            PeerDisplayState.SUSPECT: 1,
            PeerDisplayState.DEGRADED: 2,
            PeerDisplayState.HEALTHY: 3,
        }

        numeric_states = [state_order[s] for s in states]

        # Verify monotonic increase (non-decreasing)
        for i in range(1, len(numeric_states)):
            assert numeric_states[i] >= numeric_states[i - 1]


class TestComputeDisplayStateCoverage:
    """Test all display states are reachable."""

    def test_unknown_state_reachable(self):
        """GIVEN: confidence = 0.0 THEN: UNKNOWN reachable."""
        state = compute_display_state(0.0)
        assert state == PeerDisplayState.UNKNOWN

    def test_suspect_state_reachable(self):
        """GIVEN: confidence in (0.0, 0.30) THEN: SUSPECT reachable."""
        state = compute_display_state(0.15)
        assert state == PeerDisplayState.SUSPECT

    def test_degraded_state_reachable(self):
        """GIVEN: confidence in [0.30, 0.70) THEN: DEGRADED reachable."""
        state = compute_display_state(0.50)
        assert state == PeerDisplayState.DEGRADED

    def test_healthy_state_reachable(self):
        """GIVEN: confidence >= 0.70 THEN: HEALTHY reachable."""
        state = compute_display_state(0.85)
        assert state == PeerDisplayState.HEALTHY


class TestComputeDisplayStateFromPeer:
    """Test integration with PeerObservation."""

    def _make_peer_observation(self, proof_score: float, freshness_score: float) -> PeerObservation:
        """Helper: create a PeerObservation with given scores."""
        now = time.time()
        return PeerObservation(
            peer_id="test-peer-001",
            epoch=1,
            timestamp=now,
            proof_score=proof_score,
            freshness_score=freshness_score,
            witness_agreement=0,
            witness_disagreement=0,
            observation_type=ObservationType.REACHABLE,
            observer_id="test-observer-001",
            direct_status=DirectStatus.REACHABLE,
            endpoint="127.0.1.1:9000",
            endpoint_epoch=1,
            last_heartbeat_timestamp=now,
            last_probe_timestamp=now,
            probe_latency_ms=5.0,
            route=Route.DIRECT,
            probe_result=None,
            relay_proof=None,
            witness_set=(),
            backend_caps=(),
            backend_state=None,
            backend_state_timestamp=None,
            ttl_seconds=60,
            tags=frozenset(),
            notes="test observation",
            source_id=None,
            chain_depth=0,
        )

    def test_compute_display_state_from_peer_ghost_peer(self):
        """GIVEN: PeerObservation with proof_score=0 (ghost peer)
        THEN: compute_confidence()=0 → UNKNOWN."""
        peer_obs = self._make_peer_observation(proof_score=0.0, freshness_score=0.9)
        state = compute_display_state_from_peer(peer_obs)
        assert state == PeerDisplayState.UNKNOWN

    def test_compute_display_state_from_peer_low_proof(self):
        """GIVEN: PeerObservation with low proof_score (0.15)
        THEN: confidence < 0.30 → SUSPECT."""
        # Confidence = 0.15 * (0.40 + 0.60*0.9) * 0.85 ≈ 0.12 → SUSPECT
        peer_obs = self._make_peer_observation(proof_score=0.15, freshness_score=0.9)
        state = compute_display_state_from_peer(peer_obs)
        assert state == PeerDisplayState.SUSPECT

    def test_compute_display_state_from_peer_medium_confidence(self):
        """GIVEN: PeerObservation with medium proof_score (0.6)
        THEN: confidence ∈ [0.30, 0.70) → DEGRADED."""
        # Confidence = 0.6 * (0.40 + 0.60*0.8) * 0.85 ≈ 0.38 → DEGRADED
        peer_obs = self._make_peer_observation(proof_score=0.6, freshness_score=0.8)
        state = compute_display_state_from_peer(peer_obs)
        assert state == PeerDisplayState.DEGRADED

    def test_compute_display_state_from_peer_high_confidence(self):
        """GIVEN: PeerObservation with high proof_score (0.95)
        THEN: confidence >= 0.70 → HEALTHY."""
        # Confidence = 0.95 * (0.40 + 0.60*0.95) * 0.85 ≈ 0.69 → HEALTHY
        peer_obs = self._make_peer_observation(proof_score=0.95, freshness_score=0.95)
        state = compute_display_state_from_peer(peer_obs)
        assert state == PeerDisplayState.HEALTHY

    def test_compute_display_state_from_peer_perfect_score(self):
        """GIVEN: PeerObservation with all perfect scores (1.0)
        THEN: confidence = 1.0 → HEALTHY."""
        peer_obs = self._make_peer_observation(proof_score=1.0, freshness_score=1.0)
        state = compute_display_state_from_peer(peer_obs)
        assert state == PeerDisplayState.HEALTHY

    def test_compute_display_state_from_peer_with_witnesses(self):
        """GIVEN: PeerObservation with witness agreement
        THEN: witness_multiplier=1.0 increases confidence → possibly higher state."""
        peer_obs = self._make_peer_observation(proof_score=0.75, freshness_score=0.75)
        # Override witness counts to get multiplier=1.0
        # We need to create a new object since it's frozen
        now = time.time()
        peer_obs_with_witnesses = PeerObservation(
            peer_id="test-peer-001",
            epoch=1,
            timestamp=now,
            proof_score=0.75,
            freshness_score=0.75,
            witness_agreement=2,  # triggers multiplier=1.0
            witness_disagreement=0,
            observation_type=ObservationType.REACHABLE,
            observer_id="test-observer-001",
            direct_status=DirectStatus.REACHABLE,
            endpoint="127.0.1.1:9000",
            endpoint_epoch=1,
            last_heartbeat_timestamp=now,
            last_probe_timestamp=now,
            probe_latency_ms=5.0,
            route=Route.DIRECT,
            probe_result=None,
            relay_proof=None,
            witness_set=(),
            backend_caps=(),
            backend_state=None,
            backend_state_timestamp=None,
            ttl_seconds=60,
            tags=frozenset(),
            notes="test observation",
            source_id=None,
            chain_depth=0,
        )
        state = compute_display_state_from_peer(peer_obs_with_witnesses)
        # Confidence = 0.75 * (0.40 + 0.60*0.75) * 1.0 = 0.75 * 0.85 = 0.6375 → DEGRADED
        assert state == PeerDisplayState.DEGRADED


class TestComputeDisplayStateParametrized:
    """Parametrized tests covering a range of confidence values."""

    @pytest.mark.parametrize(
        "confidence,expected_state",
        [
            # UNKNOWN: exactly 0.0
            (0.0, PeerDisplayState.UNKNOWN),
            # SUSPECT: 0.0 < confidence < 0.30
            (0.01, PeerDisplayState.SUSPECT),
            (0.05, PeerDisplayState.SUSPECT),
            (0.15, PeerDisplayState.SUSPECT),
            (0.29, PeerDisplayState.SUSPECT),
            (0.299, PeerDisplayState.SUSPECT),
            # DEGRADED: 0.30 <= confidence < 0.70
            (0.30, PeerDisplayState.DEGRADED),
            (0.301, PeerDisplayState.DEGRADED),
            (0.40, PeerDisplayState.DEGRADED),
            (0.50, PeerDisplayState.DEGRADED),
            (0.60, PeerDisplayState.DEGRADED),
            (0.699, PeerDisplayState.DEGRADED),
            # HEALTHY: confidence >= 0.70
            (0.70, PeerDisplayState.HEALTHY),
            (0.701, PeerDisplayState.HEALTHY),
            (0.80, PeerDisplayState.HEALTHY),
            (0.90, PeerDisplayState.HEALTHY),
            (0.99, PeerDisplayState.HEALTHY),
            (1.0, PeerDisplayState.HEALTHY),
        ],
    )
    def test_parametrized_confidence_to_state(
        self, confidence: float, expected_state: PeerDisplayState
    ):
        """GIVEN: confidence value THEN: correct display state."""
        state = compute_display_state(confidence)
        assert state == expected_state


class TestComputeDisplayStateInvariants:
    """Test invariants and properties."""

    def test_output_always_valid_enum_member(self):
        """GIVEN: any valid confidence value
        THEN: output is valid PeerDisplayState member."""
        test_values = [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]
        for confidence in test_values:
            state = compute_display_state(confidence)
            assert isinstance(state, PeerDisplayState)
            assert state in list(PeerDisplayState)

    def test_no_input_raises_exception_in_valid_range(self):
        """GIVEN: confidence in [0.0, 1.0]
        THEN: no exception raised."""
        import random

        for _ in range(10):
            confidence = random.uniform(0.0, 1.0)
            # Should not raise
            state = compute_display_state(confidence)
            assert isinstance(state, PeerDisplayState)
