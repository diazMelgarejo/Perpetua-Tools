"""Tests for agent_launcher.resolve_local_or_remote's SSRF handling."""
from __future__ import annotations

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
    DNS/classification). Also confirms the IP-pinning fix's own shape: the
    dialed URL's host is the validated IP, while Host/SNI still carry the
    original hostname."""

    class _FakeResponse:
        status_code = 200

    calls = []

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def get(self, url, headers=None, extensions=None):
            calls.append((url, headers, extensions))
            return _FakeResponse()

    monkeypatch.setattr(agent_launcher.httpx, "AsyncClient", lambda **kw: _FakeClient())

    reachable, latency = await agent_launcher.check_remote_worker(
        "http://192.168.1.10:11434", _retries=0
    )

    assert reachable is True
    assert latency is not None
    assert len(calls) == 1
    dial_url, headers, extensions = calls[0]
    assert dial_url.startswith("http://192.168.1.10:11434/"), (
        "192.168.1.10 is a literal IP, so it is its own 'resolved' address -- "
        "the dial URL must still target it directly, unchanged"
    )
    assert headers["Host"] == "192.168.1.10:11434", (
        "port 11434 is not the scheme's default -- Host must include it "
        "(RFC 7230 §5.4), even though SNI never carries a port"
    )
    assert extensions["sni_hostname"] == "192.168.1.10"


@pytest.mark.asyncio
async def test_check_remote_worker_dials_the_validated_address_despite_dns_rebinding(
    monkeypatch,
):
    """The actual DNS-rebinding/TOCTOU regression the review asked for:
    getaddrinfo returns a safe LAN address on the validation call, then a
    prohibited address on any later call, simulating an adversarial DNS
    server changing its answer between validation and connection. The fix
    must dial the address returned by the FIRST (validation) call only --
    a real re-resolution here would connect to the prohibited address
    instead, and the test would need to assert that failure to catch a
    regression."""
    calls = {"n": 0}

    def _rebinding_getaddrinfo(host, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return [(2, 1, 6, "", ("192.168.1.10", 0))]  # safe, on validation
        return [(2, 1, 6, "", ("169.254.169.254", 0))]  # rebound to metadata IP

    monkeypatch.setattr(agent_launcher.socket, "getaddrinfo", _rebinding_getaddrinfo)

    class _FakeResponse:
        status_code = 200

    calls_made = []

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def get(self, url, headers=None, extensions=None):
            calls_made.append(url)
            return _FakeResponse()

    monkeypatch.setattr(agent_launcher.httpx, "AsyncClient", lambda **kw: _FakeClient())

    reachable, latency = await agent_launcher.check_remote_worker(
        "http://model-server.lan:11434", _retries=0
    )

    assert reachable is True
    assert len(calls_made) == 1
    assert calls_made[0].startswith("http://192.168.1.10:11434/"), (
        f"dialed {calls_made[0]!r} -- must be the address validated on the "
        "FIRST getaddrinfo call, never a later, rebound answer"
    )
    assert calls["n"] == 1, (
        "resolve_dial_target must call getaddrinfo exactly once -- a second "
        "call anywhere in the dial path re-opens the rebinding window"
    )


@pytest.mark.asyncio
async def test_check_lmstudio_worker_dials_the_validated_address_despite_dns_rebinding(
    monkeypatch,
):
    """Same DNS-rebinding regression as above, for the LM Studio path."""
    monkeypatch.setattr(agent_launcher, "LMS_API_TOKEN", "")
    calls = {"n": 0}

    def _rebinding_getaddrinfo(host, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return [(2, 1, 6, "", ("10.0.0.20", 0))]
        return [(2, 1, 6, "", ("169.254.169.254", 0))]

    monkeypatch.setattr(agent_launcher.socket, "getaddrinfo", _rebinding_getaddrinfo)

    class _FakeResponse:
        status_code = 200

    calls_made = []

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def get(self, url, headers=None, extensions=None):
            calls_made.append(url)
            return _FakeResponse()

    monkeypatch.setattr(agent_launcher.httpx, "AsyncClient", lambda **kw: _FakeClient())

    reachable, latency = await agent_launcher.check_lmstudio_worker(
        "http://lmstudio.lan:1234", _retries=0
    )

    assert reachable is True
    assert len(calls_made) == 1
    assert calls_made[0].startswith("http://10.0.0.20:1234/")


@pytest.mark.asyncio
async def test_check_lmstudio_worker_refuses_to_send_token_over_http(monkeypatch):
    """The credential-leak regression the review asked for: LMS_API_TOKEN
    set, endpoint is HTTP (not HTTPS) -- must report unavailable, never
    send the token in cleartext, and never silently retry unauthenticated
    (which would misreport a secured endpoint as reachable)."""
    monkeypatch.setattr(agent_launcher, "LMS_API_TOKEN", "secret-token-value")
    monkeypatch.setattr(
        agent_launcher.socket,
        "getaddrinfo",
        lambda host, *a, **kw: [(2, 1, 6, "", ("10.0.0.40", 0))],
    )

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
        "http://lmstudio.lan:1234", _retries=0
    )

    assert (reachable, latency) == (False, None)
    assert called is False


@pytest.mark.asyncio
async def test_check_lmstudio_worker_sends_token_over_https(monkeypatch):
    """Regression: confirm the fix isn't over-broad -- HTTPS + a token must
    still work, with the token genuinely attached."""
    monkeypatch.setattr(agent_launcher, "LMS_API_TOKEN", "secret-token-value")
    monkeypatch.setattr(
        agent_launcher.socket,
        "getaddrinfo",
        lambda host, *a, **kw: [(2, 1, 6, "", ("10.0.0.30", 0))],
    )

    class _FakeResponse:
        status_code = 200

    calls = []

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def get(self, url, headers=None, extensions=None):
            calls.append((url, headers))
            return _FakeResponse()

    monkeypatch.setattr(agent_launcher.httpx, "AsyncClient", lambda **kw: _FakeClient())

    reachable, latency = await agent_launcher.check_lmstudio_worker(
        "https://lmstudio.lan:1234", _retries=0
    )

    assert reachable is True
    assert len(calls) == 1
    _, headers = calls[0]
    assert headers["Authorization"] == "Bearer secret-token-value"


@pytest.mark.parametrize(
    "url, host, expected",
    [
        ("http://model-server.lan:11434/api/tags", "model-server.lan", "model-server.lan:11434"),
        ("http://model-server.lan:80/api/tags", "model-server.lan", "model-server.lan"),
        ("http://model-server.lan/api/tags", "model-server.lan", "model-server.lan"),
        ("https://lmstudio.lan:443/v1/models", "lmstudio.lan", "lmstudio.lan"),
        ("https://lmstudio.lan:8443/v1/models", "lmstudio.lan", "lmstudio.lan:8443"),
        ("http://192.168.1.10:11434/api/tags", "192.168.1.10", "192.168.1.10:11434"),
    ],
)
def test_host_header_authority_includes_only_non_default_ports(url, host, expected):
    assert agent_launcher._host_header_authority(url, host) == expected


@pytest.mark.asyncio
async def test_check_remote_worker_omits_default_port_from_host_header(monkeypatch):
    """The other half of the review's requirement: a default port (80 for
    http) must still be omitted from Host, not just non-default ports
    included -- verified end-to-end through the real dialing path, not
    only the unit-level table above."""
    monkeypatch.setattr(
        agent_launcher.socket,
        "getaddrinfo",
        lambda host, *a, **kw: [(2, 1, 6, "", ("10.0.0.50", 0))],
    )

    class _FakeResponse:
        status_code = 200

    calls = []

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def get(self, url, headers=None, extensions=None):
            calls.append(headers)
            return _FakeResponse()

    monkeypatch.setattr(agent_launcher.httpx, "AsyncClient", lambda **kw: _FakeClient())

    reachable, _ = await agent_launcher.check_remote_worker(
        "http://model-server.lan:80", _retries=0
    )

    assert reachable is True
    assert calls[0]["Host"] == "model-server.lan"
