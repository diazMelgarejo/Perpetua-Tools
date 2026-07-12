import pytest, respx, httpx
from perpetua.discovery.backend import BackendHealth
from perpetua.discovery.probe import health_probe


@pytest.mark.asyncio
@respx.mock
async def test_probe_returns_online_when_models_endpoint_serves_200():
    respx.get("http://127.0.2.1:1234/v1/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "qwen3-coder-30b"}]})
    )
    result = await health_probe("http://127.0.2.1:1234/v1")
    assert result.health is BackendHealth.ONLINE
    assert "qwen3-coder-30b" in result.models


@pytest.mark.asyncio
@respx.mock
async def test_probe_returns_offline_when_endpoint_404s():
    respx.get("http://127.0.2.1:1234/v1/models").mock(return_value=httpx.Response(404))
    result = await health_probe("http://127.0.2.1:1234/v1")
    assert result.health is BackendHealth.OFFLINE


@pytest.mark.asyncio
@respx.mock
async def test_probe_returns_offline_on_connection_error():
    respx.get("http://127.0.1.1:1234/v1/models").mock(side_effect=httpx.ConnectError("nope"))
    result = await health_probe("http://127.0.1.1:1234/v1")
    assert result.health is BackendHealth.OFFLINE
