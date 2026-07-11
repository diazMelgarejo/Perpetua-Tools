# StateTransitionManager Integration Plan (Steelmanned + Program-Aligned)

**Date:** 2026-07-11 · **Scope:** Wire G1/G4/G5/G6/G8 into a `PeerObservation` security-decision pipeline  
**Effort:** 2 phases (design + implementation) · **Timeline:** 2–3 days  
**Auto-reviewed by:** Claude subagent + Codex (gpt-5.5) via `/autoplan`  
**Program parent:** [`PATTERN-MULTIAGENT-EXECUTION-PLAN.md`](./PATTERN-MULTIAGENT-EXECUTION-PLAN.md)  
**Security foundation:** [`MULTIAGENT-SWARM-SECURITY-ANALYSIS.md`](./MULTIAGENT-SWARM-SECURITY-ANALYSIS.md)

---

## Program Context

This plan is a **concrete integration milestone** inside the broader P2P security patterns program described in `PATTERN-MULTIAGENT-EXECUTION-PLAN.md`. That program covers 20 patterns (P1–P20) and 16 security gaps (G1–G16) across Perpetua-Tools and orama-system over ~4 weeks.

This milestone focuses on the Perpetua-Tools **state-authority layer** and integrates the five patterns already implemented in isolation:

| Pattern | Gap | Module | PATTERN Plan Track |
|---------|-----|--------|-------------------|
| P2 Distance Bucketing | G6 | `orchestrator/distance_bucket.py` | Track A7 |
| P5 Provenance Dedup | G1 | `orchestrator/provenance.py` + `witness_quorum.py` | Track A3 |
| P6 Reputation Scoring | G5 | `orchestrator/reputation.py` | Track A4 |
| P13 Equivocation Detection | G4 | `orchestrator/equivocation.py` | Track A5 |
| P19 Audit Log | G8 | `orchestrator/audit_log.py` | Track A6 |

**Important adaptation:** The parent PATTERN plan assumes these modules still need to be implemented. In the current working tree they already exist and are unit-tested. Therefore this milestone is **integration-only** and much shorter than the parent plan's Track A estimates.

### Mapping to Parent Plan Tracks

| This Milestone | Parent PATTERN Plan | Notes |
|----------------|---------------------|-------|
| Design & contracts | Iteration 2 (feasibility) + Iteration 3 (repo split) | Reuse feasibility conclusions; confirm repo ownership |
| Implement `StateTransitionManager` | Track A3–A7 compressed | Modules exist; only wiring needed |
| Rewrite fixtures + integration tests | Track A9 | Focus on cross-module behavior |
| Wire into startup/ingestion | Iteration 3 integration points | Locate real L2 apply path |
| Fleet mode prerequisite | Track D (Fleet Mode Integration) | STM is a prerequisite for D2–D5 |

### Branch Alignment

The parent PATTERN plan targets `feature/phase-0-blocker-fixes`. This milestone can be implemented on that branch or on `main`; the modules and interfaces referenced are the same in both. If the broader program proceeds on `feature/phase-0-blocker-fixes`, open the STM implementation PR against that branch so Track D can build on it.

---

## Problem Statement

Phase 1b security gaps are implemented and unit-tested in isolation:

| Gap | Module | Status |
|-----|--------|--------|
| G1 | `provenance.py` | ✅ Wired into `witness_quorum.py` |
| G4 | `equivocation.py` | ⚠️ Standalone, 0 production callers |
| G5 | `reputation.py` | ⚠️ Standalone, 0 production callers |
| G6 | `distance_bucket.py` | ⚠️ Standalone, 0 production callers |
| G8 | `audit_log.py` | ⚠️ Standalone, 0 production callers |

**Missing:** an orchestration layer that calls these modules in a deterministic sequence, records decisions, and produces a single authoritative result for each incoming `PeerObservation`.

**Scope boundary (important):** This plan implements the *security decision pipeline* that the integration review (`2026-07-11-phase1b-integration-review.md`) asked for. It does **not** implement the full DELIVERABLE-2 §5.3 hysteresis state machine (persistent peer counters, promote/demote windows, asymmetric reachability, `CONFIRM_DEAD_HOLD`). That remains a follow-up milestone once this pipeline is proven. Keeping the scope narrow respects the review's warning not to build the full STM speculatively in one pass.

---

## Design: Security Decision Pipeline

### Execution Flow

