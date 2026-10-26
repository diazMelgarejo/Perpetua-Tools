"""Connection-level telemetry of the TLS front end: metadata only, never request content.

Live handshakes against a real proxy and a fake upstream on derived loopback. The proxy
used to discard failed handshakes at DEBUG and log nothing per request, so an attempt that
never completed left no trace on the host that was supposed to receive it.
"""
from __future__ import annotations

import http.server
import ipaddress
import logging
import socket
import socketserver
import ssl
import threading
import time

import pytest

from orchestrator import alphaclaw_tls_proxy as base
from orchestrator import portal_tls_proxy as portal

pytestmark = pytest.mark.skipif(
    not base._CRYPTOGRAPHY_AVAILABLE, reason="'cryptography' library not installed"
)

LOOP = str(ipaddress.IPv4Address((127 << 24) | 1))
SECRET_HEADER_VALUE = "telemetry-test-credential-value"
LOGGER = "orchestrator.alphaclaw_tls_proxy"


class _Upstream(http.server.BaseHTTPRequestHandler):
    """Fake Portal answering 200 with a small JSON body."""

    def do_GET(self) -> None:
        """Answer every GET with a fixed body."""
        body = b'{"ok": true}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # noqa: A002
        """Silence the default request logging."""


class _FragmentedWebSocketUpstream(socketserver.BaseRequestHandler):
    """Return an HTTP status split inside its three-digit code."""

    def handle(self) -> None:
        """Read the tunnel request and split the response status over two socket writes."""
        self.request.recv(4096)
        self.request.sendall(b"HTTP/1.1 2")
        time.sleep(0.05)
        self.request.sendall(b"00 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")


class _EchoWebSocketUpstream(socketserver.BaseRequestHandler):
    """Accept the upgrade with a 101, then echo every byte the client sends."""

    RESPONSE = b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n"

    def handle(self) -> None:
        """Read the tunnel request, answer 101, then echo until the client closes."""
        self.request.recv(4096)
        self.request.sendall(self.RESPONSE)
        while True:
            data = self.request.recv(4096)
            if not data:
                return
            self.request.sendall(data)


@pytest.fixture
def running_proxy(tmp_path):
    """A started Portal TLS proxy in front of the fake upstream; yields (proxy, ca_path)."""
    server = socketserver.TCPServer((LOOP, 0), _Upstream)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with socket.socket() as s:
        s.bind((LOOP, 0))
        port = s.getsockname()[1]
    proxy = portal.build_portal_proxy(
        listen_port=port, upstream_port=server.server_address[1], listen_host=LOOP,
        cert_dir=tmp_path / "state", san_names=("portal.example.test",), ip_source=lambda: (LOOP,),
    )
    proxy.start()
    yield proxy, proxy.pki.ca_public_path
    proxy.stop()
    server.shutdown()
    server.server_close()


