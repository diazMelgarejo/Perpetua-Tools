"""CA mode, store layout, CLI contract and WebSocket pass-through of the
Portal TLS front end. Loopback (derived) and TEST-NET addresses only."""
from __future__ import annotations

import hashlib
import http.server
import ipaddress
import socket
import socketserver
import ssl
import threading
import time
import urllib.request
from datetime import timedelta

import pytest

from orchestrator import alphaclaw_tls_proxy as base
from orchestrator import portal_tls_proxy as portal

pytestmark = pytest.mark.skipif(
    not base._CRYPTOGRAPHY_AVAILABLE, reason="'cryptography' library not installed"
)

LOOP = str(ipaddress.IPv4Address((127 << 24) | 1))
NET_A = "192.0.2.10"


class _Health(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = b'{"status": "ok"}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # noqa: A002
        pass


@pytest.fixture
def upstream():
    server = socketserver.TCPServer((LOOP, 0), _Health)
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
        cert_dir=tmp_path / "state",
        san_names=names,
        ip_source=lambda: ips,
    )


def test_store_layout_public_has_only_ca_and_sums(tmp_path, upstream):
    proxy = _make(tmp_path, upstream)
    proxy.ensure_certificate()
    pki = proxy.pki
    pub = sorted(p.name for p in pki.public_dir.iterdir())
    assert pub == sorted([pki.ca_public_path.name, "SHA256SUMS"])
    for p in pki.public_dir.iterdir():
        assert b"PRIVATE" not in p.read_bytes()
    digest = hashlib.sha256(pki.ca_public_path.read_bytes()).hexdigest()
    assert pki.sums_path.read_text() == f"{digest}  {pki.ca_public_path.name}\n"
    assert pki.ca_public_path.name.startswith("orama-lan-ca-")
    priv = {p.name for p in pki.private_dir.iterdir()}
    assert {"ca.key", "leaf.key", "leaf.pem", "ca-pin.json"} <= priv


def test_certificate_profile(tmp_path, upstream):
    from cryptography import x509
    from cryptography.x509.oid import ExtendedKeyUsageOID

    proxy = _make(tmp_path, upstream)
    proxy.ensure_certificate()
    ca = x509.load_pem_x509_certificate(proxy.pki.ca_public_path.read_bytes())
    chain = x509.load_pem_x509_certificates(proxy.pki.leaf_chain_path.read_bytes())
    leaf = chain[0]
    assert len(chain) == 2 and chain[1] == ca
    bc = ca.extensions.get_extension_for_class(x509.BasicConstraints)
    assert bc.critical and bc.value.ca and bc.value.path_length == 0
    ku = ca.extensions.get_extension_for_class(x509.KeyUsage)
    assert ku.critical and ku.value.key_cert_sign and ku.value.crl_sign
    ca.extensions.get_extension_for_class(x509.SubjectKeyIdentifier)
    assert "Orama LAN Control Plane CA (" in ca.subject.rfc4514_string()
    assert 700 <= (ca.not_valid_after_utc - ca.not_valid_before_utc).days <= 740
    lbc = leaf.extensions.get_extension_for_class(x509.BasicConstraints)
    assert lbc.critical and not lbc.value.ca
    lku = leaf.extensions.get_extension_for_class(x509.KeyUsage)
    assert lku.critical and lku.value.digital_signature and lku.value.key_encipherment
    eku = leaf.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    assert list(eku) == [ExtendedKeyUsageOID.SERVER_AUTH]
    leaf.extensions.get_extension_for_class(x509.SubjectKeyIdentifier)
    leaf.extensions.get_extension_for_class(x509.AuthorityKeyIdentifier)
    assert 29 <= (leaf.not_valid_after_utc - leaf.not_valid_before_utc).days <= 31


def test_leaf_rotated_under_seven_days_ca_unchanged(tmp_path, upstream, monkeypatch, caplog):
    from orchestrator import lan_control_plane_pki as pki_mod

    first = _make(tmp_path, upstream)
    first.ensure_certificate()
    ca_fp, leaf_fp = first.fingerprint, first.pki.leaf_fingerprint
    real = pki_mod._utc_after

    def fake(cert):  # the leaf (not the self-signed CA) has 3 days left
        out = real(cert)
        return out if cert.subject == cert.issuer else out - timedelta(days=27)

    monkeypatch.setattr(pki_mod, "_utc_after", fake)
    with caplog.at_level("INFO"):
        second = _make(tmp_path, upstream)
        second.ensure_certificate()
    assert second.pki.leaf_event == "rotated"
    assert second.fingerprint == ca_fp and second.pki.leaf_fingerprint != leaf_fp
    assert any("rotated" in r.getMessage() for r in caplog.records)