```text
PeerObservation
    ↓
[1] Dedup + Monotonic Gate        ← reject replays / out-of-order sequence
    ↓
[2] Equivocation Gate (G4)        ← cheapest check; record evidence & penalize reputation
    ↓ (continue if no contradiction)
[3] Witness Quorum (G1)           ← uses provenance_bucket() internally
    ↓ (continue if quorum passes)
[4] Reputation Weighting (G5)     ← weight each independent witness vote
    ↓ (weighted quorum predicate)
[5] Sybil Correlation (G6)        ← cross-check KBucket distance vs. provenance collapse
    ↓ (flag; does not block)
[6] Audit Commit (G8)             ← append terminal decision to hash chain
    ↓
StateTransitionResult
    (accepted | rejected | flagged)
```

### Module Wiring (corrected to actual APIs)

| Step | Pattern | Module | Real API | Caller |
|------|---------|--------|----------|--------|
| 1 | P8/P9 | `membership.PeerObservation` | `(peer_id, epoch, sequence, observer_id, ...)` | `_is_duplicate_or_stale()` |
| 2 | P13 | `equivocation.EquivocationLog` | `record_observation(obs) -> List[EquivocationEvidence]` | `_check_equivocation()` |
| 3 | P5/P12 | `witness_quorum` | `validate_witness_quorum(obs) -> bool` | `_check_quorum()` |
| 4 | P6 | `reputation.ReputationLedger` | `reputation_weight(observer_id) -> float` | `_weight_votes()` |
| 5 | P2 | `distance_bucket.KBucketTable` | `is_correlated(a, b, proximity_bits=4) -> bool` | `_check_sybil_correlation()` |
| 6 | P19 | `audit_log.AuditLog` | `append(peer_id, old_status, new_status, witnesses, *, signer) -> AuditEntry` | `_commit_decision()` |

### Concurrency Model

The pipeline is **synchronous** because every dependency is in-memory and synchronous. Concurrent callers are serialized with an `asyncio.Lock` keyed by `peer_id` when called from async code (FastAPI, async worker loops). This prevents races on:

- per-peer dedup / monotonic sequence state
- `EquivocationLog._observations`
- `KBucketTable._buckets`
- `ReputationLedger._scores`
- `AuditLog._entries`
- the peer-state lookup used to compute `old_status`

If the caller is synchronous (e.g., a background thread), use `threading.Lock` instead, or marshal calls through an async actor queue.

---

## Phase 1: Design & Contracts (4–6 hours)

### 1a. Define Types (`orchestrator/state_transition_manager.py`)

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from orchestrator.audit_log import AuditEntry
from orchestrator.equivocation import EquivocationEvidence
from orchestrator.membership import PeerObservation


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

    STRONG = "strong"      # is_correlated True for multiple witnesses / known peers
    WEAK = "weak"          # same bucket but not within proximity_bits
    NONE = "none"


@dataclass(frozen=True)
class QuorumVote:
    """Structured result of the witness quorum gate."""

    passes: bool
    witness_count: int
    unique_observer_ids: int
    unique_provenance_buckets: int
    witness_ids: Tuple[str, ...]
    witness_provenance_buckets: Tuple[str, ...]


@dataclass(frozen=True)
class WeightedQuorum:
    """Quorum after reputation weighting."""

    passes: bool
    weighted_score: float
    threshold: float
    weighted_by_observer: Dict[str, float]


@dataclass(frozen=True)
class SybilCorrelation:
    """Correlation signal between the observed peer and its witnesses / known peers."""

    signal: SybilSignal
    correlated_pairs: List[Tuple[str, str]] = field(default_factory=list)
    witness_bucket_index: Optional[int] = None
    details: Dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class StateTransitionResult:
    """Outcome of evaluating one observation through the security pipeline."""

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
```

### 1b. Define `StateTransitionManager` Interface

```python
import asyncio
from typing import Callable, Dict, Optional

from orchestrator.audit_log import AuditLog, AuditEntry
from orchestrator.distance_bucket import KBucketTable
from orchestrator.equivocation import EquivocationLog
from orchestrator.membership import PeerObservation
from orchestrator.provenance import provenance_bucket
from orchestrator.reputation import ReputationLedger
from orchestrator.witness_quorum import validate_witness_quorum


class InvalidObservationError(ValueError):
    """Observation failed a structural gate (stale, duplicate, malformed)."""


