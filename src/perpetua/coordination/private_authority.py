"""Non-deployable local building block for the future PT queue authority.

This module is not connected to the legacy queue or any transport.  A handle
fences acquisitions; it does not authenticate a worker.  In particular, do not
use this store as a protected queue until caller and migration closure is done.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
from collections.abc import Iterator
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sqlite3
import uuid

from orchestrator.private_sqlite import open_private_sqlite


class Conflict(RuntimeError):
    """The requested transition no longer matches the canonical acquisition."""


@dataclass(frozen=True)
class ClaimHandle:
    """Acquisition identity and task version; not a proof of worker identity."""

    task_id: str
    claim_id: str
    generation: int
    version: int
    incarnation: str


class Authority:
    """An explicitly opened private queue core, not a service or legacy adapter."""

    def __init__(self, state_dir: Path | str) -> None:
        """Open or initialize only this core's private store."""
        if os.name != "posix":
            raise RuntimeError("queue authority core requires POSIX")
        if sqlite3.sqlite_version_info < (3, 51, 3):
            raise RuntimeError("queue authority requires SQLite >= 3.51.3")
        self.state_dir = Path(state_dir)
        with self._transaction() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            tables = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            if version == 0 and not tables:
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
                db.execute("PRAGMA user_version=1")
            elif version != 1 or {row[0] for row in tables} != {"tasks", "audit", "outbox", "metadata"}:
                raise RuntimeError("unrecognized private queue store; migration is not supported")

    def _connect(self) -> sqlite3.Connection:
        """Open the private database with the shared PT permission checks."""
        return open_private_sqlite(
            self.state_dir, "queue.sqlite3", dir_label="queue authority",
            file_label="queue authority ledger", timeout=30,
        )

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        """Hold the write lock while checking journal mode and applying operations."""
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("PRAGMA journal_mode").fetchone()[0].lower() != "delete":
                raise RuntimeError("unsupported queue authority journal mode")
            yield db

    @staticmethod
    def _record(db: sqlite3.Connection, task_id: str, action: str, generation: int, version: int) -> None:
        """Record a transition and redacted, explicitly non-authoritative projection."""
        db.execute(
            "INSERT INTO audit (task_id, action, generation, version) VALUES (?, ?, ?, ?)",
            (task_id, action, generation, version),
        )
        payload = json.dumps(
            {"task_id": task_id, "action": action, "generation": generation,
             "version": version, "authoritative": False}, sort_keys=True,
        )
        db.execute("INSERT INTO outbox (payload) VALUES (?)", (payload,))

    def add(self, task_id: str) -> None:
        """Create a fresh task without importing any legacy state."""
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must not be empty")
        with self._transaction() as db:
            try:
                db.execute("INSERT INTO tasks VALUES (?, 'queued', 0, 1, NULL, NULL)", (task_id,))
            except sqlite3.IntegrityError as exc:
                raise Conflict("task already exists") from exc
            self._record(db, task_id, "add", 0, 1)

    def claim(self, task_id: str, incarnation: str) -> ClaimHandle:
        """Claim a queued task; incarnation is opaque metadata, not authentication."""
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a nonempty string")
        if not isinstance(incarnation, str) or not incarnation.strip():
            raise ValueError("incarnation must not be empty")
        with self._transaction() as db:
            row = db.execute("SELECT state, generation, version FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None or row[0] != "queued":
                raise Conflict("task is not claimable")
            generation, version = row[1] + 1, row[2] + 1
            claim_id = uuid.uuid4().hex
            db.execute(
                "UPDATE tasks SET state='claimed', generation=?, version=?, claim_id=?, incarnation=? WHERE id=?",
                (generation, version, claim_id, incarnation, task_id),
            )
            self._record(db, task_id, "claim", generation, version)
            return ClaimHandle(task_id, claim_id, generation, version, incarnation)

    def _finish(self, handle: ClaimHandle, state: str) -> None:
        """Apply a transition only for the exact current acquisition and version."""
        if (not isinstance(handle, ClaimHandle) or
                not all(isinstance(value, str) and value.strip()
                        for value in (handle.task_id, handle.claim_id, handle.incarnation)) or
                type(handle.generation) is not int or handle.generation < 1 or
                type(handle.version) is not int or handle.version < 1):
            raise ValueError("invalid claim handle")
        with self._transaction() as db:
            result = db.execute(
                "UPDATE tasks SET state=?, version=version+1, claim_id=NULL, incarnation=NULL "
                "WHERE id=? AND state='claimed' AND claim_id=? AND generation=? AND version=? AND incarnation=?",
                (state, handle.task_id, handle.claim_id, handle.generation, handle.version, handle.incarnation),
            )
            if result.rowcount != 1:
                raise Conflict("stale acquisition")
            self._record(db, handle.task_id, state, handle.generation, handle.version + 1)

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
            raise KeyError(task_id)
        return dict(zip(("state", "generation", "version"), row))
