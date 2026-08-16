import pytest, respx, httpx
from perpetua.discovery.backend import BackendKind, BackendHealth
from perpetua.discovery.registry import BackendRegistry
from perpetua.discovery.errors import BackendOfflineError


@pytest.mark.asyncio
@respx.mock
async def test_autodetect_keeps_only_responsive_seeds():
    respx.get("http://localhost:11434/v1/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "qwen3.5:9b-nvfp4"}]}))
    respx.get("http://localhost:1234/v1/models").mock(return_value=httpx.Response(404))
    respx.get("http://192.0.2.1:1234/v1/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "qwen3-coder-30b"}]}))

    reg = BackendRegistry()
    await reg.autodetect()
    online = [b.name for b in reg.online()]
    assert "ollama-local" in online
    assert "lmstudio-win" in online
    assert "lmstudio-mac" not in online


@pytest.mark.asyncio
@respx.mock
async def test_register_by_ip_admits_only_when_probe_succeeds():
    respx.get("http://127.0.2.1:1234/v1/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "qwen3-coder-30b"}]}))
    reg = BackendRegistry()
    b = await reg.register_by_ip("127.0.2.1", 1234, BackendKind.LMSTUDIO, name="win-rig")
    assert b.health is BackendHealth.ONLINE
    assert reg.find("win-rig") is b


@pytest.mark.asyncio
@respx.mock
async def test_register_by_ip_raises_when_offline():
    respx.get("http://127.0.1.1:1234/v1/models").mock(side_effect=httpx.ConnectError("nope"))
    reg = BackendRegistry()
    with pytest.raises(BackendOfflineError):
        await reg.register_by_ip("127.0.1.1", 1234, BackendKind.LMSTUDIO)


@pytest.mark.asyncio
async def test_register_by_ip_rejects_link_local_metadata_target():
    """Regression: register_by_ip() constructed and immediately probed
    f"http://{ip}:{port}/v1" with zero SSRF host-classification -- a
    caller (even if none exist in this codebase today) passing
    169.254.169.254 would have this process probe cloud instance-metadata.
    Must be rejected before any network call, not just failed offline --
    verified by asserting respx recorded zero calls, not just that the
    result was an error (a real connection failure in a sandboxed test
    runner would also raise BackendOfflineError for the wrong reason)."""
    with respx.mock:
        route = respx.get(url__regex=r".*")
        reg = BackendRegistry()
        with pytest.raises(BackendOfflineError):
            await reg.register_by_ip("169.254.169.254", 80, BackendKind.LMSTUDIO)
        assert route.call_count == 0, "must reject before any network call"
