"""Regression tests for scripts/cursor/hooks/pr-body-guard-core.py"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/cursor/hooks/pr-body-guard-core.py"

pytestmark = pytest.mark.unit


def _load_guard_core():
    spec = importlib.util.spec_from_file_location("pr_body_guard_core", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def guard_core():
    return _load_guard_core()


@pytest.fixture()
def grant_setup(monkeypatch, tmp_path, guard_core):
    ack = tmp_path / "ack"
    nonces = tmp_path / "nonces.json"
    monkeypatch.setattr(guard_core._grant_lib, "ACK_PATH", ack)
    monkeypatch.setattr(guard_core._grant_lib, "NONCE_STATE_PATH", nonces)
    monkeypatch.setenv("PR_BODY_GRANT_HMAC_SECRET", "guard-test-secret")
    return guard_core._grant_lib


def test_shell_segments_splits_on_newline(guard_core):
    cmd = "echo one\necho two"
    assert guard_core._shell_segments(cmd) == ["echo one", "echo two"]


def test_append_pr_body_denied_without_grant(guard_core):
    cmd = "bash scripts/cursor/append-pr-body.sh a/b 1 --file x.md"
    lines = guard_core._shell_decision_lines(cmd)
    assert lines[0].startswith("DENY")


def test_append_pr_body_allowed_with_grant_emits_backup(guard_core, grant_setup, tmp_path):
    append = tmp_path / "x.md"
    append.write_text("follow-up body", encoding="utf-8")
    grant_setup.mint_grant("a/b", "1", str(append), None)
    cmd = f"bash scripts/cursor/append-pr-body.sh a/b 1 --file {append}"
    lines = guard_core._shell_decision_lines(cmd)
    assert any(line.startswith("BACKUP|a/b|1") for line in lines)
    assert lines[-1] == "ALLOW"


def test_newline_hidden_body_edit_after_valid_append_still_denied(
    guard_core, grant_setup, tmp_path
):
    append = tmp_path / "x.md"
    append.write_text("ok", encoding="utf-8")
    grant_setup.mint_grant("a/b", "1", str(append), None)
    cmd = (
        f"bash scripts/cursor/append-pr-body.sh a/b 1 --file {append}\n"
        "gh pr edit 1 --body evil.md"
    )
    lines = guard_core._shell_decision_lines(cmd)
    assert lines[0].startswith("DENY")


def test_newline_hidden_manage_pr_update_is_still_denied(guard_core, grant_setup, tmp_path):
    append = tmp_path / "x.md"
    append.write_text("ok", encoding="utf-8")
    grant_setup.mint_grant("a/b", "1", str(append), None)
    cmd = (
        f"bash scripts/cursor/append-pr-body.sh a/b 1 --file {append}\n"
        'ManagePullRequest update_pr body="evil"'
    )
    lines = guard_core._shell_decision_lines(cmd)
    assert lines[0].startswith("DENY")


def test_gh_pr_comment_alone_is_allowed(guard_core):
    lines = guard_core._shell_decision_lines("gh pr comment 1 --body 'note'")
    assert lines == ["ALLOW"]
