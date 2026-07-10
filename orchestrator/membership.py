"""
orchestrator/membership.py — PeerObservation model for Phase 1.0 (Schema + Confidence).

This module implements the immutable PeerObservation dataclass with 20+ fields,
field validation, witness depth enforcement, and JSON serialization.

Core design:
- Frozen dataclass (immutable after creation)
- Mutable inputs deep-copied before object escape
- Witness depth capped at 2 (gossip-loop safety)
- Confidence computed via multiplicative formula (proof_score × freshness × witness_multiplier)

Reference: Deliverable 1 § 2–3 (D1 specification)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, astuple
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Literal, Optional, Tuple

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Constants & Thresholds
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Confidence thresholds (from D1 § 3.3)
CONFIDENCE_THRESHOLD_DIRECT = 0.70  # Minimum to add to active_view
CONFIDENCE_THRESHOLD_RELAY = 0.50  # Minimum for relay observations (needs witness)
CONFIDENCE_THRESHOLD_PROMOTED = 0.60  # Promote from passive_view
CONFIDENCE_THRESHOLD_DEMOTE = 0.30  # Below this = remove from active_view

# Witness depth limit (D1 § 2, § 6.0 T6 mitigation)
MAX_WITNESS_DEPTH = 2

# Chain depth limit for gossip loops (D1 § 6.0 T6 mitigation)
# chain_depth=0 is direct observation, chain_depth=1 is one hop, chain_depth=2 is two hops
# Reject observations with chain_depth > MAX_CHAIN_DEPTH to prevent gossip cycles
MAX_CHAIN_DEPTH = 2

# Heartbeat deadline (D1 § 2.2 for time_to_suspect_ms computation)
HEARTBEAT_DEADLINE_S = 30  # Seconds until a peer is considered suspect

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Enums
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class DirectStatus(str, Enum):
    """Direct reachability status (SWIM protocol states)."""

    REACHABLE = "REACHABLE"
    TIMEOUT = "TIMEOUT"
    UNREACHABLE = "UNREACHABLE"
    STALE = "STALE"
    SUSPECT = "SUSPECT"
    UNKNOWN = "UNKNOWN"
    DEGRADED = "DEGRADED"


class Route(str, Enum):
    """How the observation was obtained."""

    DIRECT = "direct"
    RELAY = "relay"
    DISCOVERED = "discovered"
    STATIC_SEED = "static_seed"
    PASSIVELY_LEARNED = "passively_learned"
    UNKNOWN = "unknown"


class BackendState(str, Enum):
    """Peer's backend capability state."""

    MAC_DUAL = "MAC_DUAL"  # Both Ollama + LM Studio available
    MAC_OLLAMA_ONLY = "MAC_OLLAMA_ONLY"
    WIN_LMSTUDIO = "WIN_LMSTUDIO"
    MAC_NONE = "MAC_NONE"
    OFFLINE = "OFFLINE"


