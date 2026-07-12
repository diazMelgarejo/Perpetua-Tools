"""
orchestrator/equivocation.py — authenticated equivocation detection.

A contradiction is equivocation only when it is attributable to the same
observer identity in the same peer/epoch scope. Shared network provenance alone
is not sufficient because unrelated observers may legitimately share a relay,
NAT, or provenance bucket.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

from orchestrator.membership import ObservationType, PeerObservation

MAX_OBSERVATIONS_PER_KEY = 50


@dataclass(frozen=True)
class EquivocationEvidence:
    """Forensic record of one authenticated contradiction."""

    peer_id: str
    epoch: int
    observer_id: str
    prior_observer_id: str
    observer_provenance: str
    contradicting_pair: Tuple[ObservationType, ObservationType]
    timestamps: Tuple[float, float]
    detected_at: float


class EquivocationLog:
    """Bounded observation log keyed by target peer and epoch.

    Contradictions are emitted only when both the authenticated observer
    identity and provenance match. Different observers sharing provenance are
    ordinary witness disagreement, not evidence against either observer.
    """

    def __init__(self) -> None:
        self._observations: Dict[
            Tuple[str, int], List[Tuple[str, ObservationType, float, str]]
        ] = {}

    def record_observation(
        self, observation: PeerObservation
    ) -> List[EquivocationEvidence]:
        key = (observation.peer_id, observation.epoch)
        provenance = observation.observer_provenance
        new_entry: Tuple[str, ObservationType, float, str] = (
            observation.observer_id,
            observation.observation_type,
            observation.timestamp,
            provenance,
        )

        bucket = self._observations.setdefault(key, [])
        if len(bucket) >= MAX_OBSERVATIONS_PER_KEY:
            bucket.pop(0)

        detected_at = time.time()
        evidences: List[EquivocationEvidence] = []
        for prior_observer_id, prior_type, prior_timestamp, prior_provenance in bucket:
            if prior_observer_id != observation.observer_id:
                continue
            if prior_provenance != provenance:
                continue
            if prior_type == observation.observation_type:
                continue
            evidences.append(
                EquivocationEvidence(
                    peer_id=observation.peer_id,
                    epoch=observation.epoch,
                    observer_id=observation.observer_id,
                    prior_observer_id=prior_observer_id,
                    observer_provenance=provenance,
                    contradicting_pair=(observation.observation_type, prior_type),
                    timestamps=(observation.timestamp, prior_timestamp),
                    detected_at=detected_at,
                )
            )

        bucket.append(new_entry)
        return evidences
