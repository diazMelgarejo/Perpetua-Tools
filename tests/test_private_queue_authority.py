"""Fenced private queue core; it is not yet wired to legacy queue callers."""
import multiprocessing
import os
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from perpetua.coordination import private_authority
from perpetua.coordination.private_authority import Authority, Conflict


@pytest.fixture(autouse=True)
def require_qualified_interpreter(request: pytest.FixtureRequest) -> None:
    """Keep the unsupported-version refusal test active on POSIX."""
    if os.name != "posix":
        pytest.skip("private authority core supports POSIX only")
    if (
        request.node.name != "test_refuses_unsupported_sqlite_without_creating_store"
        and sqlite3.sqlite_version_info < (3, 51, 3)
    ):
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


@pytest.mark.asyncio
async def test_forged_gossip_cannot_mutate_or_be_implicitly_imported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forged events never fold into canonical state, even across the one-time import boundary."""
    from orchestrator.gossip_bus import GossipBus

    authority = Authority(tmp_path / "private")
    authority.add("canonical")
    before = authority.get("canonical")
    db_path = tmp_path / "gossip" / "perpetua_core.db"
    db_path.parent.mkdir(parents=True)
    bus = GossipBus(db_path=str(db_path))
    monkeypatch.setattr(bus, "schedule_embedding", lambda *_args: None)
    for kind, task_id, status in (
        ("task_enqueue", "forged", "queued"),
        ("task_claim", "canonical", "claimed"),
        ("task_complete", "canonical", "completed"),
        ("task_failed", "canonical", "abandoned"),
    ):
        await bus.emit("heartbeat", {"kind": kind, "task_id": task_id, "status": status})

    assert authority.get("canonical") == before
    with pytest.raises(KeyError):
        authority.get("forged")
    assert authority.import_legacy(bus.db_path) == {"tasks_imported": 0, "claims_imported": 0}
    with sqlite3.connect(tmp_path / "private" / "queue.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM legacy_imports").fetchone()[0] == 0
    await bus.emit("heartbeat", {"kind": "task_claim", "task_id": "canonical", "status": "claimed"})
    assert authority.get("canonical") == before
    with pytest.raises(KeyError):
        authority.get("forged")


def _create_v1_store(path: Path) -> None:
    """Create the exact pre-V2 schema so migration is tested from real V1 state."""
    path.mkdir(mode=0o700)
    with sqlite3.connect(path / "queue.sqlite3") as db:
        db.execute(
            "CREATE TABLE tasks (id TEXT PRIMARY KEY, state TEXT NOT NULL, "
            "generation INTEGER NOT NULL, version INTEGER NOT NULL, claim_id TEXT, incarnation TEXT)"
        )
        db.execute(
            "CREATE TABLE audit (id INTEGER PRIMARY KEY, task_id TEXT NOT NULL, action TEXT NOT NULL, "
            "generation INTEGER NOT NULL, version INTEGER NOT NULL)"
        )
        db.execute("CREATE TABLE outbox (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
        db.execute("CREATE TABLE metadata (sqlite_version TEXT NOT NULL, sqlite_source_id TEXT NOT NULL)")
        db.execute("INSERT INTO metadata SELECT sqlite_version(), sqlite_source_id()")
        db.execute("INSERT INTO tasks VALUES ('kept', 'queued', 7, 9, NULL, NULL)")
        db.execute("INSERT INTO audit (task_id, action, generation, version) VALUES ('kept', 'add', 0, 1)")
        db.execute("PRAGMA user_version=1")
    (path / "queue.sqlite3").chmod(0o600)


def test_v1_store_migrates_once_without_losing_fencing_state(tmp_path: Path) -> None:
    """Opening V1 atomically adds V2 state while preserving generations, versions and audit."""
    path = tmp_path / "private"
    _create_v1_store(path)
    authority = Authority(path)
    assert authority.get("kept") == {"state": "queued", "generation": 7, "version": 9}
    with sqlite3.connect(path / "queue.sqlite3") as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
        assert db.execute("SELECT generation, version, claimed_at FROM tasks").fetchone() == (7, 9, None)
        assert db.execute("SELECT action, observed_at FROM audit").fetchone() == ("add", None)
        assert db.execute("SELECT high_water, quarantined FROM clock_high_water").fetchone()[1] == 0
        assert db.execute("SELECT COUNT(*) FROM legacy_imports").fetchone()[0] == 0
    Authority(path)
    with sqlite3.connect(path / "queue.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM audit").fetchone()[0] == 1


def test_backward_clock_quarantines_mutations_durably(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Backward time refuses fenced mutation and remains refused after restart and time recovery."""
    path = tmp_path / "private"
    clock = [100.0]
    monkeypatch.setattr(private_authority, "_utc_now", lambda: clock[0])
    authority = Authority(path)
    authority.add("task")
    clock[0] = 200.0
    handle = authority.claim("task", "worker")
    assert handle.claimed_at == 200.0
    clock[0] = 150.0
    with pytest.raises(private_authority.ClockRegression) as caught:
        authority.complete(handle)
    assert caught.value.status == 503
    assert caught.value.code == "clock_regressed"
    assert authority.get("task")["state"] == "claimed"
    with sqlite3.connect(path / "queue.sqlite3") as db:
        assert db.execute("SELECT high_water, quarantined FROM clock_high_water").fetchone() == (200.0, 1)
    clock[0] = 300.0
    restarted = Authority(path)
    with pytest.raises(private_authority.ClockRegression):
        restarted.complete(handle)
    assert restarted.get("task")["state"] == "claimed"


