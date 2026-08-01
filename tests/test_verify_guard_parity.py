"""Tests for scripts/git/verify-guard-parity.sh edge cases."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "scripts" / "git" / "verify-guard-parity.sh"

pytestmark = pytest.mark.unit


def test_verify_guard_parity_fails_on_inaccessible_target() -> None:
    bash = shutil.which("bash")
    assert bash is not None
    result = subprocess.run(  # noqa: S603 — test controls all arguments
        [bash, str(VERIFY), "/path/does/not/exist"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode != 0
    assert "cannot access target repository" in result.stdout + result.stderr
    assert "FAIL" in result.stdout + result.stderr
