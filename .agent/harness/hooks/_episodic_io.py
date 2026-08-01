"""Cross-platform coordination for episodic JSONL persistence.

A sidecar lock is used instead of locking the data inode itself. This matters
because the dream cycle rewrites the JSONL file with ``os.replace``: an inode
lock would remain attached to the replaced file while new appenders opened the
new inode, defeating mutual exclusion.
"""
from __future__ import annotations

import contextlib
import json
import os
from typing import Iterator

try:
    import fcntl  # POSIX
    _HAVE_FLOCK = True
except ImportError:  # native Windows
    fcntl = None  # type: ignore[assignment]
    _HAVE_FLOCK = False

try:
    import msvcrt  # Windows
    _HAVE_MSVCRT = True
except ImportError:  # POSIX
    msvcrt = None  # type: ignore[assignment]
    _HAVE_MSVCRT = False


def _lock_path(path: str) -> str:
    return f"{path}.lock"


@contextlib.contextmanager
def episodic_lock(path: str, *, exclusive: bool = True) -> Iterator[None]:
    """Coordinate readers and writers for ``path`` through a stable lock inode."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if _HAVE_FLOCK:
        with open(_lock_path(path), "a+b") as lock_stream:
            mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            fcntl.flock(lock_stream.fileno(), mode)
            try:
                yield
            finally:
                fcntl.flock(lock_stream.fileno(), fcntl.LOCK_UN)
        return

    if _HAVE_MSVCRT:
        # msvcrt has no shared-lock primitive (unlike fcntl.LOCK_SH) -- every
        # acquisition here is exclusive, byte-range locking on a 1-byte
        # region of the sidecar file. Slightly more serializing than POSIX's
        # shared-read case, but correct: never corrupts concurrent appends,
        # which is the actual invariant this lock exists to protect.
        with open(_lock_path(path), "a+b") as lock_stream:
            lock_stream.seek(0, os.SEEK_END)
            if lock_stream.tell() == 0:
                lock_stream.write(b"\0")
                lock_stream.flush()
            lock_stream.seek(0)
            msvcrt.locking(lock_stream.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock_stream.seek(0)
                msvcrt.locking(lock_stream.fileno(), msvcrt.LK_UNLCK, 1)
        return

    raise RuntimeError(
        "episodic JSONL locking requires POSIX fcntl or Windows msvcrt; "
        "neither lock backend is available in this Python interpreter"
    )


def is_legacy_episodic_row(entry: dict) -> bool:
    """True for pre-canonical rows that used date/summary instead of timestamp/action.

    Replay and dream clustering must skip these — they lack evidence_ids and the
    fields downstream loaders expect. Canonical re-encodes live as normal rows.
    """
    if not isinstance(entry, dict):
        return False
    return (
        "date" in entry
        and "summary" in entry
        and "timestamp" not in entry
        and "action" not in entry
    )


def append_jsonl(path: str, entry: dict) -> dict:
    """Append one UTF-8 JSON line while excluding concurrent rewrites/appends."""
    payload = (json.dumps(entry) + "\n").encode("utf-8")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with episodic_lock(path, exclusive=True):
        with open(path, "ab") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    return entry
