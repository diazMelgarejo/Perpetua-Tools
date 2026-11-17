"""SpendGate: the one preflight/settle/release path in front of every paid provider request.

Composes provider_limits (attestation, projection, audit) with CostGuard (shared atomic budget). Offline;
the clock and the operator-state directory are injected.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import provider_limits as pl  # noqa: E402
from orchestrator.cost_guard import CostGuard  # noqa: E402
from orchestrator.spend_gate import SpendGate  # noqa: E402

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def state(tmp_path: Path, monkeypatch) -> Path:
    """An empty operator state directory (no attestation) that the gate and provider_limits both use."""
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(tmp_path / "operator"))
    return tmp_path / "operator"


def _attest(age_days: float = 0.0, **overrides) -> None:
    """Write an operator attestation ``age_days`` old into the (patched) operator state directory."""
    record = {
        "provider": "wandb-inference", "attested_by": "operator",
        "attested_at": (NOW - timedelta(days=age_days)).isoformat(),
        "plan_is_free": True, "payg_inactive": True, "allowance_remaining": True, **overrides,
    }
    path = pl.attestation_path("wandb-inference")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(record), encoding="utf-8")


def _gate(**kw) -> SpendGate:
    """Test helper or double: gate."""
    return SpendGate(now=lambda: NOW, **kw)


def test_a_missing_attestation_is_refused_before_any_reservation(state: Path) -> None:
    """A missing attestation is refused before any reservation."""
    gate = _gate()
    out = gate.preflight(1000, 900)
    assert out["ok"] is False and out["reason"] == "attestation-required" and out["stop"] is True
    assert "attestation missing" in out["reasons"]
    assert CostGuard(state_dir=str(pl.spend_dir()), budget_file="wandb-inference-budget.json", period="monthly").in_flight() == 0.0


def test_a_stale_attestation_is_refused(state: Path) -> None:
    """A stale attestation is refused."""
    _attest(age_days=30)
    out = _gate().preflight(1000, 900)
    assert out["ok"] is False and out["reason"] == "attestation-required"
    assert any("stale" in r for r in out["reasons"])


def test_an_attestation_with_a_false_field_is_refused(state: Path) -> None:
    """An attestation with a false field is refused."""
    _attest(payg_inactive=False)
    assert _gate().preflight(1000, 900)["reason"] == "attestation-required"


def test_a_fresh_attestation_reserves_the_projected_cost(state: Path) -> None:
    """A fresh attestation reserves the projected cost."""
    _attest()
    gate = _gate()
    out = gate.preflight(4000, 900)
    assert out["ok"] is True and out["projected_usd"] == pytest.approx(pl.projected_usd(gate.policy, 4000))
    assert gate.guard.in_flight() == pytest.approx(out["projected_usd"])


def test_an_exhausted_budget_is_refused_with_the_budget_reason(state: Path) -> None:
    """An exhausted budget is refused with the budget reason."""
    _attest()
    gate = _gate()
    gate.guard.record_spend(gate.policy["budget"]["operator_estimate_ceiling_usd"] - 0.01)
    out = gate.preflight(4000, 900)
    assert out["ok"] is False and out["reason"] == "budget-exhausted" and out["stop"] is True
    assert gate.guard.in_flight() == 0.0


def test_two_gates_on_one_state_share_the_ceiling(state: Path) -> None:
    """Two gates on one state share the ceiling."""
    _attest()
    first, second = _gate(), _gate()
    first.guard.record_spend(first.policy["budget"]["operator_estimate_ceiling_usd"] - 0.07)
    assert first.preflight(4000, 900)["ok"] is True
    assert second.preflight(4000, 900)["reason"] == "budget-exhausted"


def test_the_declared_hold_outlives_the_default_ttl(state: Path) -> None:
    """The declared hold outlives the default ttl."""
    _attest()
    gate = _gate()
    gate.guard.record_spend(gate.policy["budget"]["operator_estimate_ceiling_usd"] - 0.07)
    start = datetime.now(timezone.utc).timestamp()
    with patch("orchestrator.cost_guard.time.time", return_value=start):
        assert gate.preflight(4000, 900)["ok"] is True
    with patch("orchestrator.cost_guard.time.time", return_value=start + 301):
        assert _gate().preflight(4000, 900)["reason"] == "budget-exhausted"  # still held at 301 s


def test_a_bad_hold_or_size_is_refused(state: Path) -> None:
    """A bad hold or size is refused."""
    _attest()
    for chars, hold in ((-1, 900), (float("nan"), 900), (10, 0), (10, -5), (10, float("inf"))):
        with pytest.raises(ValueError):
            _gate().preflight(chars, hold)


def test_settle_commits_the_estimate_and_writes_a_size_only_audit_row(state: Path) -> None:
    """Settle commits the estimate and writes a size only audit row."""
    _attest()
    gate = _gate()
    pre = gate.preflight(4000, 900)
    usd = gate.settle(pre["reservation"], 4000, 2000, "ok", "harness", "chat")
    assert usd == pytest.approx(pl.estimate_usd(gate.policy, 4000, 2000))
    assert gate.snapshot()["daily_spend"] == pytest.approx(usd) and gate.guard.in_flight() == 0.0
    row = json.loads(gate.audit_path.read_text().splitlines()[-1])
    assert row["input_chars"] == 4000 and row["output_chars"] == 2000 and row["estimated"] is True
    assert row["outcome"] == "ok" and row["seat"] == "harness" and row["provider"] == "wandb-inference"
    assert not {"prompt", "answer", "text", "body", "stdout"} & set(row)


def test_settle_unknown_commits_the_full_reserved_amount_and_records_output_as_unknown(state: Path) -> None:
    """Settle unknown commits the full reserved amount and records output as unknown."""
    _attest()
    gate = _gate()
    pre = gate.preflight(4000, 900)
    usd = gate.settle_unknown(pre["reservation"], 4000, "request-failed", "harness", "chat")
    assert usd == pytest.approx(pre["projected_usd"])
    assert gate.snapshot()["daily_spend"] == pytest.approx(pre["projected_usd"])
    row = json.loads(gate.audit_path.read_text().splitlines()[-1])
    assert "output_chars" not in row and row["basis"] == "output-unknown"
    assert row["estimated_usd"] == pytest.approx(pre["projected_usd"]) and row["input_chars"] == 4000


def test_a_settle_after_the_hold_lapsed_still_records_the_spend_and_marks_the_row_late(state: Path) -> None:
    """A settle after the hold lapsed still records the spend and marks the row late."""
    _attest()
    gate = _gate()
    start = datetime.now(timezone.utc).timestamp()
    with patch("orchestrator.cost_guard.time.time", return_value=start):
        pre = gate.preflight(4000, 100)
    with patch("orchestrator.cost_guard.time.time", return_value=start + 500):
        gate.guard.reserve_sync(0.0)  # sweeps the lapsed hold
        usd = gate.settle(pre["reservation"], 4000, 100, "ok", "harness", "chat")
        assert gate.snapshot()["daily_spend"] == pytest.approx(usd, abs=1e-6)
    assert json.loads(gate.audit_path.read_text().splitlines()[-1])["basis"] == "late-commit"


def test_release_frees_the_hold_and_is_idempotent(state: Path) -> None:
    """Release frees the hold and is idempotent."""
    _attest()
    gate = _gate()
    pre = gate.preflight(4000, 900)
    gate.release(pre["reservation"])
    gate.release(pre["reservation"])  # no error, nothing charged
    gate.release("never-reserved")
    assert gate.guard.in_flight() == 0.0 and gate.snapshot()["daily_spend"] == 0.0
    assert not gate.audit_path.exists()


def test_classify_uses_the_policy_stop_codes(state: Path) -> None:
    """Classify uses the policy stop codes."""
    gate = _gate()
    assert gate.classify("HTTP 402 payment required") == "provider-payment-required"
    assert gate.classify("429 too many requests") == "provider-rate-limited"
    assert gate.classify("ok") is None


def test_the_ceiling_comes_from_the_policy_not_from_prior_state(state: Path) -> None:
    """The ceiling comes from the policy not from prior state."""
    gate = _gate()
    assert gate.snapshot()["daily_budget"] == gate.policy["budget"]["operator_estimate_ceiling_usd"]


def test_an_explicit_state_dir_holds_the_budget_and_audit(tmp_path: Path, state: Path) -> None:
    """An explicit state dir holds the budget and audit."""
    _attest()
    gate = _gate(state_dir=tmp_path / "spend-elsewhere")
    pre = gate.preflight(100, 900)
    gate.settle(pre["reservation"], 100, 10, "ok", "harness", "chat")
    assert (tmp_path / "spend-elsewhere" / "wandb-inference-spend-audit.jsonl").is_file()
    assert (tmp_path / "spend-elsewhere" / "wandb-inference-budget.sqlite3").is_file()


def test_an_unknown_provider_policy_fails_closed(state: Path) -> None:
    """An unknown provider policy fails closed."""
    with pytest.raises(pl.ProviderPolicyError):
        SpendGate(provider="no-such-provider")


def test_the_module_loads_by_file_path_without_the_package(state: Path) -> None:
    """orama loads this file by path from a checkout; its sibling imports must not need the package."""
    spec = importlib.util.spec_from_file_location("spend_gate_by_path", REPO_ROOT / "orchestrator" / "spend_gate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _attest()
    assert module.SpendGate(now=lambda: NOW).preflight(100, 900)["ok"] is True


def test_the_exceptions_a_consumer_must_catch_are_public_module_attributes() -> None:
    """Consumers catch these names from spend_gate instead of reaching into its private imports."""
    import orchestrator.cost_guard as cg
    import orchestrator.spend_gate as sg

    assert sg.ProviderPolicyError is pl.ProviderPolicyError
    assert sg.BudgetExceededError is cg.BudgetExceededError
    assert sg.UnknownReservationError is cg.UnknownReservationError
    assert {"ProviderPolicyError", "BudgetExceededError", "UnknownReservationError"} <= set(sg.__all__)
