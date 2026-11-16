"""Provider policies: confirmed from official references, verified live, attested by the operator.

Runs offline: the live fetch is injected. No key, no network.
"""
from __future__ import annotations

import copy
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import provider_limits as pl  # noqa: E402

POLICY_PATH = REPO_ROOT / "config" / "provider-policies" / "wandb-inference.json"
NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def policy() -> dict:
    return pl.load_policy(POLICY_PATH)


def _attest(**over) -> dict:
    base = {
        "provider": "wandb-inference", "attested_at": (NOW - timedelta(days=1)).isoformat(),
        "attested_by": "operator", "plan_is_free": True, "payg_inactive": True, "allowance_remaining": True,
    }
    base.update(over)
    return base


# --- loading and validation --------------------------------------------------------------------


def test_the_shipped_policy_loads_and_names_only_variable_names(policy) -> None:
    assert policy["provider"] == "wandb-inference"
    assert policy["applicable_endpoint"]["base_url"] == "https://api.inference.wandb.ai/v1"
    names = policy["key_env_vars"]
    assert names["api_key"] == "DEEPSEEK_V4_FLASH_WANDB"
    text = POLICY_PATH.read_text()
    assert "sk-" not in text and "Bearer" not in text


def test_the_policy_states_the_budget_and_the_provider_cap(policy) -> None:
    b = policy["budget"]
    assert b["period"] == "monthly" and b["operator_estimate_ceiling_usd"] == 90
    assert b["provider_default_cap_usd_after_payg"] == 100
    assert b["operator_estimate_ceiling_usd"] < b["provider_default_cap_usd_after_payg"]


def test_the_policy_covers_both_causes_of_a_402(policy) -> None:
    ids = {f["id"] for ref in policy["official_references"] for f in ref["facts"]}
    assert {"402_allowance_exhausted_payg_inactive", "402_spending_cap_reached"} <= ids
    assert policy["stop_on_http"] == [402, 429]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.pop("budget"),
        lambda p: p["applicable_endpoint"].update(base_url="http://api.inference.wandb.ai/v1"),
        lambda p: p["rates_usd_per_million_tokens"].update(input=float("nan")),
        lambda p: p["rates_usd_per_million_tokens"].update(output=-1),
        lambda p: p["budget"].update(operator_estimate_ceiling_usd=0),
        lambda p: p["budget"].update(operator_estimate_ceiling_usd=150),   # above the provider cap
        lambda p: p.update(official_references=[]),
        lambda p: p["official_references"][0].update(url="file:///etc/passwd"),
        lambda p: p["official_references"][0]["facts"][0].update(expect="("),   # bad regex
        lambda p: p["key_env_vars"].update(api_key="sk-live-abcdef0123456789abcdef"),  # a value, not a name
        lambda p: p["operator_attestation"].update(max_age_days=0),
        lambda p: p.update(stop_on_http=[]),
    ],
)
def test_a_bad_policy_fails_closed(policy, tmp_path: Path, mutate) -> None:
    bad = copy.deepcopy(policy)
    mutate(bad)
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(pl.ProviderPolicyError):
        pl.load_policy(path)


def test_an_unknown_provider_is_refused() -> None:
    with pytest.raises(pl.ProviderPolicyError):
        pl.load_policy("not-a-provider")


def test_a_policy_can_be_loaded_by_id() -> None:
    assert pl.load_policy("wandb-inference")["provider"] == "wandb-inference"


# --- estimates ---------------------------------------------------------------------------------


def test_the_estimate_uses_the_policy_rates_and_four_chars_per_token(policy) -> None:
    r = policy["rates_usd_per_million_tokens"]
    assert pl.estimate_usd(policy, 4_000_000, 4_000_000) == pytest.approx(r["input"] + r["output"])


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), True, None, "9"])
def test_the_estimate_refuses_nonsense_sizes(policy, bad) -> None:
    with pytest.raises(ValueError):
        pl.estimate_usd(policy, bad, 10)
    with pytest.raises(ValueError):
        pl.estimate_usd(policy, 10, bad)


def test_the_projection_assumes_the_reasoning_stream_is_billed(policy) -> None:
    assert pl.projected_usd(policy, 10_000) > pl.estimate_usd(policy, 10_000, 0)
    assert policy["projection"]["assumed_output_chars"] >= 100_000


# --- operator attestation ----------------------------------------------------------------------


def test_a_fresh_complete_attestation_is_accepted(policy) -> None:
    assert pl.attestation_status(policy, _attest(), NOW) == {"ok": True, "reasons": []}


