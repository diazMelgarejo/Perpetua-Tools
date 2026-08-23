"""test_cost_guard.py — Unit tests for orchestrator/cost_guard.py

Tests CostGuard budget enforcement, spend tracking, alert thresholds,
24h auto-reset, and snapshot output.
Runs offline — no Ollama, no external API calls required.
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from orchestrator.cost_guard import BudgetExceededError, CostGuard, UnknownReservationError


@pytest.fixture
def guard(tmp_path):
    """Fresh CostGuard with 25.0 daily budget backed by a temp dir."""
    return CostGuard(state_dir=str(tmp_path / ".state"))


class TestCanSpend:
    def test_can_spend_within_budget(self, guard):
        assert guard.can_spend(10.0) is True

    def test_can_spend_exact_budget(self, guard):
        # spend 24.99 first, then check if 0.01 is allowed
        guard.record_spend(24.99)
        assert guard.can_spend(0.01) is True

    def test_cannot_spend_over_budget(self, guard):
        guard.record_spend(25.0)
        assert guard.can_spend(0.01) is False

    def test_cannot_spend_when_already_at_limit(self, guard):
        guard.record_spend(25.0)
        assert guard.can_spend(0.0) is True  # exactly at limit is still allowed
        assert guard.can_spend(1.0) is False

    def test_custom_budget(self, tmp_path):
        g = CostGuard(state_dir=str(tmp_path / ".state2"))
        g.set_budget(10.0)
        assert g.can_spend(9.99) is True
        assert g.can_spend(10.01) is False


class TestRecordSpend:
    def test_record_spend_accumulates(self, guard):
        guard.record_spend(5.0)
        guard.record_spend(3.0)
        snap = guard.snapshot()
        assert snap["daily_spend"] == pytest.approx(8.0)

    def test_record_spend_returns_state(self, guard):
        result = guard.record_spend(7.5)
        assert "daily_spend" in result
        assert result["daily_spend"] == pytest.approx(7.5)

    def test_record_spend_persists_to_disk(self, tmp_path):
        g = CostGuard(state_dir=str(tmp_path / ".state"))
        g.record_spend(12.0)
        # Reload from disk
        g2 = CostGuard(state_dir=str(tmp_path / ".state"))
        snap = g2.snapshot()
        assert snap["daily_spend"] == pytest.approx(12.0)


class TestAlertApproaching:
    def test_no_alert_below_threshold(self, guard):
        guard.record_spend(5.0)  # 20% of 25
        assert guard.alert_approaching() is False

    def test_alert_at_threshold(self, guard):
        guard.record_spend(20.0)  # exactly 80% of 25
        assert guard.alert_approaching() is True

    def test_alert_above_threshold(self, guard):
        guard.record_spend(24.0)  # 96% of 25
        assert guard.alert_approaching() is True


class TestAutoReset:
    def test_reset_after_24h(self, guard):
        guard.record_spend(20.0)
        # Simulate 25 hours having passed since last_reset
        p = guard._load()
        p["last_reset"] = time.time() - 90000  # 25 hours ago
        guard._save(p)
        # After auto-reset, daily_spend should be 0
        snap = guard.snapshot()
        assert snap["daily_spend"] == 0.0

    def test_no_reset_within_24h(self, guard):
        guard.record_spend(15.0)
        snap = guard.snapshot()
        assert snap["daily_spend"] == pytest.approx(15.0)


class TestSnapshot:
    def test_snapshot_keys(self, guard):
        snap = guard.snapshot()
        assert "daily_budget" in snap
        assert "daily_spend" in snap
        assert "last_reset" in snap
        assert "alert" in snap
        assert "remaining" in snap

    def test_snapshot_remaining_calculation(self, guard):
        guard.record_spend(10.0)
        snap = guard.snapshot()
        assert snap["remaining"] == pytest.approx(15.0)

    def test_snapshot_alert_false_initially(self, guard):
        snap = guard.snapshot()
        assert snap["alert"] is False


class TestAtomicReserveCommitRollback:
    """Phase 2 Task 2.3 (05-ORAMASYS-UNIFIED-ACTION-PLAN-2026-08-18.md): the old
    can_spend()/record_spend() split left a TOCTOU window across any await
    between them (orchestrator/fastapi_app.py's /orchestrate awaits
    _resolve_candidates() in between) -- two concurrent requests could both
    pass can_spend() before either recorded spend, jointly overspending the
    daily budget. reserve()/commit()/rollback() close that window."""

    @pytest.mark.asyncio
    async def test_reserve_commit_settles_spend(self, guard: CostGuard) -> None:
        reservation_id = await guard.reserve(5.0)
        await guard.commit(reservation_id)
        assert guard.snapshot()["daily_spend"] == pytest.approx(5.0)

    @pytest.mark.asyncio
    async def test_reserve_rollback_does_not_settle_spend(self, guard: CostGuard) -> None:
        reservation_id = await guard.reserve(5.0)
        await guard.rollback(reservation_id)
        assert guard.snapshot()["daily_spend"] == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_reserve_counts_other_in_flight_reservations_not_just_settled_spend(
        self, guard: CostGuard
    ) -> None:
        """The exact race this fixes: two concurrent reservations for a
        20.0-budget guard against a combined cost that only overspends when
        BOTH are honored -- the second reserve() must see the first's
        in-flight hold and refuse, even though daily_spend on disk is still
        0.0 (neither has committed yet)."""
        guard.set_budget(20.0)
        first_id = await guard.reserve(15.0)
        with pytest.raises(BudgetExceededError):
            await guard.reserve(15.0)
        # First reservation is still valid and can complete normally.
        await guard.commit(first_id)
        assert guard.snapshot()["daily_spend"] == pytest.approx(15.0)

    @pytest.mark.asyncio
    async def test_commit_unknown_reservation_raises(self, guard: CostGuard) -> None:
        with pytest.raises(UnknownReservationError):
            await guard.commit("not-a-real-reservation-id")

    @pytest.mark.asyncio
    async def test_rollback_unknown_reservation_raises(self, guard: CostGuard) -> None:
        with pytest.raises(UnknownReservationError):
            await guard.rollback("not-a-real-reservation-id")

    @pytest.mark.asyncio
    async def test_commit_is_single_use(self, guard: CostGuard) -> None:
        """A reservation_id cannot be committed twice -- prevents double-spend
        if a caller's cleanup path is ever invoked more than once."""
        reservation_id = await guard.reserve(5.0)
        await guard.commit(reservation_id)
        with pytest.raises(UnknownReservationError):
            await guard.commit(reservation_id)
        assert guard.snapshot()["daily_spend"] == pytest.approx(5.0)

    @pytest.mark.asyncio
    async def test_commit_actual_cost_overrides_estimate(self, guard: CostGuard) -> None:
        reservation_id = await guard.reserve(10.0)
        await guard.commit(reservation_id, actual_cost=3.5)
        assert guard.snapshot()["daily_spend"] == pytest.approx(3.5)

    @pytest.mark.asyncio
    async def test_concurrent_reserve_race_has_exactly_one_winner(self, guard: CostGuard) -> None:
        """Real asyncio concurrency (not sequential calls): 5 tasks each try
        to reserve() an amount that only 1 of them can fit under budget.
        Exactly 1 must succeed -- proves the asyncio.Lock actually
        serializes the check-then-reserve step under real concurrency, not
        just when called one at a time."""
        import asyncio

        guard.set_budget(10.0)

        async def try_reserve() -> str | None:
            try:
                return await guard.reserve(6.0)
            except BudgetExceededError:
                return None

        results = await asyncio.gather(*(try_reserve() for _ in range(5)))
        winners = [r for r in results if r is not None]
        assert len(winners) == 1

    @pytest.mark.asyncio
    async def test_reserve_rejects_negative_cost(self, guard: CostGuard) -> None:
        """A negative estimated_cost would LOWER in_flight, letting other
        concurrent callers reserve past the real budget -- CodeRabbit finding
        on cost_guard.py:112-133."""
        with pytest.raises(ValueError, match="non-negative"):
            await guard.reserve(-5.0)
        assert guard._reserved == {}

    @pytest.mark.asyncio
    async def test_reserve_rejects_nan_cost(self, guard: CostGuard) -> None:
        """NaN makes the budget comparison always False (any comparison with
        NaN is False in Python), so the reservation would always "succeed"
        and poison daily_spend with NaN on commit."""
        with pytest.raises(ValueError, match="non-negative"):
            await guard.reserve(float("nan"))
        assert guard._reserved == {}

    @pytest.mark.asyncio
    async def test_reserve_rejects_infinite_cost(self, guard: CostGuard) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            await guard.reserve(float("inf"))
        assert guard._reserved == {}

    @pytest.mark.asyncio
    async def test_reserve_accepts_zero_cost(self, guard: CostGuard) -> None:
        """Zero is valid and common -- OrchestrateRequest.estimated_cost
        defaults to 0.0. Must not be rejected by the non-negative check."""
        reservation_id = await guard.reserve(0.0)
        await guard.commit(reservation_id)
        assert guard.snapshot()["daily_spend"] == pytest.approx(0.0)


