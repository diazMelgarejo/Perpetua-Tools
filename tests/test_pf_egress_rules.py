"""Tests for Layer-3 macOS pf egress rules installer and verification scripts.

Tests idempotency, rule integrity, drift detection, and non-blocking verification logic.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "security" / "install-egress-pf-rules.sh"
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "security" / "verify-egress-pf-rules.sh"

EXPECTED_RULES = [
    "block drop out quick on en0 to 169.254.0.0/16",
    "block drop out quick on en0 to 169.254.169.254",
    "block drop out quick on en0 to fd00:ec2::254",
    "block drop out quick on en0 to fe80::/10",
]


class TestPFEgressScripts:
    """Test suite for install-egress-pf-rules.sh and verify-egress-pf-rules.sh."""

    def test_scripts_exist_and_executable(self) -> None:
        assert INSTALL_SCRIPT.exists(), f"Missing {INSTALL_SCRIPT}"
        assert VERIFY_SCRIPT.exists(), f"Missing {VERIFY_SCRIPT}"
        assert os.access(INSTALL_SCRIPT, os.X_OK), "install script not executable"
        assert os.access(VERIFY_SCRIPT, os.X_OK), "verify script not executable"

    def test_installer_idempotency_and_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_anchor = Path(tmpdir) / "com.perpetua-tools.egress-deny"
            env = {**os.environ, "PF_ANCHOR_FILE": str(fake_anchor), "PFCTL_SKIP": "1"}

            # Pass 1: Install should write rules
            res1 = subprocess.run(
                ["bash", str(INSTALL_SCRIPT)],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            assert res1.returncode == 0, f"Pass 1 failed: {res1.stderr}"
            assert fake_anchor.exists(), "Anchor file not created"
            content1 = fake_anchor.read_text()
            for rule in EXPECTED_RULES:
                assert rule in content1, f"Missing rule in anchor: {rule}"

            # Pass 2: Idempotent run should not duplicate or change content
            res2 = subprocess.run(
                ["bash", str(INSTALL_SCRIPT)],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            assert res2.returncode == 0, f"Pass 2 failed: {res2.stderr}"
            content2 = fake_anchor.read_text()
            assert content1 == content2, "Idempotency violated: content modified on second pass"

    def test_verify_script_detects_missing_and_drifted_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_anchor = Path(tmpdir) / "com.perpetua-tools.egress-deny"
            env = {**os.environ, "PF_ANCHOR_FILE": str(fake_anchor), "PFCTL_SKIP": "1"}

            # Missing anchor -> non-zero exit
            res_missing = subprocess.run(
                ["bash", str(VERIFY_SCRIPT)],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            assert res_missing.returncode != 0, "Verify should fail when anchor is missing"

            # Corrupted / drifted anchor -> non-zero exit
            fake_anchor.write_text("pass out quick all\n")
            res_corrupt = subprocess.run(
                ["bash", str(VERIFY_SCRIPT)],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            assert res_corrupt.returncode != 0, "Verify should fail on drifted anchor"

            # Correct anchor installed -> exit 0 (in PFCTL_SKIP mode)
            subprocess.run(
                ["bash", str(INSTALL_SCRIPT)],
                capture_output=True,
                text=True,
                env=env,
                check=True,
            )
            res_valid = subprocess.run(
                ["bash", str(VERIFY_SCRIPT)],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            assert res_valid.returncode == 0, f"Verify should succeed with valid anchor: {res_valid.stderr}"
