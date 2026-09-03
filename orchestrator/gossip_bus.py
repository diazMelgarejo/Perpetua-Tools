"""Lightweight SQLite gossip/event log with FTS5 and optional embeddings."""
from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
import subprocess
import uuid
from pathlib import Path
from typing import Literal, Optional

import aiosqlite


def _canonical_repo_state_dir() -> Optional[Path]:
    """Resolve ``.state`` relative to the repo root shared by every worktree.

    ``git rev-parse --git-common-dir`` returns the same path regardless of
    which worktree of a repo you're standing in, so every worktree converges
    on one ``.state/`` instead of each growing its own fragmented copy. A
    conventional checkout uses ``<repo>/.git`` as that common directory, but
    bare and external Git directories are themselves the state anchor.
    Returns None outside a git repo (e.g. a packaged deployment), where the
    caller falls back to a plain cwd-relative path.
    """
    try:
        common_dir = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"],
            text=True,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    common_path = Path(common_dir).resolve()
    state_anchor = common_path.parent if common_path.name == ".git" else common_path
    return state_anchor / ".state"


def resolve_default_state_dir() -> Path:
    """Return the shared runtime state directory for this repo/worktree layout."""
    env_dir = os.environ.get("PT_STATE_DIR", "").strip()
    if env_dir:
        return Path(env_dir)
    return _canonical_repo_state_dir() or Path(".state")


def is_default_state_dir_arg(state_dir: Path | str) -> bool:
    """True when the caller left state_dir at the cwd-relative default ``.state``."""
    return Path(state_dir) == Path(".state")


class GossipBusError(Exception):
    """A GossipBus operation failed against the underlying SQLite store.

    Raised by emit()/tail() (and re-raised by the atomic-claim helpers in
    scripts/agent_coordination_core.py for the same class of failure) so
    every caller-facing surface -- CLI, tests -- has one stable exception
    type to catch, instead of letting raw sqlite3/aiosqlite/OSError
    exceptions (lock contention, disk full, corruption) propagate as
    uncaught tracebacks.
    """


def resolve_gossip_db_path(state_dir: Path | str | None = None) -> str:
    explicit = os.environ.get("GOSSIP_DB_PATH", "").strip()
    if explicit:
        return explicit
    if state_dir is not None:
        root = Path(state_dir)
    else:
        root = resolve_default_state_dir()
    return str((root / "perpetua_core.db").resolve())


_pending_embeds: set[asyncio.Task] = set()
_MAX_PENDING = 500


