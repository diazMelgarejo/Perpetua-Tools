"""Direct-launch executable resolution and untracked-process containment tests."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from utils import win_exec


def test_resolve_executable_skips_interpreter_suffixes_for_bare_commands(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """A bare command skips .vbs/.js PATHEXT entries and finds a direct executable."""
    vbs = tmp_path / "tool.vbs"
    exe = tmp_path / "tool.exe"
    vbs.touch()
    exe.touch()
    monkeypatch.setattr(win_exec, "_win", lambda: True)
    monkeypatch.setattr(win_exec, "_search_path_entries", lambda allow_unc=False: (str(tmp_path),))
    monkeypatch.setenv("PATHEXT", ".VBS;.JS;.EXE")
    assert win_exec.resolve_executable("tool") == str(exe)


def test_resolve_executable_refuses_explicit_interpreter_script(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """An explicit script-host extension cannot be handed to direct process launch."""
    script = tmp_path / "tool.vbs"
    script.touch()
    script.chmod(0o755)
    monkeypatch.setattr(win_exec, "_win", lambda: True)
    with pytest.raises(win_exec.WinExecError, match="permitted Windows extension"):
        win_exec.resolve_executable(str(script))


def test_untracked_posix_termination_does_not_signal_a_pid_reused_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An untracked child is killed directly without probing or signaling its process group."""
    calls: list[object] = []
    proc = SimpleNamespace(
        pid=123,
        poll=lambda: None,
        kill=lambda: calls.append("kill"),
        wait=lambda timeout: None,
    )
    monkeypatch.setattr(win_exec.os, "getpgid", lambda pid: (_ for _ in ()).throw(AssertionError(pid)))
    monkeypatch.setattr(win_exec.os, "killpg", lambda pgid, sig: (_ for _ in ()).throw(AssertionError(pgid)))
    assert win_exec._terminate_tree_posix(proc, 0.1) == win_exec.UNKNOWN
    assert calls == ["kill"]
