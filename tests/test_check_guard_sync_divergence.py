"""Tests for scripts/git/check-guard-sync-divergence.sh."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/git/check-guard-sync-divergence.sh"

pytestmark = pytest.mark.unit


def _init_repo(path: Path, name: str, email: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", email],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", name],
        cwd=path,
        check=True,
        capture_output=True,
    )


def _commit_file(repo: Path, rel: str, content: str, msg: str) -> None:
    dest = repo / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", rel], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _run_checker(workspace: Path, canon: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["WORKSPACE_ROOT"] = str(workspace)
    env["GUARD_SYNC_CANON_ROOT"] = str(canon)
    return subprocess.run(
        ["bash", str(CHECKER), "--workspace"],
        cwd=canon,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def test_byte_identical_siblings_pass(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    canon = workspace / "orama-system"
    sibling = workspace / "Perpetua-Tools"
    rel = "scripts/git/audit_engine.py"
    body = "# canonical v1\n"

    for repo in (canon, sibling):
        _init_repo(repo, "Tester", "tester@example.com")
        _commit_file(repo, rel, body, "init")

    result = _run_checker(workspace, canon)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "byte-identical" in result.stdout


def test_sibling_lagging_canonical_history_passes(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    canon = workspace / "orama-system"
    sibling = workspace / "Perpetua-Tools"
    rel = "scripts/git/audit_engine.py"

    _init_repo(canon, "Tester", "tester@example.com")
    _commit_file(canon, rel, "# v1\n", "v1")
    _commit_file(canon, rel, "# v2\n", "v2")

    _init_repo(sibling, "Tester", "tester@example.com")
    _commit_file(sibling, rel, "# v1\n", "stale copy")

    result = _run_checker(workspace, canon)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "lags canonical history" in result.stdout


def test_sibling_ahead_of_canonical_fails_closed(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    canon = workspace / "orama-system"
    sibling = workspace / "Perpetua-Tools"
    rel = "scripts/git/audit_engine.py"

    _init_repo(canon, "Tester", "tester@example.com")
    _commit_file(canon, rel, "# canonical\n", "canon")

    _init_repo(sibling, "Tester", "tester@example.com")
    _commit_file(sibling, rel, "# sibling innovation\n", "sibling ahead")

    result = _run_checker(workspace, canon)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "GUARD_SYNC_E_DIVERGENCE" in result.stderr
    assert "forked divergence" in result.stdout or "absent from canonical history" in result.stdout
