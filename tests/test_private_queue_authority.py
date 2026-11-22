"""Fenced private queue core; it is not yet wired to legacy queue callers."""
import multiprocessing
import os
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from perpetua.coordination.private_authority import Authority, Conflict


@pytest.fixture(autouse=True)
def require_qualified_interpreter(request: pytest.FixtureRequest) -> None:
    """Keep the unsupported-version refusal test active on POSIX."""
    if os.name != "posix":
        pytest.skip("private authority core supports POSIX only")
    if request.node.name != "test_refuses_unsupported_sqlite_without_creating_store" and sqlite3.sqlite_version_info < (3, 51, 3):
        pytest.skip("private authority requires SQLite >= 3.51.3")

def _contend(path: Path, start: Any, ready: Any, results: Any) -> None:
    """Attempt one claim after the shared start barrier."""
    authority = Authority(path)
    ready.put(True)
    start.wait()
    try:
        authority.claim("task", "worker")
        results.put(True)
    except Conflict:
        results.put(False)


def test_ten_contenders_and_restart_keep_one_acquisition(tmp_path: Path) -> None:
    """Exercise ten contenders and restart keep one acquisition."""
    authority = Authority(tmp_path / "private")
    authority.add("task")
    ctx = multiprocessing.get_context("spawn")
    start = ctx.Event()
    ready = ctx.Queue()
    results = ctx.Queue()
    children = [ctx.Process(target=_contend, args=(tmp_path / "private", start, ready, results)) for _ in range(10)]
    try:
        for child in children:
            child.start()
        for _ in children:
            assert ready.get(timeout=30) is True
        start.set()
        outcomes = [results.get(timeout=30) for _ in children]
        for child in children:
            child.join(30)
            assert child.exitcode == 0
        assert sum(outcomes) == 1
    finally:
        for child in children:
            if child.is_alive():
                child.terminate()
            if child.pid is not None:
                child.join(30)
        ready.close()
        results.close()
    assert Authority(tmp_path / "private").get("task")["generation"] == 1


def test_stale_same_name_acquisition_cannot_complete(tmp_path: Path) -> None:
    """Exercise stale same name acquisition cannot complete."""
    authority = Authority(tmp_path / "private")
    authority.add("task")
    old = authority.claim("task", "worker")
    authority.release(old)
    current = authority.claim("task", "worker")
    assert current.generation == old.generation + 1
    with pytest.raises(Conflict):
        authority.complete(old)
    authority.complete(current)
    assert authority.get("task")["state"] == "completed"


def test_failed_audit_rolls_back_claim(tmp_path: Path) -> None:
    """Exercise failed audit rolls back claim."""
    import sqlite3

    path = tmp_path / "private"
    authority = Authority(path)
    authority.add("task")
    with sqlite3.connect(path / "queue.sqlite3") as db:
        db.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON audit BEGIN SELECT RAISE(ABORT, 'injected'); END")
    with pytest.raises(sqlite3.IntegrityError):
        authority.claim("task", "worker")
    assert authority.get("task") == {"state": "queued", "generation": 0, "version": 1}


def test_refuses_foreign_store(tmp_path: Path) -> None:
    """Exercise refuses foreign store."""
    import sqlite3

    path = tmp_path / "private"
    path.mkdir(mode=0o700)
    with sqlite3.connect(path / "queue.sqlite3") as db:
        db.execute("CREATE TABLE legacy (id INTEGER)")
    (path / "queue.sqlite3").chmod(0o600)
    with pytest.raises(RuntimeError, match="migration is not supported"):
        Authority(path)


def test_rejects_wrong_incarnation_even_with_other_handle_fields(tmp_path: Path) -> None:
    """Exercise rejects wrong incarnation even with other handle fields."""
    from dataclasses import replace

    authority = Authority(tmp_path / "private")
    authority.add("task")
    handle = authority.claim("task", "worker")
    with pytest.raises(Conflict):
        authority.complete(replace(handle, incarnation="other"))


