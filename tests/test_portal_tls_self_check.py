"""The ``--self-check`` evidence gate of the Portal TLS front end.

Live handshakes against a real proxy and a fake upstream on derived loopback;
unreachable hosts use TEST-NET documentation addresses.
"""
from __future__ import annotations

import http.server
import ipaddress
import socket
import socketserver
import threading

import pytest

from orchestrator import alphaclaw_tls_proxy as base
from orchestrator import portal_tls_proxy as portal

pytestmark = pytest.mark.skipif(
    not base._CRYPTOGRAPHY_AVAILABLE, reason="'cryptography' library not installed"
)

LOOP = str(ipaddress.IPv4Address((127 << 24) | 1))
ANY = str(ipaddress.IPv4Address(0))
NET_A = "192.0.2.10"
NET_B = "198.51.100.20"


class _Upstream(http.server.BaseHTTPRequestHandler):
    """Fake Portal: /health is 200; /api/peer-inbox is 401 unless leaky."""

    seen: list = []
    leaky = False

    def do_GET(self) -> None:
        """Record the request headers and answer by path."""
        type(self).seen.append(dict(self.headers.items()))
        if self.path == "/health":
            status = 200
        elif self.path == "/api/peer-inbox":
            status = 200 if type(self).leaky else 401
        else:
            status = 404
        body = b"{}"
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # noqa: A002
        """Silence the default request logging."""


def _serve(bind: str):
    """Start the fake upstream on ``bind``; return the server."""
    _Upstream.seen = []
    _Upstream.leaky = False
    server = socketserver.TCPServer((bind, 0), _Upstream)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture
def upstream():
    """Fake upstream bound to loopback only; yields its port."""
    server = _serve(LOOP)
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


@pytest.fixture
def no_lan(monkeypatch):
    """Pretend this host has loopback only, so the exposure probe is offline."""
    monkeypatch.setattr(portal, "local_ipv4_addresses", lambda: (LOOP,))


def _free_port() -> int:
    """A currently free loopback TCP port."""
    with socket.socket() as s:
        s.bind((LOOP, 0))
        return s.getsockname()[1]


def _proxy(tmp_path, upstream_port, ips=(LOOP,)):
    """Proxy on loopback with its store under ``tmp_path``."""
    return portal.build_portal_proxy(
        listen_port=_free_port(),
        upstream_port=upstream_port,
        listen_host=LOOP,
        cert_dir=tmp_path / "state",
        san_names=("portal.example.test",),
        ip_source=lambda: ips,
    )


def _run(tmp_path, proxy, upstream_port, capsys, host=LOOP):
    """Run main(--self-check) and return (exit code, parsed output dict)."""
    rc = portal.main([
        "--self-check", "--host", host, "--listen-port", str(proxy.proxy_port),
        "--upstream-port", str(upstream_port), "--state-dir", str(tmp_path / "state"),
    ])
    out = capsys.readouterr().out
    parsed = {}
    for line in out.splitlines():
        key, _, rest = line.partition("=")
        parsed[key] = rest
    return rc, parsed, out


def test_self_check_passes_against_a_healthy_endpoint(tmp_path, upstream, no_lan, capsys):
    """TLS checks PASS, the CA hash is printed and the exit code is 0; with no
    LAN address the exposure probe establishes nothing, so it is WARN."""
    proxy = _proxy(tmp_path, upstream)
    proxy.start()
    try:
        rc, out, text = _run(tmp_path, proxy, upstream, capsys)
    finally:
        proxy.stop()
    assert rc == 0, text
    for name in ("tls_health", "protected_unauth", "leaf_san", "leaf_expiry"):
        assert out[f"check_{name}"].startswith("PASS"), text
    assert out["check_upstream_loopback_only"].startswith("WARN"), text
    assert "notAfter=" in out["check_leaf_expiry"] and "Z " in out["check_leaf_expiry"]
    assert out["self_check"] == "PASS"
    assert out["ca_sha256_file"] == proxy.pki.ca_file_sha256
    assert not any(h.get("Authorization") for h in _Upstream.seen)
    assert _Upstream.seen, "the upstream should have been reached"


def test_self_check_fails_when_peer_inbox_is_open(tmp_path, upstream, no_lan, capsys):
    """An upstream answering 200 on the protected path is a FAIL (exit 1)."""
    proxy = _proxy(tmp_path, upstream)
    proxy.start()
    _Upstream.leaky = True
    try:
        rc, out, text = _run(tmp_path, proxy, upstream, capsys)
    finally:
        proxy.stop()
    assert rc == 1, text
    assert out["check_protected_unauth"].startswith("FAIL")
    assert out["check_tls_health"].startswith("PASS")
    assert out["self_check"] == "FAIL"
    assert not any(h.get("Authorization") for h in _Upstream.seen)


