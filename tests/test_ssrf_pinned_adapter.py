"""Unit tests for SSRFPinnedHTTPAdapter. No live network, no IMDS traffic."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from utils.ssrf_pinned_adapter import (
    AddressDenied,
    RedirectDenied,
    SSRFPinnedHTTPAdapter,
    SSRFPolicyError,
    default_address_allowed,
    default_url_allowed,
    ssrf_request,
    validate_resolved,
)


@pytest.mark.parametrize(
    "raw",
    [
        "127.0.0.1",
        "10.0.0.5",
        "192.168.1.1",
        "169.254.169.254",
        "169.254.170.2",
        "100.64.0.1",
        "224.0.0.1",
        "0.0.0.0",  # noqa: S104 -- deny-policy fixture, not a bind address
        "::1",
        "::ffff:169.254.169.254",
        "fd00:ec2::254",
        "fe80::1",
    ],
)
def test_denied_addresses(raw: str) -> None:
    with pytest.raises(AddressDenied):
        default_address_allowed(raw)


def test_public_address_ok() -> None:
    default_address_allowed("1.1.1.1")


def test_url_rejects_userinfo_and_scheme() -> None:
    with pytest.raises(SSRFPolicyError):
        default_url_allowed("http://user:pass@example.com/")
    with pytest.raises(SSRFPolicyError):
        default_url_allowed("file:///etc/passwd")
    with pytest.raises(SSRFPolicyError):
        default_url_allowed("https://example.com/\r\nHost: 169.254.169.254")


def test_mixed_public_private_aaaa_fails() -> None:
    infos = [
        (0, 0, 0, "", ("1.1.1.1", 443)),
        (0, 0, 0, "", ("169.254.169.254", 443)),
    ]
    with patch("utils.ssrf_pinned_adapter.socket.getaddrinfo", return_value=infos):
        with pytest.raises(AddressDenied):
            validate_resolved("evil.example", 443, default_address_allowed)


def test_ssrf_request_refuses_redirect_to_metadata() -> None:
    """Regression test for a self-inflicted false-pass: with max_redirects=3
    and a FakeSess whose request() always returns the same 302, the ORIGINAL
    version of this test passed via RedirectDenied('redirect limit exceeded')
    after 3 identical hops -- not because the metadata address itself was
    ever rejected. That FakeSess never routed through
    SSRFPinnedHTTPAdapter.send()'s real validate_resolved() call, so a
    regression that let a metadata redirect Location through address
    checking entirely would still have passed this test. Fixed by using the
    real adapter with only socket.getaddrinfo and the parent
    HTTPAdapter.send (the actual TCP/TLS step) mocked -- validate_resolved()
    itself runs for real and must be what raises."""
    import io

    import urllib3
    from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool

    def fake_getaddrinfo(host, port, family=0, type=0, *a, **kw):
        ip = {"example.com": "93.184.216.34", "169.254.169.254": "169.254.169.254"}[host]
        return [(2, 1, 6, "", (ip, port))]

    first_hop_seen = []

    def fake_urlopen(self, method, url, *args, **kwargs):
        # Only reached if validate_resolved() already allowed this hop's
        # destination -- the metadata hop must never get here. Patched at
        # the connection-pool level (not HTTPAdapter.send) so the real
        # build_response() still runs and populates a genuine
        # requests.Response (.request, .url, etc.), which is what
        # requests.Session.send()'s own redirect-precomputation needs.
        first_hop_seen.append(url)
        return urllib3.HTTPResponse(
            body=io.BytesIO(b""),
            status=302,
            headers={"Location": "http://169.254.169.254/latest/meta-data/"},
            preload_content=False,
        )

    with (
        patch("socket.getaddrinfo", side_effect=fake_getaddrinfo),
        patch.object(HTTPConnectionPool, "urlopen", fake_urlopen),
        patch.object(HTTPSConnectionPool, "urlopen", fake_urlopen),
        pytest.raises(AddressDenied, match="169.254.169.254"),
    ):
        ssrf_request(
            "GET",
            "https://example.com/out",
            allow_redirects=True,
        )
    # The first hop (public example.com) was allowed through to the
    # (mocked) transport; the metadata redirect target must never reach it.
    assert first_hop_seen == ["/out"]


def test_hook_endpoint_policy() -> None:
    # hook_endpoint_policy() itself tries `src.utils.ssrf_fetch_policy` before
    # falling back to `utils.ssrf_fetch_policy` (see its dual-try resolution).
    # Mirror that exact order here rather than picking one import path
    # ourselves: `src.utils.ssrf_fetch_policy.SSRFPolicyError` and
    # `utils.ssrf_fetch_policy.SSRFPolicyError` are the same class body but
    # DIFFERENT class objects when both module paths are importable in the
    # same interpreter (each import path creates its own module instance) --
    # picking the "wrong" one here made `pytest.raises` fail to match the
    # real exception even though the checker was correctly selected. Whatever
    # hook_endpoint_policy() actually resolved to, this must resolve to the
    # same object.
    try:
        from src.utils.ssrf_fetch_policy import SSRFPolicyError as Layer1SSRFPolicyError
    except ImportError:
        from utils.ssrf_fetch_policy import SSRFPolicyError as Layer1SSRFPolicyError
    from utils.ssrf_pinned_adapter import hook_endpoint_policy

    addr_checker, url_checker = hook_endpoint_policy()
    assert callable(addr_checker)
    assert callable(url_checker)
    # Valid address passes
    addr_checker("1.1.1.1")
    # Denied address fails
    with pytest.raises((AddressDenied, Exception)):
        addr_checker("127.0.0.1")

    # Distinguish the selected policy from the fallback: ssrf_fetch_policy's
    # url_checker has no DNS capability, so it fail-closes on any bare
    # hostname it cannot resolve (unless vendor-allowlisted) -- see
    # utils.ssrf_fetch_policy._host_denied. The Layer-2 fallback
    # (default_url_allowed) has no such check and would let this URL
    # through, since it only validates scheme/userinfo/control-chars. If
    # this raises Layer1SSRFPolicyError, hook_endpoint_policy() really did
    # select the Layer-1 checker, not the fallback.
    with pytest.raises(Layer1SSRFPolicyError):
        url_checker("https://example.com/")


def test_ssrf_request_rejects_session_without_pinned_adapter() -> None:
    """A plain requests.Session bypasses DNS pinning/redirect control entirely --
    ssrf_request must refuse it rather than silently trusting check_url alone."""
    import requests

    with pytest.raises(SSRFPolicyError):
        ssrf_request(
            "GET",
            "https://example.com/out",
            session=requests.Session(),
        )


@pytest.mark.parametrize(
    "conn_cls_name",
    ["_PinnedHTTPConnection", "_PinnedHTTPSConnection"],
)
def test_new_conn_uses_configured_address_checker_not_the_default(
    conn_cls_name: str,
) -> None:
    """_new_conn()'s connect-time peer re-check must call the adapter's
    configured address_checker, not a hardcoded default_address_allowed --
    otherwise a caller-supplied stricter checker (e.g. Layer-1's
    hook_endpoint_policy) only applies to the pre-connect DNS-resolve
    validation and silently stops applying at the connection itself.

    Split-identity: the connection's own ``host`` IS the validated pin
    (set via build_connection_pool_key_attributes()'s host_params["host"]),
    so this connects to "1.1.1.1" directly -- no separate pinned_ip kwarg.
    """
    from unittest.mock import MagicMock

    import utils.ssrf_pinned_adapter as adapter_mod

    conn_cls = getattr(adapter_mod, conn_cls_name)
    parent_cls = conn_cls.__mro__[1]  # HTTPConnection / HTTPSConnection

    fake_sock = MagicMock()
    fake_sock.getpeername.return_value = ("1.1.1.1", 443)  # a public, normally-OK address

    calls: list[str] = []

    def deny_everything(ip: str) -> None:
        calls.append(ip)
        raise adapter_mod.AddressDenied(f"denied by test checker: {ip}")

    conn = conn_cls(
        "1.1.1.1",
        port=443,
        address_checker=deny_everything,
    )
    with (
        patch.object(parent_cls, "_new_conn", return_value=fake_sock),
        pytest.raises(AddressDenied, match="denied by test checker"),
    ):
        conn._new_conn()
    # Confirm the CONFIGURED checker actually ran (not silently skipped) --
    # a regression that fell back to default_address_allowed would let
    # "1.1.1.1" through with no exception at all, failing the raises above
    # for a different reason than intended.
    assert calls == ["1.1.1.1"]


def test_build_connection_pool_key_attributes_sets_host_to_the_pin() -> None:
    """Split-identity regression: the adapter's own
    build_connection_pool_key_attributes() must set host_params["host"] to
    the VALIDATED PIN, not the original hostname -- that's what makes
    urllib3's stock PoolKey (keyed on host/port/scheme) naturally
    pin-aware. Before this fix, the adapter mutated
    self.poolmanager.connection_pool_kw with pinned_ip as a SEPARATE,
    non-pool-key field (deliberately excluded from the custom PoolKey
    normalizer to avoid a different crash) -- so two different validated
    pins for the same hostname shared one pool keyed on hostname alone,
    the exact "pool cross-contamination" gap this fix closes. The
    original hostname must still travel via server_hostname/
    assert_hostname (TLS identity) and the Host header (HTTP identity),
    not via host_params["host"]."""
    import socket as socket_module

    import requests

    from utils.ssrf_pinned_adapter import SSRFPinnedHTTPAdapter

    def fake_getaddrinfo(host, port, family=0, type=0, *a, **kw):
        ip = {"a.example.com": "1.1.1.1", "b.example.com": "8.8.8.8"}[host]
        return [(2, 1, 6, "", (ip, port))]

    adapter = SSRFPinnedHTTPAdapter()
    req_a = requests.Request("GET", "https://a.example.com/x").prepare()
    req_b = requests.Request("GET", "https://b.example.com/x").prepare()

    with patch.object(socket_module, "getaddrinfo", side_effect=fake_getaddrinfo):
        host_params_a, pool_kwargs_a = adapter.build_connection_pool_key_attributes(req_a, verify=True)
        host_params_b, pool_kwargs_b = adapter.build_connection_pool_key_attributes(req_b, verify=True)

    assert host_params_a["host"] == "1.1.1.1", "pool key host must be the validated PIN, not the hostname"
    assert host_params_b["host"] == "8.8.8.8"
    assert pool_kwargs_a["server_hostname"] == "a.example.com", "TLS identity stays the original hostname"
    assert pool_kwargs_a["assert_hostname"] == "a.example.com"
    assert req_a.headers["Host"] == "a.example.com", "HTTP virtual-hosting identity stays the original hostname"


def test_zero_adapter_state_mutation_across_a_request() -> None:
    """Required PT test #3 (session synthesis, docs/TDD.md RED-GREEN gate):
    the adapter must never write to self.poolmanager.connection_pool_kw --
    that dict is the exact shared mutable state the pre-split-identity
    `update()/pop()` anti-pattern used, which caused the concurrency race
    this rewrite eliminates. Split-identity moves all per-request data into
    build_connection_pool_key_attributes()'s return value instead."""
    import requests

    from utils.ssrf_pinned_adapter import SSRFPinnedHTTPAdapter

    def fake_getaddrinfo(host, port, family=0, type=0, *a, **kw):
        return [(2, 1, 6, "", ("1.1.1.1", port))]

    adapter = SSRFPinnedHTTPAdapter()
    # init_poolmanager() legitimately seeds block/maxsize/ssl_context at
    # construction time -- that's normal PoolManager config, not the
    # per-request race. What must never change is this dict's CONTENTS
    # across a request (no pinned_ip/address_checker/etc. ever appended).
    before = dict(adapter.poolmanager.connection_pool_kw)

    req = requests.Request("GET", "https://example.com/x").prepare()
    with patch("socket.getaddrinfo", side_effect=fake_getaddrinfo):
        adapter.build_connection_pool_key_attributes(req, verify=True)

    assert adapter.poolmanager.connection_pool_kw == before, "must be unchanged -- no shared-dict mutation"


def test_concurrent_two_pin_requests_get_isolated_pools() -> None:
    """Required PT test #1: two concurrent requests to hostnames resolving to
    different validated IPs must land in two separate, isolated connection
    pools -- proving the pool key (not just per-call kwargs) is pin-aware."""
    from concurrent.futures import ThreadPoolExecutor

    import requests

    from utils.ssrf_pinned_adapter import SSRFPinnedHTTPAdapter

    ip_by_host = {"a.example.com": "1.1.1.1", "b.example.com": "8.8.8.8"}

    def fake_getaddrinfo(host, port, family=0, type=0, *a, **kw):
        return [(2, 1, 6, "", (ip_by_host[host], port))]

    adapter = SSRFPinnedHTTPAdapter()

    def get_pool(hostname: str):
        req = requests.Request("GET", f"https://{hostname}/x").prepare()
        with patch("socket.getaddrinfo", side_effect=fake_getaddrinfo):
            return adapter.get_connection_with_tls_context(req, verify=True)

    with ThreadPoolExecutor(max_workers=2) as pool_exec:
        pool_a, pool_b = list(pool_exec.map(get_pool, ["a.example.com", "b.example.com"]))

    assert pool_a is not pool_b, "different pins must not share a connection pool"
    assert pool_a.host == "1.1.1.1"
    assert pool_b.host == "8.8.8.8"


def test_sequential_dns_change_does_not_reuse_the_old_pin_pool() -> None:
    """Required PT test #2: if the same hostname re-resolves from IP A to IP B
    between two sequential requests, the second request must get a fresh pool
    keyed on B -- not the pool urllib3 already has cached for A."""
    import requests

    from utils.ssrf_pinned_adapter import SSRFPinnedHTTPAdapter

    adapter = SSRFPinnedHTTPAdapter()
    req = requests.Request("GET", "https://example.com/x").prepare()

    def resolve_to(ip: str):
        def fake_getaddrinfo(host, port, family=0, type=0, *a, **kw):
            return [(2, 1, 6, "", (ip, port))]

        return fake_getaddrinfo

    with patch("socket.getaddrinfo", side_effect=resolve_to("1.1.1.1")):
        pool_a = adapter.get_connection_with_tls_context(req, verify=True)

    with patch("socket.getaddrinfo", side_effect=resolve_to("8.8.8.8")):
        pool_b = adapter.get_connection_with_tls_context(req, verify=True)

    assert pool_a is not pool_b, "DNS change must not reuse the pool built for the old pin"
    assert pool_a.host == "1.1.1.1"
    assert pool_b.host == "8.8.8.8"


def test_multithreaded_shared_session_does_not_crash_or_cross_contaminate() -> None:
    """Required PT test #6: a single requests.Session with SSRFPinnedHTTPAdapter
    mounted must be safe to drive concurrently from a ThreadPoolExecutor --
    each thread's resolved pin must reach its own request untouched by the
    others. Only the real TCP/TLS step (HTTPAdapter.send, the grandparent) is
    mocked; validate_resolved() and build_connection_pool_key_attributes()
    run for real on every thread."""
    import io
    from concurrent.futures import ThreadPoolExecutor

    import requests
    import urllib3
    from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool

    from utils.ssrf_pinned_adapter import SSRFPinnedHTTPAdapter

    # Public-looking IPs (not RFC1918/deny-listed) so default_address_allowed passes.
    ip_by_host = {f"host{i}.example.com": f"93.184.216.{i + 1}" for i in range(8)}

    def fake_getaddrinfo(host, port, family=0, type=0, *a, **kw):
        return [(2, 1, 6, "", (ip_by_host[host], port))]

    def fake_urlopen(self, method, url, *args, **kwargs):
        # Reached only after build_connection_pool_key_attributes() already
        # ran for real and selected/created this pool (self.host == the pin);
        # this only stands in for the actual TCP/TLS socket step.
        return urllib3.HTTPResponse(
            body=io.BytesIO(self.host.encode()),
            status=200,
            preload_content=False,
        )

    session = requests.Session()
    adapter = SSRFPinnedHTTPAdapter()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    before = dict(adapter.poolmanager.connection_pool_kw)

    def do_request(hostname: str) -> tuple[str, str]:
        # socket.getaddrinfo is patched ONCE below, outside this worker --
        # unittest.mock.patch's enter/exit is not safe to race across
        # threads on the same target (concurrent __exit__ calls can restore
        # the wrong "original", permanently corrupting the module attribute
        # for every later test in the process). fake_getaddrinfo itself is
        # a stateless pure function, so one shared patch is sufficient.
        resp = session.get(f"https://{hostname}/x")
        return resp.request.headers["Host"], resp.text

    hostnames = list(ip_by_host)
    with (
        patch("socket.getaddrinfo", side_effect=fake_getaddrinfo),
        patch.object(HTTPConnectionPool, "urlopen", fake_urlopen),
        patch.object(HTTPSConnectionPool, "urlopen", fake_urlopen),
        ThreadPoolExecutor(max_workers=8) as pool_exec,
    ):
        results = list(pool_exec.map(do_request, hostnames))

    got_hosts, got_pins = zip(*results, strict=True)
    assert sorted(got_hosts) == sorted(hostnames), "each thread's own hostname (NAME) must survive, unmixed"
    assert sorted(got_pins) == sorted(ip_by_host.values()), "each thread's own pin (PLACE) must survive, unmixed"
    assert adapter.poolmanager.connection_pool_kw == before, "no shared state accrued across threads"

