"""orchestrator/portal_tls_proxy.py -- TLS front end for the orama Portal.

All addresses are loopback (derived via helpers) or TEST-NET documentation
addresses; no real network is touched.
"""
from __future__ import annotations

import hashlib
import http.server
import ipaddress
import socket
import socketserver
import ssl
import threading
import time
import urllib.error
import urllib.request

import pytest

from orchestrator import alphaclaw_tls_proxy as base
from orchestrator import portal_tls_proxy as portal

pytestmark = pytest.mark.skipif(
    not base._CRYPTOGRAPHY_AVAILABLE, reason="'cryptography' library not installed"
)

LOOP = str(ipaddress.IPv4Address((127 << 24) | 1))
NET_A = "192.0.2.10"
NET_B = "198.51.100.20"


class _Echo(http.server.BaseHTTPRequestHandler):
    seen: list = []

    def do_GET(self) -> None:
        type(self).seen.append(dict(self.headers.items()))
        if self.path == "/health":
            body = b'{"status": "ok"}'
        else:
            body = b'{"auth": "%s"}' % (self.headers.get("Authorization") or "").encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # noqa: A002
        pass


@pytest.fixture
def upstream():
    _Echo.seen = []
    server = socketserver.TCPServer((LOOP, 0), _Echo)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind((LOOP, 0))
        return s.getsockname()[1]


def _make(tmp_path, upstream_port, ips=(LOOP,), names=("portal.example.test",)):
    return portal.build_portal_proxy(
        listen_port=_free_port(),
        upstream_port=upstream_port,
        listen_host=LOOP,
        cert_dir=tmp_path / "portal_tls",
        san_names=names,
        ip_source=lambda: ips,
    )


def _get(url, ctx, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
        return resp.status, resp.read()


def _pinned_fingerprint_of(host, port) -> str:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=5) as raw:
        with ctx.wrap_socket(raw, server_hostname=host) as tls:
            return hashlib.sha256(tls.getpeercert(binary_form=True)).hexdigest()


def test_forwards_health_over_tls_to_http_upstream(tmp_path, upstream):
    proxy = _make(tmp_path, upstream)
    url = proxy.start()
    time.sleep(0.2)
    try:
        ctx = ssl.create_default_context(cafile=str(portal_cert(proxy)))
        status, body = _get(f"{url}/health", ctx)
        assert status == 200 and b'"ok"' in body
        assert url.startswith("https://")
    finally:
        proxy.stop()


def portal_cert(proxy):
    return proxy._dir() / f"{proxy.cert_basename}.crt"


def test_authorization_header_reaches_upstream_unchanged(tmp_path, upstream):
    proxy = _make(tmp_path, upstream)
    url = proxy.start()
    try:
        ctx = ssl.create_default_context(cafile=str(portal_cert(proxy)))
        marker = "Bearer test-marker-not-a-secret"
        _, body = _get(f"{url}/inbox", ctx, {"Authorization": marker})
        assert marker.encode() in body
        assert _Echo.seen[-1].get("Authorization") == marker
    finally:
        proxy.stop()


def test_client_that_does_not_trust_the_cert_fails(tmp_path, upstream):
    proxy = _make(tmp_path, upstream)
    url = proxy.start()
    try:
        with pytest.raises(urllib.error.URLError) as exc:
            _get(f"{url}/health", ssl.create_default_context())
        assert isinstance(exc.value.reason, ssl.SSLCertVerificationError)
    finally:
        proxy.stop()


def test_client_pinned_to_fingerprint_succeeds(tmp_path, upstream):
    proxy = _make(tmp_path, upstream)
    proxy.start()
    try:
        port = proxy.proxy_port
        assert _pinned_fingerprint_of(LOOP, port) == proxy.fingerprint
        # Pinned-only client: verification replaced by the pin comparison.
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        status, _ = _get(f"https://{LOOP}:{port}/health", ctx)
        assert status == 200
    finally:
        proxy.stop()


