"""Unit tests for the canonical Tier-5 provider transport registry."""
from __future__ import annotations

import json

import pytest
import respx
from httpx import Response

from orchestrator.model_transport import (
    ProviderConfigError,
    ProviderTransportError,
    ProviderTransportRegistry,
)
from orchestrator.model_registry import ModelRegistry


@pytest.fixture
def transport_config(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "devices.yml").write_text("devices: {}\n", encoding="utf-8")
    (config_dir / "routing.yml").write_text("routes: {}\n", encoding="utf-8")
    (config_dir / "models.yml").write_text(
        """models:
  - name: glm-paid
    api_model: glm-5.2
    backend: bigmodel
    device: cloud
    host: https://open.bigmodel.cn
    port: 443
    api_path: /api/paas/v4/chat/completions
    roles: [general]
    priority: 1
    online: true
    reasoning: cloud
    frugality_tier: 5
    provenance:
      kind: provider-api
      source_model_id: glm-5.2
      source_url: https://docs.bigmodel.cn/api-reference/models
      verified_on: "2026-08-11"
  - name: sonnet-paid
    api_model: claude-sonnet-5
    backend: anthropic
    device: cloud
    host: https://api.anthropic.com
    port: 443
    roles: [general]
    priority: 2
    online: true
    reasoning: cloud
    frugality_tier: 5
    provider_options:
      output_config:
        effort: medium
    provenance:
      kind: provider-api
      source_model_id: claude-sonnet-5
      source_url: https://platform.claude.com/docs/models
      verified_on: "2026-08-11"
""",
        encoding="utf-8",
    )
    providers = config_dir / "providers.yml"
    providers.write_text(
        """version: 1
providers:
  bigmodel:
    credential_env: BIGMODEL_TEST_KEY
    allowed_hosts: [open.bigmodel.cn]
    documentation_hosts: [docs.bigmodel.cn]
    default_api_path: /api/paas/v4/chat/completions
    timeout_seconds: 1
    max_attempts: 1
  anthropic:
    credential_env: ANTHROPIC_TEST_KEY
    allowed_hosts: [api.anthropic.com]
    documentation_hosts: [platform.claude.com]
    default_api_path: /v1/messages
    api_version: 2023-06-01
    timeout_seconds: 1
    max_attempts: 1
""",
        encoding="utf-8",
    )
    return config_dir, providers


@pytest.mark.asyncio
@respx.mock
async def test_bigmodel_dispatch_uses_registry_target_and_openai_wire_shape(
    transport_config, monkeypatch
) -> None:
    config_dir, providers = transport_config
    monkeypatch.setenv("BIGMODEL_TEST_KEY", "test-key")
    route = respx.post("https://open.bigmodel.cn/api/paas/v4/chat/completions").mock(
        return_value=Response(
            200,
            json={"choices": [{"message": {"content": "classification"}}]},
        )
    )

    result = await ProviderTransportRegistry(
        config_dir=config_dir, providers_path=providers
    ).dispatch("glm-paid", "classify this", 64, "classify")

    assert result == "classification"
    request = route.calls[0].request
    assert request.headers["authorization"] == "Bearer test-key"
    assert json.loads(request.content) == {
        "model": "glm-5.2",
        "messages": [{"role": "user", "content": "classify this"}],
        "max_tokens": 64,
        "stream": False,
    }


@pytest.mark.asyncio
@respx.mock
async def test_anthropic_dispatch_uses_native_messages_and_medium_effort(
    transport_config, monkeypatch
) -> None:
    config_dir, providers = transport_config
    monkeypatch.setenv("ANTHROPIC_TEST_KEY", "test-key")
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=Response(
            200,
            json={"content": [{"type": "text", "text": "final answer"}]},
        )
    )

    result = await ProviderTransportRegistry(
        config_dir=config_dir, providers_path=providers
    ).dispatch("sonnet-paid", "write this", 256, "generate")

    assert result == "final answer"
    request = route.calls[0].request
    assert request.headers["x-api-key"] == "test-key"
    assert request.headers["anthropic-version"] == "2023-06-01"
    assert json.loads(request.content) == {
        "model": "claude-sonnet-5",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": "write this"}],
        "output_config": {"effort": "medium"},
    }


@pytest.mark.asyncio
async def test_transport_rejects_unknown_or_non_tier5_models(transport_config, monkeypatch) -> None:
    config_dir, providers = transport_config
    monkeypatch.setenv("BIGMODEL_TEST_KEY", "test-key")
    transport = ProviderTransportRegistry(config_dir=config_dir, providers_path=providers)

    with pytest.raises(ProviderConfigError, match="unknown model"):
        await transport.dispatch("missing", "prompt", 1, "stage")


def test_static_registry_load_does_not_trigger_active_tilting_discovery(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "devices.yml").write_text(
        "devices:\n  worker:\n    identity_method: active_tilting\n",
        encoding="utf-8",
    )
    (config_dir / "routing.yml").write_text("routes: {}\n", encoding="utf-8")
    (config_dir / "models.yml").write_text(
        "models:\n  - name: local\n    backend: lm-studio\n    device: worker\n    host: http://localhost\n    port: 1234\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "orchestrator.lan_discovery.detect_active_tilting_ip",
        lambda: (_ for _ in ()).throw(AssertionError("discovery must not run")),
    )
    assert ModelRegistry(config_dir=str(config_dir)).list_models(probe=False)[0].host == "http://localhost"


@pytest.mark.asyncio
@respx.mock
async def test_provider_failure_never_echoes_response_body(transport_config, monkeypatch) -> None:
    config_dir, providers = transport_config
    monkeypatch.setenv("BIGMODEL_TEST_KEY", "test-key")
    respx.post("https://open.bigmodel.cn/api/paas/v4/chat/completions").mock(
        return_value=Response(401, text="provider echoed secret prompt")
    )

    with pytest.raises(ProviderTransportError) as exc_info:
        await ProviderTransportRegistry(
            config_dir=config_dir, providers_path=providers
        ).dispatch("glm-paid", "private prompt", 64, "classify")

    assert "provider echoed" not in str(exc_info.value)
    assert "private prompt" not in str(exc_info.value)
