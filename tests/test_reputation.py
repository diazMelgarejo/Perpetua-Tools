"""
tests/test_reputation.py — Tests for per-witness reputation-decay scoring (G5).

Coverage:
- New/unknown observers receive the neutral default weight (1.0).
- Correct outcomes increase the per-witness score.
- Incorrect outcomes decrease the score per the 5x roadmap penalty.
- record_equivocation() is equivalent to record_outcome(correct=False, weight=5.0).
- reputation_weight() is floored at 0.0 even after many incorrect outcomes.
- is_untrusted() flags witnesses whose weight has dropped to/below the threshold.
- Sustained correct history produces a weight above the neutral default.
"""

import pytest

from orchestrator.reputation import ReputationLedger


class TestReputationLedgerDefaults:
    """Default behavior for unknown or newly created observers."""

    def test_unknown_observer_has_neutral_default_weight(self):
        """An observer with no recorded history starts trusted."""
        ledger = ReputationLedger()
        assert ledger.reputation_weight("new-observer") == 1.0

    def test_unknown_observer_is_not_untrusted_by_default(self):
        """A never-scored observer should not be flagged as untrusted."""
        ledger = ReputationLedger()
        assert ledger.is_untrusted("new-observer") is False


class TestReputationLedgerOutcomes:
    """Score updates for correct and incorrect outcomes."""

    def test_correct_outcome_increases_score(self):
        """A correct observation adds +weight to the running score."""
        ledger = ReputationLedger()
        ledger.record_outcome("alice", correct=True)
        assert ledger.reputation_weight("alice") == 0.1  # 1 / 10

    def test_correct_outcome_with_custom_weight(self):
        """The weight multiplier scales the positive contribution."""
        ledger = ReputationLedger()
        ledger.record_outcome("alice", correct=True, weight=3.0)
        assert ledger.reputation_weight("alice") == 0.3  # 3 / 10

    def test_incorrect_outcome_decreases_score_five_times_more(self):
        """An incorrect observation subtracts 5 * weight from the score."""
        ledger = ReputationLedger()
        ledger.record_outcome("bob", correct=False)
        # score = -5, weight = max(0, -5/10) = 0.0
        assert ledger.reputation_weight("bob") == 0.0

    def test_incorrect_outcome_with_custom_weight(self):
        """The 5x penalty scales with the supplied weight."""
        ledger = ReputationLedger()
        ledger.record_outcome("bob", correct=False, weight=2.0)
        # score = -10, weight = max(0, -10/10) = 0.0
        assert ledger.reputation_weight("bob") == 0.0


class TestReputationLedgerEquivocation:
    """Equivocation is penalized as a strongly weighted incorrect outcome."""

    def test_equivocation_equivalent_to_weighted_incorrect_outcome(self):
        """record_equivocation equals record_outcome(correct=False, weight=5.0)."""
        ledger1 = ReputationLedger()
        ledger2 = ReputationLedger()

        ledger1.record_equivocation("mallory")
        ledger2.record_outcome("mallory", correct=False, weight=5.0)

        assert ledger1.reputation_weight("mallory") == ledger2.reputation_weight("mallory")
        # score = -25, weight = max(0, -25/10) = 0.0
        assert ledger1.reputation_weight("mallory") == 0.0


class TestReputationLedgerFloor:
    """Negative scores cannot produce negative quorum influence."""

    def test_weight_never_goes_negative(self):
        """Many incorrect outcomes floor the weight at 0.0."""
        ledger = ReputationLedger()
        for _ in range(10):
            ledger.record_outcome("sybil", correct=False)
        # score = -50, weight must be floored at 0.0, not -5.0
        assert ledger.reputation_weight("sybil") == 0.0

    def test_weight_can_increase_again_after_penalty(self):
        """A witness can recover influence by supplying correct outcomes."""
        ledger = ReputationLedger()
        ledger.record_outcome("recovering", correct=False, weight=2.0)
        # score = -10, weight = 0.0
        assert ledger.reputation_weight("recovering") == 0.0

        ledger.record_outcome("recovering", correct=True, weight=20.0)
        # score = 10, weight = 1.0
        assert ledger.reputation_weight("recovering") == 1.0


class TestReputationLedgerUntrusted:
    """Threshold-based exclusion from quorum."""

    def test_is_untrusted_at_zero_threshold(self):
        """A witness whose weight has reached exactly zero is untrusted."""
        ledger = ReputationLedger()
        ledger.record_outcome("untrusted", correct=False)
        assert ledger.reputation_weight("untrusted") == 0.0
        assert ledger.is_untrusted("untrusted") is True

    def test_is_untrusted_below_custom_threshold(self):
        """A witness whose weight is at or below a positive threshold is flagged."""
        ledger = ReputationLedger()
        ledger.record_outcome("marginal", correct=True)
        # score = 1, weight = 0.1
        assert ledger.reputation_weight("marginal") == 0.1
        assert ledger.is_untrusted("marginal", threshold=0.05) is False
        assert ledger.is_untrusted("marginal", threshold=0.09) is False
        assert ledger.is_untrusted("marginal", threshold=0.1) is True
        assert ledger.is_untrusted("marginal", threshold=0.11) is True


class TestReputationLedgerReward:
    """Accurate witnesses are rewarded with influence above the default."""

    def test_sustained_correct_history_exceeds_neutral_default(self):
        """A witness with many correct outcomes has weight > 1.0."""
        ledger = ReputationLedger()
        for _ in range(25):
            ledger.record_outcome("reliable", correct=True)
        # score = 25, weight = 2.5
        assert ledger.reputation_weight("reliable") == 2.5
        assert ledger.reputation_weight("reliable") > 1.0
