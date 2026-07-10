"""Tests for P13 Equivocation Detection (T1 Malicious Relay).

Task G4: Maintain per-peer-per-epoch observation set; compare all pairs for
contradictions (status != status); log contradictions as evidence of malice.

Test coverage:
- Same provenance reports REACHABLE then UNREACHABLE -> equivocation detected.
- Different provenances disagree -> NOT equivocation (normal disagreement).
- Same provenance reports same type twice -> no equivocation.
- Different epoch -> no equivocation.
- Bounded eviction caps memory at 50 entries per (peer_id, epoch) key.
"""

import pytest
from orchestrator.equivocation import EquivocationEvidence, EquivocationLog
from orchestrator.membership import DirectStatus, ObservationType, PeerObservation


def make_obs(
    peer_id: str = "peer_a",
    epoch: int = 1,
    observer_id: str = "observer_1",
    observer_provenance: str = "provenance_1",
    observation_type: ObservationType = ObservationType.REACHABLE,
    timestamp: float = 1000.0,
    sequence: int = 1,
) -> PeerObservation:
    """Factory for creating test observations with minimal required fields."""
    return PeerObservation(
        peer_id=peer_id,
        observer_id=observer_id,
        epoch=epoch,
        timestamp=timestamp,
        observation_type=observation_type,
        direct_status=DirectStatus.REACHABLE
        if observation_type == ObservationType.REACHABLE
        else DirectStatus.UNREACHABLE,
        endpoint="192.168.1.1:9000",
        endpoint_epoch=epoch,
        sequence=sequence,
        observer_provenance=observer_provenance,
    )


class TestEquivocationDetection:
    """Core equivocation semantics for T1 malicious relay detection."""

    def test_same_provenance_contradiction_detected(self) -> None:
        """Same provenance reporting both statuses for same peer+epoch is equivocation."""
        log = EquivocationLog()
        obs_reachable = make_obs(
            observation_type=ObservationType.REACHABLE, timestamp=1000.0
        )
        obs_unreachable = make_obs(
            observation_type=ObservationType.UNREACHABLE, timestamp=1001.0
        )

        assert log.record_observation(obs_reachable) == []
        evidence_list = log.record_observation(obs_unreachable)

        assert len(evidence_list) == 1
        evidence = evidence_list[0]
        assert isinstance(evidence, EquivocationEvidence)
        assert evidence.peer_id == "peer_a"
        assert evidence.epoch == 1
        assert evidence.observer_provenance == "provenance_1"
        assert evidence.contradicting_pair == (
            ObservationType.UNREACHABLE,
            ObservationType.REACHABLE,
        )
        assert evidence.timestamps == (1001.0, 1000.0)
        assert evidence.detected_at > 0.0

    def test_different_provenance_disagreement_is_not_equivocation(self) -> None:
        """Different provenances disagreeing is normal witness disagreement."""
        log = EquivocationLog()
        obs_reachable = make_obs(
            observer_provenance="provenance_A",
            observation_type=ObservationType.REACHABLE,
            timestamp=1000.0,
        )
        obs_unreachable = make_obs(
            observer_provenance="provenance_B",
            observation_type=ObservationType.UNREACHABLE,
            timestamp=1001.0,
        )

        assert log.record_observation(obs_reachable) == []
        assert log.record_observation(obs_unreachable) == []

    def test_same_provenance_same_type_twice_no_equivocation(self) -> None:
        """Repeated identical reports from the same provenance are consistent."""
        log = EquivocationLog()
        obs_first = make_obs(
            observation_type=ObservationType.REACHABLE, timestamp=1000.0
        )
        obs_second = make_obs(
            observation_type=ObservationType.REACHABLE, timestamp=1001.0
        )

        assert log.record_observation(obs_first) == []
        assert log.record_observation(obs_second) == []

    def test_different_epoch_no_equivocation(self) -> None:
        """Contradictions across different epochs are not equivocation."""
        log = EquivocationLog()
        obs_epoch_1 = make_obs(
            epoch=1, observation_type=ObservationType.REACHABLE, timestamp=1000.0
        )
        obs_epoch_2 = make_obs(
            epoch=2, observation_type=ObservationType.UNREACHABLE, timestamp=1001.0
        )

        assert log.record_observation(obs_epoch_1) == []
        assert log.record_observation(obs_epoch_2) == []


class TestEquivocationMemoryBounds:
    """Bounded-cache behavior (P18) for the per-key observation store."""

    def test_eviction_at_51_entries_caps_memory(self) -> None:
        """The 51st entry for the same key evicts the oldest observation."""
        log = EquivocationLog()
        base_provenance = "provenance_1"

        # Seed 50 observations alternating type so later contradictions can be
        # checked against both old and recent entries.
        for i in range(50):
            obs_type = ObservationType.REACHABLE if i % 2 == 0 else ObservationType.UNREACHABLE
            obs = make_obs(
                observer_id=f"observer_{i}",
                observer_provenance=base_provenance,
                observation_type=obs_type,
                timestamp=1000.0 + i,
                sequence=i,
            )
            # No prior observations exist on the first record, and subsequent
            # records of the same provenance alternate type, producing one
            # contradiction per pair.
            log.record_observation(obs)

        # The 51st observation with the same provenance and an opposite type
        # from observer_0's REACHABLE entry. Because the bucket is capped at 50,
        # observer_0's entry (the oldest) should have been evicted before the
        # 50th append, so no contradiction with observer_0 should be reported.
        obs_51 = make_obs(
            observer_id="observer_51",
            observer_provenance=base_provenance,
            observation_type=ObservationType.UNREACHABLE,
            timestamp=1051.0,
            sequence=51,
        )
        evidence_list = log.record_observation(obs_51)

        # The oldest observer_0 (REACHABLE) was evicted. observer_1 was
        # UNREACHABLE, so it does not contradict UNREACHABLE. The most recent
        # even-indexed entries that were REACHABLE remain (observer_2, ...),
        # so we still expect contradictions from those. Count them: even indices
        # from 2 to 48 inclusive = 24 REACHABLE entries remaining.
        assert len(evidence_list) == 24
        assert all(
            evidence.contradicting_pair
            == (ObservationType.UNREACHABLE, ObservationType.REACHABLE)
            for evidence in evidence_list
        )

        # Explicitly confirm the evicted observation no longer triggers evidence.
        evicted_observer_ids = {evidence.observer_provenance for evidence in evidence_list}
        # observer_0 is gone; the remaining contradictions come from observer_2+.
        assert not any(
            evidence.timestamps == (1051.0, 1000.0) for evidence in evidence_list
        )
