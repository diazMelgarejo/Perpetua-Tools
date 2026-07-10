"""
orchestrator/witness_quorum.py — Witness Quorum Gate (T4 Sybil Defense) for Phase 1.2.

This module implements the witness independence validation gate to prevent Sybil attacks.
A quorum requires:
1. At least 2 independent witnesses (by observer_id)
2. At least 2 distinct network provenances (by observer_provenance)

Spec reference: D4 § T4 (Sybil Witnesses) + D1 § 3 (witness_multiplier)
"""

from orchestrator.membership import PeerObservation


def validate_witness_quorum(observation: PeerObservation) -> bool:
    """
    Validate that an observation has sufficient independent witness quorum.

    Quorum gate: ≥2 independent witnesses required for observation to count as consensus.
    Independence = distinct observer_id AND distinct network provenance.

    Args:
        observation: PeerObservation with witness_set to validate

    Returns:
        True if quorum is satisfied (≥2 distinct observers with ≥2 distinct provenances)
        False if quorum fails (insufficient witnesses or all from same observer/provenance)

    Sybil defense:
        - observer_id dedup prevents single observer claiming multiple identities
        - observer_provenance dedup prevents single network origin spoofing multiple sources
        - Both must pass for quorum to be satisfied
    """
    # Minimum witness requirement: need at least 2 witnesses
    if len(observation.witness_set) < 2:
        return False

    # Dedup by observer_id — need at least 2 distinct observers
    unique_observers = set(w.observer_id for w in observation.witness_set)
    if len(unique_observers) < 2:
        return False

    # Dedup by provenance — need at least 2 distinct network origins
    # Empty provenance treated as unknown/unverifiable (counts as distinct)
    unique_provenances = set(
        w.observer_provenance for w in observation.witness_set
    )
    if len(unique_provenances) < 2:
        return False

    return True