async def cancel_pending_embeddings_for_current_loop() -> None:
    """Cancel and drain background embeddings before a one-shot loop closes.

    A CLI command persists its event before scheduling optional embedding. If
    `asyncio.run()` closes immediately afterward, an embedding's aiosqlite
    worker can still attempt to resolve a future against the closed loop. Only
    tasks created on the current loop are ours to stop; tasks owned by another
    long-lived runtime must remain untouched.
    """
    loop = asyncio.get_running_loop()
    pending = [
        task
        for task in _pending_embeds
        if task.get_loop() is loop and not task.done()
    ]
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    _pending_embeds.difference_update(pending)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS gossip (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    event_uuid   TEXT    NOT NULL,
    ts           REAL    NOT NULL,
    event_type   TEXT    NOT NULL,
    payload_json TEXT    NOT NULL,
    embed_status TEXT    NOT NULL DEFAULT 'pending'
)
"""
_CREATE_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS gossip_fts
USING fts5(event_type, payload_json, content='gossip', content_rowid='id')
"""
_CREATE_FTS_AI = """
CREATE TRIGGER IF NOT EXISTS gossip_fts_ai
AFTER INSERT ON gossip BEGIN
  INSERT INTO gossip_fts(rowid, event_type, payload_json)
  VALUES (new.id, new.event_type, new.payload_json);
END
"""
_CREATE_FTS_AD = """
CREATE TRIGGER IF NOT EXISTS gossip_fts_ad
AFTER DELETE ON gossip BEGIN
  INSERT INTO gossip_fts(gossip_fts, rowid, event_type, payload_json)
  VALUES ('delete', old.id, old.event_type, old.payload_json);
END
"""
_CREATE_EMBED_IDX = """
CREATE INDEX IF NOT EXISTS idx_gossip_embed_status
ON gossip(embed_status) WHERE embed_status != 'embedded'
"""
_CREATE_UUID_IDX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_gossip_event_uuid
ON gossip(event_uuid)
"""

_FTS5_OPERATOR_RE = re.compile(r'[\"\':\*\+\-\(\)\[\]\{\}\^]')
_FTS5_KEYWORDS = {"AND", "OR", "NOT", "NEAR"}


def _sanitize_fts_query(query: str) -> str:
    if not query:
        return ""
    cleaned = _FTS5_OPERATOR_RE.sub(" ", query)
    tokens = [token.lower() if token in _FTS5_KEYWORDS else token for token in cleaned.split()]
    return " ".join(tokens).strip()


EventType = Literal[
    "dispatch",
    "route",
    "result",
    "error",
    "heartbeat",
    "fleet_topology_transition",
    "fleet_topology_stale",
    "fleet_topology_recovered",
    "split_brain_detected",
    "split_brain_resolved",
]


class GossipBus:
    """Append-only event log.

    ``insert_event()`` is the public transaction primitive for callers that must
    make an event atomic with another SQLite mutation. The caller owns commit or
    rollback and schedules embedding only after a successful commit.

    A bus created with no ``db_path`` resolves to the canonical
    ``.state/perpetua_core.db`` path. Public read/write methods lazily
    initialize the schema, so endpoint fallbacks and tests cannot accidentally
    touch an uninitialized SQLite file.
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path if db_path is not None else resolve_gossip_db_path()
        self._initialized = False

    @property
    def db_path(self) -> str:
        """Public database path for compatibility with transaction callers."""
        return self._db_path

    def connect(self):
        """Return an aiosqlite connection context manager for this bus."""
        return aiosqlite.connect(self._db_path)

    async def init_db(self) -> None:
        try:
            async with self.connect() as db:
                await db.execute(_CREATE_TABLE)
                # Schema migration: add event_uuid to existing tables (idempotent).
                try:
                    await db.execute("ALTER TABLE gossip ADD COLUMN event_uuid TEXT")
                except sqlite3.OperationalError as exc:
                    if "duplicate column" not in str(exc).lower():
                        raise
                # Schema migration: add embed_status to legacy tables (idempotent).
                try:
                    await db.execute(
                        "ALTER TABLE gossip ADD COLUMN embed_status TEXT NOT NULL DEFAULT 'pending'"
                    )
                except sqlite3.OperationalError as exc:
                    if "duplicate column" not in str(exc).lower():
                        raise
                # Backfill any rows missing event_uuid (legacy rows pre-migration).
                cursor = await db.execute("SELECT id FROM gossip WHERE event_uuid IS NULL")
                rows = await cursor.fetchall()
                for (row_id,) in rows:
                    await db.execute(
                        "UPDATE gossip SET event_uuid = ? WHERE id = ?",
                        (uuid.uuid4().hex, row_id),
                    )
                await db.execute(_CREATE_FTS)
                await db.execute(_CREATE_FTS_AI)
                await db.execute(_CREATE_FTS_AD)
                await db.execute(_CREATE_EMBED_IDX)
                await db.execute(_CREATE_UUID_IDX)
                await db.commit()
                cursor = await db.execute("SELECT COUNT(*) FROM gossip_fts")
                (fts_count,) = await cursor.fetchone()
                cursor = await db.execute("SELECT COUNT(*) FROM gossip")
                (row_count,) = await cursor.fetchone()
                if row_count > 0 and fts_count == 0:
                    await db.execute(
                        "INSERT INTO gossip_fts(rowid, event_type, payload_json) "
                        "SELECT id, event_type, payload_json FROM gossip"
                    )
                    await db.commit()
        except (aiosqlite.Error, sqlite3.Error, OSError) as exc:
            raise GossipBusError(
                f"failed to initialize the coordination database: {exc}"
            ) from exc
        self._initialized = True

    async def _ensure_initialized(self) -> None:
        """Create/migrate the backing schema before public reads and writes."""
        if not self._initialized:
            await self.init_db()

    async def insert_event(
        self,
        db: aiosqlite.Connection,
        event_type: EventType,
        payload: dict,
        *,
        timestamp: Optional[float] = None,
        event_uuid: Optional[str] = None,
    ) -> tuple[int, str, dict, bool]:
        """Insert an event using a connection the caller already owns.

        ``event_uuid`` is optional for local callers and required for faithful
        LAN replay. Supplying it lets a receiving peer store the same logical
        event under its own local row id while preserving a stable global event
        identity for merge/deduplication.

        Returns:
            ``(row_id, event_uuid, durable_payload, inserted)``. ``inserted`` is
            ``True`` for a fresh row and ``False`` when the event_uuid already
            existed (duplicate forwarded event). Callers should pass ``row_id``
            and ``durable_payload`` to ``schedule_embedding()`` only when
            ``inserted`` is ``True``.
        """
        import time

        from orchestrator.memory_governance import classify_and_redact

        safe_payload, _memory_class = classify_and_redact(
            payload, event_type=event_type
        )
        durable_payload = dict(safe_payload)
        durable_payload.pop("_memory_class", None)
        durable_payload.pop("_redaction_applied", None)
        event_uuid = event_uuid or uuid.uuid4().hex
        cursor = await db.execute(
            "INSERT OR IGNORE INTO gossip "
            "(event_uuid, ts, event_type, payload_json, embed_status) "
            "VALUES (?, ?, ?, ?, 'pending')",
            (
                event_uuid,
                time.time() if timestamp is None else timestamp,
                event_type,
                json.dumps(durable_payload),
            ),
        )
        if cursor.rowcount == 0:
            # Duplicate event_uuid — fetch existing row for idempotent return.
            # Legacy rows may still contain private governance markers, so apply
            # the same durable-payload sanitization used for fresh writes.
            existing = await db.execute(
                "SELECT id, payload_json FROM gossip WHERE event_uuid = ?",
                (event_uuid,),
            )
            row = await existing.fetchone()
            if row is not None:
                duplicate_payload = json.loads(row[1])
                if isinstance(duplicate_payload, dict):
                    duplicate_payload = dict(duplicate_payload)
                    duplicate_payload.pop("_memory_class", None)
                    duplicate_payload.pop("_redaction_applied", None)
                return int(row[0]), event_uuid, duplicate_payload, False
        return int(cursor.lastrowid), event_uuid, durable_payload, True

    def schedule_embedding(self, row_id: int, safe_payload: dict) -> None:
        """Schedule optional embedding after the containing transaction commits."""
        if len(_pending_embeds) >= _MAX_PENDING:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = loop.create_task(
            self._embed_and_store(row_id, safe_payload), name=f"embed-{row_id}"
        )
        _pending_embeds.add(task)
        task.add_done_callback(_pending_embeds.discard)

    def _extract_forwarded_uuid(
        self, payload: dict, event_uuid: Optional[str]
    ) -> tuple[dict, Optional[str]]:
        """Read and strip the private LAN transport UUID envelope if present.

        Current FastAPI endpoint models ignore unknown top-level fields, so LAN
        peers also include ``_gossip_uuid`` inside the payload. The storage layer
        strips that transport-only marker before persistence and uses it only as
        the global event identity. This keeps old endpoint code compatible while
        preventing envelope metadata from becoming searchable event content.
        """
        if event_uuid is not None or not isinstance(payload, dict):
            return payload, event_uuid
        forwarded_uuid = payload.get("_gossip_uuid")
        if not isinstance(forwarded_uuid, str) or not forwarded_uuid:
            return payload, event_uuid
        clean_payload = dict(payload)
        clean_payload.pop("_gossip_uuid", None)
        return clean_payload, forwarded_uuid

    async def emit(
        self,
        event_type: EventType,
        payload: dict,
        *,
        event_uuid: Optional[str] = None,
    ) -> str:
        """Persist an event locally and return its globally unique UUID.

        Embedding is only scheduled for genuinely new events; duplicate
        forwarded events (detected via INSERT OR IGNORE) skip embedding to
        avoid redundant work.
        """
        await self._ensure_initialized()
        payload, event_uuid = self._extract_forwarded_uuid(payload, event_uuid)
        try:
            async with self.connect() as db:
                row_id, stored_uuid, safe_payload, inserted = await self.insert_event(
                    db, event_type, payload, event_uuid=event_uuid
                )
                await db.commit()
        except (aiosqlite.Error, sqlite3.Error, OSError) as exc:
            raise GossipBusError(
                f"failed to write event to the coordination database: {exc}"
            ) from exc
        if inserted:
            self.schedule_embedding(row_id, safe_payload)
        return stored_uuid

    async def tail(
        self, limit: int = 20, event_type: Optional[str] = None
    ) -> list[dict]:
        await self._ensure_initialized()
        try:
            async with self.connect() as db:
                if event_type:
                    cursor = await db.execute(
                        "SELECT id, event_uuid, ts, event_type, payload_json FROM gossip "
                        "WHERE event_type = ? ORDER BY id DESC LIMIT ?",
                        (event_type, limit),
                    )
                else:
                    cursor = await db.execute(
                        "SELECT id, event_uuid, ts, event_type, payload_json FROM gossip "
                        "ORDER BY id DESC LIMIT ?",
                        (limit,),
                    )
                rows = await cursor.fetchall()
        except (aiosqlite.Error, sqlite3.Error, OSError) as exc:
            raise GossipBusError(
                f"failed to read events from the coordination database: {exc}"
            ) from exc
        return [
            {
                "row_id": row[0],
                "uuid": row[1],
                "ts": row[2],
                "event_type": row[3],
                "payload": json.loads(row[4]),
            }
            for row in rows
        ]

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        event_type: Optional[str] = None,
    ) -> list[dict]:
        await self._ensure_initialized()
        safe_query = _sanitize_fts_query(query)
        if not safe_query:
            return []
        try:
            async with self.connect() as db:
                if event_type:
                    cursor = await db.execute(
                        """SELECT g.id, g.event_uuid, g.ts, g.event_type, g.payload_json
                           FROM gossip_fts f
                           JOIN gossip g ON g.id = f.rowid
                           WHERE gossip_fts MATCH ? AND g.event_type = ?
                           ORDER BY rank LIMIT ?""",
                        (safe_query, event_type, limit),
                    )
                else:
                    cursor = await db.execute(
                        """SELECT g.id, g.event_uuid, g.ts, g.event_type, g.payload_json
                           FROM gossip_fts f
                           JOIN gossip g ON g.id = f.rowid
                           WHERE gossip_fts MATCH ?
                           ORDER BY rank LIMIT ?""",
                        (safe_query, limit),
                    )
                rows = await cursor.fetchall()
            return [
                {
                    "row_id": row[0],
                    "uuid": row[1],
                    "ts": row[2],
                    "event_type": row[3],
                    "payload": json.loads(row[4]),
                }
                for row in rows
            ]
        except Exception:
            return []

    async def _embed_and_store(self, row_id: int, payload: dict) -> None:
        try:
            from orchestrator.memory_embed import get_embedding
            from orchestrator.memory_store import get_lance_store

            text = json.dumps(payload)
            embedding = await get_embedding(text)
            store = get_lance_store()
            await store.add(row_id=row_id, text=text, embedding=embedding)
            await self._update_embed_status(row_id, "embedded")
        except Exception:
            await self._update_embed_status(row_id, "failed")

    async def _update_embed_status(self, row_id: int, status: str) -> None:
        async with self.connect() as db:
            await db.execute(
                "UPDATE gossip SET embed_status = ? WHERE id = ?",
                (status, row_id),
            )
            await db.commit()
