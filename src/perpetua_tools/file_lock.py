"""One advisory file lock for POSIX and Windows (stdlib only).

``locked(path, timeout, shared=...)`` holds a lock on ``path`` for the length of the block. Shared holders run side
by side and keep exclusive holders out. Windows has no shared mode, so there every holder is exclusive.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Iterator

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None  # type: ignore[assignment]

try:
    import msvcrt
except ImportError:  # POSIX
    msvcrt = None  # type: ignore[assignment]

POLL_SECONDS = 0.05


class LockTimeout(TimeoutError):
    """Another holder kept the lock for longer than the caller was willing to wait."""


def _try_lock(handle: IO[str], shared: bool) -> bool:
    if fcntl is not None:
        try:
            fcntl.flock(handle.fileno(), (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True
    if msvcrt is None:
        raise OSError("this platform offers no file locking")
    handle.seek(0)  # msvcrt locks bytes from the current position; every holder must lock the same one
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        return False
    return True


def _unlock(handle: IO[str]) -> None:
    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return
    handle.seek(0)
    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


@contextmanager
def locked(path: Path | str, timeout: float, *, shared: bool = False) -> Iterator[None]:
    """Hold the lock on ``path``; raise ``LockTimeout`` after ``timeout`` seconds (0 means one attempt)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    with open(path, "a+", encoding="utf-8") as handle:
        while not _try_lock(handle, shared):
            if time.monotonic() >= deadline:
                raise LockTimeout(f"{path.name} is held by another process")
            time.sleep(POLL_SECONDS)
        try:
            yield
        finally:
            _unlock(handle)
