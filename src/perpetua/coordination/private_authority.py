"""Non-deployable local building block for the future PT queue authority.

This module is not connected to the legacy queue or any transport.  A handle
fences acquisitions; it does not authenticate a worker.  In particular, do not
use this store as a protected queue until caller and migration closure is done.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
from typing import Any
import uuid

from orchestrator.private_sqlite import open_private_sqlite


@dataclass(frozen=True)
class ErrorMapping:
    """Stable transport mapping for one canonical authority failure code."""

    status: int
    retryable: bool


ERROR_MAP: dict[str, ErrorMapping] = {
    "invalid_request": ErrorMapping(400, False),
    "unauthenticated": ErrorMapping(401, False),
    "forbidden": ErrorMapping(403, False),
    "task_not_found": ErrorMapping(404, False),
    "conflict": ErrorMapping(409, False),
    "unavailable": ErrorMapping(503, True),
}


class AuthorityError(RuntimeError):
    """Base typed error carrying a safe status envelope and retry policy."""

    code = "unavailable"
    status = 503
    retryable = True

    def __init__(self, message: str) -> None:
        """Store a caller-safe message without persistence or transport details."""
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        """Return the safe message even for the KeyError-compatible not-found type."""
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """Serialize the canonical error envelope without exception internals."""
        return {
            "status": self.status,
            "error": {"code": self.code, "message": self.message, "retryable": self.retryable},
        }


class InvalidRequest(AuthorityError, ValueError):
    """The request is malformed or asks for an unsupported legacy disposition."""

    code = "invalid_request"
    status = 400
    retryable = False


class Unauthenticated(AuthorityError):
    """A future transport boundary has no valid authentication."""

    code = "unauthenticated"
    status = 401
    retryable = False


class Forbidden(AuthorityError):
    """A future authenticated caller lacks the required scope."""

    code = "forbidden"
    status = 403
    retryable = False


class TaskNotFound(AuthorityError, KeyError):
    """An authorized lookup names no canonical task."""

    code = "task_not_found"
    status = 404
    retryable = False


class Conflict(AuthorityError):
    """The requested transition no longer matches the canonical acquisition."""

    code = "conflict"
    status = 409
    retryable = False


class Unavailable(AuthorityError):
    """The authority cannot safely serve a request or its store is busy."""

    code = "unavailable"
    status = 503
    retryable = True


class ClockRegression(Unavailable):
    """Backward time or an unreconciled clock quarantine forbids mutation."""

    code = "clock_regressed"
    retryable = False


class SchemaUnavailable(Unavailable):
    """The on-disk schema is unsupported, incomplete or internally inconsistent."""

    code = "schema_unavailable"
    retryable = False


class UnsupportedSQLite(Unavailable):
    """The interpreter cannot satisfy the qualified SQLite floor."""

    code = "sqlite_unsupported"
    retryable = False


class StoreUnavailable(Unavailable):
    """SQLite could not acquire the write lock or serve the private store."""

    code = "store_unavailable"
    retryable = True


class JournalUnavailable(StoreUnavailable):
    """The private store uses an unqualified SQLite journal mode."""

    code = "journal_unavailable"
    retryable = False


class LegacyImportConflict(Conflict):
    """A different legacy source was supplied after the one-time import completed."""

    code = "legacy_import_conflict"


ERROR_TYPES: dict[str, type[AuthorityError]] = {
    "invalid_request": InvalidRequest,
    "unauthenticated": Unauthenticated,
    "forbidden": Forbidden,
    "task_not_found": TaskNotFound,
    "conflict": Conflict,
    "unavailable": Unavailable,
}


@dataclass(frozen=True)
class ClaimHandle:
    """Acquisition identity and task version; not a proof of worker identity."""

    task_id: str
    claim_id: str
    generation: int
    version: int
    incarnation: str
    claimed_at: float


def _utc_now() -> float:
    """Sample timezone-aware UTC time as Unix seconds."""
    return datetime.now(timezone.utc).timestamp()


def _timestamp(value: Any, label: str) -> float:
    """Validate a finite, nonnegative Unix timestamp without accepting booleans."""
    if type(value) not in {int, float}:
        raise InvalidRequest(f"{label} must be a finite nonnegative timestamp")
    try:
        timestamp = float(value)
    except (OverflowError, ValueError) as exc:
        raise InvalidRequest(f"{label} must be a finite nonnegative timestamp") from exc
    if not math.isfinite(timestamp) or timestamp < 0:
        raise InvalidRequest(f"{label} must be a finite nonnegative timestamp")
    return timestamp


def _stored_timestamp(value: Any, label: str) -> float:
    """Validate persisted clock data as store corruption, never caller input."""
    try:
        return _timestamp(value, label)
    except InvalidRequest as exc:
        raise SchemaUnavailable("private queue clock is invalid") from exc


def _table_columns(db: sqlite3.Connection, table: str) -> set[str]:
    """Return a table's column names for exact schema-family checks."""
    return {row[1] for row in db.execute(f"PRAGMA table_info({table})")}


