"""Tests for scripts/hardware_policy_cli.py: encoding safety, exit codes, policy content."""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "hardware_policy_cli.py"

_spec = importlib.util.spec_from_file_location("hardware_policy_cli_under_test", CLI)
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)


def _run(*args: str, encoding: str = "cp1252") -> subprocess.CompletedProcess:
    """Run the CLI in a subprocess with a legacy console encoding forced."""
    env = dict(os.environ, PYTHONIOENCODING=encoding, PYTHONUTF8="0")
    return subprocess.run(
        [sys.executable, str(CLI), *args], capture_output=True, env=env, timeout=60
    )


def test_validate_ok_does_not_crash_on_cp1252_console():
    """A clean --validate under cp1252 exits 0 with no UnicodeEncodeError."""
    proc = _run("--validate", "qwen/qwen3.8-27b", "win")
    assert proc.returncode == 0, proc.stderr
    assert b"UnicodeEncodeError" not in proc.stderr


def test_violation_exits_1_on_cp1252_console():
    """A real policy violation exits 1 (not a crash) even on cp1252."""
    proc = _run("--validate", "qwen/qwen3.8-27b", "mac")
    assert proc.returncode == cli.EXIT_VIOLATION == 1
    assert b"UnicodeEncodeError" not in proc.stderr
    assert b"Traceback" not in proc.stderr


def test_internal_crash_exits_with_distinct_code(monkeypatch, capsys):
    """An unexpected exception returns EXIT_INTERNAL_ERROR, never the violation code."""
    def boom(*_a, **_k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(sys, "argv", ["hardware_policy_cli.py", "--list"])
    monkeypatch.setattr(cli, "cmd_list", boom)
    rc = cli.main()
    assert rc == cli.EXIT_INTERNAL_ERROR
    assert rc not in (0, cli.EXIT_VIOLATION)
    assert "internal error: RuntimeError: kaboom" in capsys.readouterr().err


def test_sym_falls_back_to_ascii_when_stdout_cannot_encode(monkeypatch):
    """_sym returns ASCII tags for cp1252 and emoji for utf-8 streams."""
    class _S:
        encoding = "cp1252"

    monkeypatch.setattr(cli.sys, "stdout", _S())
    assert cli._sym("ok") == "[OK]"
    _S.encoding = "utf-8"
    assert cli._sym("fail") == "\u274c"


def test_policy_lists_qwen38_27b_as_windows_only():
    """qwen/qwen3.8-27b (PR #474) is windows_only, so it is refused on Mac."""
    policy = cli.load_policy()
    assert "qwen/qwen3.8-27b" in policy["windows_only"]
    assert cli.check_affinity("qwen/qwen3.8-27b", "win", policy)[0] is True
    assert cli.check_affinity("qwen/qwen3.8-27b", "mac", policy)[0] is False
