"""State-transition security decision pipeline.

Observations pass through monotonic ordering, authenticated equivocation,
independent witness quorum, reputation weighting, Sybil correlation, and an
append-only audit chain. Out-of-order observations are buffered per peer.
"""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field
from dataclasses import replace as dataclass_replace
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

from orchestrator.audit_log import AuditEntry, AuditLog
from orchestrator.distance_bucket import KBucketTable
from orchestrator.equivocation import EquivocationEvidence, EquivocationLog
from orchestrator.membership import PeerObservation
from orchestrator.provenance import provenance_bucket
from orchestrator.reputation import ReputationLedger
from orchestrator.witness_quorum import validate_witness_quorum


class InvalidObservationError(ValueError):
    """Observation failed a structural gate."""


class DecisionType(str, Enum):
    APPROVED = "approved"
    EQUIVOCATION = "equivocation"
    INSUFFICIENT_QUORUM = "insufficient_quorum"
    STALE = "stale"
    DUPLICATE = "duplicate"
    SYBIL_FLAGGED = "sybil_flagged"
    BUFFERED = "buffered"


class SybilSignal(str, Enum):
    STRONG = "strong"
    WEAK = "weak"
    NONE = "none"


@dataclass(frozen=True)
class QuorumVote:
    passes: bool
    witness_count: int
    unique_observer_ids: int
    unique_provenance_buckets: int
    witness_ids: Tuple[str, ...] = ()
    witness_provenance_buckets: Tuple[str, ...] = ()


@dataclass(frozen=True)
class WeightedQuorum:
    passes: bool
    weighted_score: float
    threshold: float
    weighted_by_observer: Dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class SybilCorrelation:
    signal: SybilSignal
    correlated_pairs: List[Tuple[str, str]] = field(default_factory=list)
    witness_bucket_index: Optional[int] = None
    details: Dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class StateTransitionResult:
    accepted: bool
    decision_type: DecisionType
    peer_id: str
    epoch: int
    observer_id: str
    rejection_reason: Optional[str] = None
    equivocation_evidences: Tuple[EquivocationEvidence, ...] = ()
    quorum_vote: Optional[QuorumVote] = None
    weighted_quorum: Optional[WeightedQuorum] = None
    sybil_correlation: Optional[SybilCorrelation] = None
    audit_entry: Optional[AuditEntry] = None
    metadata: Dict[str, object] = field(default_factory=dict)
    flushed: Tuple["StateTransitionResult", ...] = ()


class _RefCountedLock:
    __slots__ = ("lock", "ref_count")

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.ref_count = 0


