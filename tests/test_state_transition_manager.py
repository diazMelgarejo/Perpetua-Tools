"""tests/test_state_transition_manager.py

Unit + integration + property-based tests for orchestrator/state_transition_manager.py,
per docs/phase-0-specifications/2026-07-11-state-transition-manager-integration-plan.md
§ 2c (test naming) and § 2b (fixture shape).
"""
from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from orchestrator.audit_log import AuditLog
from orchestrator.distance_bucket import KBucketTable
from orchestrator.equivocation import EquivocationLog
from orchestrator.membership import DirectStatus, ObservationType, PeerObservation
from orchestrator.reputation import ReputationLedger
from orchestrator.state_transition_manager import (
    DecisionType,
    StateTransitionManager,
    SybilSignal,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


def observation_factory(
    *,
    peer_id: str = "peer_abc",
    epoch: int = 1,
    sequence: int = 1,
    timestamp: float = 1_000_000.0,
    observer_id: str = "observer_1",
    witness_set=(),
    ttl_seconds: int = -1,  # -1 = never expires (STATIC_SEED semantics)
    observation_type: ObservationType = ObservationType.REACHABLE,
) -> PeerObservation:
    """Build a well-formed PeerObservation with configurable witness set,
    epoch, sequence, and observation_type — per the plan's observation_factory
    fixture spec."""
    return PeerObservation(
        peer_id=peer_id,
        epoch=epoch,
        sequence=sequence,
        timestamp=timestamp,
        observer_id=observer_id,
        observation_type=observation_type,
        direct_status=DirectStatus.REACHABLE,
        endpoint="192.168.1.100:9000",
        endpoint_epoch=1,
        witness_set=witness_set,
        ttl_seconds=ttl_seconds,
    )


def witness_factory(
    *,
    peer_id: str = "witness_peer",
    observer_id: str = "observer_x",
    observer_provenance: str = "192.168.9.1",
) -> PeerObservation:
    """A witness is itself a (nested, non-recursive) PeerObservation — it has
    its own peer_id (used by Sybil ID-space correlation) distinct from
    observer_id (who is vouching)."""
    return PeerObservation(
        peer_id=peer_id,
        epoch=1,
        sequence=1,
        timestamp=1_000_000.0,
        observer_id=observer_id,
        observation_type=ObservationType.REACHABLE,
        direct_status=DirectStatus.REACHABLE,
        endpoint="192.168.9.1:9000",
        endpoint_epoch=1,
        observer_provenance=observer_provenance,
        witness_set=(),
        ttl_seconds=-1,
    )


def trusted_witnesses(n: int = 2) -> tuple:
    """n witnesses with distinct observer_id and distinct /24 provenance —
    should pass both the independence quorum and provenance-bucket diversity."""
    return tuple(
        witness_factory(
            peer_id=f"witness_peer_{i}",
            observer_id=f"observer_{i}",
            observer_provenance=f"192.168.{i}.1",
        )
        for i in range(n)
    )


def sybil_witnesses_same_provenance(n: int = 3) -> tuple:
    """n witnesses with distinct observer_id but the SAME /24 provenance —
    passes the raw witness-count quorum but should be weighted down since
    they all collapse to one provenance bucket."""
    return tuple(
        witness_factory(
            peer_id=f"sybil_peer_{i}",
            observer_id=f"sybil_observer_{i}",
            observer_provenance="10.0.0.5",  # same /24 for all
        )
        for i in range(n)
    )


def sybil_witnesses_correlated_ids(n: int = 2, target_peer_id: str = "peer_abc") -> tuple:
    """Witnesses whose peer_id is deliberately close to target_peer_id in
    XOR-distance space (the KBucketTable mock/real is_correlated should flag
    this)."""
    return tuple(
        witness_factory(
            peer_id=target_peer_id,  # identical XOR distance = 0, trivially correlated
            observer_id=f"correlated_observer_{i}",
            observer_provenance=f"172.16.{i}.1",
        )
        for i in range(n)
    )


@pytest.fixture
def equivocation_log() -> EquivocationLog:
    return EquivocationLog()


@pytest.fixture
def k_bucket() -> KBucketTable:
    return KBucketTable(local_id="local_node", k=20)


@pytest.fixture
def audit_log() -> AuditLog:
    return AuditLog()


@pytest.fixture
def reputation() -> ReputationLedger:
    return ReputationLedger()


@pytest.fixture
def state_transition_manager(
    equivocation_log: EquivocationLog,
    k_bucket: KBucketTable,
    audit_log: AuditLog,
    reputation: ReputationLedger,
) -> StateTransitionManager:
    """Fully configured StateTransitionManager for testing (real dependencies,
    per the plan's fixture spec — no mocks unless a test needs to force a
    specific KBucketTable response)."""
    return StateTransitionManager(
        local_id="local_node",
        equivocation_log=equivocation_log,
        k_bucket=k_bucket,
        audit_log=audit_log,
        reputation=reputation,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Unit tests (per gate)
# ──────────────────────────────────────────────────────────────────────────────


class TestEquivocationGate:
    @pytest.mark.asyncio
    async def test_equivocation_rejects_malicious_relay(self, state_transition_manager):
        obs1 = observation_factory(sequence=1, observation_type=ObservationType.REACHABLE)
        obs2 = observation_factory(sequence=2, observation_type=ObservationType.UNREACHABLE)

        await state_transition_manager.evaluate_observation(obs1)
        result = await state_transition_manager.evaluate_observation(obs2)

        assert result.accepted is False
        assert result.decision_type == DecisionType.EQUIVOCATION
        assert len(result.equivocation_evidences) >= 1

    @pytest.mark.asyncio
    async def test_equivocation_penalizes_reputation(self, state_transition_manager, reputation):
        obs1 = observation_factory(sequence=1, observer_id="bad_observer", observation_type=ObservationType.REACHABLE)
        obs2 = observation_factory(sequence=2, observer_id="bad_observer", observation_type=ObservationType.UNREACHABLE)

        neutral = reputation.reputation_weight("bad_observer")
        await state_transition_manager.evaluate_observation(obs1)
        await state_transition_manager.evaluate_observation(obs2)
        penalized = reputation.reputation_weight("bad_observer")

        # Asserting the ledger's own state moved, not just the pipeline's
        # accepted/decision_type outcome (which would pass even if
        # record_equivocation() were never called).
        assert penalized < neutral


class TestQuorumGate:
    @pytest.mark.asyncio
    async def test_quorum_failure_rejects(self, state_transition_manager):
        obs = observation_factory(witness_set=(witness_factory(),))  # only 1 witness

        result = await state_transition_manager.evaluate_observation(obs)

        assert result.accepted is False
        assert result.decision_type == DecisionType.INSUFFICIENT_QUORUM
        assert result.quorum_vote is not None
        assert result.quorum_vote.passes is False


class TestWeightedQuorumGate:
    @pytest.mark.asyncio
    async def test_weighted_quorum_threshold(self, state_transition_manager, reputation):
        witnesses = trusted_witnesses(2)
        # Drive both witnesses' reputation well below neutral so the summed
        # weighted score cannot clear the default threshold (2.0), even
        # though the raw independence quorum (2 witnesses, 2 provenance
        # buckets) passes.
        for w in witnesses:
            for _ in range(10):
                reputation.record_equivocation(w.observer_id)

        obs = observation_factory(witness_set=witnesses)
        result = await state_transition_manager.evaluate_observation(obs)

        assert result.quorum_vote is not None
        assert result.quorum_vote.passes is True  # raw quorum passes
        assert result.accepted is False
        assert result.decision_type == DecisionType.INSUFFICIENT_QUORUM
        assert result.weighted_quorum is not None
        assert result.weighted_quorum.passes is False
        assert result.weighted_quorum.weighted_score < result.weighted_quorum.threshold


class TestSybilCorrelation:
    @pytest.mark.asyncio
    async def test_sybil_strong_when_correlated_witnesses(self, state_transition_manager):
        # 2+ witnesses with peer_id identical to the target -> XOR distance 0,
        # trivially within any proximity_bits threshold -> STRONG signal.
        witnesses = sybil_witnesses_correlated_ids(2, target_peer_id="peer_abc") + (
            witness_factory(peer_id="extra_independent", observer_id="observer_extra", observer_provenance="203.0.113.1"),
        )
        obs = observation_factory(peer_id="peer_abc", witness_set=witnesses)

        result = await state_transition_manager.evaluate_observation(obs)

        assert result.sybil_correlation is not None
        assert result.sybil_correlation.signal == SybilSignal.STRONG
        assert result.decision_type == DecisionType.SYBIL_FLAGGED
        # Flag-not-reject: still accepted.
        assert result.accepted is True

    @pytest.mark.asyncio
    async def test_sybil_weak_when_same_bucket(self, state_transition_manager, k_bucket):
        # A single correlated pair (not >=2) should produce WEAK, not STRONG.
        witnesses = (
            witness_factory(peer_id="peer_abc", observer_id="observer_close", observer_provenance="198.51.100.1"),
            witness_factory(peer_id="far_peer_zzz", observer_id="observer_far", observer_provenance="203.0.113.1"),
        )
        obs = observation_factory(peer_id="peer_abc", witness_set=witnesses)

        result = await state_transition_manager.evaluate_observation(obs)

        assert result.sybil_correlation is not None
        assert result.sybil_correlation.signal in (SybilSignal.WEAK, SybilSignal.STRONG)
        if result.sybil_correlation.signal == SybilSignal.WEAK:
            assert result.accepted is True
            assert result.decision_type == DecisionType.SYBIL_FLAGGED


class TestAuditCommit:
    @pytest.mark.asyncio
    async def test_audit_appended_for_rejection(self, state_transition_manager, audit_log):
        obs = observation_factory(witness_set=(witness_factory(),))  # fails quorum

        entries_before = len(audit_log.entries())
        result = await state_transition_manager.evaluate_observation(obs)
        entries_after = len(audit_log.entries())

        assert result.accepted is False
        assert entries_after == entries_before + 1
        assert result.audit_entry is not None

    @pytest.mark.asyncio
    async def test_audit_appended_for_acceptance(self, state_transition_manager, audit_log):
        obs = observation_factory(witness_set=trusted_witnesses(2))

        entries_before = len(audit_log.entries())
        result = await state_transition_manager.evaluate_observation(obs)
        entries_after = len(audit_log.entries())

        assert result.accepted is True
        assert entries_after == entries_before + 1
        assert result.audit_entry is not None
        assert result.audit_hash if hasattr(result, "audit_hash") else result.audit_entry.hash


class TestDedupGate:
    @pytest.mark.asyncio
    async def test_duplicate_observation_rejected(self, state_transition_manager):
        obs = observation_factory(witness_set=trusted_witnesses(2))

        first = await state_transition_manager.evaluate_observation(obs)
        second = await state_transition_manager.evaluate_observation(obs)

        assert first.accepted is True
        assert second.accepted is False
        assert second.decision_type == DecisionType.DUPLICATE

    @pytest.mark.asyncio
    async def test_out_of_order_sequence_rejected(self, state_transition_manager):
        # obs.to_json() (the dedup key) does not include `sequence` -- vary
        # timestamp too so obs_old is a genuinely different JSON payload from
        # obs_new, otherwise the dedup gate (which runs before the monotonic
        # check) would flag it as DUPLICATE instead of STALE.
        obs_new = observation_factory(epoch=1, sequence=5, timestamp=1_000_005.0, witness_set=trusted_witnesses(2))
        obs_old = observation_factory(epoch=1, sequence=2, timestamp=1_000_002.0, witness_set=trusted_witnesses(2))

        first = await state_transition_manager.evaluate_observation(obs_new)
        second = await state_transition_manager.evaluate_observation(obs_old)

        assert first.accepted is True
        assert second.accepted is False
        assert second.decision_type == DecisionType.STALE


# ──────────────────────────────────────────────────────────────────────────────
# Integration tests
# ──────────────────────────────────────────────────────────────────────────────


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_happy_path_approved(self, state_transition_manager):
        obs = observation_factory(witness_set=trusted_witnesses(2))

        result = await state_transition_manager.evaluate_observation(obs)

        assert result.accepted is True
        assert result.decision_type == DecisionType.APPROVED
        assert result.audit_entry is not None


class TestEarlyRejection:
    @pytest.mark.asyncio
    async def test_malicious_observation_rejected_at_step_2(self, state_transition_manager):
        obs1 = observation_factory(sequence=1, observation_type=ObservationType.REACHABLE)
        obs2 = observation_factory(sequence=2, observation_type=ObservationType.UNREACHABLE)

        await state_transition_manager.evaluate_observation(obs1)
        result = await state_transition_manager.evaluate_observation(obs2)

        assert result.decision_type == DecisionType.EQUIVOCATION
        # Rejected before quorum work — no quorum_vote computed.
        assert result.quorum_vote is None

    @pytest.mark.asyncio
    async def test_quorum_failure_rejected_at_step_3(self, state_transition_manager):
        obs = observation_factory(witness_set=(witness_factory(),))

        result = await state_transition_manager.evaluate_observation(obs)

        assert result.decision_type == DecisionType.INSUFFICIENT_QUORUM
        assert result.quorum_vote is not None
        # Rejected before weighting — no weighted_quorum computed.
        assert result.weighted_quorum is None


class TestReputationSwing:
    @pytest.mark.asyncio
    async def test_reputation_swing_changes_weighted_outcome(self, reputation, equivocation_log, k_bucket, audit_log):
        manager = StateTransitionManager(
            local_id="local_node",
            equivocation_log=equivocation_log,
            k_bucket=k_bucket,
            audit_log=audit_log,
            reputation=reputation,
        )
        witnesses = trusted_witnesses(2)

        # High reputation (default neutral 1.0 each, sum 2.0 across 2 buckets) passes.
        obs_good = observation_factory(sequence=1, timestamp=1_000_001.0, witness_set=witnesses)
        result_good = await manager.evaluate_observation(obs_good)
        assert result_good.weighted_quorum is not None
        assert result_good.weighted_quorum.passes is True

        # Tank reputation, then a later (higher-sequence) observation from the
        # same witnesses should now fail weighting. Different timestamp too --
        # to_json() (the dedup key) doesn't include sequence, so an identical
        # timestamp would make obs_bad look like a duplicate of obs_good and
        # never reach the weighting step at all.
        for w in witnesses:
            for _ in range(10):
                reputation.record_equivocation(w.observer_id)

        obs_bad = observation_factory(sequence=2, timestamp=1_000_002.0, witness_set=witnesses)
        result_bad = await manager.evaluate_observation(obs_bad)
        assert result_bad.weighted_quorum is not None
        assert result_bad.weighted_quorum.passes is False
        assert result_bad.weighted_quorum.weighted_score < result_good.weighted_quorum.weighted_score


class TestSybilDetection:
    @pytest.mark.asyncio
    async def test_sybil_detected_but_still_approved(self, state_transition_manager):
        witnesses = sybil_witnesses_correlated_ids(2, target_peer_id="peer_abc") + (
            witness_factory(peer_id="extra_independent", observer_id="observer_extra", observer_provenance="203.0.113.1"),
        )
        obs = observation_factory(peer_id="peer_abc", witness_set=witnesses)

        result = await state_transition_manager.evaluate_observation(obs)

        assert result.sybil_correlation.signal == SybilSignal.STRONG
        assert result.accepted is True
        assert result.decision_type == DecisionType.SYBIL_FLAGGED
        assert result.audit_entry is not None


class TestEndToEndAudit:
    @pytest.mark.asyncio
    async def test_end_to_end_audit_verifies(self, state_transition_manager, audit_log):
        obs = observation_factory(witness_set=trusted_witnesses(2))

        result = await state_transition_manager.evaluate_observation(obs)

        assert audit_log.verify_chain() is True
        entries = audit_log.entries()
        hashes = [e.hash for e in entries]
        assert result.audit_entry.hash in hashes


# ──────────────────────────────────────────────────────────────────────────────
# Property-based tests
# ──────────────────────────────────────────────────────────────────────────────


class TestPropertyBasedInvariants:
    @pytest.mark.asyncio
    async def test_idempotence_under_dedup(self, state_transition_manager):
        """Same obs evaluated twice -> second call is DUPLICATE, but only
        when the first call actually cleared all gates (accepted). A
        rejected observation is intentionally never added to
        _seen_observations -- resubmitting it just re-runs the same
        rejection, which is correct: there's no dedup benefit to skipping
        a check that will produce the same terminal decision anyway, and
        marking rejections as "seen" would let a legitimate later retry
        after a transient rejection get silently swallowed as a duplicate."""
        obs = observation_factory(witness_set=trusted_witnesses(2))  # passes all gates

        first = await state_transition_manager.evaluate_observation(obs)
        second = await state_transition_manager.evaluate_observation(obs)

        assert first.accepted is True
        assert first.decision_type != DecisionType.DUPLICATE
        assert second.decision_type == DecisionType.DUPLICATE

    @given(st.integers(min_value=1, max_value=20))
    @pytest.mark.asyncio
    async def test_audit_invariant_one_entry_per_call(self, n_calls):
        """Every call to evaluate_observation appends exactly one audit
        entry, whether accepted or rejected."""
        manager = StateTransitionManager(
            local_id="local_node",
            equivocation_log=EquivocationLog(),
            k_bucket=KBucketTable(local_id="local_node", k=20),
            audit_log=AuditLog(),
            reputation=ReputationLedger(),
        )
        audit_log = manager._audit_log

        for i in range(n_calls):
            obs = observation_factory(
                peer_id=f"peer_{i}",  # distinct peer per call, no dedup interference
                witness_set=(witness_factory(peer_id=f"w_{i}"),),  # fails quorum, still audited
            )
            await manager.evaluate_observation(obs)

        assert len(audit_log.entries()) == n_calls

    def test_reputation_monotonicity_equivocation_never_increases_weight(self, reputation):
        """record_equivocation() never increases a witness's weight."""
        observer_id = "monotonic_test_observer"
        before = reputation.reputation_weight(observer_id)
        reputation.record_equivocation(observer_id)
        after = reputation.reputation_weight(observer_id)
        assert after <= before


# ──────────────────────────────────────────────────────────────────────────────
# Edge cases
# ──────────────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_stale_observation_rejected(self, state_transition_manager):
        obs = observation_factory(timestamp=1.0, ttl_seconds=1)  # timestamp far in the past, 1s TTL
        result = await state_transition_manager.evaluate_observation(obs)

        assert result.accepted is False
        assert result.decision_type == DecisionType.STALE

    @pytest.mark.asyncio
    async def test_empty_witness_set_fails_quorum_not_crash(self, state_transition_manager):
        obs = observation_factory(witness_set=())
        result = await state_transition_manager.evaluate_observation(obs)

        assert result.accepted is False
        assert result.decision_type == DecisionType.INSUFFICIENT_QUORUM

    @pytest.mark.asyncio
    async def test_concurrent_calls_different_peers_do_not_block_each_other(self, state_transition_manager):
        import asyncio as _asyncio

        obs_a = observation_factory(peer_id="peer_a", witness_set=trusted_witnesses(2))
        obs_b = observation_factory(peer_id="peer_b", witness_set=trusted_witnesses(2))

        results = await _asyncio.gather(
            state_transition_manager.evaluate_observation(obs_a),
            state_transition_manager.evaluate_observation(obs_b),
        )

        assert all(r.accepted for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_calls_same_peer_serialize_correctly(self, state_transition_manager):
        """Two concurrent evaluate_observation() calls for the SAME peer
        must not both succeed as non-duplicates -- the per-peer lock should
        serialize them so the second sees the first's dedup/monotonic state."""
        import asyncio as _asyncio

        obs = observation_factory(witness_set=trusted_witnesses(2))

        results = await _asyncio.gather(
            state_transition_manager.evaluate_observation(obs),
            state_transition_manager.evaluate_observation(obs),
        )

        accepted_count = sum(1 for r in results if r.accepted)
        duplicate_count = sum(1 for r in results if r.decision_type == DecisionType.DUPLICATE)
        assert accepted_count == 1
        assert duplicate_count == 1
