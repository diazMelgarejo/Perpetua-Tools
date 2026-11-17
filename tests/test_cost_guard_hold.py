"""A reservation is held for its own declared lifetime, and a late commit is still accounted for.

Review finding 3: reservations expired after a fixed 300 seconds while a live launcher may run 900, so a
second reservation could sweep a request that was still legitimately running, and its commit was then
refused. The clock is injected (patched time.time); nothing sleeps.
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

from orchestrator.cost_guard import BudgetExceededError, CostGuard, UnknownReservationError  # noqa: E402

T0 = 1_800_000_000.0  # fixed epoch seconds: mid-month, so no period roll during the test


def _at(seconds_after_t0: float):
    """Patch the guard's clock to ``T0 + seconds_after_t0``."""
    return patch("orchestrator.cost_guard.time.time", return_value=T0 + seconds_after_t0)


@pytest.fixture()
def guard(tmp_path: Path) -> CostGuard:
    """A monthly guard with a 10 dollar ceiling, created at T0."""
    with _at(0):
        g = CostGuard(state_dir=str(tmp_path), period="monthly")
        g.set_budget(10.0)
    return g


def test_a_900_second_hold_is_not_swept_by_another_reservation_at_301_seconds(guard: CostGuard) -> None:
    """A 900 second hold is not swept by another reservation at 301 seconds."""
    with _at(0):
        long_run = asyncio.run(guard.reserve(6.0, hold_seconds=900))
    with _at(301):
        with pytest.raises(BudgetExceededError):  # the 6.0 hold is still live, so 5.0 does not fit
            asyncio.run(guard.reserve(5.0))
        assert guard.in_flight() == pytest.approx(6.0)
        result = asyncio.run(guard.commit(long_run, 5.5))
        assert guard.snapshot()["daily_spend"] == pytest.approx(5.5)
    assert result["late_commit"] is False


def test_the_default_hold_is_unchanged_at_300_seconds(guard: CostGuard) -> None:
    """The default hold is unchanged at 300 seconds."""
    with _at(0):
        rid = asyncio.run(guard.reserve(6.0))
    with _at(299):
        assert guard.in_flight() == pytest.approx(6.0)
    with _at(301):
        asyncio.run(guard.reserve(5.0))  # the abandoned default hold was swept, so this fits
        assert guard.in_flight() == pytest.approx(5.0)
    assert rid


def test_a_hold_is_swept_only_after_its_own_declared_lifetime(guard: CostGuard) -> None:
    """A hold is swept only after its own declared lifetime."""
    with _at(0):
        asyncio.run(guard.reserve(6.0, hold_seconds=900))
    with _at(901):
        asyncio.run(guard.reserve(5.0))  # now the 900 s hold has run out
        assert guard.in_flight() == pytest.approx(5.0)


def test_a_commit_for_a_swept_reservation_still_records_the_spend_and_says_it_was_late(guard: CostGuard) -> None:
    """A commit for a swept reservation still records the spend and says it was late."""
    with _at(0):
        rid = asyncio.run(guard.reserve(6.0))
    with _at(301):
        asyncio.run(guard.reserve(1.0))  # sweeps the abandoned 6.0 hold
        result = asyncio.run(guard.commit(rid, 5.5))
        assert guard.snapshot()["daily_spend"] == pytest.approx(5.5)  # accounting is never dropped
    assert result["late_commit"] is True and result["committed_usd"] == pytest.approx(5.5)


def test_a_late_commit_without_an_amount_records_the_full_reserved_amount(guard: CostGuard) -> None:
    """A late commit without an amount records the full reserved amount."""
    with _at(0):
        rid = asyncio.run(guard.reserve(6.0))
    with _at(301):
        asyncio.run(guard.reserve(0.0))
        result = asyncio.run(guard.commit(rid))
        assert guard.snapshot()["daily_spend"] == pytest.approx(6.0)
    assert result["late_commit"] is True


def test_a_late_commit_is_single_use_and_a_swept_rollback_stays_an_unknown_reservation(guard: CostGuard) -> None:
    """A late commit is single use and a swept rollback stays an unknown reservation."""
    with _at(0):
        rid = asyncio.run(guard.reserve(2.0))
        rid2 = asyncio.run(guard.reserve(2.0))
    with _at(301):
        asyncio.run(guard.reserve(0.0))
        asyncio.run(guard.commit(rid, 1.0))
        with pytest.raises(UnknownReservationError):
            asyncio.run(guard.commit(rid, 1.0))
        with pytest.raises(UnknownReservationError):
            asyncio.run(guard.rollback(rid2))  # already swept: nothing to release, callers catch this
        assert guard.snapshot()["daily_spend"] == pytest.approx(1.0)


def test_a_never_reserved_id_is_still_unknown(guard: CostGuard) -> None:
    """A never reserved id is still unknown."""
    with pytest.raises(UnknownReservationError):
        asyncio.run(guard.commit("nope", 1.0))


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf"), 86401, True])
def test_a_bad_hold_is_refused_without_holding_anything(guard: CostGuard, bad) -> None:
    """A bad hold is refused without holding anything."""
    with pytest.raises(ValueError):
        asyncio.run(guard.reserve(1.0, hold_seconds=bad))
    assert guard.in_flight() == 0.0


def test_the_hold_is_shared_with_other_instances(guard: CostGuard, tmp_path: Path) -> None:
    """The hold is shared with other instances."""
    other = CostGuard(state_dir=str(tmp_path), period="monthly")
    with _at(0):
        asyncio.run(guard.reserve(6.0, hold_seconds=900))
    with _at(301):
        with pytest.raises(BudgetExceededError):
            asyncio.run(other.reserve(5.0))
