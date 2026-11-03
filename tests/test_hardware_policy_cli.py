"""Tests for scripts/hardware_policy_cli.py: encoding safety, exit codes, policy content."""
from __future__ import annotations

import importlib.util
import json
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


def _run(*args: str, encoding: str = "cp1252") -> subprocess.CompletedProcess[bytes]:
    """Run the CLI in a subprocess with a legacy console encoding forced."""
    env = dict(os.environ, PYTHONIOENCODING=encoding, PYTHONUTF8="0")
    return subprocess.run(
        [sys.executable, str(CLI), *args], capture_output=True, env=env, timeout=60
    )


def test_validate_ok_does_not_crash_on_cp1252_console() -> None:
    """A clean --validate under cp1252 exits 0 with no UnicodeEncodeError."""
    proc = _run("--validate", "qwen/qwen3.8-27b", "win")
    assert proc.returncode == 0, proc.stderr
    assert b"UnicodeEncodeError" not in proc.stderr


def test_violation_exits_1_on_cp1252_console() -> None:
    """A real policy violation exits 1 (not a crash) even on cp1252."""
    proc = _run("--validate", "qwen/qwen3.8-27b", "mac")
    assert proc.returncode == cli.EXIT_VIOLATION == 1
    assert b"UnicodeEncodeError" not in proc.stderr
    assert b"Traceback" not in proc.stderr


def test_internal_crash_exits_with_distinct_code(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """An unexpected exception returns EXIT_INTERNAL_ERROR, never the violation code."""
    def boom(*_a: object, **_k: object) -> int:
        """Raise to simulate an internal crash."""
        raise RuntimeError("kaboom")

    monkeypatch.setattr(sys, "argv", ["hardware_policy_cli.py", "--list"])
    monkeypatch.setattr(cli, "cmd_list", boom)
    rc = cli.main()
    assert rc == cli.EXIT_INTERNAL_ERROR
    assert rc not in (0, cli.EXIT_VIOLATION)
    err = capsys.readouterr().err
    assert "internal error (RuntimeError)" in err
    assert "kaboom" not in err


def test_sym_falls_back_to_ascii_when_stdout_cannot_encode(monkeypatch: pytest.MonkeyPatch) -> None:
    """_sym returns ASCII tags for cp1252 and emoji for utf-8 streams."""
    class _S:
        """Fake stdout with a settable encoding."""
        encoding = "cp1252"

    monkeypatch.setattr(cli.sys, "stdout", _S())
    assert cli._sym("ok") == "[OK]"
    _S.encoding = "utf-8"
    assert cli._sym("fail") == "\u274c"


def test_policy_lists_qwen38_27b_as_windows_only() -> None:
    """qwen/qwen3.8-27b (PR #474) is windows_only, so it is refused on Mac."""
    policy = cli.load_policy()
    assert "qwen/qwen3.8-27b" in policy["windows_only"]
    assert cli.check_affinity("qwen/qwen3.8-27b", "win", policy)[0] is True
    assert cli.check_affinity("qwen/qwen3.8-27b", "mac", policy)[0] is False


def test_crash_output_never_echoes_exception_message(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """P3: stderr names only the exception type; KeyError text (fake config) is withheld."""
    def boom(*_a: object, **_k: object) -> int:
        """Raise a KeyError carrying fake config text."""
        raise KeyError("FAKE_SECRET_TOKEN=abc123 windows_only")

    monkeypatch.setattr(sys, "argv", ["hardware_policy_cli.py", "--list"])
    monkeypatch.setattr(cli, "cmd_list", boom)
    assert cli.main() == cli.EXIT_INTERNAL_ERROR
    captured = capsys.readouterr()
    assert "KeyError" in captured.err
    assert "FAKE_SECRET_TOKEN" not in captured.err + captured.out
    assert "abc123" not in captured.err + captured.out


def test_cp1252_filter_preserves_unencodable_model_ids() -> None:
    """Unencodable model IDs remain recoverable as escapes, not question marks."""
    proc = _run("--filter", "\u6a21\u578b", "--platform", "win")
    assert proc.returncode == 0, proc.stderr
    assert b"\\u6a21\\u578b" in proc.stdout
    assert b"??" not in proc.stdout


@pytest.mark.parametrize("verbose", [False, True])
def test_crash_frames_are_opt_in_and_exclude_sensitive_values(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], verbose: bool,
) -> None:
    """Verbose diagnostics expose locations without exception text, source or locals."""
    def parse_secret_config() -> int:
        """Fail with configuration text retained in the JSON exception."""
        private_value = "FAKE_SECRET_CONFIG_DO_NOT_PRINT"
        return json.loads(private_value)

    argv = ["hardware_policy_cli.py", "--list"]
    if verbose:
        argv.append("--verbose")
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(cli, "cmd_list", parse_secret_config)
    assert cli.main() == cli.EXIT_INTERNAL_ERROR
    captured = capsys.readouterr()
    output = captured.err + captured.out
    assert "JSONDecodeError" in captured.err
    assert "FAKE_SECRET_CONFIG_DO_NOT_PRINT" not in output
    assert "Expecting value" not in output
    assert "private_value" not in output
    assert "raise " not in output
    assert str(ROOT) not in output
    assert ("parse_secret_config" in captured.err) is verbose
    assert ("hardware_policy_cli.py:" in captured.err) is verbose
