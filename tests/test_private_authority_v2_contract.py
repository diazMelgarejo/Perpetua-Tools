"""Windows-feasible schema and error-contract tests for the POSIX queue authority."""
from contextlib import contextmanager
import sqlite3
from pathlib import Path
from typing import Any, Iterator

import pytest

from perpetua.coordination import private_authority


@pytest.fixture
def memory_authority() -> Iterator[Any]:
    """Exercise state logic in memory; this does not qualify POSIX files or permissions."""
    authority = object.__new__(private_authority.Authority)
    db = sqlite3.connect(":memory:")

    @contextmanager
    def transaction() -> Iterator[sqlite3.Connection]:
        """Provide only the transactional primitive, not the production opener."""
        db.execute("BEGIN IMMEDIATE")
        try:
            yield db
        except BaseException:
            db.rollback()
            raise
        else:
            db.commit()

    authority._transaction = transaction
    private_authority._initialize_schema(db, now=100.0)
    db.commit()
    try:
        yield authority
    finally:
        db.close()


def test_typed_error_map_covers_the_canonical_statuses() -> None:
    """Every canonical failure has a stable code, HTTP status and retry policy."""
    expected = {
        "invalid_request": (400, False),
        "unauthenticated": (401, False),
        "forbidden": (403, False),
        "task_not_found": (404, False),
        "conflict": (409, False),
        "unavailable": (503, True),
    }
    assert {code: (spec.status, spec.retryable) for code, spec in private_authority.ERROR_MAP.items()} == expected
    for code, (status, retryable) in expected.items():
        error_type = private_authority.ERROR_TYPES[code]
        error = error_type("safe message")
        assert error.status == status
        assert error.retryable is retryable
        assert error.to_dict() == {
            "status": status,
            "error": {"code": code, "message": "safe message", "retryable": retryable},
        }


