"""Tests for Monotonic Apply Gate (T7) - Observation Ordering Enforcement.

Task 1.3.1: Enforce strict monotonic causality on peer observations.
Ordering key: (epoch, sequence, timestamp) with ±30s clock skew tolerance.

Test coverage:
- Newer epoch always accepted (peer restart)
- Same epoch: sequence comparison (canonical causality)
- Same epoch & sequence: timestamp comparison (clock skew)
- Edge cases: boundary conditions, negative values, floating-point precision
"""

import pytest
from orchestrator.membership import PeerObservation, ObservationType, DirectStatus
from orchestrator.monotonic_gate import is_observation_newer


def make_obs(
    epoch: int = 1,
    sequence: int = 1,
    timestamp: float = 1000.0,
    peer_id: str = "peer_a",
    observer_id: str = "observer_1",
) -> PeerObservation:
    """Factory for creating test observations with minimal required fields."""
    return PeerObservation(
        peer_id=peer_id,
        observer_id=observer_id,
        epoch=epoch,
        timestamp=timestamp,
        observation_type=ObservationType.REACHABLE,
        direct_status=DirectStatus.REACHABLE,
        endpoint="192.168.1.1:9000",
        endpoint_epoch=epoch,
        sequence=sequence,
    )


class TestMonotonicOrderingEpochPriority:
    """Epoch-based ordering (highest priority)."""

    def test_newer_epoch_accepted_regardless_of_sequence(self) -> None:
        """New observation with higher epoch should always be accepted."""
        current = make_obs(epoch=5, sequence=100, timestamp=1000.0)
        new = make_obs(epoch=6, sequence=10, timestamp=500.0)
        assert is_observation_newer(current, new) is True

    def test_lower_epoch_rejected_regardless_of_sequence(self) -> None:
        """New observation with lower epoch should always be rejected (stale)."""
        current = make_obs(epoch=5, sequence=10, timestamp=1000.0)
        new = make_obs(epoch=4, sequence=1000, timestamp=2000.0)
        assert is_observation_newer(current, new) is False

    def test_epoch_zero_transitions_to_epoch_one(self) -> None:
        """Epoch counter starts at 0; first restart → epoch=1."""
        current = make_obs(epoch=0, sequence=1, timestamp=1000.0)
        new = make_obs(epoch=1, sequence=1, timestamp=1001.0)
        assert is_observation_newer(current, new) is True


class TestMonotonicOrderingSequencePriority:
    """Sequence-based ordering within same epoch (canonical causality)."""

    def test_same_epoch_higher_sequence_accepted(self) -> None:
        """New observation with higher sequence in same epoch should be accepted."""
        current = make_obs(epoch=5, sequence=10, timestamp=1000.0)
        new = make_obs(epoch=5, sequence=15, timestamp=1100.0)
        assert is_observation_newer(current, new) is True

    def test_same_epoch_lower_sequence_rejected(self) -> None:
        """New observation with lower sequence in same epoch should be rejected."""
        current = make_obs(epoch=5, sequence=100, timestamp=1000.0)
        new = make_obs(epoch=5, sequence=50, timestamp=2000.0)
        assert is_observation_newer(current, new) is False

    def test_sequence_increment_by_one(self) -> None:
        """Typical case: sequence increments by 1 (consecutive observations)."""
        current = make_obs(epoch=1, sequence=42, timestamp=1000.0)
        new = make_obs(epoch=1, sequence=43, timestamp=1001.0)
        assert is_observation_newer(current, new) is True

    def test_large_sequence_gap(self) -> None:
        """Sequence can jump significantly (missed observations from packet loss)."""
        current = make_obs(epoch=1, sequence=1000, timestamp=1000.0)
        new = make_obs(epoch=1, sequence=10000, timestamp=1001.0)
        assert is_observation_newer(current, new) is True


class TestMonotonicOrderingTimestampTieBreaker:
    """Timestamp-based ordering when epoch and sequence tie (±30s tolerance)."""

    def test_same_epoch_sequence_timestamp_within_tolerance(self) -> None:
        """Same epoch & sequence, timestamp within ±30s tolerance → rejected."""
        current = make_obs(epoch=5, sequence=10, timestamp=1000.0)
        new = make_obs(epoch=5, sequence=10, timestamp=1025.0)
        assert is_observation_newer(current, new) is False

    def test_same_epoch_sequence_timestamp_exactly_at_threshold(self) -> None:
        """Same epoch & sequence, timestamp at exactly 30s boundary → rejected."""
        current = make_obs(epoch=5, sequence=10, timestamp=1000.0)
        new = make_obs(epoch=5, sequence=10, timestamp=1030.0)
        assert is_observation_newer(current, new) is False

    def test_same_epoch_sequence_timestamp_exceeds_tolerance(self) -> None:
        """Same epoch & sequence, timestamp beyond ±30s tolerance → accepted."""
        current = make_obs(epoch=5, sequence=10, timestamp=1000.0)
        new = make_obs(epoch=5, sequence=10, timestamp=1031.0)
        assert is_observation_newer(current, new) is True

    def test_timestamp_clock_skew_backward(self) -> None:
        """Clock skew backward: rejected if within tolerance."""
        current = make_obs(epoch=5, sequence=10, timestamp=1000.0)
        new = make_obs(epoch=5, sequence=10, timestamp=980.0)
        assert is_observation_newer(current, new) is False

    def test_timestamp_exact_same_value(self) -> None:
        """Same timestamp (duplicate observation) → rejected."""
        current = make_obs(epoch=5, sequence=10, timestamp=1000.0)
        new = make_obs(epoch=5, sequence=10, timestamp=1000.0)
        assert is_observation_newer(current, new) is False


