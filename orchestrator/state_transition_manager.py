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
    """Observation failed a structural gate (stale, duplicate, malformed)."""


class DecisionType(str, Enum):
    """Terminal decision categories produced by the security pipeline."""

    APPROVED = "approved"
    EQUIVOCATION = "equivocation"
    INSUFFICIENT_QUORUM = "insufficient_quorum"
    STALE = "stale"
    DUPLICATE = "duplicate"
    SYBIL_FLAGGED = "sybil_flagged"
    # Sequence arrived ahead of a gap (epoch matches, sequence > last_applied
    # + 1); held in the per-peer reorder buffer (P9, PATTERN-SYNTHESIS.md)
    # pending the missing sequence. Not a terminal decision -- not `accepted`,
    # state has not transitioned yet.
    BUFFERED = "buffered"


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
    equivocation, staleness, duplicates, and BUFFERED set accepted=False.

    flushed carries the results of any reorder-buffered successor
    observations that this observation's application unblocked (P9,
    PATTERN-SYNTHESIS.md) -- e.g. this result is for sequence 2, and
    sequence 3 was already buffered waiting on it; sequence 3's own
    (now-applied) result appears here. Empty for the common case where
    nothing was buffered. Kept as an *additive* field rather than changing
    evaluate_observation()'s return type to a list, so every existing caller
    reading a single StateTransitionResult keeps working unmodified.
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
    flushed: Tuple["StateTransitionResult", ...] = ()