def _conn_lines(caplog, needle: str, timeout: float = 5.0) -> list:
    """Wait for telemetry lines containing ``needle`` (the proxy logs from its own threads)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        hits = [r.getMessage() for r in caplog.records if "conn remote=" in r.getMessage() and needle in r.getMessage()]
        if hits:
            return hits
        time.sleep(0.05)
    return []


def test_served_request_logs_one_metadata_line_and_no_request_content(running_proxy, caplog):
    """A served GET leaves remote, outcome, method, status, byte counts and durations, and no header, path or credential."""
    proxy, ca = running_proxy
    caplog.set_level(logging.INFO, logger=LOGGER)
    ctx = ssl.create_default_context(cafile=str(ca))
    with socket.create_connection((LOOP, proxy.proxy_port), timeout=8) as raw:
        with ctx.wrap_socket(raw, server_hostname=LOOP) as tls:
            request = (
                "GET /api/secret-path-segment HTTP/1.1\r\nHost: x\r\n"
                f"Authorization: Bearer {SECRET_HEADER_VALUE}\r\nConnection: close\r\n\r\n"
            )
            tls.sendall(request.encode("ascii"))
            while tls.recv(4096):
                pass
    lines = _conn_lines(caplog, "outcome=served")
    assert lines, "no telemetry line for the served request"
    line = lines[0]
    assert "method=GET" in line and "status=200" in line
    assert "bytes_up=0" in line and "bytes_down=" in line and "bytes_down=0" not in line
    assert "hs_ms=" in line and "dur_ms=" in line
    everything = " ".join(r.getMessage() for r in caplog.records)
    for forbidden in (SECRET_HEADER_VALUE, "Authorization", "secret-path-segment", "Bearer"):
        assert forbidden not in everything


def test_failed_handshake_is_visible_with_the_error_class_only(running_proxy, caplog):
    """A client that speaks plain HTTP to the TLS port is recorded as handshake_failed (previously a DEBUG-only discard)."""
    proxy, _ca = running_proxy
    caplog.set_level(logging.INFO, logger=LOGGER)
    with socket.create_connection((LOOP, proxy.proxy_port), timeout=8) as raw:
        raw.sendall(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
        raw.settimeout(5)
        try:
            raw.recv(1024)
        except OSError:
            pass
    lines = _conn_lines(caplog, "outcome=handshake_failed")
    assert lines, "a failed handshake left no trace"
    assert "error=SSLError" in lines[0] and "hs_ms=" in lines[0]
    assert "GET /" not in " ".join(r.getMessage() for r in caplog.records)


def test_handshake_without_a_request_is_recorded_as_no_request(running_proxy, caplog):
    """A client that completes TLS and sends nothing is visible as no_request, not silence."""
    proxy, ca = running_proxy
    caplog.set_level(logging.INFO, logger=LOGGER)
    ctx = ssl.create_default_context(cafile=str(ca))
    with socket.create_connection((LOOP, proxy.proxy_port), timeout=8) as raw:
        with ctx.wrap_socket(raw, server_hostname=LOOP):
            # Linger so the server finishes the handshake; closing instantly aborts it, which is
            # a different (and also recorded) outcome: handshake_failed.
            time.sleep(0.5)
    lines = _conn_lines(caplog, "outcome=no_request")
    assert lines, "a connection that never sent a request left no trace"
    assert "status=" not in lines[0]


def test_unsupported_method_is_recorded_with_its_error_status(running_proxy, caplog):
    """A method the handler does not implement gets a 501 from the base class; that is not no_request."""
    proxy, ca = running_proxy
    caplog.set_level(logging.INFO, logger=LOGGER)
    ctx = ssl.create_default_context(cafile=str(ca))
    with socket.create_connection((LOOP, proxy.proxy_port), timeout=8) as raw:
        with ctx.wrap_socket(raw, server_hostname=LOOP) as tls:
            tls.sendall(b"BREW / HTTP/1.1\nHost: x\nConnection: close\n\n")
            while tls.recv(4096):
                pass
    lines = _conn_lines(caplog, "outcome=served")
    assert lines, "a rejected request was recorded as no_request"
    assert "status=501" in lines[0]


def test_declined_websocket_upgrade_records_the_upstream_status_not_101(running_proxy, caplog):
    """When the upstream answers an Upgrade request with a plain 200, the line says 200, never a fixed 101."""
    proxy, ca = running_proxy
    caplog.set_level(logging.INFO, logger=LOGGER)
    ctx = ssl.create_default_context(cafile=str(ca))
    with socket.create_connection((LOOP, proxy.proxy_port), timeout=8) as raw:
        with ctx.wrap_socket(raw, server_hostname=LOOP) as tls:
            tls.sendall(
                b"GET /ws HTTP/1.1\nHost: x\nConnection: Upgrade\nUpgrade: websocket\n\n"
            )
            tls.settimeout(5)
            try:
                while tls.recv(4096):
                    pass
            except OSError:
                pass
    lines = _conn_lines(caplog, "outcome=served")
    assert lines, "the tunnelled request left no telemetry line"
    assert "status=200" in lines[0] and "status=101" not in lines[0]


def test_fragmented_websocket_status_is_recorded_after_all_digits(tmp_path, caplog):
    """A response split at ``HTTP/1.1 2`` is recorded as 200, rather than 2 or no_request."""
    server = socketserver.TCPServer((LOOP, 0), _FragmentedWebSocketUpstream)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with socket.socket() as s:
        s.bind((LOOP, 0))
        port = s.getsockname()[1]
    proxy = portal.build_portal_proxy(
        listen_port=port, upstream_port=server.server_address[1], listen_host=LOOP,
        cert_dir=tmp_path / "state", san_names=("portal.example.test",), ip_source=lambda: (LOOP,),
    )
    proxy.start()
    caplog.set_level(logging.INFO, logger=LOGGER)
    ctx = ssl.create_default_context(cafile=str(proxy.pki.ca_public_path))
    try:
        with socket.create_connection((LOOP, proxy.proxy_port), timeout=8) as raw:
            with ctx.wrap_socket(raw, server_hostname=LOOP) as tls:
                tls.sendall(b"GET /ws HTTP/1.1\nHost: x\nConnection: Upgrade\nUpgrade: websocket\n\n")
                while tls.recv(4096):
                    pass
        lines = _conn_lines(caplog, "outcome=served")
        assert lines, "the fragmented tunnelled response left no telemetry line"
        assert "status=200" in lines[0] and "status=2 " not in lines[0]
    finally:
        proxy.stop()
        server.shutdown()
        server.server_close()


def test_websocket_tunnel_counts_relayed_bytes_in_both_directions(tmp_path, caplog):
    """The connection line reports the payload bytes actually relayed up and down, not zero."""
    server = socketserver.TCPServer((LOOP, 0), _EchoWebSocketUpstream)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with socket.socket() as s:
        s.bind((LOOP, 0))
        port = s.getsockname()[1]
    proxy = portal.build_portal_proxy(
        listen_port=port, upstream_port=server.server_address[1], listen_host=LOOP,
        cert_dir=tmp_path / "state", san_names=("portal.example.test",), ip_source=lambda: (LOOP,),
    )
    proxy.start()
    caplog.set_level(logging.INFO, logger=LOGGER)
    ctx = ssl.create_default_context(cafile=str(proxy.pki.ca_public_path))
    payload = b"0123456789"
    response = _EchoWebSocketUpstream.RESPONSE
    try:
        with socket.create_connection((LOOP, proxy.proxy_port), timeout=8) as raw:
            with ctx.wrap_socket(raw, server_hostname=LOOP) as tls:
                tls.settimeout(5)
                tls.sendall(b"GET /ws HTTP/1.1\r\nHost: x\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\r\n")
                received = b""
                while len(received) < len(response):
                    received += tls.recv(4096)
                tls.sendall(payload)
                echoed = b""
                while len(echoed) < len(payload):
                    echoed += tls.recv(4096)
        lines = _conn_lines(caplog, "outcome=served")
        assert lines, "the tunnelled request left no telemetry line"
        assert f"bytes_up={len(payload)}" in lines[0]
        assert f"bytes_down={len(response) + len(payload)}" in lines[0]
    finally:
        proxy.stop()
        server.shutdown()
        server.server_close()


def test_rate_limit_drops_excess_lines_and_reports_the_count(caplog):
    """Past the burst, lines are dropped (an open port cannot flood the log); the next written line reports how many."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    limiter = base._ConnectionTelemetry(burst=2, per_second=0.0)
    for _ in range(5):
        limiter.record("test", ("203.0.113.9", 1234), "served", status=200)
    written = [r.getMessage() for r in caplog.records if "conn remote=" in r.getMessage()]
    assert len(written) == 2
    limiter._tokens = 1.0  # a refill
    limiter.record("test", ("203.0.113.9", 1234), "served", status=200)
    last = [r.getMessage() for r in caplog.records if "conn remote=" in r.getMessage()][-1]
    assert "suppressed_before=3" in last
