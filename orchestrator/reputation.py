"""
orchestrator/reputation.py — P6 Reputation-Decay Witness Scoring (T1, T4) for Phase 1b.

This module maintains a per-witness accuracy ledger keyed by ``observer_id``.
Ground-truth outcomes (confirmation, human review, or automated detection such as
equivocation) are recorded as correct or incorrect observations, and the resulting
score is used to weight future quorum votes. A witness with a sustained history of
accuracy earns influence above the neutral default, while a witness that is
equivocating or repeatedly wrong is progressively deprioritized and can be excluded
from quorum once its weight reaches zero.

The module is intentionally stdlib-only; it keeps a running score per observer so
that reputation is always current without requiring an external daily batch.

Spec reference: docs/phase-0-specifications/MULTIAGENT-SWARM-SECURITY-ANALYSIS.md
§3 HIGH gap G5 (P6 Reputation-Decay Witness Scoring) — T1 (Malicious Relay), T4 (Sybil
Witnesses).
"""

from __future__ import annotations

from typing import Dict


class ReputationLedger:
    """
    Per-witness reputation ledger for weighted witness quorum voting.

    Each ``observer_id`` accumulates a running score derived from confirmed
    correct and incorrect outcomes. Correct outcomes add ``+weight`` to the score;
    incorrect outcomes subtract ``5 * weight``. The resulting weight applied to
    quorum votes is ``score / 10``, floored at ``0.0`` so a witness can lose all
    influence but never exert negative influence.

    Args:
        neutral_default: Reputation weight returned for observers that have never
            been scored. Defaults to ``1.0`` so new witnesses start trusted
            rather than penalized for lack of history.
    """

    def __init__(self, neutral_default: float = 1.0) -> None:
        """Initialize an empty reputation ledger."""
        self._neutral_default = float(neutral_default)
        # observer_id -> running reputation score.
        self._scores: Dict[str, float] = {}

    def record_outcome(
        self, observer_id: str, correct: bool, *, weight: float = 1.0
    ) -> None:
        """
        Record a ground-truth outcome for a witness's past observation.

        The caller reports whether a given witness observation was later confirmed
        correct or incorrect. The outcome can arrive from any source: STM
        confirmation, human review, automated contradiction detection, etc.

        Args:
            observer_id: Identifier of the witness whose observation is being
                judged.
            correct: ``True`` if the observation was confirmed correct, ``False``
                if it was confirmed incorrect.
            weight: Optional multiplier for the outcome's importance. Defaults
                to ``1.0``.

        Returns:
            None.

        Sybil-or-malice-defense rationale:
            Without per-witness accuracy tracking, every witness contributes
            equally to quorum regardless of historical reliability. An adversary
            can register or compromise many low-quality identities and persist
            indefinitely as long as their lies happen to align with the majority.
            Recording outcomes lets the system distinguish consistently accurate
            witnesses from noisy or malicious ones and progressively reduce the
            influence of the latter.
        """
        weight = float(weight)
        score = self._scores.get(observer_id, 0.0)
        if correct:
            score += weight
        else:
            score -= 5.0 * weight
        self._scores[observer_id] = score

    def record_equivocation(self, observer_id: str) -> None:
        """
        Record that a witness has issued contradictory observations.

        This is a convenience wrapper around ``record_outcome`` that treats an
        equivocation as an incorrect outcome with weight ``5.0``, matching the
        roadmap formula ``correct_predictions - 5 * incorrect`` while expressing
        that contradicting signed claims is an especially strong negative signal.

        Args:
            observer_id: Identifier of the equivocating witness.

        Returns:
            None.

        Sybil-or-malice-defense rationale:
            Equivocation (the same provenance issuing contradictory signed
            observations for the same peer and epoch) is direct evidence of
            malicious or faulty behavior, not merely an unlucky wrong guess.
            Penalizing it five times more heavily than a normal incorrect
            observation lets the ledger react quickly to detected malice,
            shrinking the window during which a malicious witness can poison
            quorum decisions.
        """
        self.record_outcome(observer_id, correct=False, weight=5.0)

    def reputation_weight(self, observer_id: str) -> float:
        """
        Return the quorum vote weight for an observer.

        Args:
            observer_id: Observer whose weight is requested.

        Returns:
            ``max(0.0, score / 10)`` for observers with recorded history, or the
            neutral default (``1.0`` by default) for observers that have never
            been scored. The result is floored at ``0.0`` so a witness cannot
            have negative influence.

        Sybil-or-malice-defense rationale:
            Weighting votes by ``reputation / 10`` means a brand-new or
            historically accurate witness has meaningful influence, while a
            witness with a poor track record contributes little or nothing. This
            slows Sybil attacks because freshly minted identities start at the
            neutral default rather than inheriting fabricated reputation, and it
            eventually removes persistent malicious witnesses from effective
            quorum participation.
        """
        if observer_id not in self._scores:
            return self._neutral_default
        return max(0.0, self._scores[observer_id] / 10.0)

    def is_untrusted(self, observer_id: str, threshold: float = 0.0) -> bool:
        """
        Return whether an observer's reputation weight is at or below a threshold.

        Args:
            observer_id: Observer to evaluate.
            threshold: Reputation-weight floor below which the observer is
                considered untrusted. Defaults to ``0.0``.

        Returns:
            ``True`` if ``reputation_weight(observer_id) <= threshold``,
            ``False`` otherwise. Observers that have never been scored are
            evaluated against their neutral default weight, so by default they
            are trusted.

        Sybil-or-malice-defense rationale:
            A simple threshold gate lets callers exclude witnesses whose
            reputation has decayed to zero from active quorum participation.
            Combined with progressive decay, this converts a long-running Sybil
            or compromised-relay campaign into a temporary disruption rather
            than a persistent voting bloc.
        """
        return self.reputation_weight(observer_id) <= threshold