def test_self_check_fails_when_host_is_not_in_the_san(tmp_path, upstream, no_lan,
                                                      monkeypatch, capsys):
    """A host outside the leaf SAN fails the verified handshake and leaf_san."""
    proxy = _proxy(tmp_path, upstream, ips=(LOOP, NET_A))
    proxy.start()
    real = socket.create_connection

    def redirect(address, *args, **kwargs):
        """Send connections for the TEST-NET host to the real loopback proxy."""
        host, port = address
        return real((LOOP if host == NET_B else host, port), *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", redirect)
    try:
        rc, out, text = _run(tmp_path, proxy, upstream, capsys, host=NET_B)
    finally:
        proxy.stop()
    assert rc == 1, text
    assert out["check_leaf_san"].startswith("FAIL")
    assert out["check_tls_health"].startswith("FAIL")
    assert out["self_check"] == "FAIL"
    assert not any(h.get("Authorization") for h in _Upstream.seen)


def test_self_check_fails_when_the_ca_store_is_missing(tmp_path, upstream, no_lan, capsys):
    """A missing store is a clear FAIL, exit 1, and nothing gets created."""
    state = tmp_path / "state"
    rc = portal.main(["--self-check", "--host", LOOP, "--listen-port", str(_free_port()),
                      "--upstream-port", str(upstream), "--state-dir", str(state)])
    text = capsys.readouterr().out
    assert rc == 1
    assert "check_tls_health=FAIL" in text and "CA certificate missing" in text
    assert "self_check=FAIL" in text and "ca_sha256_file=" not in text
    assert not state.exists()


def test_self_check_reports_an_unreachable_host_as_fail(tmp_path, upstream, no_lan,
                                                        monkeypatch, capsys):
    """An unreachable TEST-NET host fails within the shortened timeout."""
    proxy = _proxy(tmp_path, upstream)
    proxy.ensure_certificate()
    monkeypatch.setattr(portal, "_NET_TIMEOUT", 0.5)
    rc, out, text = _run(tmp_path, proxy, upstream, capsys, host=NET_A)
    assert rc == 1, text
    assert out["check_tls_health"].startswith("FAIL")
    assert out["check_protected_unauth"].startswith("FAIL")
    assert out["check_leaf_san"].startswith("FAIL")


def test_self_check_fails_when_upstream_is_exposed_on_a_lan_address(tmp_path, capsys,
                                                                    monkeypatch):
    """An upstream reachable on a non-loopback address is a FAIL naming it."""
    lan = [a for a in portal.local_ipv4_addresses()
           if not ipaddress.ip_address(a).is_loopback]
    if not lan:
        pytest.skip("no non-loopback local address on this host")
    monkeypatch.setattr(portal, "local_ipv4_addresses", lambda: (LOOP, lan[0]))
    server = _serve(ANY)
    try:
        status, detail = portal._check_upstream_loopback_only(server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()
    assert status == "FAIL" and lan[0] in detail


def test_upstream_check_warns_when_nothing_non_loopback_was_probed(monkeypatch):
    """Probing no non-loopback address establishes nothing: WARN, never PASS."""
    monkeypatch.setattr(portal, "local_ipv4_addresses", lambda: (LOOP,))
    status, detail = portal._check_upstream_loopback_only(1)
    assert status == "WARN" and "not established" in detail


def test_upstream_check_counts_only_explicit_refusal_as_safe(monkeypatch):
    """A timeout is inconclusive (WARN); only ConnectionRefusedError is PASS."""
    monkeypatch.setattr(portal, "local_ipv4_addresses", lambda: (LOOP, NET_A))

    def timeout(*_a, **_k):
        """Simulate a probe that never gets an answer."""
        raise socket.timeout("timed out")

    monkeypatch.setattr(socket, "create_connection", timeout)
    status, detail = portal._check_upstream_loopback_only(1)
    assert status == "WARN" and NET_A in detail

    def refused(*_a, **_k):
        """Simulate an explicit refusal from the probed address."""
        raise ConnectionRefusedError()

    monkeypatch.setattr(socket, "create_connection", refused)
    assert portal._check_upstream_loopback_only(1)[0] == "PASS"


def test_older_cli_contract_usage_error_exits_2(capsys):
    """An unknown flag is an argparse error with exit code 2."""
    with pytest.raises(SystemExit) as exc:
        portal.main(["--no-such-flag"])
    assert exc.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


def test_default_host_is_first_non_loopback_else_loopback(monkeypatch):
    """The default target skips loopback and falls back to it when alone."""
    monkeypatch.setattr(portal, "local_ipv4_addresses", lambda: (LOOP, NET_A, NET_B))
    assert portal._default_self_check_host() == NET_A
    monkeypatch.setattr(portal, "local_ipv4_addresses", lambda: (LOOP,))
    assert portal._default_self_check_host() == LOOP


def test_expiry_thresholds_and_san_matching():
    """More than 7 days PASS, within 7 WARN, past FAIL; SAN kinds are matched."""
    from datetime import datetime, timedelta, timezone

    def cert_in(days):
        """A peer-cert dict whose notAfter is ``days`` from now."""
        when = datetime.now(timezone.utc) + timedelta(days=days)
        return {"notAfter": when.strftime("%b %d %H:%M:%S %Y GMT")}

    assert portal._expiry_result(cert_in(20))[0] == "PASS"
    assert portal._expiry_result(cert_in(3))[0] == "WARN"
    assert portal._expiry_result(cert_in(-1))[0] == "FAIL"
    assert portal._expiry_result({})[0] == "FAIL"
    cert = {"subjectAltName": (("DNS", "Portal.Example.Test"), ("IP Address", LOOP))}
    assert portal._san_covers(cert, "portal.example.test")
    assert portal._san_covers(cert, LOOP)
    assert not portal._san_covers(cert, NET_A)
    assert not portal._san_covers({"subjectAltName": (("DNS", LOOP),)}, LOOP)