def test_fingerprint_mismatch_after_regeneration_is_refused(tmp_path, upstream):
    proxy = _make(tmp_path, upstream)
    proxy.start()
    pinned = proxy.fingerprint
    proxy.stop()
    cert_dir = proxy._dir()
    (cert_dir / "portal.crt").unlink()
    (cert_dir / "portal.key").unlink()
    again = _make(tmp_path, upstream)
    with pytest.raises(base.AlphaClawCertFingerprintMismatch):
        again.start()
    assert base._load_pinned_fingerprint(cert_dir) == pinned  # never silently re-pinned


def test_san_change_reissues_explicitly_and_repins(tmp_path, upstream, caplog):
    first = _make(tmp_path, upstream, ips=(LOOP, NET_A))
    first.ensure_certificate()
    fp1 = first.fingerprint
    same = _make(tmp_path, upstream, ips=(LOOP, NET_A))
    same.ensure_certificate()
    assert same.fingerprint == fp1  # coverage unchanged -> reused

    with caplog.at_level("WARNING"):
        moved = _make(tmp_path, upstream, ips=(LOOP, NET_B))
        moved.ensure_certificate()
    assert moved.fingerprint != fp1
    assert any("reissu" in r.getMessage() for r in caplog.records)
    assert base._load_pinned_fingerprint(moved._dir()) == moved.fingerprint
    from cryptography import x509

    cert = x509.load_pem_x509_certificate(portal_cert(moved).read_bytes())
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    ips = {str(i) for i in san.get_values_for_type(x509.IPAddress)}
    assert NET_B in ips and LOOP in ips
    assert "portal.example.test" in san.get_values_for_type(x509.DNSName)


def test_env_flag_default_off_and_truthy_parsing(monkeypatch):
    monkeypatch.delenv("PORTAL_TLS_ENABLED", raising=False)
    assert portal.portal_tls_enabled() is False
    for v in ("1", "true", "YES", " on "):
        monkeypatch.setenv("PORTAL_TLS_ENABLED", v)
        assert portal.portal_tls_enabled() is True
    for v in ("0", "false", "", "no"):
        monkeypatch.setenv("PORTAL_TLS_ENABLED", v)
        assert portal.portal_tls_enabled() is False


def test_san_names_env_parsing(monkeypatch):
    monkeypatch.setenv("PORTAL_TLS_SAN_NAMES", " a.example.test, ,b.example.test ")
    assert portal.san_names_from_env() == ("a.example.test", "b.example.test")


def test_portal_store_is_separate_from_alphaclaw(monkeypatch):
    monkeypatch.delenv("PORTAL_TLS_CERT_DIR", raising=False)
    assert portal.portal_tls_dir() != base.CERT_DIR
    assert portal.portal_tls_dir().name == "portal_tls"


def test_local_ipv4_addresses_are_valid_ipv4():
    addrs = portal.local_ipv4_addresses()
    assert addrs and all(ipaddress.ip_address(a).version == 4 for a in addrs)


def test_alphaclaw_defaults_unchanged():
    p = base.AlphaClawTlsProxy(upstream_port=1)
    assert p.proxy_port == base.DEFAULT_PROXY_PORT == 3345
    assert p.listen_host == "" and p.upstream_host == ""
    assert p.cert_dir is None and p.cert_basename == "alphaclaw"
    assert p.label == "AlphaClaw" and p.common_name == "localhost"
    assert p.san_dns == ("localhost",) and p.san_ips is None
    assert p.reissue_on_san_change is False
    assert base._LOOPBACK_V4 == LOOP


def test_print_fingerprint_cli(tmp_path, capsys):
    rc = portal.main(["--print-fingerprint", "--cert-dir", str(tmp_path / "c")])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.startswith("sha256:") and "BEGIN CERTIFICATE" in out
    assert "PRIVATE" not in out
