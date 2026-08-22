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
    assert len(client._sync._client.event_hooks.get("request", [])) > 0
    assert client._async._client.follow_redirects is False
    assert len(client._async._client.event_hooks.get("request", [])) > 0
