"""Denied process-group observations must not manufacture containment evidence."""

from unittest.mock import MagicMock
import threading

import pytest

from utils import win_exec

pytest_plugins = ("posix_containment_fixtures",)


def test_group_probe_permission_error_is_unknown(
    monkeypatch: pytest.MonkeyPatch, posix_process_mocks: None
) -> None:
    """A successful signal cannot prove membership after a denied observation."""
    calls: list[int] = []

    def killpg(pid: int, sig: int) -> None:
        """Allow termination but refuse the final process-group observation."""
        calls.append(sig)
        if sig == 0:
            raise PermissionError

    monkeypatch.setattr(win_exec.os, "killpg", killpg, raising=False)
    proc = MagicMock(pid=3456, returncode=None, _win_exec_group=3456)
    proc._waitpid_lock = threading.Lock()
    assert win_exec.terminate_tree(proc) == "unknown"
    assert calls and calls[0] != 0 and 0 in calls[1:]
    assert getattr(proc, "_win_exec_result", None) != "contained"
