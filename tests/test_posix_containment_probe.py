"""Denied process-group observations must not manufacture containment evidence."""

from unittest.mock import MagicMock

import pytest

from utils import win_exec


def test_group_probe_permission_error_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """A successful signal cannot prove membership after a denied observation."""
    monkeypatch.setattr(win_exec.sys, "platform", "linux")

    def killpg(pid: int, sig: int) -> None:
        """Allow termination but refuse the final process-group observation."""
        if sig == 0:
            raise PermissionError

    monkeypatch.setattr(win_exec.os, "killpg", killpg, raising=False)
    proc = MagicMock(pid=3456, _win_exec_group=3456)
    assert win_exec.terminate_tree(proc) == "unknown"
    assert getattr(proc, "_win_exec_result", None) != "contained"
