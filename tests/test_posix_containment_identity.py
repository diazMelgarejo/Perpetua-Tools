"""Protect the shared process-group boundary from reaped-leader reuse."""

import signal
import threading
from typing import Any
from unittest.mock import MagicMock

import pytest

from utils import win_exec

pytest_plugins = ("posix_containment_fixtures",)


def test_reaped_leader_cannot_authorize_group_signal(
    posix_process_mocks: None,
) -> None:
    """A stale numeric group marker is insufficient once the root is reaped."""
    proc = MagicMock(pid=3457, returncode=0, _win_exec_group=3457)
    proc._waitpid_lock = threading.Lock()
    assert win_exec.terminate_tree(proc, grace=0) == win_exec.UNKNOWN
    proc.wait.assert_called_once()


def test_all_group_signals_precede_root_reaping(
    monkeypatch: pytest.MonkeyPatch, posix_process_mocks: None,
) -> None:
    """Escalation retains the child identity; only observation follows wait."""
    proc = MagicMock(pid=3458, returncode=None, _win_exec_group=3458)
    proc._waitpid_lock = threading.Lock()
    reaped = False
    signals: list[int] = []

    def wait(*args: Any, **kwargs: Any) -> int:
        """Release the simulated root identity at the explicit reap point."""
        nonlocal reaped
        reaped = True
        proc.returncode = 0
        return 0

    def killpg(pid: int, sig: int) -> None:
        """Forbid effectful group signals after root identity is released."""
        if reaped:
            assert sig == 0
            raise ProcessLookupError
        if sig:
            assert proc._waitpid_lock.locked()
            signals.append(sig)

    proc.wait.side_effect = wait
    monkeypatch.setattr(win_exec.os, "killpg", killpg)
    assert win_exec.terminate_tree(proc, grace=0) == win_exec.CONTAINED
    assert signals == [signal.SIGTERM, getattr(signal, "SIGKILL", 9)]
