"""The one attestation authority: the CLI and a future portal relay both write through it.

Offline and browser-free: state lives in a temporary OPENCLAW_STATE_DIR and no fact is fetched.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import provider_limits as pl  # noqa: E402

POLICY_PATH = REPO_ROOT / "config" / "provider-policies" / "wandb-inference.json"
PROVIDER = "wandb-inference"
NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
FACTS = {"plan_is_free": True, "payg_inactive": True, "allowance_remaining": True}
CLI_ARGS = ["attest", PROVIDER, "--plan-free", "--payg-inactive", "--allowance-remaining", "--by", "operator"]


@pytest.fixture()
def policy() -> dict:
    return pl.load_policy(POLICY_PATH)


@pytest.fixture()
def state(tmp_path: Path, monkeypatch) -> Path:
    """Point the operator state directory at a temp dir; nothing touches the real one."""
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(tmp_path))
    return tmp_path


def _write(**over) -> Path:
    """Call the authority with sane defaults, overriding one argument per test."""
    args: dict = {"provider": PROVIDER, "attested_by": "operator", "facts": dict(FACTS), "now": NOW}
    args.update(over)
    return pl.write_attestation_record(**args)


def _record() -> dict:
    return json.loads(pl.attestation_path(PROVIDER).read_text())


def _rows(path: Path) -> list[dict]:
    """Parse an append-only audit log."""
    return [json.loads(line) for line in path.read_text().splitlines()]


def _interactive(monkeypatch, answer: str | None = None) -> None:
    """Stand in for a person at a terminal typing the phrase."""
    monkeypatch.setattr(pl, "_is_interactive", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": pl.ATTEST_PHRASE if answer is None else answer)


# --- the write refuses anything that is not exactly True ----------------------------------------


@pytest.mark.parametrize("field", sorted(FACTS))
@pytest.mark.parametrize("bad", [False, "yes", "true", 1, 0, None, ""])
def test_every_fact_must_be_literally_true(state, field: str, bad) -> None:
    with pytest.raises(ValueError, match=field):
        _write(facts={**FACTS, field: bad})
    assert not pl.attestation_path(PROVIDER).exists()
    assert not pl.attestation_audit_path(PROVIDER).exists()


def test_a_missing_fact_is_refused(state) -> None:
    facts = dict(FACTS)
    facts.pop("payg_inactive")
    with pytest.raises(ValueError, match="payg_inactive must be true"):
        _write(facts=facts)
    assert not pl.attestation_path(PROVIDER).exists()


def test_a_fact_the_policy_does_not_ask_for_is_refused(state) -> None:
    with pytest.raises(ValueError, match="not a policy fact"):
        _write(facts={**FACTS, "billing_page_read": True})
    assert not pl.attestation_path(PROVIDER).exists()


@pytest.mark.parametrize("facts", [None, [], ["plan_is_free"], "plan_is_free", True])
def test_facts_must_be_a_mapping(state, facts) -> None:
    with pytest.raises(ValueError):
        _write(facts=facts)
    assert not pl.attestation_path(PROVIDER).exists()


@pytest.mark.parametrize("who", ["", "   ", None, 0])
def test_the_attestor_must_be_named(state, who) -> None:
    with pytest.raises(ValueError, match="attested_by"):
        _write(attested_by=who)
    assert not pl.attestation_path(PROVIDER).exists()


@pytest.mark.parametrize("now", [None, "2026-11-17T12:00:00+00:00", 0])
def test_now_must_be_a_datetime(state, now) -> None:
    with pytest.raises(ValueError, match="now must be a datetime"):
        _write(now=now)
    assert not pl.attestation_path(PROVIDER).exists()


def test_an_unknown_provider_is_refused(state) -> None:
    with pytest.raises(pl.ProviderPolicyError):
        _write(provider="no-such-provider")
    assert not pl.attestation_path("no-such-provider").exists()


# --- one schema, one authority: the CLI is unchanged --------------------------------------------


def test_the_record_schema_is_the_cli_schema(state, monkeypatch) -> None:
    """The shared record and the CLI record have the same keys, order, types and bytes."""
    _write()
    shared = _record()
    for stale in (pl.attestation_path(PROVIDER), pl.attestation_audit_path(PROVIDER)):
        stale.unlink(missing_ok=True)
    _interactive(monkeypatch)
    assert pl.main(list(CLI_ARGS)) == 0
    cli_text = pl.attestation_path(PROVIDER).read_text()
    cli = json.loads(cli_text)
    expected = ["provider", "attested_at", "attested_by",
                "plan_is_free", "payg_inactive", "allowance_remaining"]
    assert list(shared) == expected and list(cli) == expected
    assert shared.keys() == cli.keys()
    assert {k: v for k, v in shared.items() if k != "attested_at"} == \
           {k: v for k, v in cli.items() if k != "attested_at"}
    assert [type(v) for v in shared.values()] == [type(v) for v in cli.values()]
    assert cli_text == json.dumps(cli, indent=2) + "\n"


def test_the_cli_writes_through_the_one_authority(state, monkeypatch) -> None:
    seen: dict = {}
    real = pl.write_attestation_record

    def spy(provider, attested_by, facts, now):
        seen.update(provider=provider, attested_by=attested_by, facts=dict(facts), now=now)
        return real(provider, attested_by, facts, now)

    monkeypatch.setattr(pl, "write_attestation_record", spy)
    _interactive(monkeypatch)
    assert pl.main(list(CLI_ARGS)) == 0
    assert seen["provider"] == PROVIDER and seen["attested_by"] == "operator"
    assert seen["facts"] == FACTS and isinstance(seen["now"], datetime)
    assert pl.attestation_path(PROVIDER).is_file()


# --- mode 600, one audit row, and never a partial file ------------------------------------------


def test_the_record_is_created_mode_600(state) -> None:
    path = _write()
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert [p.name for p in path.parent.iterdir() if p.name.endswith(".tmp")] == []


def test_the_write_appends_one_size_only_audit_row(state, policy) -> None:
    _write()
    rows = _rows(pl.attestation_audit_path(PROVIDER))
    assert len(rows) == 1
    row = rows[0]
    assert row["ts"] == NOW.isoformat()
    assert row["provider"] == PROVIDER and row["outcome"] == "attestation-written"
    assert row["policy_id"] == policy["policy_id"] and row["label"] == "operator"
    assert row["estimated_usd"] == 0.0
    assert set(row) <= {"ts", "provider", "outcome", "policy_id", "label", "estimated_usd", "basis"}


def test_the_audit_row_slugs_prose_while_the_record_keeps_the_name(state) -> None:
    """The audit schema stores identifiers only, so prose is compressed; the record keeps the name."""
    _write(attested_by="the operator on duty")
    assert _rows(pl.attestation_audit_path(PROVIDER))[0]["label"] == "the-operator-on-duty"
    assert _record()["attested_by"] == "the operator on duty"


def test_a_failed_write_leaves_no_partial_record_and_no_audit_row(state, monkeypatch) -> None:
    def boom(fd):
        raise OSError("no space left on device")

    monkeypatch.setattr(pl.os, "fsync", boom)
    with pytest.raises(OSError):
        _write()
    assert not pl.attestation_path(PROVIDER).exists()
    assert list(pl.attestation_path(PROVIDER).parent.iterdir()) == []
    assert not pl.attestation_audit_path(PROVIDER).exists()


def test_a_failed_rewrite_keeps_the_previous_record_intact(state, monkeypatch) -> None:
    _write()
    before = pl.attestation_path(PROVIDER).read_bytes()

    def boom(fd):
        raise OSError("disk went away")

    monkeypatch.setattr(pl.os, "fsync", boom)
    with pytest.raises(OSError):
        _write(now=NOW + timedelta(days=1))
    assert pl.attestation_path(PROVIDER).read_bytes() == before
    assert len(_rows(pl.attestation_audit_path(PROVIDER))) == 1


def test_a_naive_now_is_read_as_utc(state) -> None:
    path = _write(now=datetime(2026, 11, 17, 12, 0))
    assert json.loads(path.read_text())["attested_at"] == "2026-11-17T12:00:00+00:00"
    assert _rows(pl.attestation_audit_path(PROVIDER))[0]["ts"] == "2026-11-17T12:00:00+00:00"


# --- revocation ---------------------------------------------------------------------------------


def test_revoke_removes_the_record_and_leaves_the_status_missing(state, policy) -> None:
    _write()
    later = NOW + timedelta(hours=1)
    assert pl.revoke_attestation(PROVIDER, "operator", "billing page changed", later) is True
    assert not pl.attestation_path(PROVIDER).exists()
    status = pl.attestation_status(policy, None, later)
    assert status["ok"] is False and any("missing" in reason for reason in status["reasons"])
    rows = _rows(pl.attestation_audit_path(PROVIDER))
    assert [row["outcome"] for row in rows] == ["attestation-written", "attestation-revoked"]
    assert rows[1]["ts"] == later.isoformat() and rows[1]["label"] == "operator"
    assert rows[1]["basis"] == "billing-page-changed"


def test_revoking_a_missing_record_is_a_clean_audited_no_op(state) -> None:
    assert pl.revoke_attestation(PROVIDER, "operator", "no record", NOW) is False
    assert not pl.attestation_path(PROVIDER).exists()
    rows = _rows(pl.attestation_audit_path(PROVIDER))
    assert len(rows) == 1 and rows[0]["outcome"] == "attestation-revoke-missing"
    assert rows[0]["basis"] == "no-record" and rows[0]["provider"] == PROVIDER


@pytest.mark.parametrize("who", ["", "   ", None])
def test_revoke_requires_a_revoker(state, who) -> None:
    _write()
    with pytest.raises(ValueError, match="revoked_by"):
        pl.revoke_attestation(PROVIDER, who, "x", NOW)
    assert pl.attestation_path(PROVIDER).is_file()


@pytest.mark.parametrize("provider", ["../escape", "a/b", "", "-leading", "x" * 65])
def test_a_provider_that_is_not_a_short_identifier_is_refused(state, provider: str) -> None:
    with pytest.raises(ValueError, match="short identifier"):
        pl.revoke_attestation(provider, "operator", "x", NOW)
