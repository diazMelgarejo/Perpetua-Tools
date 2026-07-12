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
except ImportError:  # pragma: no cover - native Windows
    fcntl = None  # type: ignore[assignment]
    _HAVE_FLOCK = False


def _lock_path(path: str) -> str:
    return f"{path}.lock"


@contextlib.contextmanager
def episodic_lock(path: str, *, exclusive: bool = True) -> Iterator[None]:
    """Coordinate readers and writers for ``path`` through a stable lock inode."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not _HAVE_FLOCK:
        yield
        return

    with open(_lock_path(path), "a+b") as lock_stream:
        mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        fcntl.flock(lock_stream.fileno(), mode)
        try:
            yield
        finally:
            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_UN)


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