class ObservationType(str, Enum):
    """Classification of the observation (SWIM extended)."""

    REACHABLE = "REACHABLE"
    UNREACHABLE = "UNREACHABLE"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PeerObservation Schema
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@dataclass(frozen=True)
class PeerObservation:
    """
    Immutable snapshot of one observer's view of another peer's reachability.

    Design principles:
    - Frozen: all fields immutable after construction
    - Mutable inputs (list, dict, set) are deep-copied in __post_init__
    - Witness depth capped at 2 to prevent gossip loops (T6 mitigation)
    - Confidence computed via multiplicative formula (proof is a hard gate)

    Fields (20 core + derived):
        Identity & Timing:
            peer_id, epoch, timestamp, observer_id

        Reachability:
            observation_type, direct_status, endpoint, endpoint_epoch

        Probe History:
            last_heartbeat_timestamp, last_probe_timestamp, probe_latency_ms

        Routing & Proof:
            route, probe_result, relay_proof

        Confidence & Consensus:
            proof_score, freshness_score, witness_agreement, witness_disagreement
            witness_set (recursive, max depth 2)

        Backend State:
            backend_caps, backend_state, backend_state_timestamp

        Metadata:
            ttl_seconds, tags, notes, source_id, chain_depth
    """

    # ──────────────────────────────────────────────────────────────────────────
    # IDENTITY & TIMING
    # ──────────────────────────────────────────────────────────────────────────

    peer_id: str  # Target peer being observed (ed25519 pub key hex or hostname)
    epoch: int  # Incarnation counter (increments on peer restart/IP change)
    timestamp: float  # Unix seconds when this observation was recorded
    observer_id: str  # Who made this observation

    # ──────────────────────────────────────────────────────────────────────────
    # REACHABILITY (directed: observer → peer)
    # ──────────────────────────────────────────────────────────────────────────

    observation_type: ObservationType  # REACHABLE or UNREACHABLE
    direct_status: DirectStatus  # Detailed SWIM state
    endpoint: str  # Network address ("192.168.1.1:9000")
    endpoint_epoch: int  # Incarnation counter for this endpoint
    observer_provenance: str = ""  # Network origin identifier (ASN, subnet, or origin IP for Sybil defense)

    # ──────────────────────────────────────────────────────────────────────────
    # PROBE HISTORY
    # ──────────────────────────────────────────────────────────────────────────

    last_heartbeat_timestamp: Optional[float] = None  # Last successful probe
    last_probe_timestamp: Optional[float] = None  # Last probe attempt
    probe_latency_ms: Optional[float] = None  # Observed RTT (for tie-breaking)

    # ──────────────────────────────────────────────────────────────────────────
    # ROUTING & PROOF
    # ──────────────────────────────────────────────────────────────────────────

    route: Route = Route.UNKNOWN  # How observation was obtained
    probe_result: Optional[Dict[str, Any]] = None  # Detailed probe outcome
    relay_proof: Optional[str] = None  # Signed relay claim from target

    # ──────────────────────────────────────────────────────────────────────────
    # CONFIDENCE & CONSENSUS
    # ──────────────────────────────────────────────────────────────────────────

    proof_score: float = 0.0  # [0.0, 1.0] — proof of reachability
    freshness_score: float = 0.0  # [0.0, 1.0] — recency factor
    witness_agreement: int = 0  # Number of other observers agreeing
    witness_disagreement: int = 0  # Number of observers disagreeing
    witness_set: Tuple[PeerObservation, ...] = ()  # Recursive witnesses (max depth 2)

    # ──────────────────────────────────────────────────────────────────────────
    # BACKEND STATE (for inference scheduling)
    # ──────────────────────────────────────────────────────────────────────────

    backend_caps: Tuple[str, ...] = ()  # Advertised capabilities ("ollama", "lmstudio")
    backend_state: Optional[BackendState] = None  # Peer's backend status
    backend_state_timestamp: Optional[float] = None  # When state was last updated

    # ──────────────────────────────────────────────────────────────────────────
    # METADATA & LIFECYCLE
    # ──────────────────────────────────────────────────────────────────────────

    ttl_seconds: int = 60  # How long to trust this observation
    tags: FrozenSet[str] = field(default_factory=frozenset)  # Metadata tags
    notes: str = ""  # Human-readable explanation
    source_id: Optional[str] = None  # Observer who reported this (for relay)
    chain_depth: int = 0  # Gossip chain depth (incremented on relay)

    def __post_init__(self) -> None:
        """Validate fields and enforce immutability for mutable inputs."""

        # Field validation
        self._validate_bounds()
        self._validate_witness_depth()
        self._validate_chain_depth()

        # Deep-freeze mutable inputs
        if self.probe_result is not None:
            frozen_result = self._deep_freeze_dict(self.probe_result)
            object.__setattr__(self, "probe_result", frozen_result)

        # Tags and backend_caps should already be frozen, but ensure it
        if not isinstance(self.tags, frozenset):
            object.__setattr__(self, "tags", frozenset(self.tags))

        if not isinstance(self.backend_caps, tuple):
            object.__setattr__(self, "backend_caps", tuple(self.backend_caps))

        if not isinstance(self.witness_set, tuple):
            object.__setattr__(self, "witness_set", tuple(self.witness_set))

    def _validate_bounds(self) -> None:
        """Validate proof_score and freshness_score are in [0.0, 1.0]."""
        if not 0.0 <= self.proof_score <= 1.0:
            raise ValueError(
                f"proof_score must be in [0.0, 1.0], got {self.proof_score}"
            )
        if not 0.0 <= self.freshness_score <= 1.0:
            raise ValueError(
                f"freshness_score must be in [0.0, 1.0], got {self.freshness_score}"
            )

    def _validate_witness_depth(self) -> None:
        """Validate witness_set depth does not exceed MAX_WITNESS_DEPTH.

        Depth is computed as the longest chain from root to deepest witness.
        If root has no witnesses, depth = 1 (just the root).
        If root has witnesses with max depth D, this root has depth = 1 + D.

        Depth check (gossip loop safety, D1 § 2, T6 mitigation):
        - Depth 1: no witnesses (allowed)
        - Depth 2: witnesses with no nested witnesses (allowed)
        - Depth 3: witnesses with depth-1 witnesses (REJECTED when MAX=2)

        With MAX_WITNESS_DEPTH = 2:
        - observations at depth 1 or 2 are allowed
        - observations at depth 3+ are rejected
        """
        max_depth = self._compute_witness_depth()
        if max_depth > MAX_WITNESS_DEPTH:
            raise ValueError(
                f"witness_set depth exceeds maximum {MAX_WITNESS_DEPTH}, "
                f"computed depth: {max_depth}"
            )

    def _validate_chain_depth(self) -> None:
        """Validate chain_depth does not exceed MAX_CHAIN_DEPTH (T6 gossip-loop defense).

        Chain depth tracks how many hops this observation has traveled:
        - chain_depth = 0: direct observation (from target directly)
        - chain_depth = 1: reported by one peer
        - chain_depth = 2: reported by peer who got it from another peer

        With MAX_CHAIN_DEPTH = 2, we reject chain_depth > 2 to prevent
        unbounded gossip loops (D1 § 6.0 T6 mitigation).
        """
        if self.chain_depth > MAX_CHAIN_DEPTH:
            raise ValueError(
                f"chain_depth exceeds MAX_CHAIN_DEPTH {MAX_CHAIN_DEPTH} "
                f"(T6 gossip-loop defense), got {self.chain_depth}"
            )

    def _compute_witness_depth(self) -> int:
        """Compute the depth (chain length) of this observation's witness tree.

        Depth = 1 (self) + max depth of any witness in witness_set.
        If witness_set is empty, depth = 1.
        """
        if not self.witness_set:
            return 1

        max_witness_depth = max(w._compute_witness_depth() for w in self.witness_set)
        return 1 + max_witness_depth

    def _deep_freeze_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively freeze a dict by converting to types that resist mutation.

        Note: We return a regular dict because nested mutations can't be
        prevented in Python anyway. The important part is that the object
        itself doesn't hold mutable references it can accidentally mutate.
        """
        if isinstance(d, dict):
            return {k: self._deep_freeze_dict(v) for k, v in d.items()}
        elif isinstance(d, list):
            return tuple(self._deep_freeze_dict(item) for item in d)
        elif isinstance(d, set):
            return frozenset(self._deep_freeze_dict(item) for item in d)
        else:
            return d

    def compute_confidence(self) -> float:
        """
        Compute confidence score using multiplicative formula.

        Formula (from D1 § 3.2):
            confidence = proof_score × freshness_factor × witness_multiplier

        where:
            freshness_factor = 0.40 + 0.60 × freshness_score  ∈ [0.40, 1.00]
            witness_multiplier ∈ [0.50, 1.00]

        Key property: proof_score = 0 ⟹ confidence = 0 (multiplicative gate).
        This prevents unproven observations from crossing reachability thresholds
        based on freshness or witness count alone.

        Returns:
            float: confidence score ∈ [0.0, 1.0], rounded to 2 decimals
        """
        proof_gate = self.proof_score

        # Freshness factor: 0.40 (floor for stale) + 0.60 × freshness_score
        freshness_factor = 0.40 + 0.60 * self.freshness_score

        # Witness multiplier based on agreement/disagreement
        witness_multiplier = self._compute_witness_multiplier()

        # Multiplicative formula
        confidence = proof_gate * freshness_factor * witness_multiplier

        # Clamp and round to 2 decimals
        confidence = max(0.0, min(1.0, confidence))
        return round(confidence, 2)

    @property
    def time_to_suspect_ms(self) -> float:
        """Time until this observation becomes suspect (T5 + heartbeat deadline).

        Returns 0.0 immediately if TTL has expired, otherwise uses heartbeat deadline.

        This is a COMPUTED property, not a stored field. It is recomputed on each read
        to avoid stale values under clock skew. Considers both:
        - T5: TTL staleness (observation expires after ttl_seconds from timestamp)
        - HEARTBEAT_DEADLINE_S (30 seconds, D1 § 2.2) — declares peer SUSPECT if no heartbeat

        Returns:
            float: milliseconds until peer should be marked SUSPECT, or 0 if deadline passed
        """
        import time

        # T5: TTL-based staleness takes priority
        if self.is_stale:
            return 0.0

        # T5 + heartbeat deadline: use heartbeat freshness
        if self.last_heartbeat_timestamp is None:
            return 0.0

        now_s = time.time()
        deadline_s = self.last_heartbeat_timestamp + HEARTBEAT_DEADLINE_S  # 30s
        time_remaining_s = max(0.0, deadline_s - now_s)
        return time_remaining_s * 1000.0

    @property
    def is_stale(self) -> bool:
        """True if this observation has exceeded its TTL (T5 mitigation).

        ttl_seconds == -1 means "never expires" (e.g., STATIC_SEED route).
        ttl_seconds > 0 means observation expires that many seconds after timestamp.
        """
        if self.ttl_seconds is None or self.ttl_seconds < 0:
            # Sentinel for "never expires"
            return False
        import time
        age_s = time.time() - self.timestamp
        return age_s > self.ttl_seconds

    def _compute_witness_multiplier(self) -> float:
        """
        Compute witness multiplier ∈ [0.50, 1.00].

        Based on D1 § 3.2:
            0.50 if witness_disagreement > witness_agreement (contradicted)
            0.85 if witness_agreement == 0 (solo observation)
            0.95 if witness_agreement == 1 (one corroborator)
            1.00 if witness_agreement >= 2 (consensus)
        """
        if self.witness_disagreement > self.witness_agreement:
            return 0.50
        elif self.witness_agreement == 0:
            return 0.85
        elif self.witness_agreement == 1:
            return 0.95
        else:  # witness_agreement >= 2
            return 1.00

    def to_json(self) -> str:
        """
        Serialize to JSON string.

        Handles enum serialization and recursive witness_set.
        """
        data = self._to_dict()
        return json.dumps(data)

    def _to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "peer_id": self.peer_id,
            "epoch": self.epoch,
            "timestamp": self.timestamp,
            "observer_id": self.observer_id,
            "observation_type": self.observation_type.value,
            "direct_status": self.direct_status.value,
            "endpoint": self.endpoint,
            "endpoint_epoch": self.endpoint_epoch,
            "last_heartbeat_timestamp": self.last_heartbeat_timestamp,
            "last_probe_timestamp": self.last_probe_timestamp,
            "probe_latency_ms": self.probe_latency_ms,
            "route": self.route.value,
            "probe_result": self.probe_result,
            "relay_proof": self.relay_proof,
            "proof_score": self.proof_score,
            "freshness_score": self.freshness_score,
            "witness_agreement": self.witness_agreement,
            "witness_disagreement": self.witness_disagreement,
            "witness_set": [w._to_dict() for w in self.witness_set],
            "backend_caps": list(self.backend_caps),
            "backend_state": self.backend_state.value if self.backend_state else None,
            "backend_state_timestamp": self.backend_state_timestamp,
            "ttl_seconds": self.ttl_seconds,
            "tags": sorted(list(self.tags)),  # Sort for deterministic JSON
            "notes": self.notes,
            "source_id": self.source_id,
            "chain_depth": self.chain_depth,
        }

    @classmethod
    def from_json(cls, json_str: str) -> PeerObservation:
        """
        Deserialize from JSON string.

        Handles enum deserialization and recursive witness_set reconstruction.
        """
        data = json.loads(json_str)
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> PeerObservation:
        """Reconstruct from dict."""
        # Recursively deserialize witness_set
        witness_list = data.get("witness_set", [])
        witnesses = tuple(cls._from_dict(w) for w in witness_list)

        return cls(
            peer_id=data["peer_id"],
            epoch=data["epoch"],
            timestamp=data["timestamp"],
            observer_id=data["observer_id"],
            observation_type=ObservationType(data["observation_type"]),
            direct_status=DirectStatus(data["direct_status"]),
            endpoint=data["endpoint"],
            endpoint_epoch=data["endpoint_epoch"],
            last_heartbeat_timestamp=data.get("last_heartbeat_timestamp"),
            last_probe_timestamp=data.get("last_probe_timestamp"),
            probe_latency_ms=data.get("probe_latency_ms"),
            route=Route(data.get("route", "unknown")),
            probe_result=data.get("probe_result"),
            relay_proof=data.get("relay_proof"),
            proof_score=data["proof_score"],
            freshness_score=data["freshness_score"],
            witness_agreement=data["witness_agreement"],
            witness_disagreement=data["witness_disagreement"],
            witness_set=witnesses,
            backend_caps=tuple(data.get("backend_caps", [])),
            backend_state=(
                BackendState(data["backend_state"])
                if data.get("backend_state")
                else None
            ),
            backend_state_timestamp=data.get("backend_state_timestamp"),
            ttl_seconds=data.get("ttl_seconds", 60),
            tags=frozenset(data.get("tags", [])),
            notes=data.get("notes", ""),
            source_id=data.get("source_id"),
            chain_depth=data.get("chain_depth", 0),
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Public Exports
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

__all__ = [
    # Enums
    "DirectStatus",
    "Route",
    "BackendState",
    "ObservationType",
    # Main class
    "PeerObservation",
    # Constants
    "CONFIDENCE_THRESHOLD_DIRECT",
    "CONFIDENCE_THRESHOLD_RELAY",
    "CONFIDENCE_THRESHOLD_PROMOTED",
    "CONFIDENCE_THRESHOLD_DEMOTE",
    "MAX_WITNESS_DEPTH",
    "MAX_CHAIN_DEPTH",
    "HEARTBEAT_DEADLINE_S",
]