def test_verifies_with_python_strict_x509_over_live_handshake(tmp_path, upstream):
    proxy = _make(tmp_path, upstream, ips=(LOOP, NET_A))
    url = proxy.start()
    time.sleep(0.2)
    try:
        ctx = ssl.create_default_context(cafile=str(proxy.pki.ca_public_path))
        assert ctx.check_hostname and ctx.verify_mode == ssl.CERT_REQUIRED
        if hasattr(ssl, "VERIFY_X509_STRICT"):
            ctx.verify_flags |= ssl.VERIFY_X509_STRICT
            assert ctx.verify_flags & ssl.VERIFY_X509_STRICT
        with urllib.request.urlopen(f"{url}/health", timeout=5, context=ctx) as resp:
            assert resp.status == 200 and b'"ok"' in resp.read()
        # Name-based verification (SAN DNS) is strict-clean too.
        with socket.create_connection((LOOP, proxy.proxy_port), timeout=5) as raw:
            with ctx.wrap_socket(raw, server_hostname="portal.example.test") as tls:
                assert tls.getpeercert()["subject"]
    finally:
        proxy.stop()


def test_ca_swap_is_refused_exit_3(tmp_path, capsys):
    state = tmp_path / "state"
    assert portal.main(["--print-fingerprint", "--state-dir", str(state)]) == 0
    other = tmp_path / "other"
    assert portal.main(["--print-fingerprint", "--state-dir", str(other)]) == 0
    capsys.readouterr()
    for name in ("ca.crt", "ca.key"):
        (state / "private" / name).write_bytes((other / "private" / name).read_bytes())
    assert portal.main(["--print-fingerprint", "--state-dir", str(state)]) == 3


def test_cannot_start_exit_2_when_port_is_taken(tmp_path, upstream):
    with socket.socket() as busy:
        busy.bind((LOOP, 0))
        busy.listen(1)
        rc = portal.main([
            "--listen-host", LOOP, "--listen-port", str(busy.getsockname()[1]),
            "--upstream-port", str(upstream), "--state-dir", str(tmp_path / "s"),
        ])
    assert rc == 2


# --- WebSocket pass-through ---------------------------------------------------

def _ws_upstream():
    """Raw-socket upstream: completes a WebSocket-style 101 and echoes bytes."""
    srv = socket.socket()
    srv.bind((LOOP, 0))
    srv.listen(5)
    heads: list = []

    def handle(c):
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = c.recv(4096)
            if not chunk:
                c.close()
                return
            buf += chunk
        heads.append(buf)
        c.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                  b"Connection: Upgrade\r\n\r\n")
        try:
            while True:
                data = c.recv(4096)
                if not data:
                    break
                c.sendall(data)
        except OSError:
            pass
        finally:
            c.close()

    def serve():
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            threading.Thread(target=handle, args=(conn,), daemon=True).start()

    threading.Thread(target=serve, daemon=True).start()
    return srv, heads


def _ws_client(proxy):
    ctx = ssl.create_default_context(cafile=str(proxy.pki.ca_public_path))
    tls = ctx.wrap_socket(socket.create_connection((LOOP, proxy.proxy_port), timeout=5),
                          server_hostname=LOOP)
    tls.sendall(b"GET /ws HTTP/1.1\r\nHost: x\r\nConnection: keep-alive, Upgrade\r\n"
                b"Upgrade: websocket\r\nAuthorization: Bearer ws-marker\r\n"
                b"Sec-WebSocket-Key: dGVzdA==\r\nSec-WebSocket-Version: 13\r\n\r\n")
    return tls


def _read_until(tls, marker):
    buf = b""
    while marker not in buf:
        chunk = tls.recv(4096)
        if not chunk:
            break
        buf += chunk
    return buf


def test_websocket_upgrade_passthrough_echo(tmp_path):
    srv, heads = _ws_upstream()
    proxy = _make(tmp_path, srv.getsockname()[1])
    proxy.start()
    try:
        tls = _ws_client(proxy)
        assert _read_until(tls, b"\r\n\r\n").startswith(b"HTTP/1.1 101")
        tls.sendall(b"hello-bytes")
        assert _read_until(tls, b"hello-bytes").endswith(b"hello-bytes")
        tls.sendall(b"second")
        assert _read_until(tls, b"second").endswith(b"second")
        assert heads[0].startswith(b"GET /ws HTTP/1.1\r\n")
        assert b"Authorization: Bearer ws-marker" in heads[0]
        tls.close()
    finally:
        proxy.stop()
        srv.close()


def test_websocket_idle_timeout_closes_tunnel(tmp_path):
    srv, _ = _ws_upstream()
    proxy = _make(tmp_path, srv.getsockname()[1])
    proxy.ws_idle_timeout = 1.5
    proxy.start()
    try:
        tls = _ws_client(proxy)
        assert _read_until(tls, b"\r\n\r\n").startswith(b"HTTP/1.1 101")
        tls.settimeout(8)
        start = time.monotonic()
        try:
            data = tls.recv(10)
        except (ssl.SSLError, OSError):
            data = b""
        assert data == b"" and time.monotonic() - start < 7
    finally:
        proxy.stop()
        srv.close()