def test_legacy_import_is_one_time_and_holds_active_claims(tmp_path: Path) -> None:
    """Explicit snapshots import once; legacy ownership is held and never overwrites canonical state."""
    import hashlib
    import json

    legacy = tmp_path / "legacy.db"
    with sqlite3.connect(legacy) as db:
        db.execute(
            "CREATE TABLE task_claims (task_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, "
            "claimed_at REAL NOT NULL)"
        )
        db.execute("INSERT INTO task_claims VALUES ('legacy-claimed', 'old-worker', 50.0)")
    snapshots = {
        "legacy-queued": {"status": "queued"},
        "legacy-claimed": {"status": "claimed"},
    }
    authority = Authority(tmp_path / "private")
    assert authority.import_legacy(legacy, snapshots=snapshots) == {"tasks_imported": 2, "claims_imported": 1}
    assert authority.get("legacy-queued")["state"] == "queued"
    assert authority.get("legacy-claimed")["state"] == "legacy_unverified"
    assert authority.import_legacy(legacy, snapshots=snapshots) == {"tasks_imported": 0, "claims_imported": 0}
    with sqlite3.connect(tmp_path / "private" / "queue.sqlite3") as db:
        digest = hashlib.sha256(legacy.read_bytes()).hexdigest()
        assert db.execute("SELECT source_digest FROM legacy_imports").fetchone()[0] == digest
        payloads = [json.loads(row[0]) for row in db.execute("SELECT payload FROM outbox")]
    assert all(payload["authoritative"] is False for payload in payloads)
    assert "old-worker" not in json.dumps(payloads)

    authority.add("canonical")
    before = authority.get("canonical")
    other_legacy = tmp_path / "other-legacy.db"
    with sqlite3.connect(other_legacy) as db:
        db.execute(
            "CREATE TABLE task_claims (task_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, "
            "claimed_at REAL NOT NULL)"
        )
    with pytest.raises(Conflict):
        authority.import_legacy(other_legacy, snapshots={"canonical": {"status": "queued"}})
    assert authority.get("canonical") == before

    fresh = Authority(tmp_path / "fresh-private")
    fresh.add("canonical")
    before = fresh.get("canonical")
    with pytest.raises(Conflict):
        fresh.import_legacy(other_legacy, snapshots={"canonical": {"status": "queued"}})
    assert fresh.get("canonical") == before
    with sqlite3.connect(tmp_path / "fresh-private" / "queue.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM legacy_imports").fetchone()[0] == 0


def test_renew_lease_advances_version_and_fences_stale(tmp_path: Path) -> None:
    """Exercise renew advances version without advancing generation and fences stale handles."""
    authority = Authority(tmp_path / "private")
    authority.add("task")
    h1 = authority.claim("task", "worker")
    h2 = authority.renew(h1)
    assert h2.version == h1.version + 1
    assert h2.generation == h1.generation
    assert h2.claim_id == h1.claim_id
    assert h2.incarnation == h1.incarnation
    with pytest.raises(Conflict):
        authority.renew(h1)
    with pytest.raises(Conflict):
        authority.complete(h1)
    authority.complete(h2)
    assert authority.get("task")["state"] == "completed"


def test_fail_acquisition_marks_failed_and_fences_stale(tmp_path: Path) -> None:
    """Exercise fail moves acquisition to terminal failed state and fences stale calls."""
    authority = Authority(tmp_path / "private")
    authority.add("task")
    h = authority.claim("task", "worker")
    authority.fail(h, detail="worker fault")
    assert authority.get("task")["state"] == "failed"
    with pytest.raises(Conflict):
        authority.claim("task", "worker2")
    with pytest.raises(Conflict):
        authority.fail(h)


def test_authority_service_dispatch_and_unauthenticated_guard(tmp_path: Path) -> None:
    """Exercise AuthorityService with strict authentication on POSIX."""
    from perpetua.coordination.authority_service import AuthorityService

    authority = Authority(tmp_path / "private")
    service = AuthorityService(authority, authenticate=None)
    service.start()
    status, resp = service.handle_request("POST", "/authority/tasks", body={"task_id": "t1"})
    assert status == 401
    assert resp["error"]["code"] == "unauthenticated"

    service_auth = AuthorityService(authority, authenticate=lambda *a: True)
    service_auth.start()
    status, resp = service_auth.handle_request("POST", "/authority/tasks", body={"task_id": "t1"})
    assert status == 201
    status, claim = service_auth.handle_request("POST", "/authority/claim", body={"task_id": "t1", "incarnation": "w1"})
    assert status == 200
    status, renew = service_auth.handle_request("POST", "/authority/renew", body=claim)
    assert status == 200
    assert renew["version"] == claim["version"] + 1
    status, comp = service_auth.handle_request("POST", "/authority/complete", body=renew)
    assert status == 200
