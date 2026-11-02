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
    # The POSIX CI filesystem is case-sensitive; use the configured spelling
    # while emulating Windows lookup, where the spelling is case-insensitive.
    exe = tmp_path / "tool.EXE"
    vbs.touch()
    exe.touch()
    monkeypatch.setattr(win_exec, "_win", lambda: True)
    monkeypatch.setattr(win_exec, "_search_path_entries", lambda allow_unc=False: (str(tmp_path),))
    monkeypatch.setenv("PATHEXT", ".VBS;.JS;.EXE")
    assert Path(win_exec.resolve_executable("tool")).samefile(exe)


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


def test_windows_pathext_probe_preserves_configured_suffix_spelling(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Windows emulation probes PATHEXT filenames in configured case and order."""
    tried: list[str] = []
    monkeypatch.setattr(win_exec, "_win", lambda: True)
    monkeypatch.setattr(win_exec, "_search_path_entries", lambda allow_unc=False: (str(tmp_path),))
    monkeypatch.setenv("PATHEXT", ".EXE;.Cmd;.VBS")
    monkeypatch.setattr(Path, "is_file", lambda self: tried.append(self.name) or False)
    assert win_exec.find_bare_command("tool") is None
    assert tried == ["tool.EXE", "tool.Cmd", "tool"]


@pytest.mark.parametrize("candidate", ("./tool", ".\\tool", "nested/tool"))
def test_resolve_executable_refuses_relative_paths_on_every_host(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, candidate: str,
) -> None:
    """A relative path never falls through to PATH lookup, including Windows syntax on POSIX."""
    (tmp_path / "tool").touch()
    monkeypatch.chdir(tmp_path)
    with pytest.raises(win_exec.WinExecError, match="absolute"):
        win_exec.resolve_executable(candidate)


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
