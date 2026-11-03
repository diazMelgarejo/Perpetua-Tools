"""Tests for orchestrator.cli_launch and its use by worker_registry / supervisor."""
from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

import pytest

from orchestrator import cli_launch
from utils import win_exec


def test_prepare_cli_command_posix_is_passthrough(monkeypatch):
    """On POSIX the command is returned unchanged (no resolution, no refusal)."""
    monkeypatch.setattr(cli_launch, "_is_windows", lambda: False)
    assert cli_launch.prepare_cli_command(["codex", "a&b"]) == ["codex", "a&b"]


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

    def fake_tree(popen, grace):
        """Test double: fake tree."""
        seen["pid"] = popen.pid
        return "escaped:2"

    monkeypatch.setattr(cli_launch, "terminate_tree", fake_tree)
    proc = SimpleNamespace(pid=4242, returncode=None, popen=SimpleNamespace(pid=4242))
    assert await cli_launch.terminate_cli_tree(proc, 1.0) == "escaped:2"
    assert seen["pid"] == 4242


@pytest.mark.asyncio
async def test_terminate_cli_tree_windows_runs_for_already_exited_root(monkeypatch):
    """Orphans: terminate_tree is still called when the root has already exited."""
    monkeypatch.setattr(cli_launch, "_is_windows", lambda: True)
    calls = []
    monkeypatch.setattr(cli_launch, "terminate_tree", lambda p, g: calls.append(p) or "contained")
    popen = SimpleNamespace(pid=9)
    proc = SimpleNamespace(pid=9, returncode=0, popen=popen)
    assert await cli_launch.terminate_cli_tree(proc, 1.0) == "contained"
    assert calls == [popen]


@pytest.mark.asyncio
async def test_terminate_cli_tree_windows_untracked_handle_is_unknown(monkeypatch):
    """A handle not started through launch_tree cannot claim containment."""
    monkeypatch.setattr(cli_launch, "_is_windows", lambda: True)
    proc = SimpleNamespace(pid=1, returncode=None, terminate=lambda: None)
    assert await cli_launch.terminate_cli_tree(proc, 1.0) == cli_launch.UNKNOWN


def test_containment_note_wording(monkeypatch):
    """Only the exact status 'contained' is called contained; Windows adds the scope note."""
    monkeypatch.setattr(cli_launch, "_is_windows", lambda: True)
    assert "escaped:2" in cli_launch.containment_note("escaped:2")
    note = cli_launch.containment_note("contained")
    assert cli_launch.CONTAINMENT_SCOPE_NOTE in note
    assert "process-tree containment" not in note
    assert "unknown" in cli_launch.containment_note("unknown")


@pytest.mark.asyncio
async def test_spawn_cli_windows_launch_error_becomes_runtimeerror(monkeypatch):
    """A LaunchError from the suspended start is handled like other launch failures."""
    monkeypatch.setattr(cli_launch, "_is_windows", lambda: True)

    def bad(argv, **kw):
        """Test double: bad."""
        raise cli_launch.LaunchError("resume failed")

    monkeypatch.setattr(cli_launch, "launch_tree", bad)
    with pytest.raises(RuntimeError, match="launch failed: resume failed"):
        await cli_launch.spawn_cli(["x.exe"])


@pytest.mark.asyncio
async def test_spawn_cli_windows_wraps_popen_in_proxy(monkeypatch):
    """Windows spawn goes through launch_tree and returns an asyncio-style proxy."""
    monkeypatch.setattr(cli_launch, "_is_windows", lambda: True)
    seen = {}

    class _Popen:
        """Test double: Popen."""
        pid = 5

        def poll(self):
            """Test double: poll."""
            return 3

        def communicate(self):
            """Test double: communicate."""
            return b"o", b"e"

    def fake_launch(argv, **kw):
        """Test double: fake launch."""
        seen["argv"], seen["kw"] = argv, kw
        return _Popen()

    monkeypatch.setattr(cli_launch, "launch_tree", fake_launch)
    proc = await cli_launch.spawn_cli(["C:\\bin\\codex.exe", "x"])
    assert seen["argv"][0].endswith("codex.exe")
    assert proc.pid == 5 and proc.returncode == 3
    assert await proc.communicate() == (b"o", b"e")


