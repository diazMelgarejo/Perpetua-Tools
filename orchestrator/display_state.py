"""
orchestrator/display_state.py — Display state derivation from confidence scores.

This module implements the PeerDisplayState enum and the compute_display_state()
function which maps confidence thresholds to UI display states.

Core design:
- PeerDisplayState: enum with 4 states (UNKNOWN, SUSPECT, DEGRADED, HEALTHY)
- compute_display_state(): maps confidence ∈ [0.0, 1.0] to display state
- Boundary handling: exact thresholds (0.0, 0.30, 0.70) via < and >= operators
- Deterministic: identical confidence always produces identical state

Reference: D1 § 2.3 (display state derivation)
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orchestrator.membership import PeerObservation

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Display State Enum
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class PeerDisplayState(str, Enum):
    """UI display state derived from confidence score (D1 § 2.3)."""

    UNKNOWN = "UNKNOWN"  # confidence == 0.0 (ghost peer or recent failure)
    SUSPECT = "SUSPECT"  # 0.0 < confidence < 0.30 (low confidence)
    DEGRADED = "DEGRADED"  # 0.30 <= confidence < 0.70 (medium confidence, link quality issue)
    HEALTHY = "HEALTHY"  # confidence >= 0.70 (high confidence)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Display State Computation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def compute_display_state(confidence: float) -> PeerDisplayState:
    """
    Map confidence score to UI display state.

    Thresholds (from D1 § 2.3):
        confidence == 0.0       → UNKNOWN
        0.0 < confidence < 0.30 → SUSPECT
        0.30 <= confidence < 0.70 → DEGRADED
        confidence >= 0.70      → HEALTHY

    Args:
        confidence: score ∈ [0.0, 1.0], typically from PeerObservation.compute_confidence()

    Returns:
        PeerDisplayState: one of UNKNOWN, SUSPECT, DEGRADED, or HEALTHY

    Design notes:
        - Boundary cases: exact 0.0 is UNKNOWN; 0.30 is DEGRADED; 0.70 is HEALTHY
        - Floating-point precision: comparisons use < and >= (no epsilon tolerance)
        - Deterministic: same input always produces same output
    """
    # Boundary case: exactly 0.0 → UNKNOWN
    if confidence == 0.0:
        return PeerDisplayState.UNKNOWN

    # Case 1: 0.0 < confidence < 0.30 → SUSPECT
    if confidence < 0.30:
        return PeerDisplayState.SUSPECT

    # Case 2: 0.30 <= confidence < 0.70 → DEGRADED
    if confidence < 0.70:
        return PeerDisplayState.DEGRADED

    # Case 3: confidence >= 0.70 → HEALTHY
    return PeerDisplayState.HEALTHY


def compute_display_state_from_peer(peer_obs: PeerObservation) -> PeerDisplayState:
    """
    Convenience wrapper: derive display state directly from PeerObservation.

    Args:
        peer_obs: PeerObservation instance with compute_confidence() method

    Returns:
        PeerDisplayState: derived from peer_obs.compute_confidence()
    """
    confidence = peer_obs.compute_confidence()
    return compute_display_state(confidence)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Public Exports
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

__all__: list[str] = [
    "PeerDisplayState",
    "compute_display_state",
    "compute_display_state_from_peer",
]