class TestMonotonicOrderingEdgeCases:
    """Edge cases and boundary conditions."""

    def test_negative_sequence_numbers(self) -> None:
        """Sequence can be any integer, including negative."""
        current = make_obs(epoch=1, sequence=-5, timestamp=1000.0)
        new = make_obs(epoch=1, sequence=-1, timestamp=1001.0)
        assert is_observation_newer(current, new) is True

    def test_zero_sequence_number(self) -> None:
        """Sequence can be zero (bootstrap)."""
        current = make_obs(epoch=0, sequence=0, timestamp=1000.0)
        new = make_obs(epoch=0, sequence=1, timestamp=1001.0)
        assert is_observation_newer(current, new) is True

    def test_floating_point_timestamp_precision(self) -> None:
        """Timestamp comparison uses exact > (30s tolerance is large)."""
        current = make_obs(epoch=1, sequence=1, timestamp=1000.123456789)
        new = make_obs(epoch=1, sequence=1, timestamp=1031.123456789)
        assert is_observation_newer(current, new) is True

    def test_very_large_epoch_values(self) -> None:
        """Epoch can be any integer; test large values."""
        current = make_obs(epoch=999999, sequence=1, timestamp=1000.0)
        new = make_obs(epoch=1000000, sequence=0, timestamp=500.0)
        assert is_observation_newer(current, new) is True

    def test_unix_timestamp_values(self) -> None:
        """Real-world Unix timestamps (seconds since epoch)."""
        current = make_obs(epoch=1, sequence=100, timestamp=1720569600.0)
        new = make_obs(epoch=1, sequence=101, timestamp=1720569630.0)
        assert is_observation_newer(current, new) is True


class TestMonotonicOrderingIntegration:
    """Integration tests combining multiple ordering dimensions."""

    def test_multi_update_sequence(self) -> None:
        """Simulate multi-peer observation sequence with out-of-order arrivals."""
        obs_base = make_obs(epoch=1, sequence=1, timestamp=1000.0)
        obs_seq2 = make_obs(epoch=1, sequence=2, timestamp=1001.0)
        obs_seq3 = make_obs(epoch=1, sequence=3, timestamp=1002.0)

        # Accept seq 2 (newer than base)
        assert is_observation_newer(obs_base, obs_seq2) is True

        # Try to apply seq 3, then seq 2 (out-of-order)
        assert is_observation_newer(obs_base, obs_seq3) is True
        # After applying seq 3 as current:
        assert is_observation_newer(obs_seq3, obs_seq2) is False

    def test_peer_restart_with_stale_messages(self) -> None:
        """Simulate peer restart: old observations from before restart rejected."""
        # Before restart
        obs_pre_restart = make_obs(epoch=10, sequence=9999, timestamp=1000.0)

        # After peer restart (new epoch)
        obs_post_restart = make_obs(epoch=11, sequence=1, timestamp=2000.0)
        assert is_observation_newer(obs_pre_restart, obs_post_restart) is True

        # Delayed message from before restart arrives after restart epoch established
        obs_delayed = make_obs(epoch=10, sequence=10000, timestamp=1500.0)
        # Reject delayed pre-restart message (lower epoch)
        assert is_observation_newer(obs_post_restart, obs_delayed) is False

    def test_clock_skew_recovery(self) -> None:
        """Simulate recovery from transient clock skew."""
        obs_normal = make_obs(epoch=1, sequence=10, timestamp=1000.0)

        # Clock skew ahead (sequence tie, timestamp ahead by 50s)
        obs_skewed = make_obs(epoch=1, sequence=10, timestamp=1050.0)
        # Accept skewed observation (exceeds 30s tolerance)
        assert is_observation_newer(obs_normal, obs_skewed) is True

        # Recovery: next message with higher sequence
        obs_recovered = make_obs(epoch=1, sequence=11, timestamp=1060.0)
        # Accept recovery (higher sequence)
        assert is_observation_newer(obs_skewed, obs_recovered) is True
