"""Regression tests for the Portal TLS front end review findings.

All addresses are loopback (derived via helpers) or TEST-NET documentation
addresses; no real network is touched.
"""
from __future__ import annotations

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
NAME = "portal.example.test"


class _Scripted(http.server.BaseHTTPRequestHandler):
    hits: list = []

    def do_GET(self) -> None:
        type(self).hits.append(self.path)
        if self.path == "/protected":
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Bearer realm="portal"')
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "unauthorized"}')
        elif self.path == "/redir":
            self.send_response(302)
            self.send_header("Location", f"http://{NET_A}:9/elsewhere")
            self.end_headers()
        else:
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, *args) -> None:  # noqa: A002
        pass


@pytest.fixture
def upstream():
    _Scripted.hits = []
    server = socketserver.TCPServer((LOOP, 0), _Scripted)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind((LOOP, 0))
        return s.getsockname()[1]


def _make(tmp_path, upstream_port):
    return portal.build_portal_proxy(
        listen_port=_free_port(),
        upstream_port=upstream_port,
        listen_host=LOOP,
        cert_dir=tmp_path / "portal_tls",
        san_names=(NAME,),
        ip_source=lambda: (LOOP,),
    )


def _ctx(proxy):
    return ssl.create_default_context(cafile=str(proxy.pki.ca_public_path))


class _NoFollow(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def test_idle_tcp_connection_does_not_block_other_clients(tmp_path, upstream):
    proxy = _make(tmp_path, upstream)
    url = proxy.start()
    try:
        idle = socket.create_connection((LOOP, proxy.proxy_port), timeout=5)
        try:
            started = time.monotonic()
            with urllib.request.urlopen(f"{url}/health", timeout=5, context=_ctx(proxy)) as r:
                assert r.status == 200
            assert time.monotonic() - started < 3.0
        finally:
            idle.close()
    finally:
        proxy.stop()


def test_upstream_401_headers_reach_the_client(tmp_path, upstream):
    proxy = _make(tmp_path, upstream)
    url = proxy.start()
    try:
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"{url}/protected", timeout=5, context=_ctx(proxy))
        assert exc.value.code == 401
        assert exc.value.headers.get("WWW-Authenticate") == 'Bearer realm="portal"'
        assert exc.value.headers.get("Content-Type") == "application/json"
        assert b"unauthorized" in exc.value.read()
    finally:
        proxy.stop()


def test_upstream_redirect_is_relayed_not_followed(tmp_path, upstream):
    proxy = _make(tmp_path, upstream)
    url = proxy.start()
    try:
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=_ctx(proxy)), _NoFollow
        )
        req = urllib.request.Request(
            f"{url}/redir", headers={"Authorization": "Bearer test-marker-not-a-secret"}
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            opener.open(req, timeout=5)
        assert exc.value.code == 302
        assert exc.value.headers.get("Location") == f"http://{NET_A}:9/elsewhere"
        assert _Scripted.hits == ["/redir"]  # the redirect target is never contacted
    finally:
        proxy.stop()


def test_websocket_tunnel_survives_a_slow_reading_client(tmp_path):
    total = 16 * 1024 * 1024
    srv = socket.socket()
    srv.bind((LOOP, 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    sent = {"n": 0, "err": None}

    def serve() -> None:
        conn, _ = srv.accept()
        try:
            buf = b""
            while b"\r\n\r\n" not in buf:
                buf += conn.recv(4096)
            conn.sendall(
                b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                b"Connection: Upgrade\r\n\r\n"
            )
            block = b"x" * 65536
            while sent["n"] < total:
                conn.sendall(block)
                sent["n"] += len(block)
        except OSError as exc:
            sent["err"] = exc
        finally:
            conn.close()

    threading.Thread(target=serve, daemon=True).start()
    proxy = _make(tmp_path, port)
    proxy.start()
    try:
        with socket.create_connection((LOOP, proxy.proxy_port), timeout=30) as raw:
            with _ctx(proxy).wrap_socket(raw, server_hostname=NAME) as tls:
                tls.sendall(
                    b"GET /ws HTTP/1.1\r\nHost: portal.example.test\r\n"
                    b"Connection: Upgrade\r\nUpgrade: websocket\r\n\r\n"
                )
                time.sleep(3.0)  # fall behind well past the old 1 s socket timeout
                got = 0
                while True:
                    data = tls.recv(1 << 16)
                    if not data:
                        break
                    got += len(data)
        assert sent["err"] is None
        assert got >= total  # payload plus the 101 head, nothing lost
    finally:
        proxy.stop()
        srv.close()


def test_concurrent_first_starts_agree_on_one_ca(tmp_path):
    state = tmp_path / "concurrent"
    results: list = []
    errors: list = []

    def run() -> None:
        try:
            p = portal.build_portal_proxy(
                listen_port=1, upstream_port=1, listen_host=LOOP, cert_dir=state,
                san_names=(NAME,), ip_source=lambda: (LOOP,),
            )
            p.ensure_certificate()
            results.append(p.pki.ca_file_sha256)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(180)
    assert not errors
    assert len(results) == 4 and len(set(results)) == 1
    sums = (state / "public" / "SHA256SUMS").read_text(encoding="ascii")
    assert results[0] in sums
    names = [p.name for p in (state / "public").iterdir()]
    assert len(names) == 2 and "SHA256SUMS" in names  # no leftover temp files


@pytest.mark.parametrize("content", ["", "{not json", "[]", '{"ca_fingerprint": "zz"}'])
def test_corrupt_pin_file_fails_closed(tmp_path, upstream, content):
    proxy = _make(tmp_path, upstream)
    proxy.ensure_certificate()
    pin = proxy.pki.pin_path
    pin.write_text(content, encoding="utf-8")
    again = _make(tmp_path, upstream)
    with pytest.raises(base.AlphaClawCertFingerprintMismatch):
        again.ensure_certificate()
    assert pin.read_text(encoding="utf-8") == content  # never silently re-pinned


def test_running_proxy_applies_a_renewed_leaf(tmp_path, upstream):
    proxy = _make(tmp_path, upstream)
    proxy.pki_recheck_seconds = 0.2
    proxy.start()
    try:
        before = proxy.pki.leaf_fingerprint
        proxy.pki.leaf_chain_path.unlink()  # force a reissue on the next recheck
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and proxy.pki.leaf_fingerprint == before:
            time.sleep(0.1)
        assert proxy.pki.leaf_fingerprint != before
        time.sleep(0.5)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((LOOP, proxy.proxy_port), timeout=5) as raw:
            with ctx.wrap_socket(raw, server_hostname=LOOP) as tls:
                import hashlib

                seen = hashlib.sha256(tls.getpeercert(binary_form=True)).hexdigest()
        assert seen == proxy.pki.leaf_fingerprint
    finally:
        proxy.stop()