class StateTransitionManager:
    """
    Evaluate a PeerObservation through the G1/G4/G5/G6/G8 security pipeline.

    This is the *security decision* layer, not the full DELIVERABLE-2 peer-state
    hysteresis machine. It returns a terminal decision and audit hash; callers
    decide how to apply that decision to peer display state.
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
        self._seen_observations: set[str] = set()  # dedup key: hash of canonical observation bytes

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
        peer_id = obs.peer_id
        lock = self._peer_locks.setdefault(peer_id, asyncio.Lock())
        async with lock:
            return self._evaluate_locked(obs, old_status)

    def _evaluate_locked(
        self,
        obs: PeerObservation,
        old_status: str,
    ) -> StateTransitionResult:
        # [1] Dedup / monotonic gate
        dedup_key = obs.to_json()
        if dedup_key in self._seen_observations:
            return self._reject(obs, DecisionType.DUPLICATE, "Duplicate observation", old_status)

        last = self._last_applied_key.get(obs.peer_id)
        if last is not None:
            last_epoch, last_seq = last
            if obs.epoch < last_epoch or (obs.epoch == last_epoch and obs.sequence <= last_seq):
                return self._reject(
                    obs, DecisionType.STALE,
                    f"Out-of-order observation (epoch={obs.epoch}, seq={obs.sequence} <= last {last})",
                    old_status,
                )

        if obs.is_stale:
            return self._reject(obs, DecisionType.STALE, "Observation TTL expired", old_status)

        # [2] Equivocation gate (cheapest)
        evidences = self._equivocation_log.record_observation(obs)
        if evidences:
            # Penalize obs.observer_id (the reporter of THIS contradictory
            # observation), not EquivocationEvidence.observer_provenance.
            # observer_provenance identifies a network origin, not an
            # accountable identity, and multiple observers can legitimately
            # share a provenance bucket -- penalizing it would punish
            # innocent co-located observers alongside the actual offender.
            # obs.observer_id is always available here (the triggering
            # observation's own field), so no provenance fallback is needed.
            self._reputation.record_equivocation(obs.observer_id)
            return self._reject(
                obs,
                DecisionType.EQUIVOCATION,
                f"Equivocation detected from {len({e.observer_provenance for e in evidences})} provenance(s)",
                old_status,
                equivocation_evidences=tuple(evidences),
            )

        # [3] Witness quorum
        quorum_passes = self._check_quorum(obs)
        quorum_vote = self._build_quorum_vote(obs, quorum_passes)
        if not quorum_passes:
            return self._reject(
                obs,
                DecisionType.INSUFFICIENT_QUORUM,
                "Insufficient independent witness quorum",
                old_status,
                quorum_vote=quorum_vote,
            )

        # [4] Reputation-weighted quorum
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

        # [5] Sybil correlation (flag only)
        sybil = self._check_sybil_correlation(obs)
        decision_type = DecisionType.APPROVED
        if sybil.signal in (SybilSignal.STRONG, SybilSignal.WEAK):
            decision_type = DecisionType.SYBIL_FLAGGED

        # [6] Audit commit (terminal decision)
        new_status = decision_type.value
        audit_entry = self._audit_log.append(
            peer_id=obs.peer_id,
            old_status=old_status,
            new_status=new_status,
            witnesses=tuple(weighted.weighted_by_observer.keys()),
            signer=self._signer,
        )

        # Mark observation applied for monotonic ordering
        self._seen_observations.add(dedup_key)
        self._last_applied_key[obs.peer_id] = (obs.epoch, obs.sequence)

        return StateTransitionResult(
            # APPROVED and SYBIL_FLAGGED both accept the observation (Sybil
            # correlation is a heuristic signal carried forward for
            # downstream review, not proof of malice like equivocation —
            # see step [5] above). Only the earlier hard-reject paths
            # (insufficient quorum, weighted-quorum-below-threshold) set
            # accepted=False, and they return before reaching this point.
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_quorum(self, obs: PeerObservation) -> bool:
        return validate_witness_quorum(obs)

    def _build_quorum_vote(self, obs: PeerObservation, passes: bool) -> QuorumVote:
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

    def _weight_votes(self, obs: PeerObservation, quorum_vote: QuorumVote) -> WeightedQuorum:
        # Weight by independent provenance bucket so Sybils in the same bucket
        # cannot inflate the score.
        weighted_by_bucket: Dict[str, float] = {}
        for witness, bucket in zip(obs.witness_set, quorum_vote.witness_provenance_buckets):
            weight = self._reputation.reputation_weight(witness.observer_id)
            weighted_by_bucket[bucket] = max(
                weighted_by_bucket.get(bucket, 0.0),
                weight,
            )

        total = sum(weighted_by_bucket.values())
        weighted_by_observer = {
            w.observer_id: self._reputation.reputation_weight(w.observer_id)
            for w in obs.witness_set
        }
        return WeightedQuorum(
            passes=total >= self._weighted_quorum_threshold,
            weighted_score=total,
            threshold=self._weighted_quorum_threshold,
            weighted_by_observer=weighted_by_observer,
        )

    def _check_sybil_correlation(self, obs: PeerObservation) -> SybilCorrelation:
        correlated_pairs: List[Tuple[str, str]] = []

        # Signal 1: observed peer is suspiciously close to one of its witnesses in ID-space.
        for witness in obs.witness_set:
            if self._k_bucket.is_correlated(
                obs.peer_id, witness.peer_id, self._sybil_proximity_bits
            ):
                correlated_pairs.append((obs.peer_id, witness.peer_id))

        # Signal 2: many witnesses land in the same bucket as the observed peer.
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
        # Audit rejection as a terminal decision (old_status -> decision_type)
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
```

### 1c. Integration Points

**Already wired:**
- ✅ `witness_quorum.validate_witness_quorum()` uses `provenance_bucket()` internally.
- ✅ `reputation.ReputationLedger` is fully implemented with `reputation_weight`, `record_outcome`, `record_equivocation`.

**Need to wire (actual APIs):**
- `equivocation.EquivocationLog.record_observation(obs)` → returns `List[EquivocationEvidence]`.
- `reputation.ReputationLedger.reputation_weight(observer_id)` → read weight.
- `reputation.ReputationLedger.record_equivocation(observer_id)` → penalize on equivocation.
- `distance_bucket.KBucketTable(local_id, k=20)` → constructed with local peer ID.
- `distance_bucket.KBucketTable.is_correlated(a, b, proximity_bits=4)` → Sybil signal.
- `audit_log.AuditLog()` → in-memory, no constructor args.
- `audit_log.AuditLog.append(peer_id, old_status, new_status, witnesses, signer=...)` → returns `AuditEntry`.

### 1d. Relationship to `PeerRecord`

`StateTransitionManager` does **not** replace `PeerRecord.update_from_observation()`. The intended call graph is:

```
inbound PeerObservation
    ↓
StateTransitionManager.evaluate_observation(obs, old_status=peer_record.display_state or "UNKNOWN")
    ↓
if result.accepted:
    peer_record.update_from_observation(obs)   # existing confidence/display-state logic
    # optionally feed confirmed outcome back to reputation
else:
    # optionally feed rejected outcome back to reputation
```

This keeps `PeerRecord` as the display-state authority and `StateTransitionManager` as the security gate.

---

## Phase 2: Implementation (1.5–2 days)

### 2a. Create `orchestrator/state_transition_manager.py`

Implement the class and types in §1a–1b. Requirements:

- Synchronous core (`_evaluate_locked`).
- `asyncio.Lock` per peer in the public async wrapper.
- Clear error handling: never raise on expected rejections; raise `InvalidObservationError` only for malformed input (e.g., missing required fields before `PeerObservation` validation catches it).
- Audit every terminal decision, including rejections.
- Keep `old_status` overridable by the caller; default to `"UNKNOWN"`.

### 2b. Update `tests/fixtures/state_transition_fixtures.py`

The existing fixture file models a generic counter/threshold machine (`IDLE/COUNTING/THRESHOLD_REACHED/RECOVERING`) that has nothing to do with the security pipeline. **Replace it** with fixtures that exercise real observation scenarios:

- `observation_factory` — builds `PeerObservation` with configurable witness set, epoch, sequence, observation_type.
- `trusted_witnesses` / `sybil_witnesses_same_provenance` / `sybil_witnesses_correlated_ids`.
- `state_transition_manager` fixture — constructs `StateTransitionManager` with real dependencies.
- Parametrized scenarios:
  - approved observation
  - equivocation rejection
  - insufficient quorum
  - weighted quorum fails due to bad reputation
  - strong Sybil flag
  - stale/duplicate rejection
  - audit chain verified

Delete the `_PlaceholderStateTransitionManager` and `TransitionState` enum. If a generic counter state machine is still needed elsewhere, move it to a fixture file with a name that does not collide with this security pipeline.

### 2c. Add Unit + Integration Tests (`tests/test_state_transition_manager.py`)

**Unit tests (per gate):**

- `test_equivocation_rejects_malicious_relay()`
- `test_equivocation_penalizes_reputation()`
- `test_quorum_failure_rejects()`
- `test_weighted_quorum_threshold()`
- `test_sybil_strong_when_correlated_witnesses()`
- `test_sybil_weak_when_same_bucket()`
- `test_audit_appended_for_rejection()`
- `test_audit_appended_for_acceptance()`
- `test_duplicate_observation_rejected()`
- `test_out_of_order_sequence_rejected()`

**Integration tests:**

- `test_happy_path_approved()`
- `test_malicious_observation_rejected_at_step_2()`
- `test_quorum_failure_rejected_at_step_3()`
- `test_reputation_swing_changes_weighted_outcome()`
- `test_sybil_detected_but_still_approved()`
- `test_end_to_end_audit_verifies()`

**Property-based tests:**

- Monotonicity: same obs, same result (idempotence under dedup).
- Audit invariant: every call to `evaluate_observation` appends exactly one audit entry.
- Reputation monotonicity: `record_equivocation` never increases a witness's weight.

### 2d. Wire into Startup

Find the real observation ingestion path (likely `agent_tracker.py`, `heartbeat_monitor.py`, or `peer_record.update_from_observation()` callers). Add construction:

```python
from orchestrator.equivocation import EquivocationLog
from orchestrator.distance_bucket import KBucketTable
from orchestrator.audit_log import AuditLog
from orchestrator.reputation import ReputationLedger
from orchestrator.state_transition_manager import StateTransitionManager

stm = StateTransitionManager(
    local_id=local_peer_id,
    equivocation_log=EquivocationLog(),
    k_bucket=KBucketTable(local_id=local_peer_id, k=20),
    audit_log=AuditLog(),
    reputation=ReputationLedger(),
)
```

Do **not** expose a public HTTP endpoint for this milestone. The portal endpoint from the original plan is deferred to the G7 async-notification milestone, when the control-plane API surface is reviewed separately.

### 2e. Add `orchestrator/__init__.py` Re-exports

Export the public types from `state_transition_manager.py` so callers can import:

```python
from orchestrator.state_transition_manager import (
    DecisionType,
    InvalidObservationError,
    QuorumVote,
    StateTransitionManager,
    StateTransitionResult,
    SybilCorrelation,
    SybilSignal,
    WeightedQuorum,
)
```

---

## Blockers & Dependencies

| Blocker | Status | Mitigation |
|---------|--------|-----------|
| G5 (Reputation) | ✅ Implemented | Use `ReputationLedger` directly; no stub needed |
| G2 (Confidence formula) | ✅ Implemented | Kept inside `PeerRecord.compute_confidence()`; STM does not touch it |
| G7 (Async notifications) | 📋 Planned (Track B2/B5) | Portal endpoint deferred to G7 milestone |
| P8 Monotonic sequence enforcement | ✅ Implemented | `PeerObservation.sequence` exists; STM adds per-peer `(epoch, sequence)` gate |
| P9 Reorder buffer | ✅ Implemented (2026-07-12) | Superseded the original "out of scope" decision — see Deferred Items and Decision Audit Trail #15 |
| ASN lookup (P5) | 📋 Parent-plan decision | Parent plan default is MaxMind free tier; STM uses existing `/24` + `/64` provenance bucketing and does not require ASN |
| Full DELIVERABLE-2 hysteresis | 📋 Out of scope | Separate milestone after this pipeline is proven |
| Persistence of in-memory modules | ⚠️ Design decision | Documented as follow-up; in-memory is acceptable for Phase 1b integration |
| Branch target | ⚠️ `main` vs `feature/phase-0-blocker-fixes` | Implement on whichever branch Track D (Fleet Mode) will consume |
| G4/G6 real production caller (2d, unwired) | 🔒 **GATED (2026-07-12)** | `evaluate_observation()` has zero production callers — confirmed independently 4+ times in the PR #205 quad-CEO-review. Further P5/P6/P13 pattern-hardening requires (1) this wiring landed and (2) a threat-model premise re-check for the actual single-operator LAN topology. See `docs/phase-0-specifications/PATTERN-SYNTHESIS.md` § "GATE on P5/P6/P13 (2026-07-12)" and `docs/phase-0-specifications/2026-07-12-ceo-review-quad-voices/`. PR #205 itself is unaffected — it stays merged/unblocked. |

---

## Success Criteria

- [ ] `StateTransitionManager` exists and wires G1/G4/G5/G6/G8 into a single callable pipeline.
- [ ] G4 (`equivocation`) has a real production caller. **Still unmet as of 2026-07-12 — see Blockers table row "G4/G6 real production caller."**
- [ ] G5 (`reputation`) is read for weighting and written on equivocation.
- [ ] G6 (`distance_bucket`) has a real production caller. **Still unmet as of 2026-07-12 — same gate as G4.**
- [ ] G8 (`audit_log`) records every terminal decision (accepted and rejected).
- [ ] Unit and integration tests cover all gates and cross-module behavior.
- [ ] `tests/fixtures/state_transition_fixtures.py` is rewritten for the security pipeline; placeholder counter machine removed.
- [ ] No new public HTTP endpoint in this milestone.
- [ ] All tests pass.

---

## Estimated Timeline

| Phase | Task | Effort | Sequencing |
|-------|------|--------|-----------|
| 1a | Define corrected types + API table | 1–2 h | Sequential |
| 1b | Define `StateTransitionManager` class + concurrency model | 2–3 h | After 1a |
| 1c | Document integration with `PeerRecord` and startup path | 1 h | After 1b |
| 2a | Implement `orchestrator/state_transition_manager.py` | 4–6 h | After 1 |
| 2b | Rewrite fixtures | 2–3 h | Parallel with 2a |
| 2c | Write unit + integration + property tests | 4–6 h | After 2a/2b |
| 2d | Wire into real startup/ingestion path | 2–3 h | After 2a |
| 2e | Run full test suite, fix regressions | 2–3 h | After 2c/2d |
| **Total** | | **2–3 days** | |

---

## Recommendation

Treat this as a **dedicated 2–3 day milestone**, not a 6–8 hour bolt-on. The original estimate was too low because the actual module APIs diverge from the pseudocode and because the test fixtures need to be rewritten. Allocate one implementer for the manager + wiring and one for tests + fixtures. Do **not** expand into the full DELIVERABLE-2 hysteresis machine in this pass.

---

## Related

- [`orchestrator/equivocation.py`](../../orchestrator/equivocation.py) — G4
- [`orchestrator/distance_bucket.py`](../../orchestrator/distance_bucket.py) — G6
- [`orchestrator/audit_log.py`](../../orchestrator/audit_log.py) — G8
- [`orchestrator/provenance.py`](../../orchestrator/provenance.py) — G1
- [`orchestrator/witness_quorum.py`](../../orchestrator/witness_quorum.py) — Calls G1
- [`orchestrator/reputation.py`](../../orchestrator/reputation.py) — G5
- [`orchestrator/peer_record.py`](../../orchestrator/peer_record.py) — Downstream display-state consumer
- [`orchestrator/membership.py`](../../orchestrator/membership.py) — `PeerObservation` schema
- [`DELIVERABLE-2-HEARTBEAT-LIVENESS-REGENERATED.md`](./DELIVERABLE-2-HEARTBEAT-LIVENESS-REGENERATED.md) — §5.3 full state machine (out of scope here)
- [`2026-07-11-phase1b-integration-review.md`](./2026-07-11-phase1b-integration-review.md) — Prior review that flagged the integration gap
- [`MULTIAGENT-SWARM-SECURITY-ANALYSIS.md`](./MULTIAGENT-SWARM-SECURITY-ANALYSIS.md) — Threat model (T1–T7) and gap analysis (G1–G16) that motivates the security pipeline
- [`PATTERN-MULTIAGENT-EXECUTION-PLAN.md`](./PATTERN-MULTIAGENT-EXECUTION-PLAN.md) — Parent program plan (20 patterns, 16 gaps, 4-week execution)

---

## Review Report — `/autoplan` Steelmanning

### Scope Decision (auto-decided)

**Decision:** Keep the plan narrow — implement a security decision pipeline, not the full DELIVERABLE-2 hysteresis state machine.

**Rationale (Principle 5 — explicit over clever, Principle 2 — boil lakes in blast radius):** The integration review explicitly warned against speculatively building the full STM. The original plan's 6–8 hour estimate and hand-wavy state semantics would have produced an unmaintainable partial state machine. Narrowing the scope makes the milestone deliverable and testable while keeping the full hysteresis machine as a follow-up.

### Key Issues Resolved

1. **API mismatches corrected**
   - `EquivocationLog.record_observation()` returns `List[EquivocationEvidence]`, not an `.is_equivocal` object.
   - `validate_witness_quorum()` returns `bool`, not a `QuorumVote` object.
   - `KBucketTable` exposes `is_correlated()` / `peers_in_bucket()`, not `query()`.
   - `AuditLog.append()` signature matches the real code.
   - `ReputationLedger` is used directly, not treated as an in-progress stub.

2. **Concurrency and state safety added**
   - Synchronous core with `asyncio.Lock` per peer.
   - Dedup set and per-peer `(epoch, sequence)` monotonic gate.

3. **Audit coverage fixed**
   - Every terminal decision appends an audit entry, including rejections.

4. **Fixtures aligned**
   - Existing generic counter fixtures are replaced with real `PeerObservation`-based scenarios.

5. **Relationship to `PeerRecord` clarified**
   - STM is a security gate; `PeerRecord` remains the display-state authority.

### Cross-Model Consensus

Claude subagent and Codex independently flagged the same critical issues:

| Dimension | Claude | Codex | Consensus |
|-----------|--------|-------|-----------|
| Plan scope too narrow vs. DELIVERABLE-2 | Critical | Critical | Confirmed |
| API mismatches (equivocation, quorum, distance, audit) | Critical/High | Critical/High | Confirmed |
| Missing audit of rejections | High | Critical | Confirmed |
| Mismatched placeholder fixtures | High | Medium | Confirmed |
| Reputation already implemented | High | High | Confirmed |
| Async/unsafe concurrency | High | Medium | Confirmed |

No disagreements required taste decisions; both models converged on the steelmanned direction.

### Deferred Items

- Full DELIVERABLE-2 hysteresis state machine (`ACTIVE/SUSPECT/INACTIVE`, promote/demote counters, `CONFIRM_DEAD_HOLD`).
- Public HTTP portal endpoint for observation evaluation (G7 milestone / Track B).
- Persistence for `EquivocationLog`, `KBucketTable`, `ReputationLedger`, and `AuditLog`.
- Detailed reputation feedback loop after confirmed state transitions.
- ~~P9 reorder buffer (parent plan Track A2) — STM only gates duplicates, it does not buffer.~~
  **Superseded 2026-07-12** (see Decision Audit Trail #15): implemented inside
  STM after all, per a PR #205 code-review follow-up plan
  (`~/.gemini/antigravity-cli/brain/c135322b-e318-4038-93e4-e83a92cd48bb/plan.md`)
  identifying P9 as still-missing alongside two memory-leak fixes. See
  [PATTERN-SYNTHESIS.md](PATTERN-SYNTHESIS.md) P9 for the canonical spec.
  `orchestrator/state_transition_manager.py` now has a per-peer
  `(epoch, sequence)`-keyed reorder buffer (`_reorder_buffer`, capped at
  `reorder_buffer_max`), draining via `_flush_reorder_buffer()` and surfacing
  flushed results through `StateTransitionResult.flushed`. Also landed in the
  same pass: P18 bounded LRU caches (`_seen_observations`, `_last_applied_key`,
  `max_cache_size`), P2 `KBucketTable.update()` on every accepted observation,
  ref-counted `_peer_locks` eviction (memory-leak fix, PR #205 code review),
  and an audit-log naming fix (`new_status` uses `observation_type`, not the
  internal `decision_type` label, for accepted decisions).

### Adaptation Notes (integration with parent PATTERN plan)

- **Module status mismatch resolved:** The parent PATTERN plan schedules implementation of P2, P5, P6, P13, P19 modules. The current tree already contains `distance_bucket.py`, `provenance.py`, `reputation.py`, `equivocation.py`, and `audit_log.py`. This milestone was adapted from "implement modules" to "integrate modules," reducing effort from ~36 h (Track A) to 2–3 days.
- **Fleet Mode prerequisite identified:** Track D of the parent plan needs the STM pipeline before D2–D5. This milestone is positioned as that prerequisite.
- **Branch alignment noted:** Parent plan targets `feature/phase-0-blocker-fixes`; this milestone can land there or on `main` depending on where Track D is being built.
- **Pattern numbering added:** All gates now reference their P-pattern (P2, P5, P6, P13, P19) so the parent plan's traceability matrix stays consistent.

### Outcome

Plan approved with the scope and API corrections above. Next step: implement `orchestrator/state_transition_manager.py`, rewrite fixtures, and add `tests/test_state_transition_manager.py`.

---

## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|----------------|-----------|-----------|----------|
| 1 | CEO | Narrow scope to security pipeline; defer full DELIVERABLE-2 hysteresis | Mechanical | P5 (explicit over clever), P2 (blast radius) | Integration review warned against speculative full-STM implementation; narrow scope is deliverable and testable | Full DELIVERABLE-2 state machine in this pass |
| 2 | CEO | Drop public HTTP portal endpoint from this milestone | Mechanical | P5, P3 (pragmatic) | Endpoint expands auth/audit surface before core pipeline is validated; defer to G7 | Expose `/api/peer-observation` now |
| 3 | Eng | Make `StateTransitionManager` synchronous core with per-peer `asyncio.Lock` | Mechanical | P5, P1 (completeness) | All dependencies are sync in-memory; async wrapper without locks would be unsafe | `async def` all the way down with unprotected shared state |
| 4 | Eng | Audit every terminal decision including rejections | Mechanical | P1 | G4/G8 are forensics gaps; rejections are the events most likely to need later investigation | Audit only accepted transitions |
| 5 | Eng | Use actual module APIs exactly as implemented | Mechanical | P4 (DRY), P5 | Plan pseudocode used non-existent methods; steelmanned code matches real signatures | Refactor all dependencies to match the plan |
| 6 | Eng | Weight quorum by independent provenance bucket, not per-witness | Mechanical | P1 | Prevents same-subnet Sybils from inflating weighted score | Simple per-witness sum |
| 7 | Eng | Treat `StateTransitionManager` as security gate, keep `PeerRecord` as display-state authority | Mechanical | P5, P4 | Avoids duplicating `PeerRecord` confidence/display logic and keeps responsibilities clear | Move display-state logic into STM |
| 8 | Eng | Rewrite `tests/fixtures/state_transition_fixtures.py` instead of reusing generic counter fixtures | Mechanical | P2, P4 | Existing fixtures describe a different machine; reusing them would test the wrong abstraction | Keep placeholder fixtures and add a compatibility shim |
| 9 | Eng | Penalize `observer_provenance` on equivocation when distinct observer_id is unavailable | Taste | P3 (pragmatic) | `EquivocationEvidence` stores provenance, not observer_id; using provenance as penalty key is the minimal viable path | Penalize every historical observer_id for the provenance (requires richer evidence) |
| 10 | DX | Keep Python 3.9-compatible type syntax (`Optional[X]`, `Dict`) to match `contracts.py` | Mechanical | P4 | Project uses Python 3.9 compat in shared modules; new code should follow suit | Use `X \| Y` syntax |
| 11 | Program | Treat this milestone as integration-only; do not reimplement P2/P5/P6/P13/P19 | Mechanical | P4 (DRY), P3 | Modules already exist and pass unit tests; reimplementation would duplicate work | Follow parent PATTERN plan Track A3–A7 literally and rebuild modules |
| 12 | Program | Position STM as prerequisite to parent plan Track D (Fleet Mode) | Mechanical | P5 | Fleet mode self-healing and topology consensus need the security pipeline before they can trust observations | Implement Fleet Mode first and retrofit security later |
| 13 | Program | Leave P9 reorder buffer out of STM scope | Mechanical | P2 (blast radius) | Reorder buffer is a separate pattern with its own state and tests; STM only needs a dedup/monotonic gate | Implement buffering inside STM |
| 14 | Program | Target `feature/phase-0-blocker-fixes` if Track D is active there, else `main` | Mechanical | P3 | Minimizes cross-branch merge work for the broader program | Force all STM work onto `main` regardless of broader program branch |
| 15 | Program | **Supersedes #13** (2026-07-12): implement P9 reorder buffer inside STM after all, plus P18 bounded caches and P2 k-bucket maintenance in the same pass | Mechanical | P1 (completeness), P5 | A PR #205 code-review follow-up (antigravity-cli plan) found P9/P18/P2 still pseudocode-only per PATTERN-SYNTHESIS.md, plus a real `_peer_locks`/`_seen_observations` memory-leak risk under many distinct peer_ids; the original blast-radius concern (#13) was addressed by scoping the buffer to a private, per-peer, capped structure with no new public surface, not by staying out of STM | Ship a separate `ReorderBuffer` module and wire it externally (would re-fragment the same peer-ordering state STM already owns via `_last_applied_key`) |
| 16 | Eng | Add `StateTransitionResult.flushed` as an additive field rather than changing `evaluate_observation()`'s return type to a list | Taste | P5, P3 (pragmatic) | Every existing caller reads a single `StateTransitionResult`; a list return type is a breaking change with no compensating benefit for the common (nothing flushed) case | Return `list[StateTransitionResult]` unconditionally, per the antigravity plan's original proposal |
