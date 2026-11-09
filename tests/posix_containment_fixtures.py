"""Portable fixtures for deterministic POSIX containment tests."""

from typing import Any, Iterator

import pytest

from utils import win_exec


@pytest.fixture
def posix_process_mocks(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Supply POSIX process APIs even when the test host is Windows."""
    def waitid(*args: Any) -> None:
        """Model an owned child that remains running."""
        return None

    def killpg(pid: int, sig: int) -> None:
        """Require tests to specify their expected group behavior."""
        raise AssertionError((pid, sig))

    monkeypatch.setattr(win_exec, "_win", lambda: False)
    monkeypatch.setattr(win_exec.os, "waitid", waitid, raising=False)
    monkeypatch.setattr(win_exec.os, "killpg", killpg, raising=False)
    for name, value in (("P_PID", 1), ("WEXITED", 4), ("WNOWAIT", 0x1000000), ("WNOHANG", 1)):
        monkeypatch.setattr(win_exec.os, name, value, raising=False)
    yield