class _RefCountedLock:
    """asyncio.Lock wrapper that tracks how many in-flight callers are
    waiting on / holding it, so StateTransitionManager can evict the entry
    from _peer_locks once nobody needs it — otherwise _peer_locks grows by
    one entry per distinct peer_id ever seen and never shrinks (a Sybil
    flood of throwaway peer_ids is an unbounded-memory DoS vector otherwise).

    Safe without extra synchronization: asyncio is single-threaded, so
    ref_count increments/decrements and the dict get/del in
    evaluate_observation() never interleave with each other mid-operation —
    only at await points, and there are none between the check and the
    delete.
    """

    __slots__ = ("lock", "ref_count")

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.ref_count = 0


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
        max_cache_size: Bound on _seen_observations and _last_applied_key
            (P18, PATTERN-SYNTHESIS.md — LRU eviction once exceeded). Also
            caps memory for both, independent of how many distinct
            observations/peers have ever been seen. Lower values are useful
            in tests; production default (10000) matches the pattern doc's
            replay-cache sizing.
        reorder_buffer_max: Bound on the per-peer P9 reorder buffer. An
            observation that arrives with a gap larger than this many
            missing sequences is rejected (STALE) rather than buffered
            indefinitely.

    Concurrency: evaluate_observation() serializes calls per peer_id via a
    per-peer asyncio.Lock (not a single global lock, and not threading.Lock —
    asyncio.Lock is the correct primitive for serializing coroutines sharing
    an event loop; see the plan doc's Concurrency Model section and
    docs/phase-0-specifications/2026-07-11-PHASE-2-BLOCKERS.md for why the
    alternatives considered were rejected). Per-peer (not global) locking is
    intentional: unrelated peers' observations must not block each other,
    only concurrent evaluations for the *same* peer need serializing. The
    lock itself is ref-counted and evicted once idle (_RefCountedLock) so
    _peer_locks does not grow unbounded across many distinct peer_ids.
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

        # Per-peer concurrency (ref-counted, evicted once idle — see
        # _RefCountedLock) and idempotency state.
        self._peer_locks: Dict[str, _RefCountedLock] = {}

        # P18 (PATTERN-SYNTHESIS.md): bounded LRU caches, not unbounded
        # dict/set growth. OrderedDict gives O(1) move-to-end (mark most
        # recently used) and O(1) popitem(last=False) (evict least recently
        # used) — same complexity as a plain dict/set, bounded memory.
        # peer_id -> (epoch, sequence); LRU-evicting this means a peer that
        # falls out of the cache loses monotonic-ordering protection on its
        # next observation (accepted as if fresh) — an accepted tradeoff of
        # bounding memory against unbounded distinct peer_ids, not a
        # correctness bug: see class docstring `max_cache_size`.
        self._last_applied_key: "OrderedDict[str, Tuple[int, int]]" = OrderedDict()
        # dedup key (canonical observation digest) -> None; used as an
        # ordered set.
        self._seen_observations: "OrderedDict[str, None]" = OrderedDict()

        # P9 (PATTERN-SYNTHESIS.md): peer_id -> {(epoch, sequence): (obs, old_status)},
        # capped at _reorder_buffer_max entries per peer.
        self._reorder_buffer: Dict[str, "OrderedDict[Tuple[int, int], Tuple[PeerObservation, str]]"] = {}

    def _touch_cache(self, cache: "OrderedDict", key, value) -> None:
        """Insert/refresh `key` in an LRU-bounded OrderedDict cache, evicting
        the least-recently-used entry once _max_cache_size is exceeded."""
        cache[key] = value
        cache.move_to_end(key)
        if len(cache) > self._max_cache_size:
            cache.popitem(last=False)

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
        entry = self._peer_locks.setdefault(obs.peer_id, _RefCountedLock())
        entry.ref_count += 1
        try:
            async with entry.lock:
                return self._evaluate_locked(obs, old_status)
        finally:
            entry.ref_count -= 1
            if entry.ref_count == 0:
                # Only evict if this is still the entry we incremented — a
                # concurrent caller cannot have swapped it (single-threaded
                # event loop, no await between the check and the delete).
                if self._peer_locks.get(obs.peer_id) is entry:
                    del self._peer_locks[obs.peer_id]

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
            # P9 (PATTERN-SYNTHESIS.md): a gap within the SAME epoch — hold it
            # in the reorder buffer rather than rejecting outright. Only a
            # same-epoch gap is bufferable: an epoch advance is treated as a
            # fresh sequence (existing behavior, unchanged) since the pattern
            # doc scopes the buffer's watermark to "epoch matches".
            if obs.epoch == last_epoch and obs.sequence > last_seq + 1:
                return self._buffer_observation(obs, old_status)

        if obs.is_stale:
            return self._reject(obs, DecisionType.STALE, "Observation TTL expired", old_status)

        result = self._apply_observation(obs, old_status, dedup_key)
        flushed = self._flush_reorder_buffer(obs.peer_id)
        if flushed:
            result = dataclass_replace(result, flushed=tuple(flushed))
        return result

    def _buffer_observation(self, obs: PeerObservation, old_status: str) -> StateTransitionResult:
        """Hold an out-of-order-ahead observation (P9) pending the missing
        sequence. Not a terminal decision — no audit entry, not marked seen —
        so the same observation re-submitted later still resolves correctly
        once the gap fills or the buffer evicts it."""
        buffer = self._reorder_buffer.setdefault(obs.peer_id, OrderedDict())
        key = (obs.epoch, obs.sequence)
        if key not in buffer and len(buffer) >= self._reorder_buffer_max:
            # Buffer capacity guard (P5/T5 in PATTERN-SYNTHESIS.md's DoS
            # framing): an attacker flooding many far-future sequences for
            # one peer_id must not grow memory unboundedly. Reject as STALE
            # — from the caller's perspective this observation cannot be
            # applied in order right now, same practical outcome as a
            # too-far-in-the-past rejection, even though the cause differs.
            return self._reject(
                obs,
                DecisionType.STALE,
                f"Reorder buffer full for peer {obs.peer_id} (max {self._reorder_buffer_max}); "
                f"discarding out-of-order observation (seq={obs.sequence})",
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
        """After applying an observation, drain any buffered successors that
        are now next-in-sequence, applying each in turn (which may itself
        unblock the next one — hence the loop, not a single check)."""
        buffer = self._reorder_buffer.get(peer_id)
        if not buffer:
            return []
        flushed: List[StateTransitionResult] = []
        while True:
            last_epoch, last_seq = self._last_applied_key[peer_id]
            next_key = (last_epoch, last_seq + 1)
            entry = buffer.pop(next_key, None)
            if entry is None:
                break
            buffered_obs, buffered_old_status = entry
            buffered_dedup_key = buffered_obs.to_json()
            if buffered_dedup_key in self._seen_observations:
                continue  # defensive; should not happen given the gap-gate above
            flushed.append(self._apply_observation(buffered_obs, buffered_old_status, buffered_dedup_key))
        if not buffer:
            del self._reorder_buffer[peer_id]
        return flushed

    def _apply_observation(
        self,
        obs: PeerObservation,
        old_status: str,
        dedup_key: str,
    ) -> StateTransitionResult:
        """Steps [2]-[6] of the pipeline: equivocation through audit commit.
        Shared by the primary evaluate_observation() path and by
        _flush_reorder_buffer() applying a previously-buffered observation
        now that it is next-in-sequence — both need identical gate/audit
        behavior, just reached via a different entry point."""
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
        # Naming clarity: for an accepted decision (APPROVED or
        # SYBIL_FLAGGED — the only two reachable here, since every rejecting
        # gate above already returned), the audit trail's new_status should
        # reflect the peer's actual reachability (REACHABLE/UNREACHABLE),
        # not the internal decision label — SYBIL_FLAGGED in the status
        # column reads as if the peer itself were rejected, when the
        # observation was in fact accepted with a heuristic flag attached.
        if decision_type in (DecisionType.APPROVED, DecisionType.SYBIL_FLAGGED):
            new_status = obs.observation_type.value
        else:
            new_status = decision_type.value
        audit_entry = self._audit_log.append(
            peer_id=obs.peer_id,
            old_status=old_status,
            new_status=new_status,
            witnesses=tuple(weighted.weighted_by_observer.keys()),
            signer=self._signer,
        )

        # Mark observation applied for monotonic ordering / dedup (P18
        # bounded LRU — see _touch_cache).
        self._touch_cache(self._seen_observations, dedup_key, None)
        self._touch_cache(self._last_applied_key, obs.peer_id, (obs.epoch, obs.sequence))

        # P2 (PATTERN-SYNTHESIS.md): maintain the distance-metric routing
        # table on every successful observation, so k-bucket membership
        # reflects who is actually being heard from (not just who was ever
        # seen once) — only on APPROVED/SYBIL_FLAGGED, never on a rejected
        # gate, matching "after an observation successfully clears all
        # gates" in the plan.
        self._k_bucket.update(obs.peer_id, obs.timestamp)

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
