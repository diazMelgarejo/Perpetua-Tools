"""Tests for authenticated equivocation detection."""

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
    return PeerObservation(
        peer_id=peer_id,
        observer_id=observer_id,
        epoch=epoch,
        timestamp=timestamp,
        observation_type=observation_type,
        direct_status=(
            DirectStatus.REACHABLE
            if observation_type == ObservationType.REACHABLE
            else DirectStatus.UNREACHABLE
        ),
        endpoint="127.0.1.1:9000",
        endpoint_epoch=epoch,
        sequence=sequence,
        observer_provenance=observer_provenance,
    )


class TestEquivocationDetection:
    def test_same_authenticated_observer_contradiction_detected(self) -> None:
        log = EquivocationLog()
        reachable = make_obs(
            observer_id="observer_1",
            observation_type=ObservationType.REACHABLE,
            timestamp=1000.0,
        )
        unreachable = make_obs(
            observer_id="observer_1",
            observation_type=ObservationType.UNREACHABLE,
            timestamp=1001.0,
        )

        assert log.record_observation(reachable) == []
        evidence_list = log.record_observation(unreachable)

        assert len(evidence_list) == 1
        evidence = evidence_list[0]
        assert isinstance(evidence, EquivocationEvidence)
        assert evidence.peer_id == "peer_a"
        assert evidence.epoch == 1
        assert evidence.observer_id == "observer_1"
        assert evidence.prior_observer_id == "observer_1"
        assert evidence.observer_provenance == "provenance_1"
        assert evidence.contradicting_pair == (
            ObservationType.UNREACHABLE,
            ObservationType.REACHABLE,
        )
        assert evidence.timestamps == (1001.0, 1000.0)
        assert evidence.detected_at > 0.0

    def test_different_observers_sharing_provenance_are_not_equivocation(self) -> None:
        log = EquivocationLog()
        reachable = make_obs(
            observer_id="observer_A",
            observer_provenance="shared-relay",
            observation_type=ObservationType.REACHABLE,
        )
        unreachable = make_obs(
            observer_id="observer_B",
            observer_provenance="shared-relay",
            observation_type=ObservationType.UNREACHABLE,
            timestamp=1001.0,
        )

        assert log.record_observation(reachable) == []
        assert log.record_observation(unreachable) == []

    def test_same_observer_different_provenance_is_not_equivocation(self) -> None:
        log = EquivocationLog()
        reachable = make_obs(
            observer_id="observer_1",
            observer_provenance="relay_A",
            observation_type=ObservationType.REACHABLE,
        )
        unreachable = make_obs(
            observer_id="observer_1",
            observer_provenance="relay_B",
            observation_type=ObservationType.UNREACHABLE,
            timestamp=1001.0,
        )

        assert log.record_observation(reachable) == []
        assert log.record_observation(unreachable) == []

    def test_same_identity_same_type_twice_no_equivocation(self) -> None:
        log = EquivocationLog()
        first = make_obs(observation_type=ObservationType.REACHABLE)
        second = make_obs(
            observation_type=ObservationType.REACHABLE,
            timestamp=1001.0,
        )

        assert log.record_observation(first) == []
        assert log.record_observation(second) == []

    def test_different_epoch_no_equivocation(self) -> None:
        log = EquivocationLog()
        first = make_obs(epoch=1, observation_type=ObservationType.REACHABLE)
        second = make_obs(
            epoch=2,
            observation_type=ObservationType.UNREACHABLE,
            timestamp=1001.0,
        )

        assert log.record_observation(first) == []
        assert log.record_observation(second) == []


class TestEquivocationMemoryBounds:
    def test_eviction_at_51_entries_caps_memory(self) -> None:
        log = EquivocationLog()
        for index in range(50):
            log.record_observation(
                make_obs(
                    observer_id="observer_1",
                    observer_provenance="provenance_1",
                    observation_type=(
                        ObservationType.REACHABLE
                        if index % 2 == 0
                        else ObservationType.UNREACHABLE
                    ),
                    timestamp=1000.0 + index,
                    sequence=index,
                )
            )

        evidence_list = log.record_observation(
            make_obs(
                observer_id="observer_1",
                observer_provenance="provenance_1",
                observation_type=ObservationType.UNREACHABLE,
                timestamp=1051.0,
                sequence=51,
            )
        )

        assert len(log._observations[("peer_a", 1)]) == 50
        assert not any(
            evidence.timestamps == (1051.0, 1000.0)
            for evidence in evidence_list
        )
        assert all(
            evidence.observer_id == "observer_1"
            and evidence.prior_observer_id == "observer_1"
            for evidence in evidence_list
        )
