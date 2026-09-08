"""Tests for agent_launcher.resolve_local_or_remote's SSRF handling."""
from __future__ import annotations

import socket

import pytest

import perpetua_tools.agent_launcher as agent_launcher


def test_resolve_local_or_remote_uses_fallback_ip_when_remote(monkeypatch):
    monkeypatch.setattr(agent_launcher, "RUNNING_ON_MAC", False)
    monkeypatch.setattr(agent_launcher, "RUNNING_ON_WINDOWS", True)
    result = agent_launcher.resolve_local_or_remote(
        "mac", 11434, fallback_ip="192.168.1.50"
    )
    assert result == "http://192.168.1.50:11434"


def test_resolve_local_or_remote_rejects_link_local_metadata_override(monkeypatch):
    """Regression: the env_var override path returned an operator-supplied
    URL with zero SSRF host-classification when the target role is remote
    (is_local False) -- only the is_local/loopback-heal branch was checked
    for locality, never for a blocked destination range. An
    OLLAMA_WINDOWS_ENDPOINT=http://169.254.169.254:11434 override would be
    returned and later fetched with no validation."""
    monkeypatch.setattr(agent_launcher, "RUNNING_ON_MAC", True)
    monkeypatch.setattr(agent_launcher, "RUNNING_ON_WINDOWS", False)
    monkeypatch.setenv("TEST_REMOTE_ENDPOINT", "http://169.254.169.254:11434")
    result = agent_launcher.resolve_local_or_remote(
        "windows", 11434, env_var="TEST_REMOTE_ENDPOINT", fallback_ip="127.0.0.1"
    )
    assert "169.254.169.254" not in result


def test_resolve_local_or_remote_redacts_rejected_override(monkeypatch, caplog):
    monkeypatch.setattr(agent_launcher, "RUNNING_ON_MAC", True)
    monkeypatch.setattr(agent_launcher, "RUNNING_ON_WINDOWS", False)
    monkeypatch.setenv("TEST_REMOTE_ENDPOINT", "http://user:secret@1.1.1.1:11434")

    result = agent_launcher.resolve_local_or_remote(
        "windows", 11434, env_var="TEST_REMOTE_ENDPOINT", fallback_ip="127.0.0.1"
    )

    assert result == "http://127.0.0.1:11434"
    assert "secret" not in caplog.text


def test_resolve_local_or_remote_rejects_link_local_metadata_fallback(monkeypatch):
    """A rejected override must not make an unsafe fallback reachable."""
    monkeypatch.setattr(agent_launcher, "RUNNING_ON_MAC", True)
    monkeypatch.setattr(agent_launcher, "RUNNING_ON_WINDOWS", False)
    monkeypatch.setenv("TEST_REMOTE_ENDPOINT", "http://169.254.169.254:11434")
    result = agent_launcher.resolve_local_or_remote(
        "windows",
        11434,
        env_var="TEST_REMOTE_ENDPOINT",
        fallback_ip="169.254.169.254",
    )
    assert result == "http://127.0.0.1:11434"


def test_resolve_local_or_remote_still_accepts_lan_override(monkeypatch):
    """Confirm the fix isn't over-broad -- a genuine RFC1918 override must
    still pass through unchanged."""
    monkeypatch.setattr(agent_launcher, "RUNNING_ON_MAC", True)
    monkeypatch.setattr(agent_launcher, "RUNNING_ON_WINDOWS", False)
    monkeypatch.setenv("TEST_REMOTE_ENDPOINT", "http://192.168.1.77:11434")
    result = agent_launcher.resolve_local_or_remote(
        "windows", 11434, env_var="TEST_REMOTE_ENDPOINT", fallback_ip="127.0.0.1"
    )
    assert result == "http://192.168.1.77:11434"


# ---------------------------------------------------------------------------
# Gate 4 Half B: DNS-resolution + address-class validation.
#
# Gate 2 (orama-system docs/v2/64) named the precise gap: syntactic
# validation (validate_model_endpoint_url) checks a URL's *text*, never what
# its host *resolves to*. These tests use IP literals throughout (never a
# hostname), so getaddrinfo never touches the workstation's real resolver or
# the network -- matching the same test-constraint used for the v2 dialer
# this mirrors (doc 65/66).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "address,expected",
    [
        ("127.0.0.1", True),
        ("::1", True),  # IPv6 loopback: is_reserved==True on CPython 3.13,
        # loopback must be checked first or this is wrongly rejected.
        ("192.168.1.10", True),
        ("10.0.0.5", True),
        ("fd00::1", True),  # ULA
        ("169.254.169.254", False),  # cloud metadata (link-local)
        ("0.0.0.0", False),
        ("255.255.255.255", False),
        ("224.0.0.1", False),  # multicast
        ("100.64.0.1", False),  # CGNAT
        ("192.88.99.1", False),  # 6to4 relay anycast
        ("2001:0:4136:e378:8000:63bf:3fff:fdd2", False),  # Teredo
        ("2002:a9fe:c9fe::1", False),  # 6to4, embeds 169.254.169.254
        ("::ffff:169.254.169.254", False),  # IPv4-mapped metadata
        ("8.8.8.8", False),  # ordinary public address -- no opt-in exists
        # at this layer, so agent_launcher.py must never dial it.
    ],
)
def test_is_dialable_address_matches_v2_dialer_classification(address, expected):
    assert agent_launcher._is_dialable_address(address) is expected


