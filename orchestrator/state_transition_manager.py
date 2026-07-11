"""
orchestrator/state_transition_manager.py — PR #203/#205: Phase 1b Security Decision Pipeline.

StateTransitionManager evaluates a PeerObservation through the G1/G4/G5/G6/G8
security pipeline and produces a terminal, audited decision:

  [1] Dedup / monotonic gate     — reject replays and out-of-order sequences
  [2] Equivocation gate (G4)     — cheapest check; record evidence & penalize reputation
  [3] Witness quorum (G1)        — uses provenance_bucket() internally
  [4] Reputation-weighted quorum (G5) — reject if weighted score < threshold
  [5] Sybil correlation (G6)     — flag only, does not block
  [6] Audit commit (G8)          — every terminal decision is audited, including rejections

This is the *security decision* layer, not the full DELIVERABLE-2 peer-state
hysteresis machine. It returns a terminal decision and audit hash; callers
decide how to apply that decision to peer display state (see PeerRecord).

Spec reference: docs/phase-0-specifications/2026-07-11-state-transition-manager-integration-plan.md
Pattern source: PATTERN-MULTIAGENT-EXECUTION-PLAN.md (Iterations 1-10)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
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
    """Observation failed a structural gate (stale, duplicate, malformed)."""


class DecisionType(str, Enum):
    """Terminal decision categories produced by the security pipeline."""

    APPROVED = "approved"
    EQUIVOCATION = "equivocation"
    INSUFFICIENT_QUORUM = "insufficient_quorum"
    STALE = "stale"
    DUPLICATE = "duplicate"
    SYBIL_FLAGGED = "sybil_flagged"


class SybilSignal(str, Enum):
    """Strength of the Sybil correlation signal."""

    STRONG = "strong"  # is_correlated True for multiple witnesses / known peers
    WEAK = "weak"       # same bucket but not within proximity_bits
    NONE = "none"


@dataclass(frozen=True)
class QuorumVote:
    """Structured result of the witness quorum gate."""

    passes: bool
    witness_count: int
    unique_observer_ids: int
    unique_provenance_buckets: int
    witness_ids: Tuple[str, ...] = ()
    witness_provenance_buckets: Tuple[str, ...] = ()


@dataclass(frozen=True)
class WeightedQuorum:
    """Quorum after reputation weighting."""

    passes: bool
    weighted_score: float
    threshold: float
    weighted_by_observer: Dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class SybilCorrelation:
    """Correlation signal between the observed peer and its witnesses / known peers."""

    signal: SybilSignal
    correlated_pairs: List[Tuple[str, str]] = field(default_factory=list)
    witness_bucket_index: Optional[int] = None
    details: Dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class StateTransitionResult:
    """
    Immutable outcome of evaluating one observation through the security pipeline.

    accepted is True for APPROVED and SYBIL_FLAGGED (Sybil correlation is a
    heuristic signal carried forward for downstream review, not proof of
    malice like equivocation). Only insufficient/weighted-quorum failures,
    equivocation, staleness, and duplicates set accepted=False.
    """

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


class StateTransitionManager:
    """
    Evaluate a PeerObservation through the G1/G4/G5/G6/G8 security pipeline.

    Args:
        local_id: This node's own peer ID (used for KBucketTable and metadata).
        equivocation_log: EquivocationLog instance (G4).
        k_bucket: KBucketTable for Sybil distance-bucketing correlation (G6).
        audit_log: AuditLog instance for hash-chain commitment (G8).
        reputation: ReputationLedger instance (G5). Read via reputation_weight()
            for vote weighting; written via record_equivocation() on detection.
        weighted_quorum_threshold: Minimum summed reputation-weighted score
            (by independent provenance bucket) required to pass step [4].
        sybil_proximity_bits: XOR-distance proximity threshold for G6 correlation.
        signer: Optional Callable(content_bytes) -> signature, forwarded to
            every AuditLog.append() call.

    Concurrency: evaluate_observation() serializes calls per peer_id via a
    per-peer asyncio.Lock (not a single global lock, and not threading.Lock —
    asyncio.Lock is the correct primitive for serializing coroutines sharing
    an event loop; see the plan doc's Concurrency Model section and
    docs/phase-0-specifications/2026-07-11-PHASE-2-BLOCKERS.md for why the
    alternatives considered were rejected). Per-peer (not global) locking is
    intentional: unrelated peers' observations must not block each other,
    only concurrent evaluations for the *same* peer need serializing.
    """

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
    ):
        self._local_id = local_id
        self._equivocation_log = equivocation_log
        self._k_bucket = k_bucket
        self._audit_log = audit_log
        self._reputation = reputation
        self._weighted_quorum_threshold = weighted_quorum_threshold
        self._sybil_proximity_bits = sybil_proximity_bits
        self._signer = signer

        # Per-peer concurrency and idempotency state.
        self._peer_locks: Dict[str, asyncio.Lock] = {}
        self._last_applied_key: Dict[str, Tuple[int, int]] = {}  # peer_id -> (epoch, sequence)
        self._seen_observations: set[str] = set()  # dedup key: canonical observation digest

    async def evaluate_observation(
        self,
        obs: PeerObservation,
        old_status: str = "UNKNOWN",
    ) -> StateTransitionResult:
        """
        End-to-end security pipeline for one observation.

        Args:
            obs: The incoming PeerObservation.
            old_status: Current display/peer status, used for the audit log.
                Callers that do not yet track peer state may pass "UNKNOWN".

        Returns:
            StateTransitionResult with accepted/rejected decision, audit entry,
            and metadata.
        """
        lock = self._peer_locks.setdefault(obs.peer_id, asyncio.Lock())
        async with lock:
            return self._evaluate_locked(obs, old_status)

    # ──────────────────────────────────────────────────────────────────────────
    # Synchronous core — all dependencies are in-memory and synchronous; the
    # per-peer asyncio.Lock in evaluate_observation() is what needs to be async.
    # ──────────────────────────────────────────────────────────────────────────

    def _evaluate_locked(
        self,
        obs: PeerObservation,
        old_status: str,
    ) -> StateTransitionResult:
        # [1] Dedup / monotonic gate — cheapest possible check, before any
        # module call. Duplicate/stale observations should never even reach
        # the equivocation log (they're not new information).
        dedup_key = obs.to_json()
        if dedup_key in self._seen_observations:
            return self._reject(obs, DecisionType.DUPLICATE, "Duplicate observation", old_status)

        last = self._last_applied_key.get(obs.peer_id)
        if last is not None:
            last_epoch, last_seq = last
            if obs.epoch < last_epoch or (obs.epoch == last_epoch and obs.sequence <= last_seq):
                return self._reject(
                    obs,
                    DecisionType.STALE,
                    f"Out-of-order observation (epoch={obs.epoch}, seq={obs.sequence} <= last {last})",
                    old_status,
                )

        if obs.is_stale:
            return self._reject(obs, DecisionType.STALE, "Observation TTL expired", old_status)

        # [2] Equivocation gate (G4) — cheapest remaining check, fail fast.
        evidences = self._equivocation_log.record_observation(obs)
        if evidences:
            # Penalize obs.observer_id (the reporter of THIS contradictory
            # observation) — not EquivocationEvidence.observer_provenance,
            # which identifies a network origin, not an accountable identity,
            # and multiple observers can legitimately share a provenance
            # bucket. obs.observer_id is always available here (it's the
            # triggering observation's own field), so no provenance fallback
            # is needed.
            self._reputation.record_equivocation(obs.observer_id)
            return self._reject(
                obs,
                DecisionType.EQUIVOCATION,
                f"{len(evidences)} equivocation(s): observer {obs.observer_id} issued contradictory reports",
                old_status,
                equivocation_evidences=tuple(evidences),
            )

        # [3] Witness quorum (G1)
        quorum_passes = self._check_quorum(obs)
        quorum_vote = self._build_quorum_vote(obs, quorum_passes)
        if not quorum_passes:
            return self._reject(
                obs,
                DecisionType.INSUFFICIENT_QUORUM,
                f"Insufficient independent witness quorum ({quorum_vote.witness_count} witnesses, "
                f"{quorum_vote.unique_observer_ids} unique observers, "
                f"{quorum_vote.unique_provenance_buckets} unique provenance buckets)",
                old_status,
                quorum_vote=quorum_vote,
            )

        # [4] Reputation-weighted quorum (G5) — the quorum gate above is a
        # binary independence check; this step additionally requires the
        # *trust-weighted* score to clear a threshold, so a quorum of
        # low-reputation witnesses (e.g. previously equivocating observers)
        # cannot approve an observation just by being numerically distinct.
        weighted = self._weight_votes(obs, quorum_vote)
        if not weighted.passes:
            return self._reject(
                obs,
                DecisionType.INSUFFICIENT_QUORUM,
                f"Weighted quorum score {weighted.weighted_score:.2f} < threshold {weighted.threshold}",
                old_status,
                quorum_vote=quorum_vote,
                weighted_quorum=weighted,
            )

        # [5] Sybil correlation (G6) — flag only, does not block. Per
        # DELIVERABLE-2 §5.3's own pseudocode ("Log but don't reject (just
        # flag)"), Sybil correlation is a heuristic signal, not proof of
        # malice like equivocation — a false-positive hard-reject would drop
        # a legitimate peer's observation on circumstantial network-topology
        # evidence alone.
        sybil = self._check_sybil_correlation(obs)
        decision_type = DecisionType.APPROVED
        if sybil.signal in (SybilSignal.STRONG, SybilSignal.WEAK):
            decision_type = DecisionType.SYBIL_FLAGGED

        # [6] Audit commit (G8) — terminal decision, always recorded.
        new_status = decision_type.value
        audit_entry = self._audit_log.append(
            peer_id=obs.peer_id,
            old_status=old_status,
            new_status=new_status,
            witnesses=tuple(weighted.weighted_by_observer.keys()),
            signer=self._signer,
        )

        # Mark observation applied for monotonic ordering / dedup.
        self._seen_observations.add(dedup_key)
        self._last_applied_key[obs.peer_id] = (obs.epoch, obs.sequence)

        return StateTransitionResult(
            accepted=decision_type in (DecisionType.APPROVED, DecisionType.SYBIL_FLAGGED),
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

    # ──────────────────────────────────────────────────────────────────────────
    # Private: step helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _check_quorum(self, obs: PeerObservation) -> bool:
        return validate_witness_quorum(obs)

    def _build_quorum_vote(self, obs: PeerObservation, passes: bool) -> QuorumVote:
        witnesses = obs.witness_set
        observer_ids = tuple(w.observer_id for w in witnesses)
        provenance_buckets = tuple(provenance_bucket(w.observer_provenance) for w in witnesses)
        return QuorumVote(
            passes=passes,
            witness_count=len(witnesses),
            unique_observer_ids=len(set(observer_ids)),
            unique_provenance_buckets=len(set(provenance_buckets)),
            witness_ids=observer_ids,
            witness_provenance_buckets=provenance_buckets,
        )

    def _weight_votes(self, obs: PeerObservation, quorum_vote: QuorumVote) -> WeightedQuorum:
        # Weight by independent provenance bucket (max weight per bucket, not
        # summed) so multiple Sybils in the same bucket cannot inflate the
        # score just by being counted individually.
        weighted_by_bucket: Dict[str, float] = {}
        for witness, bucket in zip(obs.witness_set, quorum_vote.witness_provenance_buckets):
            weight = self._reputation.reputation_weight(witness.observer_id)
            weighted_by_bucket[bucket] = max(weighted_by_bucket.get(bucket, 0.0), weight)

        total = sum(weighted_by_bucket.values())
        weighted_by_observer = {
            w.observer_id: self._reputation.reputation_weight(w.observer_id) for w in obs.witness_set
        }
        return WeightedQuorum(
            passes=total >= self._weighted_quorum_threshold,
            weighted_score=total,
            threshold=self._weighted_quorum_threshold,
            weighted_by_observer=weighted_by_observer,
        )

    def _check_sybil_correlation(self, obs: PeerObservation) -> SybilCorrelation:
        correlated_pairs: List[Tuple[str, str]] = []

        # Signal 1: the observed peer is suspiciously close to one of its own
        # witnesses in XOR-distance ID-space (a witness deliberately
        # generated near the peer it's vouching for).
        for witness in obs.witness_set:
            if self._k_bucket.is_correlated(obs.peer_id, witness.peer_id, self._sybil_proximity_bits):
                correlated_pairs.append((obs.peer_id, witness.peer_id))

        # Signal 2: many witnesses already share the observed peer's k-bucket.
        bucket_index = self._k_bucket.bucket_for(obs.peer_id)
        peers_in_bucket = self._k_bucket.peers_in_bucket(bucket_index)
        witness_ids = {w.peer_id for w in obs.witness_set}
        bucket_overlap = [p for p in peers_in_bucket if p in witness_ids]

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
        # Audit rejection as a terminal decision too (old_status -> decision_type)
        # — G4/G8 are forensics gaps otherwise; rejections are the events most
        # likely to need later investigation.
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