class TestReservationTTLSelfHeal:
    """Defense-in-depth for the CancelledError leak CodeRabbit found in
    orchestrator/fastapi_app.py: a reservation whose caller never reaches
    commit()/rollback() at all (process killed outright, not just the task
    cancelled) would otherwise hold a phantom budget block forever. A TTL
    sweep on the next reserve() call reclaims it."""

    @pytest.mark.asyncio
    async def test_expired_reservation_no_longer_counts_against_budget(
        self, guard: CostGuard, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        guard.set_budget(10.0)
        reservation_id = await guard.reserve(8.0)

        # Simulate RESERVATION_TTL_SECONDS having elapsed without commit()/
        # rollback() ever being called (the leak scenario).
        amount, _ = guard._reserved[reservation_id]
        guard._reserved[reservation_id] = (amount, guard._reserved[reservation_id][1] - 301.0)

        # A second reserve() that would have failed against the phantom
        # 8.0 in-flight hold now succeeds, because the sweep drops it first.
        second_id = await guard.reserve(8.0)
        assert reservation_id not in guard._reserved
        await guard.commit(second_id)

    @pytest.mark.asyncio
    async def test_fresh_reservation_is_not_swept(self, guard: CostGuard) -> None:
        """A reservation well within the TTL must survive a sweep triggered
        by an unrelated concurrent reserve() call."""
        guard.set_budget(10.0)
        reservation_id = await guard.reserve(3.0)
        await guard.reserve(1.0)  # triggers a sweep pass; must not touch reservation_id
        assert reservation_id in guard._reserved
        await guard.commit(reservation_id)
        assert guard.snapshot()["daily_spend"] == pytest.approx(3.0)

    @pytest.mark.asyncio
    async def test_commit_after_ttl_expiry_raises_unknown_reservation(
        self, guard: CostGuard
    ) -> None:
        """The rare race a caller must tolerate: TTL sweep beats a very slow
        commit() to the punch. Documented as benign in commit()'s docstring
        -- orchestrator/fastapi_app.py's cleanup path catches this
        specifically rather than crashing the response."""
        reservation_id = await guard.reserve(1.0)
        amount, _ = guard._reserved[reservation_id]
        guard._reserved[reservation_id] = (amount, guard._reserved[reservation_id][1] - 301.0)
        await guard.reserve(0.0)  # triggers the sweep

        with pytest.raises(UnknownReservationError):
            await guard.commit(reservation_id)


class TestSetBudget:
    def test_set_budget_changes_limit(self, guard):
        guard.set_budget(50.0)
        snap = guard.snapshot()
        assert snap["daily_budget"] == pytest.approx(50.0)

    def test_set_budget_persists(self, tmp_path):
        g = CostGuard(state_dir=str(tmp_path / ".state"))
        g.set_budget(100.0)
        g2 = CostGuard(state_dir=str(tmp_path / ".state"))
        assert g2.snapshot()["daily_budget"] == pytest.approx(100.0)


# NOTE on the orchestrator/fastapi_app.py:778-781 CancelledError fix
# (CodeRabbit finding on PR #362): the fix itself -- except Exception ->
# try/finally with a `committed` flag, so cleanup runs for ANY unwind
# including asyncio.CancelledError -- was RED-GREEN verified interactively
# via `git stash push --keep-index` against the pre-fix code: a reservation
# genuinely leaked in CostGuard._reserved with the old code, and did not
# leak with the fix. No permanent end-to-end regression test for it lives
# in this file: every attempt (a bare `await orchestrate(req)` call, and a
# TestClient(app) call with resolve_routing_state/sync_ecc_tools/registry
# all mocked to match tests/test_orama_integration.py's own client
# fixture) still corrupted that file's routing assertions when run in the
# same pytest session -- entering fastapi_app.app's real module-level
# singleton (registry/tracker/lifespan) from a second test file appears to
# leave SOME state dirty beyond what was tried here. The TTL-sweep and
# input-validation behavior around it are fully covered above
# (TestReservationTTLSelfHeal, TestAtomicReserveCommitRollback); only the
# CancelledError path itself lacks a permanent regression test. Flagged as
# a known gap, not silently dropped.
