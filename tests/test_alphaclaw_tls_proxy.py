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
    cert1, _ = proxy1._generate_cert()
    fingerprint1 = mod.verify_or_pin_fingerprint(cert1)

    proxy2 = AlphaClawTlsProxy(upstream_port=9999, proxy_port=_free_port())
    cert2, _ = proxy2._generate_cert()
    fingerprint2 = mod.verify_or_pin_fingerprint(cert2)

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
    cert1, key1 = proxy1._generate_cert()
    mod.verify_or_pin_fingerprint(cert1)

    # Simulate only the cert+key changing (attacker swap, or a rotation
    # that bypassed this module's own reuse logic) -- pin file untouched.
    cert1.unlink()
    key1.unlink()
    proxy2 = AlphaClawTlsProxy(upstream_port=9999, proxy_port=_free_port())
    cert2, _ = proxy2._generate_cert()

    with pytest.raises(mod.AlphaClawCertFingerprintMismatch):
        mod.verify_or_pin_fingerprint(cert2)


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
