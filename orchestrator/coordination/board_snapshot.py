"""Best-effort JSON snapshot of the latest coordination-board notes.

``log_message`` refreshes the snapshot after each note so tools that read
``gossip_board_snapshot.json`` never see a stale board. The snapshot is only
written when an output path is configured (``GOSSIP_BOARD_SNAPSHOT``) or the
bus uses the default board database, so tests on temporary databases never
touch the operator's home directory.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import sqlite3
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

SNAPSHOT_ENV = "GOSSIP_BOARD_SNAPSHOT"
DEFAULT_SNAPSHOT = Path("~/.openclaw/state/gossip_board_snapshot.json")
NOTE_LIMIT = 20
MESSAGE_CHARS = 1200


def _note_message(payload: dict) -> str:
    message = payload.get("message")
    if message:
        return str(message)
    return json.dumps({k: v for k, v in payload.items() if k not in ("kind", "agent_id")})


def read_notes(db_path: str, limit: int = NOTE_LIMIT) -> list[dict]:
    """Return the newest ``agent_note`` rows, oldest first."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
    try:
        rows = conn.execute(
            "SELECT id, payload_json FROM gossip "
            "WHERE payload_json LIKE '%\"agent_note\"%' ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    notes = []
    for row_id, raw in reversed(rows):
        payload = json.loads(raw)
        notes.append(
            {
                "id": row_id,
                "agent_id": payload.get("agent_id"),
                "message": _note_message(payload)[:MESSAGE_CHARS],
            }
        )
    return notes


def write_snapshot(db_path: str, out_path: Path, limit: int = NOTE_LIMIT) -> None:
    """Atomically rewrite the snapshot, keeping fields this writer does not own."""
    out_path = Path(out_path).expanduser()
    try:
        existing = json.loads(out_path.read_text())
    except (OSError, ValueError):
        existing = {}
    snapshot = {
        **existing,
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "db": str(db_path),
        "recent_notes": read_notes(db_path, limit),
        "source": "perpetua_core.db gossip table (agent_note rows), written by board_snapshot",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=out_path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(snapshot, handle, indent=2)
        os.replace(tmp, out_path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def refresh_snapshot(db_path: str, default_db_path: str) -> None:
    """Refresh the snapshot if configured; never raise into the caller."""
    configured = os.environ.get(SNAPSHOT_ENV, "").strip()
    if not configured and os.path.realpath(db_path) != os.path.realpath(default_db_path):
        return
    try:
        write_snapshot(db_path, Path(configured) if configured else DEFAULT_SNAPSHOT)
    except Exception:
        logger.debug("board snapshot refresh failed", exc_info=True)
