"""orchestrator/alphaclaw_tls_proxy.py -- Perpetua-Tools

Minimum scaffolding to make HTTPS possible in front of the AlphaClaw
gateway. AlphaClaw (Node.js/Express) has no native HTTPS -- it runs its
internal HTTP server on loopback only. This module is the PT-authoritative
answer to "how does a bearer token ever reach AlphaClaw over TLS": a
local-only HTTPS reverse proxy, self-signed, terminating TLS in front of
AlphaClaw's existing HTTP port.

Scope note (read before extending this file): this is deliberately the
MINIMUM scaffolding, not the full plan. It provides genuine, working
HTTPS termination + forwarding + a fresh self-signed cert per run -- what
it does NOT yet do: fingerprint pinning / TOFU persistence, certificate
rotation policy, mTLS, or wiring into alphaclaw_manager.py's
AlphaClawState.gateway_url by default (that integration, and everything
else deferred, is tracked in the full plan -- see "Companion plan" below).

Architecture invariant this respects (see alphaclaw_manager.py's own
docstring): PT is authoritative for gateway discovery, route choice,
topology, and readiness. This proxy lives in orchestrator/, not a
standalone packages/ package, because the decision of whether/when to run
it is a PT gateway-management decision, not something orama-system or any
other consumer should own independently.

Companion plan (full design, deferred): orama-system
docs/v2/49-peer-mesh-auth-tls-v2-plan.md, section A.2 -- ingests the
original alphaclaw-tls package sketch (there proposed as a standalone
Python package under Perpetua-Tools/packages/) and reconciles it with
this file's actual home in orchestrator/, since alphaclaw_manager.py's
own architecture invariant means gateway-adjacent TLS logic belongs in PT
core, not a separately-versioned package.
Companion PR: orama-system PR (stacked on #197) that ingests the same 3
security-hardening design docs this module implements the PT half of.
"""
from __future__ import annotations

import http.server
import logging
import socketserver
import ssl
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

_log = logging.getLogger(__name__)

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    import ipaddress
    _CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    _CRYPTOGRAPHY_AVAILABLE = False

CERT_DIR = Path.home() / ".openclaw" / "alphaclaw_tls"
DEFAULT_PROXY_PORT = 3345


class AlphaClawTlsUnavailable(RuntimeError):
    """Raised when the proxy cannot start (missing 'cryptography', bind
    failure, etc). Callers must treat this as "HTTPS isn't available right
    now" and fall back to their own existing behavior -- never silently
    downgrade a bearer-token request to plain HTTP on this exception; the
    caller decides whether that's acceptable, this module doesn't."""


@dataclass
class AlphaClawTlsProxy:
    """Local-only HTTPS reverse proxy in front of AlphaClaw's HTTP port.

    Binds to 127.0.0.1 ONLY -- never reachable from the LAN. Generates a
    fresh self-signed certificate on first start each run (no persistence
    or fingerprint pinning yet -- see module docstring's scope note).
    """

    upstream_port: int
    proxy_port: int = DEFAULT_PROXY_PORT
    _server: Optional[socketserver.ThreadingTCPServer] = None
    _thread: Optional[threading.Thread] = None

    def _generate_cert(self) -> tuple[Path, Path]:
        if not _CRYPTOGRAPHY_AVAILABLE:
            raise AlphaClawTlsUnavailable(
                "'cryptography' library not available -- cannot generate a "
                "TLS certificate. Install it, or fall back to your own "
                "existing HTTP behavior."
            )
        CERT_DIR.mkdir(parents=True, exist_ok=True)
        cert_path = CERT_DIR / "alphaclaw.crt"
        key_path = CERT_DIR / "alphaclaw.key"

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]
        )
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName(
                    [
                        x509.DNSName("localhost"),
                        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                    ]
                ),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )
        key_path.write_bytes(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        return cert_path, key_path

    def start(self) -> str:
        """Start the proxy (idempotent-ish: safe to call once; calling
        again while already running raises OSError from the socket bind,
        which is the correct signal -- this class does not track its own
        "already running" state beyond the OS-level port bind).

        Returns the https:// URL callers should use in place of the
        AlphaClaw HTTP URL.
        """
        cert_path, key_path = self._generate_cert()

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(str(cert_path), str(key_path))

        upstream = self.upstream_port

        class _ProxyHandler(http.server.BaseHTTPRequestHandler):
            def _forward(self, method: str) -> None:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length else None
                url = f"http://127.0.0.1:{upstream}{self.path}"
                req = urllib.request.Request(url, method=method, data=body)
                for header, value in self.headers.items():
                    if header.lower() not in ("host", "content-length"):
                        req.add_header(header, value)
                try:
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        self.send_response(resp.status)
                        for header, value in resp.getheaders():
                            self.send_header(header, value)
                        self.end_headers()
                        self.wfile.write(resp.read())
                except urllib.error.HTTPError as exc:
                    self.send_response(exc.code)
                    self.end_headers()
                    self.wfile.write(exc.read())
                except urllib.error.URLError as exc:
                    self.send_response(502)
                    self.end_headers()
                    self.wfile.write(str(exc.reason).encode("utf-8"))

            def do_GET(self) -> None:
                self._forward("GET")

            def do_POST(self) -> None:
                self._forward("POST")

            def do_PUT(self) -> None:
                self._forward("PUT")

            def do_DELETE(self) -> None:
                self._forward("DELETE")

            def log_message(self, fmt: str, *args) -> None:  # noqa: A002
                _log.debug("[alphaclaw-tls-proxy] " + fmt, *args)

        self._server = socketserver.ThreadingTCPServer(
            ("127.0.0.1", self.proxy_port), _ProxyHandler
        )
        self._server.socket = context.wrap_socket(self._server.socket, server_side=True)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        url = f"https://127.0.0.1:{self.proxy_port}"
        _log.info(
            "AlphaClaw TLS proxy started: %s -> http://127.0.0.1:%d",
            url, upstream,
        )
        return url

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