def _create_v2_extras(db: sqlite3.Connection, now: float) -> None:
    """Create V2-only tables and indexes after base-table validation."""
    db.execute(
        "CREATE TABLE clock_high_water (id INTEGER PRIMARY KEY CHECK (id=1), "
        "high_water REAL NOT NULL, quarantined INTEGER NOT NULL DEFAULT 0 CHECK (quarantined IN (0, 1)))"
    )
    db.execute(
        "CREATE TABLE legacy_imports (id INTEGER PRIMARY KEY CHECK (id=1), "
        "source_digest TEXT NOT NULL UNIQUE, imported_at REAL NOT NULL, "
        "tasks_imported INTEGER NOT NULL, claims_imported INTEGER NOT NULL)"
    )
    db.execute("CREATE INDEX idx_tasks_state ON tasks(state)")
    db.execute("CREATE INDEX idx_audit_task_id ON audit(task_id)")
    db.execute("INSERT INTO clock_high_water (id, high_water, quarantined) VALUES (1, ?, 0)", (now,))


def _initialize_schema(db: sqlite3.Connection, *, now: float) -> None:
    """Create V2 or migrate an exact V1 store inside the caller's write transaction."""
    now = _timestamp(now, "now")
    version = db.execute("PRAGMA user_version").fetchone()[0]
    tables = {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    }
    v1_tables = {"tasks", "audit", "outbox", "metadata"}
    v2_tables = v1_tables | {"clock_high_water", "legacy_imports"}
    v1_task_columns = {"id", "state", "generation", "version", "claim_id", "incarnation"}
    v1_audit_columns = {"id", "task_id", "action", "generation", "version"}
    metadata_columns = {"sqlite_version", "sqlite_source_id"}

    if version == 0 and not tables:
        db.execute(
            "CREATE TABLE tasks (id TEXT PRIMARY KEY, state TEXT NOT NULL, "
            "generation INTEGER NOT NULL, version INTEGER NOT NULL, claim_id TEXT, "
            "incarnation TEXT, claimed_at REAL)"
        )
        db.execute(
            "CREATE TABLE audit (id INTEGER PRIMARY KEY, task_id TEXT NOT NULL, action TEXT NOT NULL, "
            "generation INTEGER NOT NULL, version INTEGER NOT NULL, observed_at REAL)"
        )
        db.execute("CREATE TABLE outbox (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
        db.execute("CREATE TABLE metadata (sqlite_version TEXT NOT NULL, sqlite_source_id TEXT NOT NULL)")
        db.execute("INSERT INTO metadata SELECT sqlite_version(), sqlite_source_id()")
        _create_v2_extras(db, now)
    elif version == 1 and tables == v1_tables:
        if (
            _table_columns(db, "tasks") != v1_task_columns
            or _table_columns(db, "audit") != v1_audit_columns
            or _table_columns(db, "metadata") != metadata_columns
            or _table_columns(db, "outbox") != {"id", "payload"}
        ):
            raise SchemaUnavailable("unrecognized private queue store; migration is not supported")
        db.execute("ALTER TABLE tasks ADD COLUMN claimed_at REAL")
        db.execute("ALTER TABLE audit ADD COLUMN observed_at REAL")
        _create_v2_extras(db, now)
    elif version == 2 and tables == v2_tables:
        if (
            _table_columns(db, "tasks") != v1_task_columns | {"claimed_at"}
            or _table_columns(db, "audit") != v1_audit_columns | {"observed_at"}
            or _table_columns(db, "metadata") != metadata_columns
            or _table_columns(db, "outbox") != {"id", "payload"}
            or _table_columns(db, "clock_high_water") != {"id", "high_water", "quarantined"}
            or _table_columns(db, "legacy_imports")
            != {"id", "source_digest", "imported_at", "tasks_imported", "claims_imported"}
        ):
            raise SchemaUnavailable("unrecognized private queue store; migration is not supported")
        clocks = db.execute("SELECT id, high_water, quarantined FROM clock_high_water").fetchall()
        if len(clocks) != 1 or clocks[0][0] != 1 or clocks[0][2] not in {0, 1}:
            raise SchemaUnavailable("unrecognized private queue store; migration is not supported")
        _stored_timestamp(clocks[0][1], "stored high_water")
    else:
        raise SchemaUnavailable("unrecognized private queue store; migration is not supported")
    db.execute("PRAGMA user_version=2")


def _advance_clock(db: sqlite3.Connection, now: float | None = None) -> float:
    """Check and persist the clock floor while the caller holds the write lock."""
    sampled = _utc_now() if now is None else _timestamp(now, "now")
    row = db.execute("SELECT high_water, quarantined FROM clock_high_water WHERE id=1").fetchone()
    if row is None:
        raise SchemaUnavailable("private queue clock is missing")
    high_water, quarantined = _stored_timestamp(row[0], "stored high_water"), row[1]
    if quarantined:
        raise ClockRegression("queue authority clock is quarantined")
    if sampled < high_water:
        db.execute("UPDATE clock_high_water SET quarantined=1 WHERE id=1")
        # The refusal must survive the exception rollback and every later restart.
        db.commit()
        raise ClockRegression("queue authority clock moved backward")
    if sampled > high_water:
        db.execute("UPDATE clock_high_water SET high_water=? WHERE id=1", (sampled,))
    return sampled


class Authority:
    """An explicitly opened private queue core, not a service or legacy adapter."""

    def __init__(self, state_dir: Path | str) -> None:
        """Open or initialize only this core's private V2 store."""
        if os.name != "posix":
            raise RuntimeError("queue authority core requires POSIX")
        if sqlite3.sqlite_version_info < (3, 51, 3):
            raise UnsupportedSQLite("queue authority requires SQLite >= 3.51.3")
        self.state_dir = Path(state_dir)
        with self._transaction() as db:
            _initialize_schema(db, now=_utc_now())

    def _connect(self) -> sqlite3.Connection:
        """Open the private database with the shared PT permission checks."""
        return open_private_sqlite(
            self.state_dir, "queue.sqlite3", dir_label="queue authority",
            file_label="queue authority ledger", timeout=30,
        )

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        """Hold the write lock while checking journal mode and applying operations."""
        try:
            with closing(self._connect()) as db, db:
                db.execute("BEGIN IMMEDIATE")
                if db.execute("PRAGMA journal_mode").fetchone()[0].lower() != "delete":
                    raise JournalUnavailable("unsupported queue authority journal mode")
                yield db
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                raise StoreUnavailable("queue authority store is busy") from exc
            raise

    @staticmethod
    def _record(
        db: sqlite3.Connection,
        task_id: str,
        action: str,
        generation: int,
        version: int,
        observed_at: float,
    ) -> None:
        """Record a transition and redacted, explicitly non-authoritative projection."""
        db.execute(
            "INSERT INTO audit (task_id, action, generation, version, observed_at) VALUES (?, ?, ?, ?, ?)",
            (task_id, action, generation, version, observed_at),
        )
        payload = json.dumps(
            {"task_id": task_id, "action": action, "generation": generation,
             "version": version, "authoritative": False}, sort_keys=True,
        )
        db.execute("INSERT INTO outbox (payload) VALUES (?)", (payload,))

    def add(self, task_id: str) -> None:
        """Create a fresh task without importing any legacy state."""
        if not isinstance(task_id, str) or not task_id.strip():
            raise InvalidRequest("task_id must not be empty")
        with self._transaction() as db:
            now = _advance_clock(db)
            try:
                db.execute(
                    "INSERT INTO tasks (id, state, generation, version, claim_id, incarnation, claimed_at) "
                    "VALUES (?, 'queued', 0, 1, NULL, NULL, NULL)",
                    (task_id,),
                )
            except sqlite3.IntegrityError as exc:
                raise Conflict("task already exists") from exc
            self._record(db, task_id, "add", 0, 1, now)

    def claim(self, task_id: str, incarnation: str) -> ClaimHandle:
        """Claim a queued task; incarnation is opaque metadata, not authentication."""
        if not isinstance(task_id, str) or not task_id.strip():
            raise InvalidRequest("task_id must be a nonempty string")
        if not isinstance(incarnation, str) or not incarnation.strip():
            raise InvalidRequest("incarnation must not be empty")
        with self._transaction() as db:
            now = _advance_clock(db)
            row = db.execute("SELECT state, generation, version FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None or row[0] != "queued":
                raise Conflict("task is not claimable")
            generation, version = row[1] + 1, row[2] + 1
            claim_id = uuid.uuid4().hex
            db.execute(
                "UPDATE tasks SET state='claimed', generation=?, version=?, claim_id=?, incarnation=?, "
                "claimed_at=? WHERE id=?",
                (generation, version, claim_id, incarnation, now, task_id),
            )
            self._record(db, task_id, "claim", generation, version, now)
            return ClaimHandle(task_id, claim_id, generation, version, incarnation, now)

    def _finish(self, handle: ClaimHandle, state: str) -> None:
        """Apply a transition only for the exact current acquisition and version."""
        if (not isinstance(handle, ClaimHandle) or
                not all(isinstance(value, str) and value.strip()
                        for value in (handle.task_id, handle.claim_id, handle.incarnation)) or
                type(handle.generation) is not int or handle.generation < 1 or
                type(handle.version) is not int or handle.version < 1):
            raise InvalidRequest("invalid claim handle")
        claimed_at = _timestamp(handle.claimed_at, "claimed_at")
        with self._transaction() as db:
            now = _advance_clock(db)
            result = db.execute(
                "UPDATE tasks SET state=?, version=version+1, claim_id=NULL, incarnation=NULL, claimed_at=NULL "
                "WHERE id=? AND state='claimed' AND claim_id=? AND generation=? AND version=? "
                "AND incarnation=? AND claimed_at=?",
                (state, handle.task_id, handle.claim_id, handle.generation, handle.version,
                 handle.incarnation, claimed_at),
            )
            if result.rowcount != 1:
                raise Conflict("stale acquisition")
            self._record(db, handle.task_id, state, handle.generation, handle.version + 1, now)

    def release(self, handle: ClaimHandle) -> None:
        """Release the current acquisition back to the queued state."""
        self._finish(handle, "queued")

    def complete(self, handle: ClaimHandle) -> None:
        """Complete only the current acquisition."""
        self._finish(handle, "completed")

    def get(self, task_id: str) -> dict:
        """Read canonical task state without disclosing the incarnation."""
        with self._transaction() as db:
            row = db.execute("SELECT state, generation, version FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise TaskNotFound(task_id)
        return dict(zip(("state", "generation", "version"), row))

    @staticmethod
    def _legacy_digest(path: Path) -> str:
        """Hash the quiesced legacy database bytes for the one-time import marker."""
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _legacy_claims(path: Path) -> list[tuple[str, str, float]]:
        """Read only canonical legacy ownership rows; never fold gossip events."""
        claims: list[tuple[str, str, float]] = []
        seen: set[str] = set()
        uri = path.resolve().as_uri() + "?mode=ro"
        try:
            with closing(sqlite3.connect(uri, uri=True)) as db:
                db.execute("PRAGMA query_only=ON")
                exists = db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='task_claims'"
                ).fetchone()
                if exists is None:
                    return claims
                for task_id, agent_id, claimed_at in db.execute(
                    "SELECT task_id, agent_id, claimed_at FROM task_claims"
                ):
                    if not isinstance(task_id, str) or not task_id.strip():
                        raise InvalidRequest("legacy claim task_id must be a nonempty string")
                    if task_id in seen:
                        raise InvalidRequest("legacy claim task_id must be unique")
                    seen.add(task_id)
                    if not isinstance(agent_id, str) or not agent_id.strip():
                        raise InvalidRequest("legacy claim agent_id must be a nonempty string")
                    claims.append((task_id, agent_id, _timestamp(claimed_at, "legacy claimed_at")))
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                raise StoreUnavailable("legacy claim store is busy") from exc
            raise InvalidRequest("legacy claim table is unreadable") from exc
        except sqlite3.DatabaseError as exc:
            raise InvalidRequest("legacy claim table is unreadable") from exc
        return claims

    @staticmethod
    def _legacy_task_state(payload: Mapping[str, Any]) -> str:
        """Map an operator-selected legacy snapshot to a safe V2 disposition."""
        status = payload.get("status")
        if not isinstance(status, str):
            raise InvalidRequest("legacy snapshot status must be a string")
        normalized = status.strip().lower()
        if normalized == "queued":
            return "queued"
        if normalized in {"completed", "done"}:
            return "completed"
        if normalized in {"claimed", "failed", "abandoned", "legacy_unverified"}:
            return "legacy_unverified"
        raise InvalidRequest("legacy snapshot has an unsupported status")

    def import_legacy(
        self,
        legacy_db_path: Path | str,
        *,
        snapshots: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> dict[str, int]:
        """Import one explicitly reconciled legacy source exactly once.

        ``snapshots`` is supplied by the operator-selected canonical fold. This
        method never reads or folds the legacy gossip table. Active ownership
        rows become ``legacy_unverified`` holds; recovery remains out of scope.
        A different source digest, or any collision with canonical state,
        refuses the entire import without consuming the one-time marker. An
        empty source is a no-op and does not consume that marker.
        """
        path = Path(legacy_db_path)
        if not path.is_file():
            raise InvalidRequest("legacy database must be an existing file")
        source_digest = self._legacy_digest(path)
        selected = {} if snapshots is None else snapshots
        if not isinstance(selected, Mapping):
            raise InvalidRequest("snapshots must be a task-id mapping")

        with self._transaction() as db:
            marker = db.execute("SELECT source_digest FROM legacy_imports WHERE id=1").fetchone()
            if marker is not None:
                if marker[0] == source_digest:
                    return {"tasks_imported": 0, "claims_imported": 0}
                raise LegacyImportConflict("legacy import has already completed")

            tasks: dict[str, str] = {}
            for task_id, payload in selected.items():
                if not isinstance(task_id, str) or not task_id.strip():
                    raise InvalidRequest("legacy snapshot task_id must be a nonempty string")
                if not isinstance(payload, Mapping):
                    raise InvalidRequest("legacy snapshot payload must be a mapping")
                tasks[task_id] = self._legacy_task_state(payload)
            claims = self._legacy_claims(path)
            if self._legacy_digest(path) != source_digest:
                raise InvalidRequest("legacy database changed while it was being read")
            for task_id, _agent_id, _claimed_at in claims:
                tasks[task_id] = "legacy_unverified"
            if not tasks:
                return {"tasks_imported": 0, "claims_imported": 0}

            task_ids = set(tasks)
            if task_ids:
                placeholders = ",".join("?" for _ in task_ids)
                existing = db.execute(
                    f"SELECT id FROM tasks WHERE id IN ({placeholders})", tuple(sorted(task_ids)),
                ).fetchall()
                if existing:
                    raise Conflict("legacy import would overwrite canonical task state")

            observed_at = _advance_clock(db)
            claim_by_task = {task_id: (agent_id, claimed_at) for task_id, agent_id, claimed_at in claims}
            for task_id, state in tasks.items():
                claim = claim_by_task.get(task_id)
                claim_id = uuid.uuid4().hex if claim is not None else None
                incarnation = claim[0] if claim is not None else None
                claimed_at = claim[1] if claim is not None else None
                db.execute(
                    "INSERT INTO tasks (id, state, generation, version, claim_id, incarnation, claimed_at) "
                    "VALUES (?, ?, 0, 1, ?, ?, ?)",
                    (task_id, state, claim_id, incarnation, claimed_at),
                )
                self._record(db, task_id, "legacy_import", 0, 1, observed_at)
            db.execute(
                "INSERT INTO legacy_imports (id, source_digest, imported_at, tasks_imported, claims_imported) "
                "VALUES (1, ?, ?, ?, ?)",
                (source_digest, observed_at, len(tasks), len(claims)),
            )
            return {"tasks_imported": len(tasks), "claims_imported": len(claims)}