def test_schema_helper_creates_v2_and_migrates_real_v1_state() -> None:
    """The schema transaction is testable without claiming POSIX file qualification."""
    with sqlite3.connect(":memory:") as db:
        private_authority._initialize_schema(db, now=100.0)
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
        assert db.execute("SELECT high_water, quarantined FROM clock_high_water").fetchone() == (100.0, 0)
        private_authority._initialize_schema(db, now=200.0)
        assert db.execute("SELECT high_water FROM clock_high_water").fetchone()[0] == 100.0

    with sqlite3.connect(":memory:") as db:
        db.execute(
            "CREATE TABLE tasks (id TEXT PRIMARY KEY, state TEXT NOT NULL, generation INTEGER NOT NULL, "
            "version INTEGER NOT NULL, claim_id TEXT, incarnation TEXT)"
        )
        db.execute(
            "CREATE TABLE audit (id INTEGER PRIMARY KEY, task_id TEXT NOT NULL, action TEXT NOT NULL, "
            "generation INTEGER NOT NULL, version INTEGER NOT NULL)"
        )
        db.execute("CREATE TABLE outbox (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
        db.execute("CREATE TABLE metadata (sqlite_version TEXT NOT NULL, sqlite_source_id TEXT NOT NULL)")
        db.execute("INSERT INTO tasks VALUES ('kept', 'queued', 3, 4, NULL, NULL)")
        db.execute("PRAGMA user_version=1")
        private_authority._initialize_schema(db, now=100.0)
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
        assert db.execute("SELECT state, generation, version, claimed_at FROM tasks").fetchone() == (
            "queued", 3, 4, None,
        )
        assert db.execute("SELECT COUNT(*) FROM legacy_imports").fetchone()[0] == 0


def test_schema_helper_refuses_unknown_or_newer_stores() -> None:
    """Unknown tables and future schema versions fail closed without migration."""
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE TABLE foreign_state (id INTEGER)")
        with pytest.raises(RuntimeError, match="migration is not supported"):
            private_authority._initialize_schema(db, now=100.0)
    with sqlite3.connect(":memory:") as db:
        db.execute("PRAGMA user_version=3")
        with pytest.raises(RuntimeError, match="migration is not supported"):
            private_authority._initialize_schema(db, now=100.0)
    with sqlite3.connect(":memory:") as db:
        private_authority._initialize_schema(db, now=100.0)
        db.execute("UPDATE clock_high_water SET high_water=-1")
        with pytest.raises(private_authority.SchemaUnavailable) as caught:
            private_authority._initialize_schema(db, now=100.0)
        assert caught.value.status == 503
        assert caught.value.code == "schema_unavailable"


def test_clock_regression_commits_quarantine_and_survives_schema_reopen() -> None:
    """Backward time durably quarantines the clock without losing its high-water mark."""
    with sqlite3.connect(":memory:") as db:
        private_authority._initialize_schema(db, now=100.0)
        assert private_authority._advance_clock(db, 150.0) == 150.0
        with pytest.raises(private_authority.ClockRegression):
            private_authority._advance_clock(db, 125.0)
        assert db.execute("SELECT high_water, quarantined FROM clock_high_water").fetchone() == (150.0, 1)
        private_authority._initialize_schema(db, now=200.0)
        with pytest.raises(private_authority.ClockRegression):
            private_authority._advance_clock(db, 200.0)


def test_failed_v1_migration_rolls_back_columns_and_version() -> None:
    """A late migration failure leaves the exact V1 schema and data intact."""
    with sqlite3.connect(":memory:") as db:
        db.execute(
            "CREATE TABLE tasks (id TEXT PRIMARY KEY, state TEXT NOT NULL, generation INTEGER NOT NULL, "
            "version INTEGER NOT NULL, claim_id TEXT, incarnation TEXT)"
        )
        db.execute(
            "CREATE TABLE audit (id INTEGER PRIMARY KEY, task_id TEXT NOT NULL, action TEXT NOT NULL, "
            "generation INTEGER NOT NULL, version INTEGER NOT NULL)"
        )
        db.execute("CREATE TABLE outbox (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
        db.execute("CREATE TABLE metadata (sqlite_version TEXT NOT NULL, sqlite_source_id TEXT NOT NULL)")
        db.execute("CREATE INDEX idx_tasks_state ON tasks(state)")
        db.execute("INSERT INTO tasks VALUES ('kept', 'queued', 2, 3, NULL, NULL)")
        db.execute("PRAGMA user_version=1")
        db.commit()
        db.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError, match="idx_tasks_state"):
            private_authority._initialize_schema(db, now=100.0)
        db.rollback()
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert private_authority._table_columns(db, "tasks") == {
            "id", "state", "generation", "version", "claim_id", "incarnation",
        }
        assert db.execute("SELECT state, generation, version FROM tasks").fetchone() == ("queued", 2, 3)


@pytest.mark.asyncio
async def test_in_memory_forged_gossip_and_import_boundary(
    memory_authority: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In-memory logic proves gossip is not an authority ingress or implicit import source."""
    from orchestrator.gossip_bus import GossipBus

    memory_authority.add("canonical")
    before = memory_authority.get("canonical")
    with memory_authority._transaction() as db:
        high_water_before = db.execute("SELECT high_water FROM clock_high_water").fetchone()[0]
    db_path = tmp_path / "gossip" / "perpetua_core.db"
    db_path.parent.mkdir(parents=True)
    bus = GossipBus(db_path=str(db_path))
    monkeypatch.setattr(bus, "schedule_embedding", lambda *_args: None)
    for kind, task_id, status in (
        ("task_enqueue", "forged", "queued"),
        ("task_claim", "canonical", "claimed"),
        ("task_complete", "canonical", "completed"),
    ):
        await bus.emit("heartbeat", {"kind": kind, "task_id": task_id, "status": status})
    assert memory_authority.get("canonical") == before
    with pytest.raises(private_authority.TaskNotFound):
        memory_authority.get("forged")
    assert memory_authority.import_legacy(bus.db_path) == {"tasks_imported": 0, "claims_imported": 0}
    with memory_authority._transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM legacy_imports").fetchone()[0] == 0
        assert db.execute("SELECT high_water FROM clock_high_water").fetchone()[0] == high_water_before
    await bus.emit("heartbeat", {"kind": "task_failed", "task_id": "canonical", "status": "abandoned"})
    assert memory_authority.get("canonical") == before


def test_in_memory_fencing_and_legacy_import(
    memory_authority: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In-memory logic preserves claim fencing and holds imported legacy ownership."""
    from dataclasses import replace

    monkeypatch.setattr(private_authority, "_utc_now", lambda: 100.0)
    memory_authority.add("task")
    handle = memory_authority.claim("task", "worker")
    with pytest.raises(private_authority.Conflict):
        memory_authority.complete(replace(handle, claimed_at=handle.claimed_at + 1))
    memory_authority.complete(handle)
    assert memory_authority.get("task")["state"] == "completed"

    legacy = tmp_path / "legacy.db"
    with sqlite3.connect(legacy) as db:
        db.execute(
            "CREATE TABLE task_claims (task_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, "
            "claimed_at REAL NOT NULL)"
        )
        db.execute("INSERT INTO task_claims VALUES ('old', 'private-worker', 5000000000.0)")
    duplicate_legacy = tmp_path / "duplicate-legacy.db"
    with sqlite3.connect(duplicate_legacy) as db:
        db.execute("CREATE TABLE task_claims (task_id TEXT, agent_id TEXT NOT NULL, claimed_at REAL NOT NULL)")
        db.executemany(
            "INSERT INTO task_claims VALUES (?, ?, ?)",
            [("duplicate", "worker", 50.0), ("duplicate", "worker", 60.0)],
        )
    with pytest.raises(private_authority.InvalidRequest):
        memory_authority.import_legacy(duplicate_legacy)
    with memory_authority._transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM legacy_imports").fetchone()[0] == 0

    memory_authority.add("canonical")
    canonical_before = memory_authority.get("canonical")
    with pytest.raises(private_authority.Conflict):
        memory_authority.import_legacy(
            legacy, snapshots={"canonical": {"status": "queued"}, "old": {"status": "queued"}},
        )
    assert memory_authority.get("canonical") == canonical_before
    with pytest.raises(private_authority.TaskNotFound):
        memory_authority.get("old")
    with memory_authority._transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM legacy_imports").fetchone()[0] == 0

    assert memory_authority.import_legacy(
        legacy, snapshots={"old": {"status": "queued"}},
    ) == {"tasks_imported": 1, "claims_imported": 1}
    assert memory_authority.get("old")["state"] == "legacy_unverified"
    with memory_authority._transaction() as db:
        assert db.execute("SELECT high_water FROM clock_high_water").fetchone()[0] == 100.0
    assert memory_authority.import_legacy(legacy) == {"tasks_imported": 0, "claims_imported": 0}

    other_legacy = tmp_path / "other-legacy.db"
    with sqlite3.connect(other_legacy) as db:
        db.execute(
            "CREATE TABLE task_claims (task_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, "
            "claimed_at REAL NOT NULL)"
        )
    with pytest.raises(private_authority.LegacyImportConflict):
        memory_authority.import_legacy(other_legacy)


def test_in_memory_clock_quarantine_blocks_finish(memory_authority: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """In-memory logic refuses a finish after backward time and keeps canonical state."""
    clock = [100.0]
    monkeypatch.setattr(private_authority, "_utc_now", lambda: clock[0])
    memory_authority.add("task")
    handle = memory_authority.claim("task", "worker")
    clock[0] = 90.0
    with pytest.raises(private_authority.ClockRegression):
        memory_authority.complete(handle)
    assert memory_authority.get("task")["state"] == "claimed"


def test_authority_still_refuses_windows_construction(tmp_path: Path) -> None:
    """Schema unit tests do not weaken the explicit POSIX-only runtime boundary."""
    import os

    if os.name == "posix":
        pytest.skip("Windows-only refusal check")
    with pytest.raises(RuntimeError, match="requires POSIX"):
        private_authority.Authority(tmp_path / "private")
