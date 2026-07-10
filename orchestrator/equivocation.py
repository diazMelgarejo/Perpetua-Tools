"""
orchestrator/equivocation.py — P13 Equivocation Detection (T1 Malicious Relay) for Phase 1b.

This module detects contradictory reachability reports issued by the same network
provenance for the same peer in the same epoch. A relay that tells one consumer a
peer is REACHABLE and another consumer the same peer is UNREACHABLE for an
identical (peer_id, epoch) leaves signed, contradictory observations in the
system. Those contradictions are logged as forensic evidence of malice.

Equivocation definition (spec reference D4 § T1 + G4):
- Same peer_id and epoch.
- Same observer_provenance (one relay origin).
- Contradicting observation_type values (REACHABLE vs UNREACHABLE).

Disagreement between *different* provenances is ordinary witness disagreement,
not equivocation, and is intentionally NOT logged here.

Spec reference: D4 § T1 (Malicious relay) + Section 4 G4 (Equivocation Detection)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

from orchestrator.membership import ObservationType, PeerObservation

# Maximum observations retained per (peer_id, epoch) key. Oldest evicted first.
# Matches the bounded-caches pattern (P18) used elsewhere in the Phase 0 spec family.
MAX_OBSERVATIONS_PER_KEY = 50


@dataclass(frozen=True)
class EquivocationEvidence:
    """
    Forensic record of a single equivocation event.

    Captures the contradiction between two signed observations issued by the
    same provenance for the same peer/epoch. The contradicting_pair preserves
    order: (new_observation_type, prior_observation_type).

    Fields:
        peer_id: Target peer that the contradictory observations describe.
        epoch: Incarnation/epoch scope in which the contradiction occurred.
        observer_provenance: Network origin that issued both contradictory claims.
        contradicting_pair: Tuple of the two conflicting observation types.
        timestamps: Tuple of timestamps from the two observations, same order as
            contradicting_pair.
        detected_at: Wall-clock time when the contradiction was detected.

    Threat defended:
        T1 Malicious relay — turns contradictory relay claims into auditable
        evidence of malice for downstream reputation/slashing decisions.
    """

    peer_id: str
    epoch: int
    observer_provenance: str
    contradicting_pair: Tuple[ObservationType, ObservationType]
    timestamps: Tuple[float, float]
    detected_at: float


class EquivocationLog:
    """
    In-memory log of peer observations that detects and records equivocations.

    Design:
    - Keyed by (peer_id, epoch) → ordered list of observed tuples.
    - Each tuple records (observer_id, observation_type, timestamp,
      observer_provenance) for a single incoming PeerObservation.
    - When a new observation is recorded, it is compared against every OTHER
      already-recorded observation for the same key.
    - A contradiction is reported only when observer_provenance matches and the
      observation_type values differ.
    - Memory is bounded per key: when a key reaches MAX_OBSERVATIONS_PER_KEY,
      the oldest observation is evicted before the new one is appended.

    Spec reference: D4 § G4 (Equivocation Detection)
    """

    def __init__(self) -> None:
        """Initialize an empty equivocation log."""
        # (peer_id, epoch) -> list of observed tuples, oldest first.
        self._observations: Dict[
            Tuple[str, int], List[Tuple[str, ObservationType, float, str]]
        ] = {}

    def record_observation(
        self, observation: PeerObservation
    ) -> List[EquivocationEvidence]:
        """
        Record an observation and return any new equivocations it creates.

        The observation is appended to the per-(peer_id, epoch) set. It is then
        compared against every previously recorded observation for the same key.
        Only pairs with the SAME observer_provenance and DIFFERENT
        observation_type are returned as EquivocationEvidence.

        Args:
            observation: The PeerObservation to record.

        Returns:
            A list of EquivocationEvidence instances, one for each prior
            observation that contradicts the newly recorded one. Empty list if
            no equivocation is detected.

        Threat defended:
            T1 Malicious relay — contradictory signed observations from a single
            provenance are surfaced as proof of malice.
        """
        key = (observation.peer_id, observation.epoch)
        provenance = observation.observer_provenance
        new_entry: Tuple[str, ObservationType, float, str] = (
            observation.observer_id,
            observation.observation_type,
            observation.timestamp,
            provenance,
        )

        bucket = self._observations.setdefault(key, [])

        # Enforce bounded memory per key: evict oldest first (P18 bounded cache).
        if len(bucket) >= MAX_OBSERVATIONS_PER_KEY:
            bucket.pop(0)

        detected_at = time.time()
        evidences: List[EquivocationEvidence] = []

        for prior_observer_id, prior_type, prior_timestamp, prior_provenance in bucket:
            if prior_provenance != provenance:
                # Different provenances disagreeing is normal witness disagreement,
                # not equivocation.
                continue
            if prior_type == observation.observation_type:
                # Same provenance and same type is consistent (possibly duplicate).
                continue
            evidences.append(
                EquivocationEvidence(
                    peer_id=observation.peer_id,
                    epoch=observation.epoch,
                    observer_provenance=provenance,
                    contradicting_pair=(observation.observation_type, prior_type),
                    timestamps=(observation.timestamp, prior_timestamp),
                    detected_at=detected_at,
                )
            )

        bucket.append(new_entry)
        return evidences
