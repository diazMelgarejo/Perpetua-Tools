"""
orchestrator/state_transition_manager.py — PR #203: Phase 1b Multiagent Orchestration.

StateTransitionManager orchestrates the 5-step security pipeline for peer observation
validation:

  [1] Equivocation gate (G4) — reject malicious early
  [2] Witness quorum (G1) — consensus check
  [3] Reputation weighting (G5) — adjust votes by agent reputation
  [4] Sybil correlation (G6) — cross-check distance bucket + provenance
  [5] Audit commit (G8) — record decision to hash chain

This module wires the isolated security modules (G1, G4, G6, G8) and reputation stub (G5)
into a working pipeline for Phase 1b integration testing.

Spec reference: docs/phase-0-specifications/2026-07-11-pr203-multiagent-orchestration.md
Pattern source: PATTERN-MULTIAGENT-EXECUTION-PLAN.md (Iterations 1-10)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from orchestrator.audit_log import AuditLog, AuditEntry
from orchestrator.distance_bucket import KBucketTable
from orchestrator.equivocation import EquivocationLog, EquivocationEvidence
from orchestrator.membership import PeerObservation, ObservationType
from orchestrator.provenance import provenance_bucket
from orchestrator.reputation import ReputationLedger
from orchestrator.witness_quorum import validate_witness_quorum


@dataclass(frozen=True)
class EquivocationCheck:
    """Result of equivocation gate (G4) check."""

    is_equivocal: bool
    reason: str = ""
    evidence: list[EquivocationEvidence] = field(default_factory=list)


@dataclass(frozen=True)
class QuorumCheck:
    """Result of witness quorum (G1) validation."""

    passes: bool
    votes: Dict[str, float] = field(default_factory=dict)
    message: str = ""


@dataclass(frozen=True)
class SybilSignals:
    """Cross-correlated Sybil signals from G6 + G1."""

    correlated_ids: Dict[str, str] = field(default_factory=dict)
    provenance_clustering: Dict[str, int] = field(default_factory=dict)
    overall_risk: str = "low"  # "low", "medium", "high"


@dataclass(frozen=True)
class StateTransitionResult:
    """
    Immutable result of end-to-end observation validation.

    Fields:
        accepted: True if the observation was committed to the audit chain —
            "approved" and "sybil_flagged" both accept (Sybil correlation is
            a carried-forward heuristic flag, not a hard reject); only the
            earlier gate failures (equivocation, quorum) set this False.
        decision_type: One of "malicious", "insufficient_quorum", "approved",
            "sybil_flagged".
        quorum_votes: Weighted votes by agent_id (post-G5 reputation weighting).
        sybil_signals: Cross-referenced signals from G6 + G1.
        audit_hash: G8 reference hash from audit log (empty if rejected before audit).
        rejection_reason: Human-readable reason if accepted=False.
        metadata: Additional context (e.g., step timing, confidence scores).
    """

    accepted: bool
    decision_type: str
    quorum_votes: Dict[str, float] = field(default_factory=dict)
    sybil_signals: Optional[SybilSignals] = None
    audit_hash: str = ""
    rejection_reason: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


class StateTransitionManager:
    """
    Orchestrate the 5-step peer observation validation pipeline.

    This manager sequences equivocation detection (G4), witness quorum validation (G1),
    reputation-weighted vote adjustment (G5), Sybil correlation checking (G6), and
    audit log commitment (G8) into a single coherent gate for peer state transitions.

    Pattern: Each step is a potential fail-fast gate; later steps are skipped if
    an earlier gate rejects. Accepted observations flow through all 5 steps and
    commit to the audit chain (G8).

    Args:
        equivocation_log: EquivocationLog instance (G4).
        witness_quorum_fn: Function to validate witness quorum (G1).
        k_bucket: KBucketTable for Sybil distance-bucketing correlation (G6).
        audit_log: AuditLog instance for hash-chain commitment (G8).
        reputation_ledger: Optional ReputationLedger instance (G5). When
            provided, closes the G4->G5 feedback loop: an equivocation
            detection (step 1) immediately penalizes the equivocating
            observer's reputation via record_equivocation(), and vote
            weighting (step 3) reads live scores via reputation_weight().
            If None, reputation weighting falls back to reputation_fn (or
            a neutral 1.0 stub), and equivocation detection cannot
            penalize reputation at all — TODO-stm-reputation-feedback
            (job board) tracked this gap; passing a ledger here closes it.
        reputation_fn: Callable(observer_id) -> float for vote weighting (G5).
            Returns reputation weight [0.0, ∞). Ignored if reputation_ledger
            is provided. Defaults to 1.0 (stub) if neither is given.
    """

    def __init__(
        self,
        equivocation_log: EquivocationLog,
        k_bucket: KBucketTable,
        audit_log: AuditLog,
        reputation_ledger: Optional[ReputationLedger] = None,
        reputation_fn: Optional[Callable[[str], float]] = None,
    ):
        """Initialize StateTransitionManager with security modules."""
        self._equivocation_log = equivocation_log
        self._k_bucket = k_bucket
        self._audit_log = audit_log
        self._reputation_ledger = reputation_ledger
        if reputation_ledger is not None:
            self._reputation_fn = reputation_ledger.reputation_weight
        else:
            # G5 stub: returns 1.0 (neutral) until a ledger is wired in
            self._reputation_fn = reputation_fn or (lambda agent_id: 1.0)

    async def evaluate_observation(
        self,
        obs: PeerObservation,
        quorum_members: Optional[list[str]] = None,
    ) -> StateTransitionResult:
        """
        End-to-end observation validation pipeline.

        Sequence:
          [1] Equivocation gate (G4) → reject if malicious
          [2] Quorum validation (G1) → reject if insufficient consensus
          [3] Reputation weighting (G5) → adjust vote weights
          [4] Sybil correlation (G6) → flag if both G6+G1 Sybil signals present
          [5] Audit commit (G8) → hash-chain the decision

        Args:
            obs: PeerObservation to evaluate.
            quorum_members: Optional list of observer IDs to include in quorum
                (defaults to obs.witness_set observer_ids).

        Returns:
            StateTransitionResult with acceptance decision and detailed metadata.
        """
        start_time = time.time()

        # [1] Equivocation gate (G4) — cheapest, fail fast
        eq_check = await self._check_equivocation(obs)
        if eq_check.is_equivocal:
            return StateTransitionResult(
                accepted=False,
                decision_type="malicious",
                rejection_reason=f"Equivocation detected: {eq_check.reason}",
                metadata={"step_1_equivocation_check": True, "elapsed_ms": (time.time() - start_time) * 1000},
            )

        # [2] Quorum validation (G1) — quorum must pass before weighting
        quorum_check = await self._check_quorum(obs, quorum_members)
        if not quorum_check.passes:
            return StateTransitionResult(
                accepted=False,
                decision_type="insufficient_quorum",
                quorum_votes=quorum_check.votes,
                rejection_reason=quorum_check.message,
                metadata={"step_2_quorum_check": True, "elapsed_ms": (time.time() - start_time) * 1000},
            )

        # [3] Reputation weighting (G5) — adjust quorum votes by agent reputation
        weighted_votes = self._weight_votes(quorum_check.votes, obs.observer_id)

        # [4] Sybil correlation (G6) — cross-check distance bucket + provenance.
        # Per the design this pipeline implements (DELIVERABLE-2 §5.3's
        # pseudocode: "Log but don't reject (just flag)"), Sybil correlation
        # is a heuristic signal, not proof of malice like equivocation — a
        # false-positive hard-reject would drop a legitimate peer's
        # observation on circumstantial network-topology evidence alone.
        # Flag it (decision_type + sybil_signals carry the risk forward for
        # downstream/human review) but still let the observation through to
        # the audit commit step.
        sybil_signals = await self._check_sybil_correlation(obs)
        decision_type = "sybil_flagged" if sybil_signals.overall_risk == "high" else "approved"

        # [5] Audit commit (G8) — record decision to hash chain
        audit_entry = await self._commit_decision(
            obs,
            quorum_votes=weighted_votes,
            sybil=sybil_signals,
        )

        return StateTransitionResult(
            accepted=True,
            decision_type=decision_type,
            quorum_votes=weighted_votes,
            sybil_signals=sybil_signals,
            audit_hash=audit_entry.hash,
            metadata={
                "all_steps_passed": True,
                "audit_sequence": audit_entry.sequence_number,
                "elapsed_ms": (time.time() - start_time) * 1000,
            },
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Private: Step implementations
    # ──────────────────────────────────────────────────────────────────────────

    async def _check_equivocation(self, obs: PeerObservation) -> EquivocationCheck:
        """
        [Step 1] Equivocation gate (G4).

        Call equivocation_log.record_observation() to detect and log any
        contradictory reports from the same observer for the same peer/epoch.

        On detection, if a ReputationLedger was provided, immediately penalize
        the equivocating observer via record_equivocation() -- this is the
        G4->G5 feedback loop TODO-stm-reputation-feedback tracked. Penalizes
        obs.observer_id (the actual peer identity), not observer_provenance
        (the network-origin string) -- provenance identifies where a report
        came from, not who is accountable for issuing it, and multiple
        observers can legitimately share a provenance bucket.

        Returns:
            EquivocationCheck with is_equivocal=True if contradiction found.
        """
        evidences = self._equivocation_log.record_observation(obs)
        if evidences:
            if self._reputation_ledger is not None:
                self._reputation_ledger.record_equivocation(obs.observer_id)
            reason = f"{len(evidences)} equivocation(s): observer {obs.observer_provenance} issued contradictory reports"
            return EquivocationCheck(is_equivocal=True, reason=reason, evidence=evidences)
        return EquivocationCheck(is_equivocal=False)

    async def _check_quorum(
        self,
        obs: PeerObservation,
        quorum_members: Optional[list[str]] = None,
    ) -> QuorumCheck:
        """
        [Step 2] Witness quorum validation (G1).

        Validate that obs.witness_set has sufficient independent witnesses
        (≥2 unique observers with ≥2 distinct network provenances).

        Returns:
            QuorumCheck with passes=True if quorum valid, False otherwise.
            votes dict maps observer_id -> vote_weight (all 1.0 at this stage).
        """
        quorum_passes = validate_witness_quorum(obs)

        # Build vote dict from witnesses (pre-weighting)
        votes = {}
        if quorum_passes:
            for witness in obs.witness_set:
                votes[witness.observer_id] = 1.0

        message = (
            "Quorum passed: sufficient independent witnesses"
            if quorum_passes
            else f"Quorum failed: witness_set has only {len(obs.witness_set)} members (need ≥2)"
        )

        return QuorumCheck(passes=quorum_passes, votes=votes, message=message)

    def _weight_votes(self, quorum_votes: Dict[str, float], observer_id: str) -> Dict[str, float]:
        """
        [Step 3] Reputation weighting (G5).

        Multiply each vote by the observer's reputation weight.

        Args:
            quorum_votes: Observer ID → vote weight (from G1 step).
            observer_id: Primary observer to prioritize (optional weighting hint).

        Returns:
            Updated votes dict with reputation-adjusted weights.
        """
        weighted = {}
        for agent_id, vote in quorum_votes.items():
            rep = self._reputation_fn(agent_id)
            weighted[agent_id] = vote * rep
        return weighted

    async def _check_sybil_correlation(self, obs: PeerObservation) -> SybilSignals:
        """
        [Step 4] Sybil correlation (G6).

        Cross-reference G6 distance bucketing (is_correlated XOR distance check)
        with G1 provenance clustering to detect Sybil attack patterns.

        Returns:
            SybilSignals with correlated_ids, provenance_clustering, overall_risk.
        """
        correlated = {}
        provenance_counts: Dict[str, int] = {}

        # Collect provenance clustering data from witness_set. Bucket by
        # subnet (provenance_bucket(), same helper witness_quorum.py uses)
        # rather than the raw provenance string -- otherwise Sybils on the
        # same /24 or /64 with distinct observer_provenance strings would
        # count as independent origins and dilute the clustering signal.
        for witness in obs.witness_set:
            bucket = self._k_bucket.bucket_for(witness.observer_id)
            bucketed_provenance = provenance_bucket(witness.observer_provenance)
            provenance_counts[bucketed_provenance] = provenance_counts.get(
                bucketed_provenance, 0
            ) + 1

        # Check for XOR-distance correlation among witnesses. Mark BOTH sides
        # of a correlated pair, not just id_a — the previous version only
        # recorded id_a, undercounting len(correlated) by up to half. That
        # made the >50% threshold below mathematically unreachable at the
        # minimum quorum size (2 witnesses, 1 possible pair: 1 correlated id
        # out of 2 needs "1 > 1", never true), so a fully Sybil-correlated
        # minimum-size quorum always silently scored "low" risk.
        witness_ids = [w.observer_id for w in obs.witness_set]
        for i, id_a in enumerate(witness_ids):
            for id_b in witness_ids[i + 1 :]:
                if self._k_bucket.is_correlated(id_a, id_b, proximity_bits=4):
                    correlated[id_a] = f"correlated with {id_b}"
                    correlated[id_b] = f"correlated with {id_a}"

        # Risk assessment: high if >=50% witnesses are correlated or
        # provenance clustering is skewed (>2/3 from single origin). >= (not
        # >) so an exactly-half-correlated set — including the minimum
        # 2-witness quorum where both are correlated with each other — is
        # not silently waved through as "low".
        risk = "low"
        if correlated and len(correlated) >= len(witness_ids) / 2:
            risk = "high"
        elif provenance_counts and max(provenance_counts.values()) > len(obs.witness_set) * 0.67:
            risk = "medium"

        return SybilSignals(
            correlated_ids=correlated,
            provenance_clustering=provenance_counts,
            overall_risk=risk,
        )

    async def _commit_decision(
        self,
        obs: PeerObservation,
        quorum_votes: Dict[str, float],
        sybil: SybilSignals,
    ) -> AuditEntry:
        """
        [Step 5] Audit commit (G8).

        Record the decision to the append-only hash chain.

        Args:
            obs: Original observation.
            quorum_votes: Weighted vote dict.
            sybil: Sybil signals from G6 check.

        Returns:
            AuditEntry with hash reference for later audit trail verification.
        """
        witness_ids = tuple(quorum_votes.keys())
        # State transitions are tracked as observation_type (REACHABLE/UNREACHABLE) changes
        old_status = "UNKNOWN"  # Placeholder; caller may set actual prior status
        new_status = obs.observation_type.value

        entry = self._audit_log.append(
            peer_id=obs.peer_id,
            old_status=old_status,
            new_status=new_status,
            witnesses=witness_ids,
            timestamp=obs.timestamp,
        )
        return entry
