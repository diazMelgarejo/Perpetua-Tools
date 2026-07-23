"""orchestrator/alphaclaw_tls_proxy.py -- Perpetua-Tools

Full-featured (v1-scoped) HTTPS-in-front-of-AlphaClaw local reverse proxy,
wired into orchestrator/alphaclaw_manager.py's own gateway-resolution flow
(see bootstrap_alphaclaw() / _maybe_wrap_gateway_with_tls() there). This
module never resolves AlphaClaw's own address or decides whether to run --
alphaclaw_manager.py owns both, matching its documented architecture
invariant. This module only knows how to: generate/persist a self-signed
cert, pin its fingerprint (TOFU), and terminate TLS in front of a given
upstream port.

AlphaClaw (Node.js/Express) has no native HTTPS -- it runs its internal
HTTP server on loopback only. This is the PT-authoritative answer to "how
does a bearer token ever reach AlphaClaw over TLS".

Scope note: certificate rotation policy beyond a fixed 365-day expiry,
mTLS, and admin-pinned (as opposed to TOFU-only) fingerprints remain
deferred to the full plan -- see "Companion plan" below. What IS real
here: certificate persistence across restarts (a fresh cert every process
start would make TOFU pinning meaningless -- the whole point of pinning
is noticing when the cert *changes*), and fingerprint mismatch detection.

Companion plan (full design, deferred): orama-system
docs/v2/49-peer-mesh-auth-tls-v2-plan.md. This module implements plan
section A.1 (certificate provisioning: Option C, auto-generated + TOFU)
and A.2 (the AlphaClaw HTTPS gap), reconciled into orchestrator/ rather
than the plan's original standalone-package sketch -- see
docs/next/2026-07-24-alphaclaw-tls-proxy-scaffolding.md for why.
Companion PR: orama-system PR stacked on #197, same 3 ingested docs.
"""
from __future__ import annotations

import hashlib
import http.server
import json
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
CERT_VALIDITY_DAYS = 365
_MIN_REMAINING_DAYS_TO_REUSE = 7  # rotate proactively, not right at expiry


class AlphaClawTlsUnavailable(RuntimeError):
    """Raised when the proxy cannot start (missing 'cryptography', bind
    failure, etc). Callers must treat this as "HTTPS isn't available right
    now" and fall back to their own existing behavior -- never silently
    downgrade a bearer-token request to plain HTTP on this exception; the
    caller decides whether that's acceptable, this module doesn't."""


class AlphaClawCertFingerprintMismatch(RuntimeError):
    """Raised when the proxy's certificate fingerprint no longer matches
    the previously-pinned (TOFU) value. This is the MITM-detection signal
    the whole point of pinning exists for -- callers must NOT silently
    accept the new cert; surface this to the operator."""


def _cert_fingerprint(cert_path: Path) -> str:
    """SHA-256 fingerprint of the certificate's DER bytes."""
    if not _CRYPTOGRAPHY_AVAILABLE:
        raise AlphaClawTlsUnavailable("'cryptography' library not available")
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    return hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()


def _fingerprint_store_path() -> Path:
    """Computed fresh from CERT_DIR each call, not cached at import time --
    tests (and any future caller) that override CERT_DIR after import must
    see that override reflected here, not a stale path baked in earlier."""
    return CERT_DIR / "fingerprint.json"


def _load_pinned_fingerprint() -> Optional[str]:
    store = _fingerprint_store_path()
    if not store.is_file():
        return None
    try:
        data = json.loads(store.read_text(encoding="utf-8"))
        return data.get("fingerprint")
    except (json.JSONDecodeError, OSError):
        return None


def _store_pinned_fingerprint(fingerprint: str) -> None:
    store = _fingerprint_store_path()
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(
        json.dumps(
            {"fingerprint": fingerprint, "pinned_at": datetime.now(timezone.utc).isoformat()},
            indent=2,
        ),
        encoding="utf-8",
    )


def verify_or_pin_fingerprint(cert_path: Path) -> str:
    """TOFU: pin the fingerprint on first sight; on every later call,
    verify it hasn't changed. Raises AlphaClawCertFingerprintMismatch if
    it has -- this is a MITM-detection signal, not a routine event, and
    must never be silently auto-repinned by this function.

    Returns the current (verified-or-newly-pinned) fingerprint.
    """
    current = _cert_fingerprint(cert_path)
    pinned = _load_pinned_fingerprint()
    if pinned is None:
        _store_pinned_fingerprint(current)
        _log.info("AlphaClaw TLS: pinned certificate fingerprint (first sight): %s...", current[:16])
        return current
    if pinned != current:
        raise AlphaClawCertFingerprintMismatch(
            f"AlphaClaw TLS certificate fingerprint changed: pinned={pinned[:16]}... "
            f"current={current[:16]}... This may mean the cert was legitimately "
            "rotated (e.g. after CERT_DIR was cleared) or may indicate a MITM "
            "attack. Verify out-of-band, then delete "
            f"{_fingerprint_store_path()} to accept the new certificate explicitly -- "
            "this is never done automatically."
        )
    return current


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
    fingerprint: str = ""

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

        # Reuse an existing, still-valid certificate rather than generating
        # a fresh one every process start -- TOFU fingerprint pinning is
        # meaningless if the pinned value changes on every restart. Only
        # regenerate when the cert is missing or genuinely close to expiry.
        if cert_path.is_file() and key_path.is_file():
            try:
                existing = x509.load_pem_x509_certificate(cert_path.read_bytes())
                remaining = existing.not_valid_after_utc - datetime.now(timezone.utc)
                if remaining.days > _MIN_REMAINING_DAYS_TO_REUSE:
                    _log.debug(
                        "AlphaClaw TLS: reusing existing certificate (expires in %d days)",
                        remaining.days,
                    )
                    return cert_path, key_path
                _log.info(
                    "AlphaClaw TLS: existing certificate expires in %d days, regenerating",
                    remaining.days,
                )
            except (ValueError, OSError) as exc:
                _log.warning("AlphaClaw TLS: existing certificate unreadable (%s), regenerating", exc)

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
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=CERT_VALIDITY_DAYS))
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

        Verifies the certificate's fingerprint against the TOFU-pinned
        value before binding -- raises AlphaClawCertFingerprintMismatch
        rather than silently serving a changed certificate. Callers that
        want to run without pinning (e.g. tests, or an explicit operator
        override) should catch that exception themselves; this method
        never suppresses it.

        Returns the https:// URL callers should use in place of the
        AlphaClaw HTTP URL.
        """
        cert_path, key_path = self._generate_cert()
        self.fingerprint = verify_or_pin_fingerprint(cert_path)

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