@pytest.mark.skipif(sys.platform != "win32", reason="real Job Object smoke test needs Windows")
@pytest.mark.asyncio
async def test_real_launch_tree_terminate_smoke():
    """Real launch_tree + terminate_cli_tree: a sleeping child is killed and reported contained."""
    proc = await cli_launch.spawn_cli([sys.executable, "-c", "import time; time.sleep(60)"])
    assert proc.returncode is None
    status = await cli_launch.terminate_cli_tree(proc, 5.0)
    assert status == cli_launch.CONTAINED
    assert proc.returncode is not None


@pytest.mark.asyncio
async def test_terminate_cli_tree_windows_failure_is_unknown_not_contained(monkeypatch):
    """A crash inside the tree kill degrades to unknown (never a false 'contained')."""
    monkeypatch.setattr(cli_launch, "_is_windows", lambda: True)

    def boom(popen, grace):
        """Test double: boom."""
        raise OSError("taskkill missing")

    monkeypatch.setattr(cli_launch, "terminate_tree", boom)
    terminated = []
    proc = SimpleNamespace(
        pid=1, returncode=None, popen=object(), terminate=lambda: terminated.append(1)
    )
    assert await cli_launch.terminate_cli_tree(proc, 1.0) == cli_launch.UNKNOWN
    assert terminated == [1]


@pytest.mark.asyncio
async def test_terminate_cli_tree_posix_signals_direct_child_only(monkeypatch):
    """POSIX path keeps terminate()-on-the-direct-child semantics."""
    monkeypatch.setattr(cli_launch, "_is_windows", lambda: False)

    class _P:
        """Test double: P."""
        returncode = None

        def terminate(self):
            """Test double: terminate."""
            self.returncode = -15

        async def wait(self):
            """Test double: wait."""
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
        """Test double: spawn."""
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

    monkeypatch.setattr(cli_launch, "_is_windows", lambda: True)
    monkeypatch.setattr(cli_launch, "prepare_cli_command", lambda c: list(c))

    class _P:
        """Test double: P."""
        returncode = None
        pid = 7

        async def communicate(self):
            """Test double: communicate."""
            await asyncio.Event().wait()

        async def wait(self):
            """Test double: wait."""
            return self.returncode

    async def _create(*a, **k):
        """Test double: create."""
        return _P()

    async def _tree(proc, grace=5.0):
        """Test double: tree."""
        proc.returncode = 1
        return "escaped:3"

    monkeypatch.setattr(cli_launch, "spawn_cli", lambda cmd, **kw: _create())
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
        """Test double: P."""
        returncode = None

    async def _tree(proc, grace=5.0):
        """Test double: tree."""
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


def test_containment_note_is_empty_on_posix_for_every_status(monkeypatch):
    """P3: POSIX timeout wording is the historical one: no note for any status."""
    monkeypatch.setattr(cli_launch, "_is_windows", lambda: False)
    for status in ("contained", "unknown", "escaped:1"):
        assert cli_launch.containment_note(status) == ""


@pytest.mark.asyncio
@pytest.mark.parametrize("windows,expect_note", [(False, False), (True, True)])
async def test_timeout_message_note_only_on_windows(monkeypatch, windows, expect_note):
    """P3: an unexited child after the grace period keeps the exact old text on POSIX."""
    from orchestrator import worker_registry

    monkeypatch.setattr(cli_launch, "_is_windows", lambda: windows)
    monkeypatch.setattr(cli_launch, "prepare_cli_command", lambda c: list(c))

    class _P:
        """Test double: child that never exits."""
        returncode = None
        pid = 3

        async def communicate(self):
            """Block forever."""
            await asyncio.Event().wait()

        async def wait(self):
            """Block forever."""
            await asyncio.Event().wait()

    async def _spawn(cmd, **kw):
        """Return the never-exiting child."""
        return _P()

    async def _tree(proc, grace=5.0):
        """Report an unknown containment."""
        return "unknown"

    monkeypatch.setattr(cli_launch, "spawn_cli", _spawn)
    monkeypatch.setattr(cli_launch, "terminate_cli_tree", _tree)
    spec = SimpleNamespace(job_id="", prompt="x", constraints={"max_seconds": 0.05})
    with pytest.raises(RuntimeError) as ei:
        await worker_registry._run_dangerous_cli_subprocess(spec, ["codex", "x"], "codex")
    msg = str(ei.value)
    if expect_note:
        assert cli_launch.CONTAINMENT_SCOPE_NOTE in msg
    else:
        assert msg == "codex worker timed out after 0.05s"
