"""
orchestrator/peer_record.py — PeerRecord update loop with confidence wiring.

This module implements the PeerRecord class which maintains mutable state for a peer,
including observation history and caching of computed confidence scores.

Core design:
- PeerRecord: mutable container for a single peer's state
- update_from_observation(): processes new observations, computes confidence, emits events
- DisplayState transitions trigger StateTransitionEvent emissions (observer pattern)
- Event handlers registered via subscribe_to_state_changes()

Reference: D1 § 6 (Integration Checkpoints)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Set
from datetime import datetime

from orchestrator.membership import PeerObservation
from orchestrator.display_state import (
    PeerDisplayState,
    compute_display_state_from_peer,
    compute_display_state,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Events
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@dataclass
class StateTransitionEvent:
    """
    Event fired when PeerRecord's display_state transitions.

    Fields:
        peer_id: identifier of the peer whose state changed
        old_state: previous display state (or None if first observation)
        new_state: new display state
        confidence: confidence score that triggered the transition
        timestamp: when the transition occurred (unix seconds)
        observation: the PeerObservation that triggered this event
    """

    peer_id: str
    old_state: Optional[str]  # PeerDisplayState.value or None
    new_state: str  # PeerDisplayState.value
    confidence: float
    timestamp: float
    observation: PeerObservation


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PeerRecord
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@dataclass
class PeerRecord:
    """
    Mutable record for a single peer, tracking observations and confidence scores.

    Design:
    - Mutable (unlike PeerObservation) to support in-place state updates
    - Maintains history of observations (optional, not required for 1.1.1)
    - Caches latest confidence score and timestamp
    - Tracks display_state derived from confidence
    - Emits StateTransitionEvent when display_state changes

    Fields:
        peer_id: identifier of this peer
        latest_observation: most recently added observation (or None)
        last_confidence: cached confidence score from latest observation
        last_confidence_timestamp: when confidence was last computed
        display_state: current UI display state (UNKNOWN, SUSPECT, DEGRADED, HEALTHY)
        witness_agreement_count: cumulative witness agreement counter
        witness_disagreement_count: cumulative witness disagreement counter
        observation_count: number of observations processed
        state_change_listeners: registered event handlers
    """

    peer_id: str
    latest_observation: Optional[PeerObservation] = None
    last_confidence: float = 0.0
    last_confidence_timestamp: Optional[float] = None
    display_state: Optional[str] = None  # PeerDisplayState.value or None
    witness_agreement_count: int = 0
    witness_disagreement_count: int = 0
    observation_count: int = 0
    state_change_listeners: Set[Callable[[StateTransitionEvent], None]] = field(
        default_factory=set
    )

    def subscribe_to_state_changes(
        self, handler: Callable[[StateTransitionEvent], None]
    ) -> None:
        """Register a callback to be invoked when display_state transitions."""
        self.state_change_listeners.add(handler)

    def unsubscribe_from_state_changes(
        self, handler: Callable[[StateTransitionEvent], None]
    ) -> None:
        """Unregister a state change listener."""
        self.state_change_listeners.discard(handler)

    def _emit_state_transition(self, event: StateTransitionEvent) -> None:
        """Emit state transition event to all registered listeners."""
        for handler in self.state_change_listeners:
            try:
                handler(event)
            except Exception as e:
                # Log but don't propagate handler exceptions
                # (In production, this would use a proper logger)
                print(f"Warning: state change handler failed: {e}")

    def update_from_observation(self, obs: PeerObservation) -> None:
        """
        Process a new observation, updating confidence and display state.

        This is the core update loop that wires compute_confidence() into the
        observation processing pipeline. On each update:
        1. Validate observation (basic checks; T2, T3, T7 gates deferred to 1.2+)
        2. Increment witness counters
        3. Compute confidence via obs.compute_confidence()
        4. Cache result (last_confidence, last_confidence_timestamp)
        5. Derive display_state via compute_display_state()
        6. Emit StateTransitionEvent if display_state changed

        Args:
            obs: PeerObservation to process

        Raises:
            ValueError: if observation fails basic validation
        """
        # Validation: basic checks
        if obs.peer_id != self.peer_id:
            raise ValueError(
                f"Observation peer_id {obs.peer_id} != record peer_id {self.peer_id}"
            )

        # Update witness counters (for 1.2 hysteresis)
        self.witness_agreement_count += obs.witness_agreement
        self.witness_disagreement_count += obs.witness_disagreement

        # Compute confidence
        confidence = obs.compute_confidence()

        # Cache result
        self.last_confidence = confidence
        self.last_confidence_timestamp = obs.timestamp
        self.latest_observation = obs
        self.observation_count += 1

        # Derive display state from confidence
        new_display_state = compute_display_state(confidence).value

        # Emit event if state transitioned
        old_display_state = self.display_state
        if old_display_state != new_display_state:
            event = StateTransitionEvent(
                peer_id=self.peer_id,
                old_state=old_display_state,
                new_state=new_display_state,
                confidence=confidence,
                timestamp=obs.timestamp,
                observation=obs,
            )
            self._emit_state_transition(event)

        # Update display state
        self.display_state = new_display_state


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Public Exports
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

__all__ = [
    "PeerRecord",
    "StateTransitionEvent",
]
