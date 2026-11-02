"""Tests for orchestrator.cli_launch and its use by worker_registry / supervisor."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from orchestrator import cli_launch
from utils import win_exec


def test_prepare_cli_command_posix_is_passthrough(monkeypatch):
    """On POSIX the command is returned unchanged (no resolution, no refusal)."""
    monkeypatch.setattr(cli_launch, "_is_windows", lambda: False)
    assert cli_launch.prepare_cli_command(["codex", "a&b"]) == ["codex", "a&b"]
    assert cli_launch.cli_spawn_kwargs() == {}


def test_prepare_cli_command_windows_resolves_absolute(monkeypatch):
    """On Windows the bare name is resolved via resolve_executable to an absolute path."""
    monkeypatch.setattr(cli_launch, "_is_windows", lambda: True)
    monkeypatch.setattr(cli_launch, "resolve_executable", lambda n: r"C:\bin\codex.exe")
    assert cli_launch.prepare_cli_command(["codex", "--quiet", "p&q"]) == [
        r"C:\bin\codex.exe", "--quiet", "p&q",
    ]


def test_prepare_cli_command_windows_refuses_cmd_metachar(monkeypatch):
    """A .cmd shim target with a cmd metacharacter argument is refused."""
    monkeypatch.setattr(cli_launch, "_is_windows", lambda: True)
    monkeypatch.setattr(cli_launch, "resolve_executable", lambda n: r"C:\bin\gemini.cmd")
    with pytest.raises(win_exec.CmdArgumentRefused):
        cli_launch.prepare_cli_command(["gemini", "-p", "hello & calc"])


def test_prepare_cli_command_windows_missing_exe_raises(monkeypatch):
    """No fallback to the bare name: an unresolvable CLI raises WinExecError."""
    monkeypatch.setattr(cli_launch, "_is_windows", lambda: True)
    monkeypatch.setattr(
        cli_launch, "resolve_executable",
        lambda n: (_ for _ in ()).throw(win_exec.WinExecError("executable is unavailable or not executable")),
    )
    with pytest.raises(win_exec.WinExecError):
        cli_launch.prepare_cli_command(["nope"])


def test_prepare_cli_command_rejects_empty():
    """An empty command is refused rather than launched."""
    with pytest.raises(win_exec.WinExecError):
        cli_launch.prepare_cli_command([])


@pytest.mark.asyncio
async def test_terminate_cli_tree_windows_reports_honest_status(monkeypatch):
    """The win_exec containment status is passed through, including escaped:<n>."""
    monkeypatch.setattr(cli_launch, "_is_windows", lambda: True)
    seen = {}

    def fake_tree(adapter, grace):
        seen["pid"] = adapter.pid
        return "escaped:2"

    monkeypatch.setattr(cli_launch, "terminate_tree", fake_tree)
    proc = SimpleNamespace(pid=4242, returncode=None)
    assert await cli_launch.terminate_cli_tree(proc, 1.0) == "escaped:2"
    assert seen["pid"] == 4242


@pytest.mark.asyncio
async def test_terminate_cli_tree_windows_failure_is_unknown_not_contained(monkeypatch):
    """A crash inside the tree kill degrades to unknown (never a false 'contained')."""
    monkeypatch.setattr(cli_launch, "_is_windows", lambda: True)

    def boom(adapter, grace):
        raise OSError("taskkill missing")

    monkeypatch.setattr(cli_launch, "terminate_tree", boom)
    terminated = []
    proc = SimpleNamespace(pid=1, returncode=None, terminate=lambda: terminated.append(1))
    assert await cli_launch.terminate_cli_tree(proc, 1.0) == cli_launch.UNKNOWN
    assert terminated == [1]


@pytest.mark.asyncio
async def test_terminate_cli_tree_posix_signals_direct_child_only(monkeypatch):
    """POSIX path keeps terminate()-on-the-direct-child semantics."""
    monkeypatch.setattr(cli_launch, "_is_windows", lambda: False)

    class _P:
        returncode = None

        def terminate(self):
            self.returncode = -15

        async def wait(self):
            return self.returncode

    p = _P()
    assert await cli_launch.terminate_cli_tree(p, 1.0) == cli_launch.CONTAINED
    assert p.returncode == -15


@pytest.mark.asyncio
async def test_run_dangerous_cli_refuses_metachar_for_cmd_shim(monkeypatch):
    """worker_registry turns a refused launch into a RuntimeError before spawning."""
    from orchestrator import worker_registry

    monkeypatch.setattr(cli_launch, "_is_windows", lambda: True)
    monkeypatch.setattr(cli_launch, "resolve_executable", lambda n: r"C:\bin\gemini.cmd")
    spawned = []

    async def _spawn(*a, **k):
        spawned.append(a)
        raise AssertionError("must not spawn")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _spawn)
    spec = SimpleNamespace(job_id="j1", prompt="x", constraints={})
    with pytest.raises(RuntimeError, match="launch refused"):
        await worker_registry._run_dangerous_cli_subprocess(spec, ["gemini", "-p", "a|b"], "gemini")
    assert spawned == []


@pytest.mark.asyncio
async def test_run_dangerous_cli_timeout_kills_tree_and_reports_status(monkeypatch):
    """On timeout the tree kill runs and a non-contained status is surfaced."""
    from orchestrator import worker_registry

    monkeypatch.setattr(cli_launch, "_is_windows", lambda: False)

    class _P:
        returncode = None
        pid = 7

        async def communicate(self):
            await asyncio.Event().wait()

        async def wait(self):
            return self.returncode

    async def _create(*a, **k):
        return _P()

    async def _tree(proc, grace=5.0):
        proc.returncode = 1
        return "escaped:3"

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _create)
    monkeypatch.setattr(cli_launch, "terminate_cli_tree", _tree)
    spec = SimpleNamespace(job_id="", prompt="x", constraints={"max_seconds": 0.05})
    with pytest.raises(RuntimeError, match=r"escaped:3"):
        await worker_registry._run_dangerous_cli_subprocess(spec, ["codex", "x"], "codex")


@pytest.mark.asyncio
@pytest.mark.parametrize("status,expected", [
    ("contained", "verified"),
    ("escaped:2", "unresolved"),
    ("unknown", "unresolved"),
])
async def test_supervisor_records_tree_status_honestly(tmp_path, monkeypatch, status, expected):
    """Containment is 'verified' only when the tree status is 'contained'; detail is stored."""
    from orchestrator.supervisor import OrchestrationSupervisor

    sup = OrchestrationSupervisor(state_dir=tmp_path)

    class _P:
        returncode = None

    async def _tree(proc, grace=5.0):
        proc.returncode = 0
        return status

    monkeypatch.setattr(cli_launch, "terminate_cli_tree", _tree)
    p = _P()
    sup.note_child("job-x", p)  # type: ignore[arg-type]
    await sup._record_direct_child_containment("job-x")
    from orchestrator.supervisor import _latest_status_per_job, _load_events

    latest = _latest_status_per_job(_load_events(sup._jobs_file))["job-x"]
    assert latest["containment_state"] == expected
    assert latest["containment_detail"] == status
