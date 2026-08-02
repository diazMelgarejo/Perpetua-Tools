"""Tests for scripts/cursor/pr-body-grant-lib.py"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "scripts/cursor/pr-body-grant-lib.py"

pytestmark = pytest.mark.unit


def _load():
    spec = importlib.util.spec_from_file_location("pr_body_grant_lib", LIB)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def grant_lib(monkeypatch, tmp_path):
    module = _load()
    monkeypatch.setattr(module, "ACK_PATH", tmp_path / "ack")
    monkeypatch.setattr(module, "NONCE_STATE_PATH", tmp_path / "nonces.json")
    monkeypatch.setenv("PR_BODY_GRANT_HMAC_SECRET", "unit-test-secret")
    return module


def test_canonical_golden_vector(grant_lib):
    payload = grant_lib.canonical_payload_bytes(
        "owner/repo",
        "42",
        "nonce-abc",
        "2026-08-02T00:00:00Z",
        "append_integrative",
        "sha256:deadbeef",
    )
    assert payload == (
        b"grant-v2|owner/repo|42|nonce-abc|2026-08-02T00:00:00Z|"
        b"append_integrative|sha256:deadbeef"
    )
    token = grant_lib._sign(b"unit-test-secret", payload)
    assert token == "0852c9f3059f882ffdfc0fd4bcad37b5e8f76f1bc2e7f97df851f30e68b3a834"


def test_mint_and_verify_happy_path(grant_lib, tmp_path):
    append = tmp_path / "follow.md"
    append.write_text("## note\n", encoding="utf-8")
    grant_lib.mint_grant("owner/repo", "42", str(append), None)
    ok, err = grant_lib.verify_grant_for_append(
        "owner/repo",
        "42",
        str(append),
        None,
        consume=False,
    )
    assert ok, err


def test_wrong_repo_fails(grant_lib, tmp_path):
    append = tmp_path / "follow.md"
    append.write_text("x", encoding="utf-8")
    grant_lib.mint_grant("owner/repo", "42", str(append), None)
    ok, err = grant_lib.verify_grant_for_append(
        "other/repo",
        "42",
        str(append),
        None,
        consume=False,
    )
    assert not ok
    assert "repo mismatch" in err


def test_wrong_digest_fails(grant_lib, tmp_path):
    append = tmp_path / "follow.md"
    append.write_text("x", encoding="utf-8")
    grant_lib.mint_grant("owner/repo", "42", str(append), None)
    other = tmp_path / "other.md"
    other.write_text("y", encoding="utf-8")
    ok, err = grant_lib.verify_grant_for_append(
        "owner/repo",
        "42",
        str(other),
        None,
        consume=False,
    )
    assert not ok
    assert "content-digest mismatch" in err


def test_v1_grant_rejected(grant_lib, tmp_path):
    ack = grant_lib.ACK_PATH
    ack.parent.mkdir(parents=True, exist_ok=True)
    ack.write_text("operator-grant-v1\nissued-at=2026-08-02T00:00:00Z\n", encoding="utf-8")
    ok, err = grant_lib.verify_grant_for_append(
        "owner/repo",
        "1",
        None,
        "hello",
        consume=False,
    )
    assert not ok
    assert "operator-grant-v1" in err


def test_nonce_replay_blocked(grant_lib, tmp_path):
    append = tmp_path / "follow.md"
    append.write_text("once", encoding="utf-8")
    grant_lib.mint_grant("owner/repo", "7", str(append), None)
    ok_reserve, err_reserve = grant_lib.reserve_grant_for_append(
        "owner/repo", "7", str(append), None
    )
    assert ok_reserve, err_reserve
    fields = grant_lib.read_ack_fields()
    nonce = fields["grant-nonce"]
    ok_mark, err_mark = grant_lib.mark_remote_applied_atomic(nonce)
    assert ok_mark, err_mark
    ok, err = grant_lib.verify_grant_for_append(
        "owner/repo",
        "7",
        str(append),
        None,
        consume=True,
    )
    assert ok, err
    ok2, err2 = grant_lib.verify_grant_for_append(
        "owner/repo",
        "7",
        str(append),
        None,
        consume=False,
    )
    assert not ok2
    assert "nonce" in err2.lower() or "grant" in err2.lower()


def test_reserve_release_before_remote(grant_lib, tmp_path):
    append = tmp_path / "follow.md"
    append.write_text("draft", encoding="utf-8")
    grant_lib.mint_grant("owner/repo", "3", str(append), None)
    ok, err = grant_lib.reserve_grant_for_append("owner/repo", "3", str(append), None)
    assert ok, err
    ok_rel, err_rel = grant_lib.release_grant_for_append("owner/repo", "3", str(append), None)
    assert ok_rel, err_rel
    ok2, err2 = grant_lib.reserve_grant_for_append("owner/repo", "3", str(append), None)
    assert ok2, err2


def test_consume_requires_remote_applied(grant_lib, tmp_path):
    append = tmp_path / "follow.md"
    append.write_text("x", encoding="utf-8")
    grant_lib.mint_grant("owner/repo", "5", str(append), None)
    ok, err = grant_lib.reserve_grant_for_append("owner/repo", "5", str(append), None)
    assert ok, err
    ok_consume, err_consume = grant_lib.verify_grant_for_append(
        "owner/repo", "5", str(append), None, consume=True
    )
    assert not ok_consume
    assert "remote mutation" in err_consume.lower()


def test_parse_append_segment(grant_lib):
    parsed = grant_lib.parse_append_segment(
        "bash scripts/cursor/append-pr-body.sh diaz/repo 9 --file out.md"
    )
    assert parsed == ("diaz/repo", "9", "out.md", None)

