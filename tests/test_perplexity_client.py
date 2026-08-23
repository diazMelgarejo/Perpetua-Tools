from __future__ import annotations

import asyncio

import pytest

import orchestrator.perplexity_client as pc


def test_ensure_credentials_accepts_web_login_fallback(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    monkeypatch.delenv("PERPLEXITY_AUTH_MODE", raising=False)
    monkeypatch.setattr(pc.sys.stdin, "isatty", lambda: True)

    answers = iter(["", "y"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    status = pc.ensure_credentials(
        validate=True,
        interactive=True,
        allow_web_fallback=True,
    )

    assert status["configured"] is True
    assert status["ready_for_api"] is False
    assert status["auth_mode"] == "web-login"
    assert "PERPLEXITY_AUTH_MODE=web-login" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_client_refuses_programmatic_calls_in_web_login_mode(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PERPLEXITY_AUTH_MODE", "web-login")
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    pc.PerplexityClient.reset()

    client = pc.PerplexityClient(interactive=False)

    with pytest.raises(RuntimeError, match="web-login fallback"):
        asyncio.run(
            client.chat_async([{"role": "user", "content": "hello"}])
        )


def test_sync_and_async_clients_use_the_pinned_httpx_transport(monkeypatch, tmp_path):
    """The openai SDK's OWN default httpx client has follow_redirects=True
    (confirmed directly: OpenAI(api_key=...)._client.follow_redirects is
    True with no http_client override) -- not httpx.Client's own False
    default. Without passing a hardened http_client, PerplexityClient would
    silently auto-follow redirects from api.perplexity.ai with zero
    revalidation. Assert both the sync and async clients were built with
    build_pinned_httpx_client(), not the SDK's bare default."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PERPLEXITY_AUTH_MODE", raising=False)
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-test-key")
    pc.PerplexityClient.reset()

    client = pc.PerplexityClient(interactive=False)

    assert client._sync._client.follow_redirects is False
    sync_hooks = [h.__name__ for h in client._sync._client.event_hooks.get("request", [])]
    assert "_validate_request_host" in sync_hooks
    assert client._async._client.follow_redirects is False
    async_hooks = [h.__name__ for h in client._async._client.event_hooks.get("request", [])]
    assert "_validate_request_host_async" in async_hooks


def test_test_key_closes_the_httpx_client_after_use(monkeypatch):
    """_test_key() builds a fresh httpx client via build_pinned_httpx_client()
    on every call. The OpenAI SDK never closes a client the caller supplies
    through http_client -- without owning it via a context manager, every
    call (including every retry in _prompt_for_key's loop) leaks a
    connection pool. Assert the client's own is_closed flips True after
    _test_key returns."""
    import orchestrator.key_helper as key_helper_mod

    # Force `from orchestrator.key_helper import test_perplexity_key` to
    # raise ImportError (the branch _test_key falls through on), so the
    # openai/build_pinned_httpx_client path below actually runs.
    monkeypatch.delattr(key_helper_mod, "test_perplexity_key", raising=False)

    from utils.ssrf_pinned_adapter import build_pinned_httpx_client

    real_client = build_pinned_httpx_client()
    assert not real_client.is_closed

    class _FakeChoices:
        choices = [object()]

    class _FakeCompletions:
        def create(self, **kwargs):
            return _FakeChoices()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = _FakeChat()

    monkeypatch.setattr(
        "utils.ssrf_pinned_adapter.build_pinned_httpx_client",
        lambda **kwargs: real_client,
    )
    monkeypatch.setattr("openai.OpenAI", _FakeOpenAI)

    result = pc.PerplexityClient._test_key("pplx-fake-key")

    assert result is True
    assert real_client.is_closed, "build_pinned_httpx_client()'s client must be closed after _test_key returns"
