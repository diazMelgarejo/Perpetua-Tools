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


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits are not enforced on Windows")
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


def test_refused_first_operation_preserves_legacy_import(tmp_path: Path) -> None:
    """A rejected first reservation cannot strand the legacy migration."""
    legacy = tmp_path / "budget.json"
    legacy.write_text(json.dumps({"daily_budget": 1.0, "daily_spend": 0.8, "last_reset": 1e12}))
    guard = CostGuard(state_dir=str(tmp_path))
    with pytest.raises(BudgetExceededError):
        guard.reserve_sync(0.3)
    assert CostGuard(state_dir=str(tmp_path)).snapshot()["daily_spend"] == pytest.approx(0.8)


def test_uncertain_hold_survives_expiry_and_restart(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A possibly sent request blocks admission after expiry until reconciled."""
    import orchestrator.cost_guard as module
    monkeypatch.setattr(module.time, "time", lambda: 1000.0)
    first = CostGuard(state_dir=str(tmp_path))
    rid = first.reserve_sync(1.0, 1.0, uncertain=True)
    monkeypatch.setattr(module.time, "time", lambda: 1002.0)
    second = CostGuard(state_dir=str(tmp_path))
    with pytest.raises(RuntimeError, match="reconcil"):
        second.reserve_sync(0.1)
    assert second.in_flight() == pytest.approx(1.0)
    second.commit_sync(rid)
    assert second.snapshot()["daily_spend"] == pytest.approx(1.0)
    assert second.reserve_sync(0.1)


def test_migration_retries_after_post_commit_rename_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A crash at the rename boundary leaves a committed import available on restart."""
    import orchestrator.cost_guard as module
    legacy = tmp_path / "budget.json"
    legacy.write_text(json.dumps({"daily_budget": 5.0, "daily_spend": 2.0, "last_reset": 1e12}))
    real_link = module.os.link
    def fail_link(source: object, destination: object) -> None:
        """Simulate a failed rename after the import commits."""
        raise OSError("simulated crash")
    monkeypatch.setattr(module.os, "link", fail_link)
    with pytest.raises(OSError, match="simulated crash"):
        CostGuard(state_dir=str(tmp_path)).snapshot()
    monkeypatch.setattr(module.os, "link", real_link)
    assert CostGuard(state_dir=str(tmp_path)).snapshot()["daily_spend"] == pytest.approx(2.0)
    assert not legacy.exists()
    assert legacy.with_name("budget.json.migrated").exists()


def test_uncertain_hold_blocks_a_new_process_after_expiry(tmp_path: Path) -> None:
    """A separate interpreter cannot reuse an expired potentially sent reservation."""
    import sqlite3
    guard = CostGuard(state_dir=str(tmp_path))
    rid = guard.reserve_sync(1.0, 1.0, uncertain=True)
    with sqlite3.connect(guard.store_path) as db:
        db.execute("UPDATE reservations SET expires_at = 0 WHERE id = ?", (rid,))
    code = "from orchestrator.cost_guard import CostGuard; import sys; CostGuard(state_dir=sys.argv[1]).reserve_sync(0.1)"
    proc = subprocess.run([sys.executable, "-c", code, str(tmp_path)], cwd=REPO_ROOT, capture_output=True, text=True)
    assert proc.returncode != 0 and "reconciliation" in proc.stderr
    assert guard.in_flight() == pytest.approx(1.0)


def test_migration_survives_process_exit_after_import_commit(tmp_path: Path) -> None:
    """A killed process between import commit and rename can be recovered on restart."""
    legacy = tmp_path / "budget.json"
    legacy.write_text(json.dumps({"daily_budget": 5.0, "daily_spend": 2.0, "last_reset": 1e12}))
    code = ("import os, sys; import orchestrator.cost_guard as m; "
            "m.os.link=lambda *a: os._exit(73); m.CostGuard(state_dir=sys.argv[1]).snapshot()")
    child = subprocess.run([sys.executable, "-c", code, str(tmp_path)], cwd=REPO_ROOT)
    assert child.returncode == 73 and legacy.exists()
    assert CostGuard(state_dir=str(tmp_path)).snapshot()["daily_spend"] == pytest.approx(2.0)
    assert legacy.with_name("budget.json.migrated").exists()


def test_set_budget_rejects_mismatched_period_without_changing_ledger(tmp_path: Path) -> None:
    """A guard configured for another period cannot alter the shared ceiling."""
    monthly = CostGuard(state_dir=str(tmp_path), period="monthly")
    monthly.set_budget(90.0)
    monthly.record_spend(10.0)
    before = monthly.snapshot()
    with pytest.raises(ValueError, match="monthly"):
        CostGuard(state_dir=str(tmp_path), period="daily").set_budget(500.0)
    assert monthly.snapshot() == before


def test_existing_sqlite_reservations_upgrade_without_losing_accounting(tmp_path: Path) -> None:
    """Upgrade a populated pre-uncertainty SQLite schema and retain its active hold."""
    import sqlite3
    import time
    db_path = tmp_path / "budget.sqlite3"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE budget (id INTEGER PRIMARY KEY, daily_budget REAL NOT NULL, daily_spend REAL NOT NULL, last_reset REAL NOT NULL, period TEXT NOT NULL)")
        db.execute("CREATE TABLE reservations (id TEXT PRIMARY KEY, amount REAL NOT NULL, reserved_at REAL NOT NULL, expires_at REAL NOT NULL)")
        db.execute("CREATE TABLE swept (id TEXT PRIMARY KEY, amount REAL NOT NULL, swept_at REAL NOT NULL)")
        db.execute("INSERT INTO budget VALUES (1, 10, 3, ?, 'daily')", (time.time(),))
        db.execute("INSERT INTO reservations VALUES ('old', 2, ?, ?)", (time.time(), time.time() - 1))
        db.execute("INSERT INTO swept VALUES ('late', 1, ?)", (time.time() - 5,))
    db_path.chmod(0o600)
    guard = CostGuard(state_dir=str(tmp_path))
    assert guard.snapshot()["daily_spend"] == pytest.approx(3)
    assert guard.in_flight() == pytest.approx(3)
    with pytest.raises(RuntimeError, match="reconcil"):
        guard.reserve_sync(6)
    assert guard.commit_sync("old")["daily_spend"] == pytest.approx(5)
    assert guard.commit_sync("late")["daily_spend"] == pytest.approx(6)
    rid = guard.reserve_sync(1, 10, uncertain=True)
    with sqlite3.connect(db_path) as db:
        assert db.execute("SELECT uncertain FROM reservations WHERE id = ?", (rid,)).fetchone() == (1,)
