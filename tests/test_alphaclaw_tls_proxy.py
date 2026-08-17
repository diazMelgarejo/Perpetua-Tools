"""orchestrator/alphaclaw_tls_proxy.py -- minimum HTTPS-in-front-of-AlphaClaw scaffolding.

Companion plan (deferred full design): orama-system
docs/v2/49-peer-mesh-auth-tls-v2-plan.md.
"""
from __future__ import annotations

import http.server
import socketserver
import ssl
import threading
import time
import urllib.request

import pytest

from orchestrator.alphaclaw_tls_proxy import (
    AlphaClawTlsProxy,
    AlphaClawTlsUnavailable,
    _CRYPTOGRAPHY_AVAILABLE,
)


class _FakeAlphaClawHandler(http.server.BaseHTTPRequestHandler):
    """Trivial upstream standing in for AlphaClaw's real HTTP server."""

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true, "from": "fake-alphaclaw"}')

    def log_message(self, *args) -> None:  # noqa: A002 -- silence test output
        pass


@pytest.fixture
def fake_upstream():
    server = socketserver.TCPServer(("127.0.0.1", 0), _FakeAlphaClawHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield port
    server.shutdown()
    server.server_close()


@pytest.mark.skipif(
    not _CRYPTOGRAPHY_AVAILABLE, reason="'cryptography' library not installed"
)
def test_proxy_forwards_https_to_http_upstream(fake_upstream, tmp_path, monkeypatch):
    """Real end-to-end proof: a genuine TLS handshake against the proxy's
    self-signed cert, forwarded to the real fake-upstream HTTP server, and
    the actual upstream response comes back through the encrypted channel."""
    import orchestrator.alphaclaw_tls_proxy as mod

    monkeypatch.setattr(mod, "CERT_DIR", tmp_path / "alphaclaw_tls")

    proxy = AlphaClawTlsProxy(upstream_port=fake_upstream, proxy_port=_free_port())
    https_url = proxy.start()
    time.sleep(0.2)

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE  # self-signed, no pinning yet (scoped out)

        req = urllib.request.Request(f"{https_url}/v1/models")
        with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
            assert resp.status == 200
            body = resp.read().decode()
            assert '"from": "fake-alphaclaw"' in body
    finally:
        proxy.stop()


@pytest.mark.skipif(
    not _CRYPTOGRAPHY_AVAILABLE, reason="'cryptography' library not installed"
)
def test_proxy_binds_loopback_only(fake_upstream, tmp_path, monkeypatch):
    """Regression: must never bind anything but 127.0.0.1 -- this proxy
    exists specifically because AlphaClaw itself is loopback-only; the
    proxy must preserve that, not accidentally widen exposure."""
    import orchestrator.alphaclaw_tls_proxy as mod

    monkeypatch.setattr(mod, "CERT_DIR", tmp_path / "alphaclaw_tls")

    proxy = AlphaClawTlsProxy(upstream_port=fake_upstream, proxy_port=_free_port())
    proxy.start()
    try:
        assert proxy._server is not None
        bound_host = proxy._server.server_address[0]
        assert bound_host == "127.0.0.1"
    finally:
        proxy.stop()


@pytest.mark.skipif(
    not _CRYPTOGRAPHY_AVAILABLE, reason="'cryptography' library not installed"
)
def test_proxy_bounds_stalled_client_connections(fake_upstream, tmp_path, monkeypatch):
    """Regression: a client that opens the TLS handshake and then sends
    headers/chunk data arbitrarily slowly (or not at all) must not hang
    its handler thread forever -- ThreadingTCPServer spawns one thread
    per connection with no cap, so unbounded stalls are a Slowloris-style
    resource exhaustion. Verifies both halves of the fix: the handler's
    socket-level read timeout is actually wired to proxy_timeout, and
    handler threads are daemon so a hung one can't block process exit."""
    import orchestrator.alphaclaw_tls_proxy as mod

    monkeypatch.setattr(mod, "CERT_DIR", tmp_path / "alphaclaw_tls")

    proxy = AlphaClawTlsProxy(
        upstream_port=fake_upstream, proxy_port=_free_port(), proxy_timeout=7.0
    )
    proxy.start()
    try:
        assert proxy._server is not None
        assert proxy._server.daemon_threads is True
        handler_cls = proxy._server.RequestHandlerClass
        assert handler_cls.timeout == 7.0
    finally:
        proxy.stop()


@pytest.mark.skipif(
    not _CRYPTOGRAPHY_AVAILABLE, reason="'cryptography' library not installed"
)
def test_proxy_returns_400_on_malformed_chunked_body(fake_upstream, tmp_path, monkeypatch):
    """Regression: a non-hex chunk-size line (malformed client, or a
    client that disconnects mid-chunk) must not crash the connection
    handler uncaught -- it must return a clean 400 and leave the proxy
    able to serve subsequent requests."""
    import http.client
    import orchestrator.alphaclaw_tls_proxy as mod

    monkeypatch.setattr(mod, "CERT_DIR", tmp_path / "alphaclaw_tls")

    proxy = AlphaClawTlsProxy(upstream_port=fake_upstream, proxy_port=_free_port())
    proxy.start()
    time.sleep(0.2)

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        conn = http.client.HTTPSConnection("127.0.0.1", proxy.proxy_port, context=ctx)
        conn.putrequest("POST", "/v1/models")
        conn.putheader("Transfer-Encoding", "chunked")
        conn.endheaders()
        conn.send(b"ZZZ\r\nhello\r\n0\r\n\r\n")  # non-hex chunk size
        resp = conn.getresponse()
        assert resp.status == 400
        resp.read()

        # Proxy must still be alive and correct for the next request.
        conn2 = http.client.HTTPSConnection("127.0.0.1", proxy.proxy_port, context=ctx)
        conn2.request("GET", "/v1/models")
        resp2 = conn2.getresponse()
        assert resp2.status == 200
    finally:
        proxy.stop()


def test_cert_generation_raises_clear_error_without_cryptography(tmp_path, monkeypatch):
    """When 'cryptography' isn't available, callers get a specific,
    catchable exception -- never a silent fallback to plain HTTP chosen
    by this module itself. The caller decides what "TLS isn't available"
    means for their own request; this module only reports the fact."""
    import orchestrator.alphaclaw_tls_proxy as mod

    monkeypatch.setattr(mod, "_CRYPTOGRAPHY_AVAILABLE", False)
    monkeypatch.setattr(mod, "CERT_DIR", tmp_path / "alphaclaw_tls")

    proxy = AlphaClawTlsProxy(upstream_port=9999, proxy_port=_free_port())
    with pytest.raises(AlphaClawTlsUnavailable):
        proxy.start()


@pytest.mark.skipif(
    not _CRYPTOGRAPHY_AVAILABLE, reason="'cryptography' library not installed"
)
def test_cert_is_reused_across_restarts_not_regenerated(tmp_path, monkeypatch):
    """TOFU fingerprint pinning is meaningless if the cert (and therefore
    its fingerprint) changes on every process start -- verify a second
    proxy instance pointed at the same CERT_DIR gets the SAME certificate,
    not a freshly generated one."""
    import orchestrator.alphaclaw_tls_proxy as mod

    monkeypatch.setattr(mod, "CERT_DIR", tmp_path / "alphaclaw_tls")

    proxy1 = AlphaClawTlsProxy(upstream_port=9999, proxy_port=_free_port())
    cert1, _, _ = proxy1._generate_cert()
    fingerprint1 = mod.verify_or_pin_fingerprint(cert1)

    proxy2 = AlphaClawTlsProxy(upstream_port=9999, proxy_port=_free_port())
    cert2, _, mode2 = proxy2._generate_cert()
    fingerprint2 = mod.verify_or_pin_fingerprint(cert2)

    assert mode2 == "reused"

    assert fingerprint1 == fingerprint2
    assert cert1 == cert2  # literally the same file path, reused in place


@pytest.mark.skipif(
    not _CRYPTOGRAPHY_AVAILABLE, reason="'cryptography' library not installed"
)
def test_fingerprint_mismatch_detected_when_cert_changes_but_pin_persists(tmp_path, monkeypatch):
    """The realistic MITM/cert-swap scenario: the certificate file changes
    but the previously-pinned fingerprint record is untouched. Must raise,
    never silently re-pin. (Deleting the pin file together with the cert
    is a DIFFERENT scenario -- legitimate first-sight-again reset, covered
    implicitly by the reuse test above never hitting this path at all.)"""
    import orchestrator.alphaclaw_tls_proxy as mod

    monkeypatch.setattr(mod, "CERT_DIR", tmp_path / "alphaclaw_tls")

    proxy1 = AlphaClawTlsProxy(upstream_port=9999, proxy_port=_free_port())
    cert1, key1, _ = proxy1._generate_cert()
    mod.verify_or_pin_fingerprint(cert1)

    # Simulate only the cert+key changing (attacker swap, or a rotation
    # that bypassed this module's own reuse logic) -- pin file untouched.
    cert1.unlink()
    key1.unlink()
    proxy2 = AlphaClawTlsProxy(upstream_port=9999, proxy_port=_free_port())
    cert2, _, _ = proxy2._generate_cert()

    with pytest.raises(mod.AlphaClawCertFingerprintMismatch):
        proxy2.start()


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.skipif(
    not _CRYPTOGRAPHY_AVAILABLE, reason="'cryptography' library not installed"
)
def test_generate_cert_reuses_existing_cert_on_second_call(tmp_path, monkeypatch):
    """Regression: cryptography exposes not_valid_after (naive UTC), not
    not_valid_after_utc -- the reuse path must not crash on restart."""
    import orchestrator.alphaclaw_tls_proxy as mod

    monkeypatch.setattr(mod, "CERT_DIR", tmp_path / "alphaclaw_tls")

    proxy = AlphaClawTlsProxy(upstream_port=9999, proxy_port=_free_port())
    cert1, _, mode1 = proxy._generate_cert()
    assert mode1 == "renewed"

    cert2, _, mode2 = proxy._generate_cert()
    assert mode2 == "reused"
    assert cert1 == cert2


@pytest.mark.skipif(
    not _CRYPTOGRAPHY_AVAILABLE, reason="'cryptography' library not installed"
)
def test_expiry_rotation_updates_pin_without_mismatch(tmp_path, monkeypatch):
    """Legitimate expiry-driven rotation must update the TOFU pin, not
    brick TLS until an operator manually deletes fingerprint.json."""
    import orchestrator.alphaclaw_tls_proxy as mod

    monkeypatch.setattr(mod, "CERT_DIR", tmp_path / "alphaclaw_tls")

    proxy1 = AlphaClawTlsProxy(upstream_port=9999, proxy_port=_free_port())
    cert1, _, _ = proxy1._generate_cert()
    fp1 = mod.verify_or_pin_fingerprint(cert1)

    monkeypatch.setattr(mod, "_MIN_REMAINING_DAYS_TO_REUSE", 365)

    proxy2 = AlphaClawTlsProxy(upstream_port=9999, proxy_port=_free_port())
    https_url = proxy2.start()

    assert https_url.startswith("https://")
    assert proxy2.fingerprint != fp1
    assert mod._load_pinned_fingerprint() == proxy2.fingerprint

    proxy2.stop()
