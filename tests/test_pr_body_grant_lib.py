"""Tests for scripts/cursor/pr-body-grant-lib.py"""
from __future__ import annotations

import hashlib
import hmac
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
    expected = hmac.new(b"unit-test-secret", payload, hashlib.sha256).hexdigest()
    assert grant_lib._sign(b"unit-test-secret", payload) == expected


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
    assert grant_lib.nonce_is_consumed(nonce)
    ok2, err2 = grant_lib.verify_grant_for_append(
        "owner/repo",
        "7",
        str(append),
        None,
        consume=False,
    )
    assert not ok2
    assert "missing or not grant v2" in err2 or "already consumed" in err2


def test_wrong_pr_fails(grant_lib, tmp_path):
    append = tmp_path / "follow.md"
    append.write_text("x", encoding="utf-8")
    grant_lib.mint_grant("owner/repo", "42", str(append), None)
    ok, err = grant_lib.verify_grant_for_append(
        "owner/repo",
        "99",
        str(append),
        None,
        consume=False,
    )
    assert not ok
    assert "PR mismatch" in err


def test_tampered_token_fails(grant_lib, tmp_path):
    append = tmp_path / "follow.md"
    append.write_text("x", encoding="utf-8")
    grant_lib.mint_grant("owner/repo", "1", str(append), None)
    ack = grant_lib.ACK_PATH
    ack.write_text(ack.read_text(encoding="utf-8").replace("token=", "token=deadbeef"), encoding="utf-8")
    ok, err = grant_lib.verify_grant_for_append(
        "owner/repo",
        "1",
        str(append),
        None,
        consume=False,
    )
    assert not ok
    assert "HMAC" in err


def test_ttl_expired(grant_lib, tmp_path):
    append = tmp_path / "follow.md"
    append.write_text("x", encoding="utf-8")
    grant_lib.mint_grant("owner/repo", "1", str(append), None)
    ack = grant_lib.ACK_PATH
    lines = []
    for line in ack.read_text(encoding="utf-8").splitlines():
        if line.startswith("issued-at="):
            lines.append("issued-at=2020-01-01T00:00:00Z")
        else:
            lines.append(line)
    ack.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok, err = grant_lib.verify_grant_for_append(
        "owner/repo",
        "1",
        str(append),
        None,
        consume=False,
    )
    assert not ok
    assert "expired" in err.lower() or "ttl" in err.lower()


def test_future_issued_at_rejected(grant_lib, tmp_path):
    append = tmp_path / "follow.md"
    append.write_text("x", encoding="utf-8")
    grant_lib.mint_grant("owner/repo", "1", str(append), None)
    ack = grant_lib.ACK_PATH
    lines = []
    for line in ack.read_text(encoding="utf-8").splitlines():
        if line.startswith("issued-at="):
            lines.append("issued-at=2099-01-01T00:00:00Z")
        else:
            lines.append(line)
    ack.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok, err = grant_lib.verify_grant_for_append(
        "owner/repo",
        "1",
        str(append),
        None,
        consume=False,
    )
    assert not ok
    assert "expired" in err.lower() or "issued-at" in err.lower()


def test_repo_pipe_rejected(grant_lib, tmp_path):
    append = tmp_path / "follow.md"
    append.write_text("x", encoding="utf-8")
    with pytest.raises(grant_lib.GrantError, match="pipe"):
        grant_lib.mint_grant("owner|repo", "1", str(append), None)


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


def test_parse_append_segment_quoted_multiword_message(grant_lib):
    """Regression: a shell-quoted multi-word --message value must not be
    truncated at the first whitespace. Naive str.split() would previously
    return only 'hello' from '--message "hello world foo"'."""
    parsed = grant_lib.parse_append_segment(
        'bash scripts/cursor/append-pr-body.sh diaz/repo 9 --message "hello world foo"'
    )
    assert parsed == ("diaz/repo", "9", None, "hello world foo")


def test_parse_append_segment_single_quoted_message(grant_lib):
    parsed = grant_lib.parse_append_segment(
        "bash scripts/cursor/append-pr-body.sh diaz/repo 9 --message 'single quoted msg'"
    )
    assert parsed == ("diaz/repo", "9", None, "single quoted msg")