@pytest.mark.parametrize(
    ("attestation", "needle"),
    [
        (None, "missing"),
        ({}, "provider"),
        (_attest(payg_inactive=False), "payg_inactive"),
        (_attest(allowance_remaining=False), "allowance_remaining"),
        (_attest(plan_is_free=False), "plan_is_free"),
        (_attest(payg_inactive="yes"), "payg_inactive"),       # only a literal true counts
        (_attest(payg_inactive=1), "payg_inactive"),
        (_attest(attested_at=(NOW - timedelta(days=8)).isoformat()), "stale"),
        (_attest(attested_at=(NOW + timedelta(days=1)).isoformat()), "future"),
        (_attest(attested_at="not a date"), "attested_at"),
        (_attest(provider="someone-else"), "provider"),
        (_attest(attested_by=""), "attested_by"),
    ],
)
def test_an_incomplete_stale_or_foreign_attestation_is_refused(policy, attestation, needle: str) -> None:
    status = pl.attestation_status(policy, attestation, NOW)
    assert status["ok"] is False
    assert any(needle in reason for reason in status["reasons"]), status


# --- classifying provider failures -------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["402", "HTTP 402", "You exceeded your current quota, please check your plan and billing details",
     "payment required", "spending cap reached"],
)
def test_402_style_text_is_payment_required(policy, text: str) -> None:
    assert pl.classify_failure(policy, text) == "provider-payment-required"


@pytest.mark.parametrize("text", ["429 Concurrency limit reached for requests", "Too Many Requests", "rate limit"])
def test_429_style_text_is_rate_limited(policy, text: str) -> None:
    assert pl.classify_failure(policy, text) == "provider-rate-limited"


@pytest.mark.parametrize("text", ["", "error: Invalid request", "model not found", None])
def test_ordinary_failures_are_not_limit_stops(policy, text) -> None:
    assert pl.classify_failure(policy, text) is None


# --- live verification against the official references ---------------------------------------


def _pages(policy: dict, overrides: dict | None = None) -> dict:
    """Build fake official pages that contain every fact's expected text."""
    pages = {}
    for ref in policy["official_references"]:
        pages[ref["url"]] = "<html><body>" + " ".join(f["sample"] for f in ref["facts"]) + "</body></html>"
    pages.update(overrides or {})
    return pages


def test_every_fact_has_a_sample_that_its_own_pattern_matches(policy) -> None:
    import re

    for ref in policy["official_references"]:
        for fact in ref["facts"]:
            assert re.search(fact["expect"], fact["sample"], re.I), fact["id"]


def test_verify_live_confirms_when_the_pages_say_what_the_policy_says(policy) -> None:
    pages = _pages(policy)
    out = pl.verify_live(policy, fetch=lambda url, timeout: pages[url])
    assert out["ok"] is True and out["unreachable"] == 0 and out["drift"] == 0
    assert {r["status"] for r in out["results"]} == {"confirmed"}


def test_verify_live_reports_drift_when_a_page_no_longer_says_it(policy) -> None:
    ref = policy["official_references"][0]
    pages = _pages(policy, {ref["url"]: "<html>This page was rewritten.</html>"})
    out = pl.verify_live(policy, fetch=lambda url, timeout: pages[url])
    assert out["ok"] is False and out["drift"] == len(ref["facts"])


def test_verify_live_reports_unreachable_and_never_raises(policy) -> None:
    def boom(url, timeout):
        raise OSError("network down")

    out = pl.verify_live(policy, fetch=boom)
    assert out["ok"] is False and out["unreachable"] == sum(len(r["facts"]) for r in policy["official_references"])


def test_verify_live_ignores_markup_and_curly_quotes(policy) -> None:
    pages = {}
    for ref in policy["official_references"]:
        body = " ".join(f["sample"].replace("'", "’") for f in ref["facts"])
        pages[ref["url"]] = "<p>" + "</p><p>".join(body.split(". ")) + "</p>"
    out = pl.verify_live(policy, fetch=lambda url, timeout: pages[url])
    assert out["ok"] is True, out


