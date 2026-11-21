"""_call_wandb must send one request: no SDK retries, and 402 or 429 stop the caller with a typed error.

These tests run with a fresh operator attestation and an isolated state directory, so the shared spend
gate admits the request (its refusals are covered in test_wandb_spend_gate.py).
"""
from __future__ import annotations

import importlib.util
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
import openai
import pytest

REPO_ROOT = Path(__file__).parent.parent


@pytest.fixture()
def llm(monkeypatch, tmp_path):
    """Load .agent/harness/llm.py fresh with a valid attestation and an isolated state directory."""
    spec = importlib.util.spec_from_file_location("agent_llm", REPO_ROOT / ".agent/harness/llm.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["agent_llm"] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_maybe_init_wandb_weave_tracing", lambda: None)
    monkeypatch.delenv("DEEPSEEK_V4_FLASH_WANDB_PROJECT", raising=False)
    monkeypatch.setattr(socket.socket, "connect", lambda *args, **kwargs: pytest.fail("network forbidden"))
    # Exercise the worker protocol offline with the SDK doubles installed by each test.
    worker_spec = importlib.util.spec_from_file_location("wandb_worker_test", REPO_ROOT / "src/perpetua_tools/wandb_worker.py")
    worker = importlib.util.module_from_spec(worker_spec)
    worker_spec.loader.exec_module(worker)
    monkeypatch.setattr(module, "_run_wandb_worker", lambda request, timeout: worker.complete(request))
    monkeypatch.setenv("DEEPSEEK_V4_FLASH_WANDB", "test-key")
    monkeypatch.setenv("OPENCLAW_STATE_DIR", str(tmp_path / "operator"))
    attestation = tmp_path / "operator" / "provider-attestations" / "wandb-inference.json"
    attestation.parent.mkdir(parents=True)
    attestation.write_text(json.dumps({
        "provider": "wandb-inference", "attested_by": "operator",
        "attested_at": datetime.now(timezone.utc).isoformat(),
        "plan_is_free": True, "payg_inactive": True, "allowance_remaining": True,
    }), encoding="utf-8")
    return module


def _client_factory(captured: dict, create):
    """Build a fake OpenAI client class that records its kwargs and uses the given create."""
    class FakeOpenAI:
        """Fake OpenAI client exposing chat.completions.create."""
        def __init__(self, **kwargs):
            """Record the constructor kwargs and attach the fake chat object."""
            captured.update(kwargs)
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

    return FakeOpenAI


def _ok(**kwargs):
    """Return a successful fake completion whose message content is hi."""
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))], usage=None)


def _status_error(code: int):
    """Build an openai.APIStatusError carrying an HTTP response with the given status code."""
    request = httpx.Request("POST", "https://api.inference.wandb.ai/v1/chat/completions")
    response = httpx.Response(code, request=request, json={"error": "x"})
    return openai.APIStatusError(f"error {code}", response=response, body=None)


def test_the_client_is_built_with_no_sdk_retries(llm, monkeypatch) -> None:
    """The OpenAI client is constructed with max_retries 0, the W&B base URL and the API key."""
    seen: dict = {}
    monkeypatch.setattr(openai, "OpenAI", _client_factory(seen, _ok))
    assert llm._call_wandb("s", "u", temperature=0, max_tokens=5, model="m") == "hi"
    assert seen["max_retries"] == 0
    assert seen["base_url"] == llm.WANDB_BASE_URL and seen["api_key"] == "test-key"


@pytest.mark.parametrize("code", [402, 429])
def test_a_limit_response_raises_a_typed_stop_and_is_not_retried(llm, monkeypatch, code: int) -> None:
    """A 402 or 429 raises ProviderLimitStop with that status after exactly one call."""
    calls = []

    def create(**kwargs):
        """Count the call and raise the status error."""
        calls.append(1)
        raise _status_error(code)

    monkeypatch.setattr(openai, "OpenAI", _client_factory({}, create))
    with pytest.raises(llm.ProviderLimitStop) as info:
        llm._call_wandb("s", "u", temperature=0, max_tokens=5, model="m")
    assert info.value.status == code and len(calls) == 1


def test_other_http_errors_still_propagate_unchanged(llm, monkeypatch) -> None:
    """A 400 response propagates as the original openai.APIStatusError."""
    def create(**kwargs):
        """Raise a 400 status error."""
        raise _status_error(400)

    monkeypatch.setattr(openai, "OpenAI", _client_factory({}, create))
    with pytest.raises(openai.APIStatusError):
        llm._call_wandb("s", "u", temperature=0, max_tokens=5, model="m")