def test_parse_append_segment_malformed_quote_fails_closed(grant_lib):
    """An unclosed quote must fail closed (return None), not crash and not
    silently misparse."""
    parsed = grant_lib.parse_append_segment(
        'bash scripts/cursor/append-pr-body.sh diaz/repo 9 --message "unclosed'
    )
    assert parsed is None


def test_mint_grant_rejects_newline_in_pr_number(grant_lib, tmp_path):
    append = tmp_path / "follow.md"
    append.write_text("x", encoding="utf-8")
    with pytest.raises(grant_lib.GrantError):
        grant_lib.mint_grant("owner/repo", "5\ninjected", str(append), None)


def test_mint_grant_rejects_newline_in_repo(grant_lib, tmp_path):
    append = tmp_path / "follow.md"
    append.write_text("x", encoding="utf-8")
    with pytest.raises(grant_lib.GrantError):
        grant_lib.mint_grant("owner/repo\ninjected", "5", str(append), None)


def test_verify_grant_fields_rejects_newline_in_pr_number(grant_lib):
    ok, err = grant_lib.verify_grant_fields(
        {"issued-at": "2026-01-01T00:00:00Z"}, "owner/repo", "5\ninjected", "digest"
    )
    assert not ok
    assert "newline" in err.lower() or "pipe" in err.lower()


def test_validate_repo_slug_strict_schema(grant_lib):
    for bad in ["repo_without_owner", "owner//repo", "owner/repo/sub", "../evil/repo", "owner/repo with spaces", ""]:
        with pytest.raises(grant_lib.GrantError, match="repo"):
            grant_lib._validate_repo_slug(bad)


def test_validate_pr_number_strict_schema(grant_lib):
    for bad in ["0", "-1", "42.5", "abc", "042", ""]:
        with pytest.raises(grant_lib.GrantError, match="pr_number"):
            grant_lib._validate_pr_number(bad)


def test_content_digest_rejects_symlink(grant_lib, tmp_path):
    target = tmp_path / "real.md"
    target.write_text("content", encoding="utf-8")
    sym = tmp_path / "sym.md"
    try:
        sym.symlink_to(target)
    except OSError:
        pytest.skip("symlinks not supported on filesystem")
    with pytest.raises(grant_lib.GrantError, match="symlink"):
        grant_lib.content_digest_for_append(str(sym), None)


def test_content_digest_rejects_oversized_file(grant_lib, tmp_path, monkeypatch):
    big = tmp_path / "big.md"
    big.write_text("x" * 100, encoding="utf-8")
    monkeypatch.setattr(grant_lib, "MAX_APPEND_FILE_BYTES", 50)
    with pytest.raises(grant_lib.GrantError, match="size limit"):
        grant_lib.content_digest_for_append(str(big), None)


def test_content_digest_rejects_oversized_message(grant_lib, monkeypatch):
    monkeypatch.setattr(grant_lib, "MAX_APPEND_FILE_BYTES", 10)
    with pytest.raises(grant_lib.GrantError, match="size limit"):
        grant_lib.content_digest_for_append(None, "this is too long")


def test_append_operations_short_circuit_on_invalid_identity(grant_lib, tmp_path):
    # Non-existent file path would raise if read, but invalid repo must fail-closed first
    nonexistent = str(tmp_path / "does_not_exist.md")
    
    ok_v, err_v = grant_lib.verify_grant_for_append("bad_repo", "1", nonexistent, None)
    assert not ok_v and "repo" in err_v

    ok_r, err_r = grant_lib.reserve_grant_for_append("owner/repo", "-1", nonexistent, None)
    assert not ok_r and "pr_number" in err_r

    ok_m, err_m = grant_lib.mark_remote_applied_for_append("bad_repo", "1", nonexistent, None)
    assert not ok_m and "repo" in err_m

    ok_rel, err_rel = grant_lib.release_grant_for_append("owner/repo", "0", nonexistent, None)
    assert not ok_rel and "pr_number" in err_rel

    ok_rec, err_rec = grant_lib.reconcile_pending_consume("bad_repo", "1", nonexistent, None, "body", "title")
    assert not ok_rec and "repo" in err_rec
