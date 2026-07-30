"""Tests for scripts/git/check_no_pending_merge.sh."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/git/check_no_pending_merge.sh"

pytestmark = pytest.mark.unit

# KB exit codes — must match check_no_pending_merge.sh
EXIT_OK = 0
EXIT_MERGE_CLEAN = 1
EXIT_MERGE_CONFLICT = 2
EXIT_CHERRY_PICK = 3
EXIT_REVERT = 4


def _init_git_repo(repo: Path, *, branch: str = "main") -> None:
    subprocess.run(["git", "init", "-q", "-b", branch], check=True, cwd=repo)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        check=True,
        cwd=repo,
    )
    subprocess.run(["git", "config", "user.name", "Test"], check=True, cwd=repo)


def _run_check(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), str(repo)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_check_no_pending_merge_passes_without_in_progress_ops(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], check=True, cwd=repo)
    subprocess.run(["git", "commit", "-m", "init"], check=True, cwd=repo)

    result = _run_check(repo)
    assert result.returncode == EXIT_OK
    assert result.stderr == ""


def test_check_no_pending_merge_blocks_conflicted_merge_head(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], check=True, cwd=repo)
    subprocess.run(["git", "commit", "-m", "base"], check=True, cwd=repo)
    subprocess.run(["git", "branch", "side"], check=True, cwd=repo)
    (repo / "README.md").write_text("main-line\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], check=True, cwd=repo)
    subprocess.run(["git", "commit", "-m", "main"], check=True, cwd=repo)
    subprocess.run(["git", "checkout", "side"], check=True, cwd=repo)
    (repo / "README.md").write_text("side\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], check=True, cwd=repo)
    subprocess.run(["git", "commit", "-m", "side"], check=True, cwd=repo)
    subprocess.run(["git", "checkout", "main"], check=True, cwd=repo)
    merge = subprocess.run(
        ["git", "merge", "--no-commit", "side"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert merge.returncode != 0, "expected a conflicted merge to leave MERGE_HEAD set"

    result = _run_check(repo)
    assert result.returncode == EXIT_MERGE_CONFLICT
    assert "MERGE_HEAD" in result.stderr
    assert "pre-push: blocked" in result.stderr
    assert "GIT_PUSH_E_PENDING_MERGE_CONFLICT" in result.stderr
    assert "resolve and stage conflicts" in result.stderr


def test_check_no_pending_merge_blocks_resolved_no_commit_merge(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "base.txt"], check=True, cwd=repo)
    subprocess.run(["git", "commit", "-m", "base"], check=True, cwd=repo)
    subprocess.run(["git", "branch", "side"], check=True, cwd=repo)
    (repo / "main.txt").write_text("main-only\n", encoding="utf-8")
    subprocess.run(["git", "add", "main.txt"], check=True, cwd=repo)
    subprocess.run(["git", "commit", "-m", "main"], check=True, cwd=repo)
    subprocess.run(["git", "checkout", "side"], check=True, cwd=repo)
    (repo / "side.txt").write_text("side-only\n", encoding="utf-8")
    subprocess.run(["git", "add", "side.txt"], check=True, cwd=repo)
    subprocess.run(["git", "commit", "-m", "side"], check=True, cwd=repo)
    subprocess.run(["git", "checkout", "main"], check=True, cwd=repo)
    merge = subprocess.run(
        ["git", "merge", "--no-commit", "--no-ff", "side"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert merge.returncode == 0, "non-overlapping merge should succeed without conflicts"

    result = _run_check(repo)
    assert result.returncode == EXIT_MERGE_CLEAN
    assert "MERGE_HEAD" in result.stderr
    assert "pre-push: blocked" in result.stderr
    assert "GIT_PUSH_E_PENDING_MERGE_CLEAN" in result.stderr
    assert "staged merge ready" in result.stderr


def test_merge_head_with_unmerged_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], check=True, cwd=repo)
    subprocess.run(["git", "commit", "-m", "base"], check=True, cwd=repo)
    subprocess.run(["git", "branch", "side"], check=True, cwd=repo)
    (repo / "README.md").write_text("main-line\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], check=True, cwd=repo)
    subprocess.run(["git", "commit", "-m", "main"], check=True, cwd=repo)
    subprocess.run(["git", "checkout", "side"], check=True, cwd=repo)
    (repo / "README.md").write_text("side\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], check=True, cwd=repo)
    subprocess.run(["git", "commit", "-m", "side"], check=True, cwd=repo)
    subprocess.run(["git", "checkout", "main"], check=True, cwd=repo)
    subprocess.run(
        ["git", "merge", "--no-commit", "side"],
        cwd=repo,
        capture_output=True,
        text=True,
    )

    result = _run_check(repo)
    assert result.returncode == EXIT_MERGE_CONFLICT
    assert "resolve and stage" in result.stderr


def test_check_no_pending_merge_blocks_pending_cherry_pick(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / "f.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "f.txt"], check=True, cwd=repo)
    subprocess.run(["git", "commit", "-m", "base"], check=True, cwd=repo)
    subprocess.run(["git", "branch", "side"], check=True, cwd=repo)
    (repo / "f.txt").write_text("main\n", encoding="utf-8")
    subprocess.run(["git", "add", "f.txt"], check=True, cwd=repo)
    subprocess.run(["git", "commit", "-m", "main"], check=True, cwd=repo)
    subprocess.run(["git", "checkout", "side"], check=True, cwd=repo)
    (repo / "f.txt").write_text("side\n", encoding="utf-8")
    subprocess.run(["git", "add", "f.txt"], check=True, cwd=repo)
    subprocess.run(["git", "commit", "-m", "side"], check=True, cwd=repo)
    subprocess.run(["git", "checkout", "main"], check=True, cwd=repo)
    cherry = subprocess.run(
        ["git", "cherry-pick", "side"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert cherry.returncode != 0, "conflicted cherry-pick should leave CHERRY_PICK_HEAD set"

    result = _run_check(repo)
    assert result.returncode == EXIT_CHERRY_PICK
    assert "CHERRY_PICK_HEAD" in result.stderr
    assert "pre-push: blocked" in result.stderr
    assert "GIT_PUSH_E_PENDING_CHERRY_PICK" in result.stderr
    assert "cherry-pick --continue" in result.stderr


def test_check_no_pending_merge_blocks_pending_revert(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], check=True, cwd=repo)
    subprocess.run(["git", "commit", "-m", "base"], check=True, cwd=repo)
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    subprocess.run(["git", "add", "b.txt"], check=True, cwd=repo)
    subprocess.run(["git", "commit", "-m", "second"], check=True, cwd=repo)
    subprocess.run(
        ["git", "revert", "--no-commit", "HEAD"],
        check=True,
        cwd=repo,
    )

    result = _run_check(repo)
    assert result.returncode == EXIT_REVERT
    assert "REVERT_HEAD" in result.stderr
    assert "pre-push: blocked" in result.stderr
    assert "GIT_PUSH_E_PENDING_REVERT" in result.stderr
    assert "revert --continue" in result.stderr


def test_check_no_pending_merge_shell_syntax() -> None:
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True, cwd=ROOT)
