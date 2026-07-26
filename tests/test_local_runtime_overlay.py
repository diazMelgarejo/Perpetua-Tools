"""Tests for local-runtime overlay commit gate."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.git.check_local_runtime_overlay import (
    _violations_in_text,
    check_staged_overlay,
)

ROOT = Path(__file__).resolve().parents[1]


def _init_git_repo(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)


def test_devices_empty_lan_ip_ok() -> None:
    text = '    lan_ip: ""              # placeholder\n'
    assert not _violations_in_text("config/devices.yml", text)


def test_devices_private_lan_ip_blocked() -> None:
    text = '    lan_ip: "192.168.8.153"\n'
    errs = _violations_in_text("config/devices.yml", text)
    assert errs
    assert "lan_ip" in errs[0]


def test_devices_localhost_lan_ip_ok() -> None:
    text = '    lan_ip: "localhost"\n'
    assert not _violations_in_text("config/devices.yml", text)


def test_models_localhost_default_ok() -> None:
    text = '    host: "${LM_STUDIO_WIN_ENDPOINT:-http://localhost:1234}"\n'
    assert not _violations_in_text("config/models.yml", text)


def test_models_private_default_blocked() -> None:
    text = '    host: "${LM_STUDIO_WIN_ENDPOINT:-http://192.168.8.153}"\n'
    errs = _violations_in_text("config/models.yml", text)
    assert errs


def test_staged_gate_blocks_private_ip(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "config").mkdir()
    (repo / "config" / "devices.yml").write_text(
        '    lan_ip: "192.168.1.10"\n', encoding="utf-8"
    )
    _init_git_repo(repo)
    subprocess.run(["git", "add", "config/devices.yml"], cwd=repo, check=True)
    errors = check_staged_overlay(repo)
    assert errors


def test_unstaged_private_ip_not_checked(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "config").mkdir()
    devices = repo / "config" / "devices.yml"
    devices.write_text('    lan_ip: ""\n', encoding="utf-8")
    _init_git_repo(repo)
    subprocess.run(["git", "add", "config/devices.yml"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "seed", "--no-verify"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    devices.write_text('    lan_ip: "192.168.1.10"\n', encoding="utf-8")
    assert not check_staged_overlay(repo)