def test_resolve_and_validate_dial_host_accepts_private_ip_literal():
    url = "http://192.168.1.10:11434"
    assert agent_launcher.resolve_and_validate_dial_host(url) == url
    target = agent_launcher._resolve_and_pin_dial_host(url)
    assert target.origin_url == url
    assert target.hostname == "192.168.1.10"
    assert target.resolved_address == "192.168.1.10"


def test_resolve_and_validate_dial_host_rejects_metadata_ip_literal():
    with pytest.raises(ValueError, match="prohibited or public address"):
        agent_launcher.resolve_and_validate_dial_host("http://169.254.169.254:11434")


def test_resolve_and_validate_dial_host_redacts_url_in_error_message():
    with pytest.raises(ValueError) as exc_info:
        agent_launcher.resolve_and_validate_dial_host(
            "http://user:secret@169.254.169.254:11434"
        )
    assert "secret" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_check_remote_worker_refuses_to_dial_a_prohibited_resolved_address(monkeypatch):
    """Regression: check_remote_worker previously had ZERO validation of any
    kind -- not even the syntactic check other call sites use -- before
    dialing base_url with raw httpx. Must now refuse before any network
    call reaches httpx."""
    called = False

    class _UnreachedClient:
        async def __aenter__(self):
            nonlocal called
            called = True
            raise AssertionError("httpx.AsyncClient must not be constructed")

        async def __aexit__(self, *exc_info):
            return False

    monkeypatch.setattr(agent_launcher.httpx, "AsyncClient", lambda **kw: _UnreachedClient())

    reachable, latency = await agent_launcher.check_remote_worker(
        "http://169.254.169.254:11434", _retries=0
    )

    assert (reachable, latency) == (False, None)
    assert called is False


@pytest.mark.asyncio
async def test_check_lmstudio_worker_refuses_to_dial_a_prohibited_resolved_address(monkeypatch):
    called = False

    class _UnreachedClient:
        async def __aenter__(self):
            nonlocal called
            called = True
            raise AssertionError("httpx.AsyncClient must not be constructed")

        async def __aexit__(self, *exc_info):
            return False

    monkeypatch.setattr(agent_launcher.httpx, "AsyncClient", lambda **kw: _UnreachedClient())

    reachable, latency = await agent_launcher.check_lmstudio_worker(
        "http://169.254.169.254:1234", _retries=0
    )

    assert (reachable, latency) == (False, None)
    assert called is False


@pytest.mark.asyncio
async def test_check_remote_worker_still_dials_a_genuine_lan_address(monkeypatch):
    """Confirm the fix isn't over-broad -- a real LAN target must still be
    reachable through the normal path (mocking only the HTTP layer, not
    DNS/classification)."""

    class _FakeResponse:
        status_code = 200

    async def pinned_get(target, path, *, timeout, headers=None):
        return _FakeResponse()

    monkeypatch.setattr(agent_launcher, "_pinned_get", pinned_get)

    reachable, latency = await agent_launcher.check_remote_worker(
        "http://192.168.1.10:11434", _retries=0
    )

    assert reachable is True
    assert latency is not None


@pytest.mark.asyncio
async def test_pinned_backend_connects_to_validated_ip_without_rewriting_origin() -> None:
    """The HTTPX request keeps the hostname for Host/SNI; only TCP is pinned."""

    calls: list[tuple[str, int]] = []

    class RecordingBackend:
        async def connect_tcp(self, host, port, **kwargs):
            calls.append((host, port))
            return object()

        async def connect_unix_socket(self, path, **kwargs):
            raise AssertionError("unix sockets are not part of this transport")

        async def sleep(self, seconds):
            return None

    backend = agent_launcher._PinnedAsyncNetworkBackend(
        hostname="models.internal",
        resolved_address="192.168.1.44",
        delegate=RecordingBackend(),
    )

    await backend.connect_tcp("models.internal", 443)

    assert calls == [("192.168.1.44", 443)]


