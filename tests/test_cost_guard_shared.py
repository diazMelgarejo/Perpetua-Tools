"""CostGuard is one shared, atomic ledger: instances and processes on one state dir share one budget.

Review finding 2: each instance used to keep its own lock and in-flight holds, so two guards on the same
budget file could both reserve against the same last dollars. Runs offline; the processes are real.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from orchestrator.cost_guard import BudgetExceededError, CostGuard  # noqa: E402

CEILING = 90.0
SETTLED = 89.90
HOLD = 0.06125  # the W&B projected cost of a small prompt; two of them do not fit under the ceiling


def _guard(state: Path, **kw) -> CostGuard:
    """A monthly guard at the W&B ceiling with ``SETTLED`` dollars already spent."""
    g = CostGuard(state_dir=str(state), budget_file="wandb-inference-budget.json", period="monthly", **kw)
    g.set_budget(CEILING)
    if g.snapshot()["daily_spend"] == 0.0:
        g.record_spend(SETTLED)
    return g


def test_two_instances_on_one_state_dir_cannot_both_reserve_the_last_dollars(tmp_path: Path) -> None:
    """Two instances on one state dir cannot both reserve the last dollars."""
    first, second = _guard(tmp_path), _guard(tmp_path)
    rid = asyncio.run(first.reserve(HOLD))
    with pytest.raises(BudgetExceededError):
        asyncio.run(second.reserve(HOLD))
    asyncio.run(first.commit(rid, HOLD))
    assert first.snapshot()["daily_spend"] == pytest.approx(SETTLED + HOLD)
    assert second.snapshot()["daily_spend"] == pytest.approx(SETTLED + HOLD)


def test_a_reservation_made_by_one_instance_can_be_settled_or_released_by_another(tmp_path: Path) -> None:
    """A reservation made by one instance can be settled or released by another."""
    a, b = _guard(tmp_path), _guard(tmp_path)
    rid = asyncio.run(a.reserve(0.05))
    asyncio.run(b.commit(rid, 0.04))
    assert a.snapshot()["daily_spend"] == pytest.approx(SETTLED + 0.04)
    rid2 = asyncio.run(a.reserve(0.05))
    asyncio.run(b.rollback(rid2))
    assert a.in_flight() == 0.0


_WORKER = textwrap.dedent(
    """
    import asyncio, sys
    sys.path.insert(0, sys.argv[1])
    from orchestrator.cost_guard import BudgetExceededError, CostGuard
    g = CostGuard(state_dir=sys.argv[2], budget_file="wandb-inference-budget.json", period="monthly")
    try:
        asyncio.run(g.reserve(float(sys.argv[3])))
        print("RESERVED")
    except BudgetExceededError:
        print("REFUSED")
    """
)


def test_two_processes_cannot_both_reserve_the_last_dollars(tmp_path: Path) -> None:
    """Two processes cannot both reserve the last dollars."""
    _guard(tmp_path)
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", _WORKER, str(REPO_ROOT), str(tmp_path), str(HOLD)],
            stdout=subprocess.PIPE, text=True,
        )
        for _ in range(4)
    ]
    answers = sorted(p.communicate(timeout=60)[0].strip() for p in procs)
    assert [p.returncode for p in procs] == [0, 0, 0, 0]
    assert answers == ["REFUSED", "REFUSED", "REFUSED", "RESERVED"]


def test_an_existing_budget_json_is_migrated_once_into_the_shared_store(tmp_path: Path) -> None:
    """An existing budget json is migrated once into the shared store."""
    legacy = tmp_path / "budget.json"
    legacy.write_text(json.dumps({"daily_budget": 50.0, "daily_spend": 12.5, "last_reset": 1.0e12, "period": "daily"}))
    snap = CostGuard(state_dir=str(tmp_path)).snapshot()
    assert snap["daily_budget"] == 50.0 and snap["daily_spend"] == pytest.approx(12.5)
    legacy.write_text(json.dumps({"daily_budget": 1.0, "daily_spend": 0.0, "last_reset": 1.0e12, "period": "daily"}))
    again = CostGuard(state_dir=str(tmp_path)).snapshot()
    assert again["daily_budget"] == 50.0 and again["daily_spend"] == pytest.approx(12.5)  # imported once only


def test_a_malformed_legacy_budget_json_fails_closed(tmp_path: Path) -> None:
    """A malformed legacy budget json fails closed."""
    (tmp_path / "budget.json").write_text("{not json")
    with pytest.raises(ValueError):
        CostGuard(state_dir=str(tmp_path)).snapshot()


def test_the_snapshot_shape_is_unchanged(tmp_path: Path) -> None:
    """The snapshot shape is unchanged."""
    snap = CostGuard(state_dir=str(tmp_path)).snapshot()
    assert set(snap) == {"daily_budget", "daily_spend", "last_reset", "period", "alert", "remaining"}


def test_an_unwritable_store_fails_closed_instead_of_degrading_to_memory(tmp_path: Path) -> None:
    """An unwritable store fails closed instead of degrading to memory."""
    state = tmp_path / "open"
    state.mkdir(mode=0o700)
    os.chmod(state, 0o777)
    with pytest.raises(PermissionError):
        CostGuard(state_dir=str(state)).snapshot()


def test_a_symlinked_store_is_refused(tmp_path: Path) -> None:
    """A symlinked store is refused."""
    CostGuard(state_dir=str(tmp_path)).snapshot()
    target = tmp_path / "budget.sqlite3"
    moved = tmp_path / "elsewhere.sqlite3"
    target.rename(moved)
    target.symlink_to(moved)
    with pytest.raises(PermissionError):
        CostGuard(state_dir=str(tmp_path)).snapshot()


def test_a_deleted_store_after_migration_fails_closed_instead_of_reimporting(tmp_path: Path) -> None:
    """The legacy json is renamed on import; deleting the store must not resurrect or zero the spend."""
    legacy = tmp_path / "budget.json"
    legacy.write_text(json.dumps({"daily_budget": 50.0, "daily_spend": 12.5, "last_reset": 1.0e12, "period": "daily"}))
    CostGuard(state_dir=str(tmp_path)).snapshot()
    assert not legacy.exists() and (tmp_path / "budget.json.migrated").is_file()
    for store in tmp_path.glob("budget.sqlite3*"):
        store.unlink()
    with pytest.raises(RuntimeError, match=r"budget\.json\.migrated"):
        CostGuard(state_dir=str(tmp_path)).snapshot()
    assert not legacy.exists()  # still not re-imported, and nothing was recreated from zero
    with pytest.raises(RuntimeError):
        CostGuard(state_dir=str(tmp_path)).snapshot()
