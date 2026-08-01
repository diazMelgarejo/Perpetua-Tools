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
EXIT_MERGE_MSG = 5
EXIT_SQUASH = 6
EXIT_REBASE = 7
EXIT_AM = 8


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
        encoding="utf-8",
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
        encoding="utf-8",
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
        encoding="utf-8",
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
        encoding="utf-8",
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
        encoding="utf-8",
    )
    assert cherry.returncode != 0, "conflicted cherry-pick should leave CHERRY_PICK_HEAD set"

    result = _run_check(repo)
    assert result.returncode == EXIT_CHERRY_PICK
    assert "CHERRY_PICK_HEAD" in result.stderr
    assert "pre-push: blocked" in result.stderr
    assert "GIT_PUSH_E_PENDING_CHERRY_PICK" in result.stderr
    assert "cherry-pick --continue" in result.stderr


def test_check_no_pending_merge_blocks_pending_am_session(tmp_path: Path) -> None:
    """A stuck `git am` session must be reported as AM, not REBASE --
    both use .git/rebase-apply/ internally, but the recovery command
    differs (`git am --continue`/`--abort`, not `git rebase ...`)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / "f.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "f.txt"], check=True, cwd=repo)
    subprocess.run(["git", "commit", "-m", "base"], check=True, cwd=repo)

    (repo / "f.txt").write_text("patched\n", encoding="utf-8")
    subprocess.run(["git", "add", "f.txt"], check=True, cwd=repo)
    subprocess.run(["git", "commit", "-m", "to be patched"], check=True, cwd=repo)
    patch_dir = tmp_path / "patches"
    subprocess.run(
        ["git", "format-patch", "-1", "-o", str(patch_dir)],
        check=True,
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    subprocess.run(["git", "reset", "--hard", "HEAD~1"], check=True, cwd=repo)

    # Create a conflicting local change so the am gets stuck mid-apply.
    (repo / "f.txt").write_text("conflicting local change\n", encoding="utf-8")
    subprocess.run(["git", "add", "f.txt"], check=True, cwd=repo)
    subprocess.run(["git", "commit", "-m", "conflicting"], check=True, cwd=repo)

    patch_file = next(patch_dir.glob("*.patch"))
    am_result = subprocess.run(
        ["git", "am", str(patch_file)],
        cwd=repo, capture_output=True, text=True, encoding="utf-8",
    )
    assert am_result.returncode != 0, "conflicting am should leave rebase-apply/applying set"
    assert (repo / ".git" / "rebase-apply" / "applying").is_file()

    result = _run_check(repo)
    assert result.returncode == EXIT_AM
    assert "GIT_PUSH_E_PENDING_AM" in result.stderr
    assert "AM" in result.stderr
    assert "REBASE" not in result.stderr
    assert "am --continue" in result.stderr
    assert "am --abort" in result.stderr

    subprocess.run(["git", "am", "--abort"], cwd=repo, capture_output=True, text=True, encoding="utf-8")


def test_check_no_pending_merge_blocks_merge_msg_marker(tmp_path: Path) -> None:
    """Clean cherry-pick --no-commit leaves MERGE_MSG without CHERRY_PICK_HEAD (git >=2.43)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / "f.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "f.txt"], check=True, cwd=repo)
    subprocess.run(["git", "commit", "-m", "base"], check=True, cwd=repo)
    subprocess.run(["git", "branch", "side"], check=True, cwd=repo)
    (repo / "g.txt").write_text("side-only\n", encoding="utf-8")
    subprocess.run(["git", "add", "g.txt"], check=True, cwd=repo)
    subprocess.run(["git", "commit", "-m", "side"], check=True, cwd=repo)
    subprocess.run(["git", "checkout", "main"], check=True, cwd=repo)
    cherry = subprocess.run(
        ["git", "cherry-pick", "--no-commit", "side"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert cherry.returncode == 0
    merge_msg = repo / ".git" / "MERGE_MSG"
    if not merge_msg.is_file():
        pytest.skip("this git version does not leave MERGE_MSG for clean cherry-pick --no-commit")

    result = _run_check(repo)
    assert result.returncode == EXIT_MERGE_MSG
    assert "GIT_PUSH_E_PENDING_MERGE_MSG" in result.stderr
    assert "MERGE_MSG" in result.stderr
    assert "prepared message" in result.stderr


def test_check_no_pending_merge_blocks_squash_msg_marker(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], check=True, cwd=repo)
    subprocess.run(["git", "commit", "-m", "init"], check=True, cwd=repo)

    squash_rel = subprocess.check_output(
        ["git", "rev-parse", "--git-path", "SQUASH_MSG"],
        cwd=repo,
        text=True,
        encoding="utf-8",
    ).strip()
    squash_msg = (repo / squash_rel).resolve()
    squash_msg.write_text("Squashed commit of the following:\n", encoding="utf-8")

    result = _run_check(repo)
    assert result.returncode == EXIT_SQUASH
    assert "GIT_PUSH_E_PENDING_SQUASH" in result.stderr
    assert "SQUASH_MSG" in result.stderr
    assert "squash merge was prepared" in result.stderr


def test_check_no_pending_merge_blocks_rebase_marker(tmp_path: Path) -> None:
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
    rebase = subprocess.run(
        ["git", "rebase", "--merge", "side"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert rebase.returncode != 0
    assert (repo / ".git" / "rebase-merge").is_dir()

    result = _run_check(repo)
    assert result.returncode == EXIT_REBASE
    assert "GIT_PUSH_E_PENDING_REBASE" in result.stderr
    assert "REBASE" in result.stderr
    assert "rebase --continue" in result.stderr

    subprocess.run(["git", "rebase", "--abort"], cwd=repo, capture_output=True, text=True, encoding="utf-8")


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
