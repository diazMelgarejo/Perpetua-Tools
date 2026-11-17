"""Offline process-boundary tests: child programs contain no SDK or network code."""
import gc
import importlib.util
import pathlib
import socket
import subprocess
import sys
import time
import warnings
from types import ModuleType
from typing import Any

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture
def llm(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Load the harness and forbid networking in this process."""
    monkeypatch.setattr(socket.socket, "connect", lambda *args, **kwargs: pytest.fail("network forbidden"))
    spec = importlib.util.spec_from_file_location("isolated_llm", ROOT / ".agent/harness/llm.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _substitute_child(monkeypatch: pytest.MonkeyPatch, llm: ModuleType, program: str) -> list[subprocess.Popen[bytes]]:
    """Replace the worker command with a known local Python child and retain its handle."""
    original = subprocess.Popen
    children = []

    def launch(args: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        """Start only the supplied local test program and retain the child."""
        assert "secret-test-key" not in repr(args)
        kwargs["env"] = {}  # Do not pass operator credentials into test children.
        process = original([sys.executable, "-c", program], **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr(llm.subprocess, "Popen", launch)
    return children


def test_deadline_kills_and_reaps_child(llm: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unresponsive local child is terminated and reaped at the deadline."""
    children = _substitute_child(monkeypatch, llm, "import sys,time; sys.stdin.read(); time.sleep(30)")
    start = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        llm._run_wandb_worker({"api_key": "secret-test-key"}, 0.2)
    assert time.monotonic() - start < 3
    assert children[0].poll() is not None
    assert children[0].stdin.closed and children[0].stdout.closed


@pytest.mark.parametrize("program", ["import os; os._exit(9)", "print('not-json')"])
def test_crash_or_invalid_json_never_returns_a_result(llm: ModuleType, monkeypatch: pytest.MonkeyPatch, program: str) -> None:
    """A crash or invalid wire response raises and leaves no child alive."""
    children = _substitute_child(monkeypatch, llm, program)
    with pytest.raises((RuntimeError, ValueError, BrokenPipeError)):
        llm._run_wandb_worker({"api_key": "secret-test-key"}, 2)
    assert children[0].poll() is not None
    assert children[0].stdin.closed and children[0].stdout.closed


def test_timeout_closes_pipes_without_resource_warning(llm: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    """An interrupted worker releases its pipe resources as well as its process."""
    children = _substitute_child(monkeypatch, llm, "import sys,time; sys.stdin.read(); time.sleep(30)")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        with pytest.raises(subprocess.TimeoutExpired):
            llm._run_wandb_worker({"api_key": "secret-test-key"}, 0.2)
        assert children[0].stdin.closed and children[0].stdout.closed
        children.clear()
        gc.collect()
    assert not [warning for warning in caught if issubclass(warning.category, ResourceWarning)]


def test_weave_initialization_runs_only_when_configured(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    """The child reuses the harness initializer when a project is configured."""
    monkeypatch.setattr(socket.socket, "connect", lambda *args, **kwargs: pytest.fail("network forbidden"))
    spec = importlib.util.spec_from_file_location("offline_worker", ROOT / "src/perpetua_tools/wandb_worker.py")
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    marker = tmp_path / "initialized"
    fake = tmp_path / "fake_harness.py"
    fake.write_text("def _maybe_init_wandb_weave_tracing():\n    from pathlib import Path\n    Path(" + repr(str(marker)) + ").write_text('yes')\n")
    original = importlib.util.spec_from_file_location
    monkeypatch.setattr(worker.importlib.util, "spec_from_file_location", lambda name, path: original(name, fake))
    monkeypatch.delenv("DEEPSEEK_V4_FLASH_WANDB_PROJECT", raising=False)
    worker._init_tracing()
    assert not marker.exists()
    monkeypatch.setenv("DEEPSEEK_V4_FLASH_WANDB_PROJECT", "test-project")
    worker._init_tracing()
    assert marker.read_text() == "yes"


def test_exit_race_does_not_mask_interrupt(llm: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    """A child exiting before terminate does not hide the original interrupt."""
    import io

    class ExitedDuringTermination:
        """A process double that exits between poll and terminate."""
        stdin = io.BytesIO()
        stdout = io.BytesIO()
        stderr = None

        def communicate(self, payload: bytes, timeout: float) -> tuple[bytes, bytes]:
            """Interrupt after the child was started."""
            raise KeyboardInterrupt()

        def poll(self) -> None:
            """Report the child as initially alive."""
            return None

        def kill(self) -> None:
            """Simulate the child exiting just before termination."""
            raise ProcessLookupError()

        def wait(self, timeout: float) -> int:
            """Confirm the child has exited."""
            return 0

    process = ExitedDuringTermination()
    monkeypatch.setattr(llm.subprocess, "Popen", lambda *args, **kwargs: process)
    with pytest.raises(KeyboardInterrupt):
        llm._run_wandb_worker({"api_key": "secret-test-key"}, 1)
    assert process.stdin.closed and process.stdout.closed


@pytest.mark.skipif(sys.platform == "win32", reason="SIGTERM semantics differ on Windows")
def test_deadline_immediately_kills_sigterm_ignoring_child(llm: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    """Once the deadline expires, no termination grace period extends request execution."""
    original = subprocess.Popen
    children = []
    program = ("import signal,sys,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
               "print('ready', flush=True); sys.stdin.read(); time.sleep(30)")

    def launch(args: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        """Wait for a local barrier confirming the signal handler is installed."""
        kwargs["env"] = {}
        process = original([sys.executable, "-c", program], **kwargs)
        assert process.stdout.readline() == b"ready\n"
        children.append(process)
        return process

    monkeypatch.setattr(llm.subprocess, "Popen", launch)
    start = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        llm._run_wandb_worker({"api_key": "secret-test-key"}, 0.2)
    assert time.monotonic() - start < 0.8
    assert children[0].poll() is not None