class StateTransitionManager:
    """Evaluate observations through the G1/G4/G5/G6/G8 pipeline."""

    def __init__(
        self,
        local_id: str,
        equivocation_log: EquivocationLog,
        k_bucket: KBucketTable,
        audit_log: AuditLog,
        reputation: ReputationLedger,
        *,
        weighted_quorum_threshold: float = 2.0,
        sybil_proximity_bits: int = 4,
        signer: Optional[Callable[[bytes], str]] = None,
        max_cache_size: int = 10000,
        reorder_buffer_max: int = 10,
    ):
        self._local_id = local_id
        self._equivocation_log = equivocation_log
        self._k_bucket = k_bucket
        self._audit_log = audit_log
        self._reputation = reputation
        self._weighted_quorum_threshold = weighted_quorum_threshold
        self._sybil_proximity_bits = sybil_proximity_bits
        self._signer = signer
        self._max_cache_size = max_cache_size
        self._reorder_buffer_max = reorder_buffer_max
        self._peer_locks: Dict[str, _RefCountedLock] = {}
        self._last_applied_key: "OrderedDict[str, Tuple[int, int]]" = OrderedDict()
        self._seen_observations: "OrderedDict[str, None]" = OrderedDict()
        self._reorder_buffer: "OrderedDict[str, OrderedDict[Tuple[int, int], Tuple[PeerObservation, str]]]" = OrderedDict()

    def _touch_cache(self, cache: "OrderedDict", key, value) -> None:
        cache[key] = value
        cache.move_to_end(key)
        if len(cache) > self._max_cache_size:
            cache.popitem(last=False)

    async def evaluate_observation(
        self,
        obs: PeerObservation,
        old_status: str = "UNKNOWN",
    ) -> StateTransitionResult:
        entry = self._peer_locks.setdefault(obs.peer_id, _RefCountedLock())
        entry.ref_count += 1
        try:
            async with entry.lock:
                return self._evaluate_locked(obs, old_status)
        finally:
            entry.ref_count -= 1
            if entry.ref_count == 0 and self._peer_locks.get(obs.peer_id) is entry:
                del self._peer_locks[obs.peer_id]

    def _evaluate_locked(
        self,
        obs: PeerObservation,
        old_status: str,
    ) -> StateTransitionResult:
        dedup_key = obs.to_json()
        if dedup_key in self._seen_observations:
            return self._reject(
                obs, DecisionType.DUPLICATE, "Duplicate observation", old_status
            )

        last = self._last_applied_key.get(obs.peer_id)
        if last is not None:
            last_epoch, last_seq = last
            if obs.epoch < last_epoch or (
                obs.epoch == last_epoch and obs.sequence <= last_seq
            ):
                return self._reject(
                    obs,
                    DecisionType.STALE,
                    f"Out-of-order observation (epoch={obs.epoch}, "
                    f"seq={obs.sequence} <= last {last})",
                    old_status,
                )
            if obs.epoch == last_epoch and obs.sequence > last_seq + 1:
                return self._buffer_observation(obs, old_status)

        if obs.is_stale:
            return self._reject(
                obs, DecisionType.STALE, "Observation TTL expired", old_status
            )

        result = self._apply_observation(obs, old_status, dedup_key)
        flushed = self._flush_reorder_buffer(obs.peer_id)
        if flushed:
            result = dataclass_replace(result, flushed=tuple(flushed))
        return result

    def _buffer_observation(
        self, obs: PeerObservation, old_status: str
    ) -> StateTransitionResult:
        """Buffer one future sequence without replacing an existing payload.

        Retries carrying identical serialized observations are idempotent. A
        different payload for the same epoch/sequence is rejected and audited;
        the original buffered observation remains authoritative.
        """
        buffer = self._reorder_buffer.get(obs.peer_id)
        if buffer is None:
            buffer = OrderedDict()
        self._touch_cache(self._reorder_buffer, obs.peer_id, buffer)
        key = (obs.epoch, obs.sequence)
        existing = buffer.get(key)
        if existing is not None:
            existing_obs, _existing_old_status = existing
            if existing_obs.to_json() != obs.to_json():
                return self._reject(
                    obs,
                    DecisionType.DUPLICATE,
                    "Conflicting observation already buffered for "
                    f"peer={obs.peer_id}, epoch={obs.epoch}, sequence={obs.sequence}; "
                    "preserving the first payload",
                    old_status,
                )
            return StateTransitionResult(
                accepted=False,
                decision_type=DecisionType.BUFFERED,
                peer_id=obs.peer_id,
                epoch=obs.epoch,
                observer_id=obs.observer_id,
                rejection_reason=(
                    f"Out-of-order (seq={obs.sequence}); identical retry remains buffered"
                ),
            )

        if len(buffer) >= self._reorder_buffer_max:
            return self._reject(
                obs,
                DecisionType.STALE,
                f"Reorder buffer full for peer {obs.peer_id} "
                f"(max {self._reorder_buffer_max}); discarding sequence {obs.sequence}",
                old_status,
            )
        buffer[key] = (obs, old_status)
        buffer.move_to_end(key)
        return StateTransitionResult(
            accepted=False,
            decision_type=DecisionType.BUFFERED,
            peer_id=obs.peer_id,
            epoch=obs.epoch,
            observer_id=obs.observer_id,
            rejection_reason=(
                f"Out-of-order (seq={obs.sequence}); buffered pending an earlier sequence"
            ),
        )

    def _flush_reorder_buffer(self, peer_id: str) -> List[StateTransitionResult]:
        """Drain contiguous successors without stranding later sequences.

        A buffered observation that reaches the front and is terminally rejected
        is still a processed sequence. Its watermark advances so later buffered
        successors remain eligible. If processing raises, the entry is restored
        and the exception propagates, preserving a retryable gap.
        """
        buffer = self._reorder_buffer.get(peer_id)
        if not buffer:
            return []
        flushed: List[StateTransitionResult] = []
        while True:
            last = self._last_applied_key.get(peer_id)
            if last is None:
                break
            last_epoch, last_seq = last
            next_key = (last_epoch, last_seq + 1)
            entry = buffer.pop(next_key, None)
            if entry is None:
                break
            buffered_obs, buffered_old_status = entry
            buffered_dedup_key = buffered_obs.to_json()
            if buffered_dedup_key in self._seen_observations:
                self._touch_cache(
                    self._last_applied_key,
                    peer_id,
                    (buffered_obs.epoch, buffered_obs.sequence),
                )
                continue
            before = self._last_applied_key.get(peer_id)
            try:
                result = self._apply_observation(
                    buffered_obs, buffered_old_status, buffered_dedup_key
                )
            except Exception:
                buffer[next_key] = entry
                buffer.move_to_end(next_key, last=False)
                raise
            after = self._last_applied_key.get(peer_id)
            if after == before:
                self._touch_cache(
                    self._seen_observations, buffered_dedup_key, None
                )
                self._touch_cache(
                    self._last_applied_key,
                    peer_id,
                    (buffered_obs.epoch, buffered_obs.sequence),
                )
                metadata = dict(result.metadata)
                metadata["processed_watermark_advanced"] = True
                result = dataclass_replace(result, metadata=metadata)
            flushed.append(result)
        if not buffer:
            self._reorder_buffer.pop(peer_id, None)
        return flushed

    def _apply_observation(
        self,
        obs: PeerObservation,
        old_status: str,
        dedup_key: str,
    ) -> StateTransitionResult:
        evidences = self._equivocation_log.record_observation(obs)
        if evidences:
            self._reputation.record_equivocation(obs.observer_id)
            return self._reject(
                obs,
                DecisionType.EQUIVOCATION,
                f"{len(evidences)} equivocation(s): observer "
                f"{obs.observer_id} issued contradictory reports",
                old_status,
                equivocation_evidences=tuple(evidences),
            )

        quorum_passes = self._check_quorum(obs)
        quorum_vote = self._build_quorum_vote(obs, quorum_passes)
        if not quorum_passes:
            return self._reject(
                obs,
                DecisionType.INSUFFICIENT_QUORUM,
                "Insufficient independent witness quorum "
                f"({quorum_vote.witness_count} witnesses, "
                f"{quorum_vote.unique_observer_ids} unique observers, "
                f"{quorum_vote.unique_provenance_buckets} provenance buckets)",
                old_status,
                quorum_vote=quorum_vote,
            )

        weighted = self._weight_votes(obs, quorum_vote)
        if not weighted.passes:
            return self._reject(
                obs,
                DecisionType.INSUFFICIENT_QUORUM,
                f"Weighted quorum score {weighted.weighted_score:.2f} "
                f"< threshold {weighted.threshold}",
                old_status,
                quorum_vote=quorum_vote,
                weighted_quorum=weighted,
            )

        sybil = self._check_sybil_correlation(obs)
        decision_type = DecisionType.APPROVED
        if sybil.signal in (SybilSignal.STRONG, SybilSignal.WEAK):
            decision_type = DecisionType.SYBIL_FLAGGED

        audit_entry = self._audit_log.append(
            peer_id=obs.peer_id,
            old_status=old_status,
            new_status=obs.observation_type.value,
            witnesses=tuple(weighted.weighted_by_observer.keys()),
            signer=self._signer,
        )
        self._touch_cache(self._seen_observations, dedup_key, None)
        self._touch_cache(
            self._last_applied_key, obs.peer_id, (obs.epoch, obs.sequence)
        )
        self._k_bucket.update(obs.peer_id, obs.timestamp)

        return StateTransitionResult(
            accepted=True,
            decision_type=decision_type,
            peer_id=obs.peer_id,
            epoch=obs.epoch,
            observer_id=obs.observer_id,
            quorum_vote=quorum_vote,
            weighted_quorum=weighted,
            sybil_correlation=sybil,
            audit_entry=audit_entry,
            metadata={
                "local_id": self._local_id,
                "weighted_quorum_threshold": self._weighted_quorum_threshold,
            },
        )

    def _check_quorum(self, obs: PeerObservation) -> bool:
        return validate_witness_quorum(obs)

    def _build_quorum_vote(
        self, obs: PeerObservation, passes: bool
    ) -> QuorumVote:
        witnesses = obs.witness_set
        observer_ids = tuple(w.observer_id for w in witnesses)
        provenance_buckets = tuple(
            provenance_bucket(w.observer_provenance) for w in witnesses
        )
        return QuorumVote(
            passes=passes,
            witness_count=len(witnesses),
            unique_observer_ids=len(set(observer_ids)),
            unique_provenance_buckets=len(set(provenance_buckets)),
            witness_ids=observer_ids,
            witness_provenance_buckets=provenance_buckets,
        )

    def _weight_votes(
        self, obs: PeerObservation, quorum_vote: QuorumVote
    ) -> WeightedQuorum:
        weighted_by_bucket: Dict[str, float] = {}
        for witness, bucket in zip(
            obs.witness_set, quorum_vote.witness_provenance_buckets
        ):
            weight = self._reputation.reputation_weight(witness.observer_id)
            weighted_by_bucket[bucket] = max(
                weighted_by_bucket.get(bucket, 0.0), weight
            )
        total = sum(weighted_by_bucket.values())
        weighted_by_observer = {
            witness.observer_id: self._reputation.reputation_weight(
                witness.observer_id
            )
            for witness in obs.witness_set
        }
        return WeightedQuorum(
            passes=total >= self._weighted_quorum_threshold,
            weighted_score=total,
            threshold=self._weighted_quorum_threshold,
            weighted_by_observer=weighted_by_observer,
        )

    def _check_sybil_correlation(
        self, obs: PeerObservation
    ) -> SybilCorrelation:
        correlated_pairs: List[Tuple[str, str]] = []
        for witness in obs.witness_set:
            if self._k_bucket.is_correlated(
                obs.peer_id, witness.peer_id, self._sybil_proximity_bits
            ):
                correlated_pairs.append((obs.peer_id, witness.peer_id))

        bucket_index = self._k_bucket.bucket_for(obs.peer_id)
        peers_in_bucket = self._k_bucket.peers_in_bucket(bucket_index)
        witness_ids = {w.peer_id for w in obs.witness_set}
        bucket_overlap = [peer for peer in peers_in_bucket if peer in witness_ids]

        if len(correlated_pairs) >= 2 or len(bucket_overlap) >= 2:
            signal = SybilSignal.STRONG
        elif correlated_pairs or bucket_overlap:
            signal = SybilSignal.WEAK
        else:
            signal = SybilSignal.NONE

        return SybilCorrelation(
            signal=signal,
            correlated_pairs=correlated_pairs,
            witness_bucket_index=bucket_index,
            details={
                "witness_ids": sorted(witness_ids),
                "peers_in_bucket": peers_in_bucket,
                "bucket_overlap_count": len(bucket_overlap),
            },
        )

    def _reject(
        self,
        obs: PeerObservation,
        decision_type: DecisionType,
        reason: str,
        old_status: str,
        *,
        equivocation_evidences: Tuple[EquivocationEvidence, ...] = (),
        quorum_vote: Optional[QuorumVote] = None,
        weighted_quorum: Optional[WeightedQuorum] = None,
    ) -> StateTransitionResult:
        audit_entry = self._audit_log.append(
            peer_id=obs.peer_id,
            old_status=old_status,
            new_status=decision_type.value,
            witnesses=(),
            signer=self._signer,
        )
        return StateTransitionResult(
            accepted=False,
            decision_type=decision_type,
            peer_id=obs.peer_id,
            epoch=obs.epoch,
            observer_id=obs.observer_id,
            rejection_reason=reason,
            equivocation_evidences=equivocation_evidences,
            quorum_vote=quorum_vote,
            weighted_quorum=weighted_quorum,
            audit_entry=audit_entry,
        )