def test_the_default_fetch_sends_no_credentials_and_only_https(monkeypatch, policy) -> None:
    seen = {}

    class Resp:
        def read(self, n=-1):
            return b"hello"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=0):
        seen["headers"] = {k.lower(): v for k, v in req.header_items()}
        seen["url"] = req.full_url
        return Resp()

    monkeypatch.setattr(pl.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("DEEPSEEK_V4_FLASH_WANDB", "s3cret")
    assert pl._default_fetch("https://docs.example.com/x", 5) == "hello"
    assert "authorization" not in seen["headers"] and "s3cret" not in json.dumps(seen)
    with pytest.raises(ValueError):
        pl._default_fetch("http://docs.example.com/x", 5)


# --- shared state helpers and the operator-only attestation command --------------------------------


def test_state_paths_live_under_the_operator_state_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(tmp_path))
    assert pl.state_dir() == tmp_path
    assert pl.attestation_path("wandb-inference") == tmp_path / "provider-attestations" / "wandb-inference.json"
    assert pl.spend_dir() == tmp_path / "spend"


def test_audit_rows_store_sizes_only(policy, tmp_path: Path) -> None:
    log = tmp_path / "audit.jsonl"
    pl.append_audit(log, {"ts": NOW.isoformat(), "seat": "inner", "input_chars": 10, "output_chars": 20,
                          "estimated_usd": 0.001, "outcome": "ok"})
    row = json.loads(log.read_text().splitlines()[0])
    assert row["estimated_usd"] == 0.001
    for forbidden in ("prompt", "answer", "api_key", "text"):
        with pytest.raises(ValueError):
            pl.append_audit(log, {"ts": NOW.isoformat(), "estimated_usd": 0.0, forbidden: "x"})


def _interactive(monkeypatch, answer: str, tty: bool = True) -> None:
    monkeypatch.setattr(pl, "_is_interactive", lambda: tty)
    monkeypatch.setattr("builtins.input", lambda prompt="": answer)


_ATTEST_ARGS = ["attest", "wandb-inference", "--plan-free", "--payg-inactive", "--allowance-remaining", "--by", "operator"]


def test_attest_writes_a_complete_record_from_an_interactive_terminal(policy, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(tmp_path))
    _interactive(monkeypatch, pl.ATTEST_PHRASE)
    assert pl.main(list(_ATTEST_ARGS)) == 0
    path = pl.attestation_path("wandb-inference")
    record = json.loads(path.read_text())
    assert pl.attestation_status(policy, record, datetime.now(timezone.utc))["ok"] is True
    assert record["attested_by"] == "operator" and oct(path.stat().st_mode & 0o777) == "0o600"


def test_attest_refuses_without_a_terminal_and_never_reads_input(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(tmp_path))
    _interactive(monkeypatch, pl.ATTEST_PHRASE, tty=False)
    assert pl.main(list(_ATTEST_ARGS)) != 0
    assert not pl.attestation_path("wandb-inference").exists()
    err = capsys.readouterr().err
    assert "terminal" in err and pl.ATTEST_PHRASE not in err


def test_there_is_no_command_line_way_to_pass_the_confirmation(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(tmp_path))
    _interactive(monkeypatch, "ignored")
    assert pl.main(_ATTEST_ARGS + ["--confirm", pl.ATTEST_PHRASE]) != 0
    assert not pl.attestation_path("wandb-inference").exists()
    assert pl.ATTEST_PHRASE not in capsys.readouterr().err


@pytest.mark.parametrize("missing", ["--plan-free", "--payg-inactive", "--allowance-remaining", "--by"])
def test_attest_refuses_when_a_flag_is_missing(tmp_path: Path, monkeypatch, missing: str) -> None:
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(tmp_path))
    _interactive(monkeypatch, pl.ATTEST_PHRASE)
    argv = list(_ATTEST_ARGS)
    i = argv.index(missing)
    del argv[i:i + (2 if missing == "--by" else 1)]
    assert pl.main(argv) != 0 and not pl.attestation_path("wandb-inference").exists()


@pytest.mark.parametrize("answer", ["yes", "", "i read the provider billing page myself", pl.ATTEST_PHRASE + " "])
def test_attest_refuses_a_wrong_typed_phrase(tmp_path: Path, monkeypatch, answer: str) -> None:
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(tmp_path))
    _interactive(monkeypatch, answer)
    assert pl.main(list(_ATTEST_ARGS)) != 0 and not pl.attestation_path("wandb-inference").exists()


def test_the_usage_text_does_not_print_the_phrase_and_is_honest_about_the_limit(capsys) -> None:
    assert pl.main(["bogus"]) == 2
    err = capsys.readouterr().err
    assert pl.ATTEST_PHRASE not in err and "--confirm" not in err


def test_the_policy_says_attestation_is_a_speed_bump_not_a_boundary(policy) -> None:
    note = policy["operator_attestation"]["note"].lower()
    assert "terminal" in note and "same os user" in note
