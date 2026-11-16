"""CostGuard period="monthly": the shared guard enforces a calendar-month budget as well as a daily one.

Runs offline. Time is patched.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from orchestrator.cost_guard import BudgetExceededError, CostGuard  # noqa: E402


def _ts(y, m, d, h=12) -> float:
    return datetime(y, m, d, h, tzinfo=timezone.utc).timestamp()


def test_the_default_period_is_daily_and_unchanged(tmp_path: Path) -> None:
    g = CostGuard(state_dir=str(tmp_path))
    assert g.period == "daily" and g.snapshot()["period"] == "daily"


@pytest.mark.parametrize("bad", ["weekly", "", None, 30])
def test_an_unknown_period_is_refused(tmp_path: Path, bad) -> None:
    with pytest.raises(ValueError):
        CostGuard(state_dir=str(tmp_path), period=bad)


def test_monthly_spend_survives_a_day_and_resets_at_the_month_boundary(tmp_path: Path) -> None:
    with patch("orchestrator.cost_guard.time.time", return_value=_ts(2026, 11, 3)):
        g = CostGuard(state_dir=str(tmp_path), period="monthly")
        g.set_budget(90.0)
        g.record_spend(12.5)
    with patch("orchestrator.cost_guard.time.time", return_value=_ts(2026, 11, 29)):   # 26 days later
        assert g.snapshot()["daily_spend"] == pytest.approx(12.5)       # a daily guard would have reset
    with patch("orchestrator.cost_guard.time.time", return_value=_ts(2026, 12, 1, 0)):
        snap = g.snapshot()
        assert snap["daily_spend"] == 0.0 and snap["daily_budget"] == 90.0


def test_a_daily_guard_still_resets_after_24_hours(tmp_path: Path) -> None:
    with patch("orchestrator.cost_guard.time.time", return_value=_ts(2026, 11, 3)):
        g = CostGuard(state_dir=str(tmp_path))
        g.record_spend(3.0)
    with patch("orchestrator.cost_guard.time.time", return_value=_ts(2026, 11, 4, 13)):
        assert g.snapshot()["daily_spend"] == 0.0


def test_a_monthly_reservation_is_refused_when_it_would_pass_the_budget(tmp_path: Path) -> None:
    with patch("orchestrator.cost_guard.time.time", return_value=_ts(2026, 11, 3)):
        g = CostGuard(state_dir=str(tmp_path), period="monthly")
        g.set_budget(90.0)
        g.record_spend(89.99)
        with pytest.raises(BudgetExceededError):
            asyncio.run(g.reserve(0.05))
        rid = asyncio.run(g.reserve(0.005))
        asyncio.run(g.commit(rid, 0.004))
        assert g.snapshot()["daily_spend"] == pytest.approx(89.994)


def test_the_period_is_persisted_and_a_mismatch_is_refused(tmp_path: Path) -> None:
    CostGuard(state_dir=str(tmp_path), period="monthly").set_budget(90.0)
    with pytest.raises(ValueError):
        CostGuard(state_dir=str(tmp_path), period="daily").snapshot()
    assert CostGuard(state_dir=str(tmp_path), period="monthly").snapshot()["daily_budget"] == 90.0
