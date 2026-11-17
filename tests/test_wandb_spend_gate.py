"""The W&B harness path is admitted by the shared SpendGate before it is dispatched.

Review finding 1: _call_wandb sent chat.completions.create() with no attestation check and no budget
reservation (an empty operator-state directory still dispatched one completion). Disabled SDK retries and
ProviderLimitStop address retries, not authorization or spend admission. Offline; the client is mocked.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
import openai
import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import provider_limits as pl  # noqa: E402
from orchestrator.cost_guard import CostGuard  # noqa: E402


@pytest.fixture()
def llm(monkeypatch, tmp_path):
    """The harness module with Weave tracing off, a key set and an EMPTY operator-state directory."""
    spec = importlib.util.spec_from_file_location("agent_llm_spend", REPO_ROOT / ".agent/harness/llm.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["agent_llm_spend"] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_maybe_init_wandb_weave_tracing", lambda: None)
    monkeypatch.setenv("DEEPSEEK_V4_FLASH_WANDB", "test-key")
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(tmp_path / "operator"))
    return module


def _attest(age_days: float = 0.0) -> None:
    """Write an operator attestation ``age_days`` old (fresh by default) into the operator state."""
    path = pl.attestation_path("wandb-inference")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "provider": "wandb-inference", "attested_by": "operator",
        "attested_at": (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat(),
        "plan_is_free": True, "payg_inactive": True, "allowance_remaining": True,
    }), encoding="utf-8")


def _guard() -> CostGuard:
    """A view of the W&B budget the harness uses."""
    return CostGuard(state_dir=str(pl.spend_dir()), budget_file="wandb-inference-budget.json", period="monthly")


def _client(calls: list, create):
    """Test helper or double: client."""
    class FakeOpenAI:
        """Test double."""
        def __init__(self, **kwargs):
            """Test helper or double: init  ."""
            calls.append(("init", kwargs))
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

    return FakeOpenAI


def _ok(**kwargs):
    """Test helper or double: ok."""
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="hello"))], usage=None)


def _status_error(code: int):
    """Test helper or double: status error."""
    request = httpx.Request("POST", "https://api.inference.wandb.ai/v1/chat/completions")
    return openai.APIStatusError(f"error {code}", response=httpx.Response(code, request=request, json={}), body=None)


def _call(llm):
    """Test helper or double: call."""
    return llm._call_wandb("sys", "user prompt", temperature=0, max_tokens=5, model="m")


def _install(monkeypatch, create):
    """Test helper or double: install."""
    created: list = []
    sent: list = []

    def counting_create(**kwargs):
        """Test helper or double: counting create."""
        sent.append(kwargs)
        return create(**kwargs)

    monkeypatch.setattr(openai, "OpenAI", _client(created, counting_create))
    return created, sent


def test_a_missing_attestation_is_refused_before_dispatch(llm, monkeypatch) -> None:
    """A missing attestation is refused before dispatch."""
    created, sent = _install(monkeypatch, _ok)
    with pytest.raises(llm.ProviderSpendRefused) as info:
        _call(llm)
    assert info.value.reason == "attestation-required" and sent == []
    assert _guard().in_flight() == 0.0


def test_a_stale_attestation_is_refused_before_dispatch(llm, monkeypatch) -> None:
    """A stale attestation is refused before dispatch."""
    _attest(age_days=30)
    created, sent = _install(monkeypatch, _ok)
    with pytest.raises(llm.ProviderSpendRefused) as info:
        _call(llm)
    assert info.value.reason == "attestation-required" and sent == []


def test_an_exhausted_budget_is_refused_before_dispatch(llm, monkeypatch) -> None:
    """An exhausted budget is refused before dispatch."""
    _attest()
    _guard().set_budget(90.0)
    _guard().record_spend(89.99999)
    created, sent = _install(monkeypatch, _ok)
    with pytest.raises(llm.ProviderSpendRefused) as info:
        _call(llm)
    assert info.value.reason == "budget-exhausted" and sent == []
    assert _guard().in_flight() == 0.0


def test_the_call_model_wandb_branch_is_gated_too(llm, monkeypatch) -> None:
    """The call model wandb branch is gated too."""
    monkeypatch.setenv("AGENT_PROVIDER", "wandb")
    created, sent = _install(monkeypatch, _ok)
    with pytest.raises(llm.ProviderSpendRefused):
        llm.call_model("sys", "user")
    assert sent == []


def test_an_unusable_guard_fails_closed(llm, monkeypatch) -> None:
    """An unusable guard fails closed."""
    _attest()
    created, sent = _install(monkeypatch, _ok)
    monkeypatch.setattr(llm, "_WANDB_PROVIDER", "no-such-provider")
    with pytest.raises(llm.ProviderSpendRefused) as info:
        _call(llm)
    assert info.value.reason == "spend-guard-unavailable" and sent == []


def test_success_settles_the_estimate_and_releases_the_hold(llm, monkeypatch) -> None:
    """Success settles the estimate and releases the hold."""
    _attest()
    created, sent = _install(monkeypatch, _ok)
    assert _call(llm) == "hello" and len(sent) == 1
    guard = _guard()
    assert guard.in_flight() == 0.0 and guard.snapshot()["daily_spend"] > 0.0
    row = json.loads((pl.spend_dir() / "wandb-inference-spend-audit.jsonl").read_text().splitlines()[-1])
    assert row["outcome"] == "ok" and row["output_chars"] == len("hello") and "prompt" not in row


def test_the_billed_completion_tokens_are_used_when_they_exceed_the_visible_text(llm, monkeypatch) -> None:
    """The billed completion tokens are used when they exceed the visible text."""
    _attest()

    def reasoning_heavy(**kwargs):
        """Test helper or double: reasoning heavy."""
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))],
                               usage=SimpleNamespace(completion_tokens=10_000))

    _install(monkeypatch, reasoning_heavy)
    _call(llm)
    row = json.loads((pl.spend_dir() / "wandb-inference-spend-audit.jsonl").read_text().splitlines()[-1])
    assert row["output_chars"] == 40_000  # 10k tokens at the policy's 4 chars per token, not the 2 visible chars


def test_the_hold_covers_the_client_timeout(llm, monkeypatch) -> None:
    """The hold covers the client timeout."""
    _attest()
    created, sent = _install(monkeypatch, _ok)
    seen: list = []
    real = llm._wandb_spend_gate

    def spy():
        """Test helper or double: spy."""
        gate = real()
        original = gate.preflight

        def preflight(chars, hold):
            """Test helper or double: preflight."""
            seen.append(hold)
            return original(chars, hold)

        gate.preflight = preflight
        return gate

    monkeypatch.setattr(llm, "_wandb_spend_gate", spy)
    _call(llm)
    timeout = next(k["timeout"] for tag, k in created if tag == "init")
    assert seen and seen[0] > timeout


@pytest.mark.parametrize("failure", [ConnectionError("reset"), TimeoutError("slow"), KeyboardInterrupt()])
def test_a_failure_after_the_request_may_have_been_sent_settles_the_full_reservation(llm, monkeypatch, failure) -> None:
    """A failure after the request may have been sent settles the full reservation."""
    _attest()

    def create(**kwargs):
        """Test helper or double: create."""
        raise failure

    created, sent = _install(monkeypatch, create)
    with pytest.raises(type(failure)):
        _call(llm)
    guard = _guard()
    projected = pl.projected_usd(pl.load_policy("wandb-inference"), len("sys") + len("user prompt"))
    assert guard.in_flight() == 0.0 and guard.snapshot()["daily_spend"] == pytest.approx(projected, abs=1e-6)
    row = json.loads((pl.spend_dir() / "wandb-inference-spend-audit.jsonl").read_text().splitlines()[-1])
    assert "output_chars" not in row and row["basis"] == "output-unknown"


@pytest.mark.parametrize("code", [400, 402, 429])
def test_a_refusal_below_500_releases_the_reservation_and_records_nothing(llm, monkeypatch, code) -> None:
    """A received HTTP status below 500 means the provider refused before generating: release, no spend."""
    _attest()

    def create(**kwargs):
        """Test double: the provider refuses the request."""
        raise _status_error(code)

    created, sent = _install(monkeypatch, create)
    expected = llm.ProviderLimitStop if code in (402, 429) else openai.APIStatusError
    with pytest.raises(expected):
        _call(llm)
    assert len(sent) == 1
    guard = _guard()
    assert guard.in_flight() == 0.0 and guard.snapshot()["daily_spend"] == 0.0
    assert not (pl.spend_dir() / "wandb-inference-spend-audit.jsonl").exists()


@pytest.mark.parametrize("code", [402, 429])
def test_a_limit_response_still_raises_the_typed_stop_with_its_status(llm, monkeypatch, code) -> None:
    """ProviderLimitStop for 402 and 429 is unchanged."""
    _attest()

    def create(**kwargs):
        """Test double: the provider answers with a limit status."""
        raise _status_error(code)

    _install(monkeypatch, create)
    with pytest.raises(llm.ProviderLimitStop) as info:
        _call(llm)
    assert info.value.status == code


@pytest.mark.parametrize("code", [500, 503])
def test_a_server_error_may_have_been_processed_so_it_charges_the_full_reservation(llm, monkeypatch, code) -> None:
    """Status 500 and above: the request may have been processed, so settle_unknown."""
    _attest()

    def create(**kwargs):
        """Test double: the provider fails server-side."""
        raise _status_error(code)

    _install(monkeypatch, create)
    with pytest.raises(openai.APIStatusError):
        _call(llm)
    projected = pl.projected_usd(pl.load_policy("wandb-inference"), len("sys") + len("user prompt"))
    guard = _guard()
    assert guard.in_flight() == 0.0 and guard.snapshot()["daily_spend"] == pytest.approx(projected, abs=1e-6)
    row = json.loads((pl.spend_dir() / "wandb-inference-spend-audit.jsonl").read_text().splitlines()[-1])
    assert row["basis"] == "output-unknown" and row["outcome"] == f"http-{code}"


def test_a_failure_before_anything_is_sent_releases_the_reservation(llm, monkeypatch) -> None:
    """A failure before anything is sent releases the reservation."""
    _attest()

    def broken_client(**kwargs):
        """Test helper or double: broken client."""
        raise RuntimeError("cannot build client")

    monkeypatch.setattr(openai, "OpenAI", broken_client)
    with pytest.raises(RuntimeError):
        _call(llm)
    guard = _guard()
    assert guard.in_flight() == 0.0 and guard.snapshot()["daily_spend"] == 0.0
    assert not (pl.spend_dir() / "wandb-inference-spend-audit.jsonl").exists()


def test_a_missing_sdk_releases_the_reservation(llm, monkeypatch) -> None:
    """A missing sdk releases the reservation."""
    _attest()
    monkeypatch.setitem(sys.modules, "openai", None)  # import openai -> ImportError
    with pytest.raises(ImportError):
        _call(llm)
    assert _guard().in_flight() == 0.0 and _guard().snapshot()["daily_spend"] == 0.0


def test_a_malformed_response_after_a_completed_request_is_still_charged(llm, monkeypatch) -> None:
    """A malformed response after a completed request is still charged."""
    _attest()
    _install(monkeypatch, lambda **kw: SimpleNamespace(choices=[], usage=None))
    with pytest.raises(IndexError):
        _call(llm)
    assert _guard().in_flight() == 0.0 and _guard().snapshot()["daily_spend"] > 0.0


def test_sdk_retries_stay_disabled(llm, monkeypatch) -> None:
    """Sdk retries stay disabled."""
    _attest()
    created, sent = _install(monkeypatch, _ok)
    _call(llm)
    assert next(k for tag, k in created if tag == "init")["max_retries"] == 0
