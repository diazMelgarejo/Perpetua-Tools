"""Regression coverage for the reviewed ECC overlay restore workflow."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/git/ecc-submodule-sync.sh"

pytestmark = pytest.mark.integration


def _run(
    args: list[str], cwd: Path, *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def _configure_git(repo: Path) -> None:
    _run(["git", "config", "user.name", "ECC overlay test"], repo)
    _run(
        ["git", "config", "user.email", "ecc-overlay-test@example.invalid"],
        repo,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _run(["git", "init", "-b", "main"], repo)
    _configure_git(repo)


def _consumer_with_ecc(
    tmp_path: Path, files: dict[str, str], manifest_entries: str
) -> tuple[Path, Path, Path, dict[str, str]]:
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    for relative_path, content in files.items():
        target = upstream / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    _run(["git", "add", "."], upstream)
    _run(["git", "commit", "-m", "initial ECC"], upstream)

    repo = tmp_path / "consumer"
    _init_repo(repo)
    env = os.environ.copy()
    env["GIT_ALLOW_PROTOCOL"] = "file"
    _run(
        [
            "git",
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            str(upstream),
            "vendor/ecc-tools",
        ],
        repo,
        env=env,
    )
    _run(["git", "commit", "-m", "add ECC submodule"], repo)

    sync_script = repo / "scripts/git/ecc-submodule-sync.sh"
    sync_script.parent.mkdir(parents=True)
    shutil.copy2(SCRIPT, sync_script)
    sync_script.with_name("ecc-local-overlay.tsv").write_text(
        "# schema=1\n" + manifest_entries,
        encoding="utf-8",
    )
    return repo, repo / "vendor/ecc-tools", sync_script, env


def test_upgrade_restores_reviewed_overlay_from_clean_latest_checkout(
    tmp_path: Path,
) -> None:
    """A fresh clean checkout is allowed through upgrade.

    It then restores its patch.

    This covers both guards: no local candidate must not be rejected merely
    because a reviewed patch exists, and a successful apply must return zero.
    """
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    (upstream / ".env.example").write_text("BASE=1\n", encoding="utf-8")
    _run(["git", "add", ".env.example"], upstream)
    _run(["git", "commit", "-m", "initial ECC"], upstream)

    repo = tmp_path / "consumer"
    _init_repo(repo)
    env = os.environ.copy()
    env["GIT_ALLOW_PROTOCOL"] = "file"
    _run(
        [
            "git",
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            str(upstream),
            "vendor/ecc-tools",
        ],
        repo,
        env=env,
    )
    _run(["git", "commit", "-m", "add ECC submodule"], repo)

    sync_script = repo / "scripts/git/ecc-submodule-sync.sh"
    sync_script.parent.mkdir(parents=True)
    shutil.copy2(SCRIPT, sync_script)
    manifest = sync_script.with_name("ecc-local-overlay.tsv")
    manifest.write_text(
        "# schema=1\n"
        ".local/overlay.txt\tnew-file\tRegression overlay\n"
        ".env.example\tadditive\tRegression additive overlay\n",
        encoding="utf-8",
    )

    submodule = repo / "vendor/ecc-tools"
    _run(["git", "config", "core.abbrev", "7"], submodule)
    overlay = submodule / ".local/overlay.txt"
    overlay.parent.mkdir()
    overlay.write_text("preserved\n", encoding="utf-8")
    env_example = submodule / ".env.example"
    env_example.write_text("BASE=1\nOVERLAY=1\n", encoding="utf-8")
    _run(["git", "add", "--intent-to-add", ".local/overlay.txt"], submodule)
    patch = _run(
        ["git", "diff", "--binary", "--full-index", "HEAD"],
        submodule,
    ).stdout
    sync_script.with_name("ecc-local-additions.patch").write_text(
        patch,
        encoding="utf-8",
    )
    _run(["git", "reset", "--", ".local/overlay.txt"], submodule)
    _run(["git", "checkout", "--", ".env.example"], submodule)
    overlay.unlink()
    overlay.parent.rmdir()

    result = subprocess.run(
        ["bash", str(sync_script), "upgrade"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "already at origin/main" in result.stdout
    assert "restore: 2 reviewed overlay path(s) re-applied" in result.stdout
    assert overlay.read_text(encoding="utf-8") == "preserved\n"
    assert env_example.read_text(encoding="utf-8") == "BASE=1\nOVERLAY=1\n"

    repeated = subprocess.run(
        ["bash", str(sync_script), "upgrade"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )

    assert repeated.returncode == 0, repeated.stdout + repeated.stderr
    assert "restore: 2 reviewed overlay path(s) already applied" in (
        repeated.stdout
    )


def test_save_review_classifies_and_rejects_unbalanced_unapproved_markdown(
    tmp_path: Path,
) -> None:
    repo, submodule, sync_script, env = _consumer_with_ecc(
        tmp_path,
        {"docs/example.md": "```text\nexample\n```\n"},
        ".local/overlay.txt\tnew-file\tRegression overlay\n",
    )
    (submodule / "docs/example.md").write_text("```text\nexample\n", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(sync_script), "save", "--review"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )

    assert result.returncode != 0
    assert "unapproved-source-drift: docs/example.md" in result.stdout
    assert "unbalanced Markdown code fence in docs/example.md" in result.stderr


def test_save_review_rejects_unbalanced_approved_markdown_overlay(
    tmp_path: Path,
) -> None:
    repo, submodule, sync_script, env = _consumer_with_ecc(
        tmp_path,
        {"README.md": "base\n"},
        ".local/fixture.md\tnew-file\tRegression Markdown overlay\n",
    )
    fixture = submodule / ".local/fixture.md"
    fixture.parent.mkdir()
    fixture.write_text("```text\nunclosed\n", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(sync_script), "save", "--review"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )

    assert result.returncode != 0
    assert "reviewed-overlay: .local/fixture.md" in result.stdout
    assert "unbalanced Markdown code fence in .local/fixture.md" in result.stderr


def test_restore_rejects_unbalanced_markdown_patch_before_applying(
    tmp_path: Path,
) -> None:
    repo, submodule, sync_script, env = _consumer_with_ecc(
        tmp_path,
        {"README.md": "base\n"},
        ".local/fixture.md\tnew-file\tRegression Markdown overlay\n",
    )
    fixture = submodule / ".local/fixture.md"
    fixture.parent.mkdir()
    fixture.write_text("```text\nunclosed\n", encoding="utf-8")
    _run(["git", "add", "--intent-to-add", ".local/fixture.md"], submodule)
    patch = _run(["git", "diff", "--binary", "--full-index", "HEAD"], submodule).stdout
    sync_script.with_name("ecc-local-additions.patch").write_text(
        patch,
        encoding="utf-8",
    )
    _run(["git", "reset", "--", ".local/fixture.md"], submodule)
    fixture.unlink()
    fixture.parent.rmdir()

    result = subprocess.run(
        ["bash", str(sync_script), "restore"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )

    assert result.returncode != 0
    assert "reviewed overlay leaves an unbalanced Markdown code fence" in result.stderr
    assert not fixture.exists()


def test_update_ignores_generated_hook_telemetry(
    tmp_path: Path,
) -> None:
    repo, submodule, sync_script, env = _consumer_with_ecc(
        tmp_path,
        {"README.md": "base\n"},
        ".local/overlay.txt\tnew-file\tRegression overlay\n",
    )
    hook_log = submodule / ".claude/hooks/.logs/hook-log.jsonl"
    hook_log.parent.mkdir(parents=True)
    hook_log.write_text('{"hook":"runtime"}\n', encoding="utf-8")

    result = subprocess.run(
        ["bash", str(sync_script), "update"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "no local source drift" in result.stdout
    assert hook_log.read_text(encoding="utf-8") == '{"hook":"runtime"}\n'


def test_ignore_runtime_adds_idempotent_local_exclude(
    tmp_path: Path,
) -> None:
    repo, submodule, sync_script, env = _consumer_with_ecc(
        tmp_path,
        {"README.md": "base\n"},
        ".local/overlay.txt\tnew-file\tRegression overlay\n",
    )

    first = _run(["bash", str(sync_script), "ignore-runtime"], repo, env=env)
    second = _run(["bash", str(sync_script), "ignore-runtime"], repo, env=env)
    exclude = Path(
        _run(["git", "rev-parse", "--git-path", "info/exclude"], submodule).stdout.strip()
    )
    if not exclude.is_absolute():
        exclude = submodule / exclude

    assert "added local ignore" in first.stdout
    assert "already present" in second.stdout
    assert exclude.read_text(encoding="utf-8").splitlines().count(
        ".claude/hooks/.logs/hook-log.jsonl"
    ) == 1