def test_refuses_unsupported_sqlite_without_creating_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise refuses unsupported sqlite without creating store."""
    import sqlite3

    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 51, 2))
    path = tmp_path / "private"
    with pytest.raises(RuntimeError, match="SQLite >= 3.51.3"):
        Authority(path)
    assert not path.exists()


def test_outbox_projection_is_non_authoritative_and_redacts_incarnation(tmp_path: Path) -> None:
    """Exercise outbox projection is non authoritative and redacts incarnation."""
    import json
    import sqlite3

    path = tmp_path / "private"
    authority = Authority(path)
    authority.add("task")
    handle = authority.claim("task", "sensitive-incarnation")
    with sqlite3.connect(path / "queue.sqlite3") as db:
        payloads = [json.loads(row[0]) for row in db.execute("SELECT payload FROM outbox")]
    assert all(item["authoritative"] is False for item in payloads)
    assert "sensitive-incarnation" not in json.dumps(payloads)
    assert handle.claim_id not in json.dumps(payloads)


def test_connections_close_after_success_and_conflict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise connections close after success and conflict."""
    import sqlite3

    authority = Authority(tmp_path / "private")
    original = authority._connect
    opened = []

    def tracked() -> sqlite3.Connection:
        """Retain the connection so closure can be observed."""
        db = original()
        opened.append(db)
        return db

    monkeypatch.setattr(authority, "_connect", tracked)
    authority.add("task")
    with pytest.raises(Conflict):
        authority.add("task")
    for db in opened:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            db.execute("SELECT 1")


@pytest.mark.parametrize("value", [True, 1, b"task", "", "   "])
def test_add_rejects_invalid_task_id(tmp_path: Path, value: Any) -> None:
    """Exercise add rejects invalid task id."""
    authority = Authority(tmp_path / "private")
    with pytest.raises(ValueError):
        authority.add(value)


def test_version_and_handle_type_mismatch_refuse(tmp_path: Path) -> None:
    """Reject stale versions and boolean generations before mutation."""
    from dataclasses import replace

    authority = Authority(tmp_path / "private")
    authority.add("task")
    handle = authority.claim("task", "worker")
    with pytest.raises(Conflict):
        authority.complete(replace(handle, version=handle.version + 1))
    with pytest.raises(ValueError):
        authority.complete(replace(handle, generation=True))
    assert authority.get("task")["state"] == "claimed"


def test_store_records_actual_sqlite_build(tmp_path: Path) -> None:
    """Persist the SQLite version and source ID used on creation."""
    path = tmp_path / "private"
    Authority(path)
    with sqlite3.connect(path / "queue.sqlite3") as db:
        actual = db.execute("SELECT sqlite_version(), sqlite_source_id()").fetchone()
        recorded = db.execute("SELECT sqlite_version, sqlite_source_id FROM metadata").fetchone()
    assert recorded == actual


def test_refuses_existing_wal_store(tmp_path: Path) -> None:
    """A store in an unqualified journal mode is never silently reopened."""
    path = tmp_path / "private"
    Authority(path)
    with sqlite3.connect(path / "queue.sqlite3") as db:
        assert db.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    with pytest.raises(RuntimeError, match="journal mode"):
        Authority(path)


def test_wal_switched_after_open_refuses_transitions(tmp_path: Path) -> None:
    """A later journal change cannot permit a transition or alter state."""
    path = tmp_path / "private"
    authority = Authority(path)
    authority.add("task")
    with sqlite3.connect(path / "queue.sqlite3") as db:
        before = db.execute("SELECT * FROM tasks").fetchall()
        assert db.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    with pytest.raises(RuntimeError, match="journal mode"):
        authority.claim("task", "worker")
    with sqlite3.connect(path / "queue.sqlite3") as db:
        assert db.execute("SELECT * FROM tasks").fetchall() == before
