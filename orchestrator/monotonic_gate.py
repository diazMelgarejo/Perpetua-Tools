"""Monotonic Apply Gate (T7) - Observation Ordering Enforcement.

This module implements T7 from D4 (Threat Model + Validation Gates), enforcing
strict monotonic causality ordering on peer observations.

Ordering Key: (epoch, sequence, timestamp)
- Epoch: Incarnation counter (highest priority)
- Sequence: Causal ordering within an epoch (canonical)
- Timestamp: Advisory clock with ±30s skew tolerance

Usage:
    from orchestrator.monotonic_gate import is_observation_newer
    from orchestrator.membership import PeerObservation

    current_obs = peer_record.latest_observation
    new_obs = incoming_observation

    if is_observation_newer(current_obs, new_obs):
        # Accept new observation (causally newer)
        peer_record.update_from_observation(new_obs)
    else:
        # Reject new observation (stale or out-of-order)
        logger.debug(f"Monotonic gate rejected observation: {new_obs}")
"""

from orchestrator.membership import PeerObservation


def is_observation_newer(current: PeerObservation, new: PeerObservation) -> bool:
    """
    Check if new observation is strictly newer than current observation.

    Implements T7 monotonic gate: enforces causality via (epoch, sequence, timestamp).
    Sequence is canonical within an epoch; timestamp is advisory with ±30s skew tolerance.

    Args:
        current: Current (accepted) observation on record
        new: Incoming observation to validate

    Returns:
        True if new observation is causally newer and should replace current
        False if new observation is stale, duplicate, or violates monotonic ordering

    Algorithm:
        1. If new.epoch > current.epoch → return True (newer incarnation)
        2. Else if new.epoch == current.epoch:
           - If new.sequence > current.sequence → return True (causally newer)
           - Else if new.sequence == current.sequence:
             - Return new.timestamp > current.timestamp + 30  (±30s tolerance)
           - Else → return False (lower sequence violates causality)
        3. Else (new.epoch < current.epoch) → return False (stale incarnation)

    Examples:
        >>> from tests.fixtures import make_peer_observation
        >>> curr = make_peer_observation(epoch=5, sequence=10, timestamp=1000.0)
        >>> new_epoch = make_peer_observation(epoch=6, sequence=5, timestamp=500.0)
        >>> is_observation_newer(curr, new_epoch)
        True  # newer epoch wins, regardless of sequence

        >>> new_seq = make_peer_observation(epoch=5, sequence=15, timestamp=1100.0)
        >>> is_observation_newer(curr, new_seq)
        True  # same epoch, higher sequence

        >>> new_dup = make_peer_observation(epoch=5, sequence=10, timestamp=1001.0)
        >>> is_observation_newer(curr, new_dup)
        False  # same epoch & sequence, timestamp within tolerance

        >>> new_old = make_peer_observation(epoch=5, sequence=5, timestamp=2000.0)
        >>> is_observation_newer(curr, new_old)
        False  # same epoch, lower sequence (causality violation)
    """
    # Priority 1: Epoch (incarnation counter)
    if new.epoch > current.epoch:
        # Peer restarted; newer incarnation always accepted
        return True
    if new.epoch < current.epoch:
        # Stale incarnation; always rejected
        return False

    # Priority 2: Sequence (canonical causality within epoch)
    if new.sequence > current.sequence:
        # Causally newer within same incarnation
        return True
    if new.sequence < current.sequence:
        # Out-of-order; violates monotonic ordering
        return False

    # Priority 3: Timestamp (advisory, with ±30s skew tolerance)
    # At this point: new.epoch == current.epoch AND new.sequence == current.sequence
    # Use timestamp to break tie, allowing ±30s for network clock skew
    skew_tolerance_seconds = 30
    return new.timestamp > current.timestamp + skew_tolerance_seconds