@pytest.mark.asyncio
async def test_pinned_transport_preserves_configured_http_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The TCP pin must not replace the hostname used for Host or TLS SNI."""

    target = agent_launcher._ValidatedDialTarget(
        origin_url="https://models.internal:1234",
        hostname="models.internal",
        resolved_address="192.168.1.44",
    )
    observed_request: agent_launcher.httpcore.Request | None = None

    class EmptyStream:
        def __aiter__(self):
            return self

        async def __anext__(self) -> bytes:
            raise StopAsyncIteration

        async def aclose(self) -> None:
            return None

    class CoreResponse:
        status = 200
        headers: list[tuple[bytes, bytes]] = []
        stream = EmptyStream()
        extensions: dict[str, object] = {}

    class Pool:
        async def handle_async_request(
            self, request: agent_launcher.httpcore.Request
        ) -> CoreResponse:
            nonlocal observed_request
            observed_request = request
            return CoreResponse()

        async def aclose(self) -> None:
            return None

    pool = Pool()

    def make_pool(**kwargs: object) -> Pool:
        backend = kwargs["network_backend"]
        assert isinstance(backend, agent_launcher._PinnedAsyncNetworkBackend)
        return pool

    monkeypatch.setattr(agent_launcher.httpcore, "AsyncConnectionPool", make_pool)

    transport = agent_launcher._PinnedAsyncHTTPTransport(target)
    response = await transport.handle_async_request(
        agent_launcher.httpx.Request("GET", f"{target.origin_url}/v1/models")
    )

    assert response.status_code == 200
    assert observed_request is not None
    assert observed_request.url.host == b"models.internal"
    assert observed_request.url.scheme == b"https"
    assert observed_request.url.port == 1234
    assert (b"Host", b"models.internal:1234") in observed_request.headers


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("endpoint_url", "status_code", "expected_headers", "expected_reachable"),
    [
        ("https://models.internal:1234", 200, {"Authorization": "Bearer test-token"}, True),
        ("http://models.internal:1234", 401, {}, False),
    ],
)
async def test_lmstudio_probe_pins_dns_and_never_sends_token_over_http(
    monkeypatch: pytest.MonkeyPatch,
    endpoint_url: str,
    status_code: int,
    expected_headers: dict[str, str],
    expected_reachable: bool,
) -> None:
    """A later hostile DNS answer cannot change the TCP peer after validation."""

    dns_calls = 0
    pinned_requests: list[tuple[object, str, dict[str, str] | None]] = []

    def getaddrinfo(
        host: str, port: int | None
    ) -> list[tuple[int, int, int, str, tuple[str, int]]]:
        nonlocal dns_calls
        dns_calls += 1
        address = "192.168.1.44" if dns_calls == 1 else "169.254.169.254"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))]

    class Response:
        def __init__(self, status_code: int) -> None:
            self.status_code = status_code

    async def pinned_get(
        target: agent_launcher._ValidatedDialTarget,
        path: str,
        *,
        timeout: float,
        headers: dict[str, str] | None = None,
    ) -> Response:
        pinned_requests.append((target, path, headers))
        return Response(status_code)

    monkeypatch.setattr(agent_launcher.socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(agent_launcher, "_pinned_get", pinned_get)
    monkeypatch.setattr(agent_launcher, "LMS_API_TOKEN", "test-token")

    reachable, _ = await agent_launcher.check_lmstudio_worker(endpoint_url, _retries=0)

    assert reachable is expected_reachable
    assert dns_calls == 1
    target, path, headers = pinned_requests[0]
    assert target.origin_url == endpoint_url
    assert target.resolved_address == "192.168.1.44"
    assert path == "/v1/models"
    assert headers == expected_headers


@pytest.mark.asyncio
async def test_model_discovery_never_sends_lmstudio_token_over_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Discovery uses the same cleartext credential boundary as health probes."""

    target = agent_launcher._ValidatedDialTarget(
        origin_url="http://models.internal:1234",
        hostname="models.internal",
        resolved_address="192.168.1.44",
    )
    pinned_requests: list[tuple[str, dict[str, str] | None]] = []

    class Response:
        def json(self) -> dict[str, list[dict[str, str]]]:
            return {"data": [{"id": "local-model"}]}

    def resolve(url: str) -> agent_launcher._ValidatedDialTarget:
        assert url == target.origin_url
        return target

    async def pinned_get(
        dial_target: agent_launcher._ValidatedDialTarget,
        path: str,
        *,
        timeout: int,
        headers: dict[str, str] | None = None,
    ) -> Response:
        assert dial_target is target
        assert timeout == agent_launcher.DETECT_TIMEOUT
        pinned_requests.append((path, headers))
        return Response()

    monkeypatch.setattr(agent_launcher, "_resolve_and_pin_dial_host", resolve)
    monkeypatch.setattr(agent_launcher, "_pinned_get", pinned_get)
    monkeypatch.setattr(agent_launcher, "LMS_API_TOKEN", "test-token")

    models = await agent_launcher._fetch_models(
        mac_ok=False,
        mac_url="",
        mac_lms_ok=True,
        lms_url=target.origin_url,
    )

    assert models == {"mac-lmstudio": ["local-model"]}
    assert pinned_requests == [("/v1/models", {})]
