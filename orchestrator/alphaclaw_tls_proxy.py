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

Platform limitation, not silently glossed over: file-permission
enforcement (CERT_DIR, the private key, the certificate, and the
fingerprint pin file) uses POSIX mode bits (os.chmod / os.open with an
explicit mode). This restricts access on Linux and macOS. On Windows,
these calls have no meaningful effect -- Windows access control is ACL-
based, not mode-bit-based, and this module does not set any ACL. On
Windows, the private key and pin file are protected only by the OS
default ACL for the user's own profile directory (typically already
excludes other non-administrator local users, but this module makes no
explicit guarantee and applies no additional restriction). Real ACL
enforcement (icacls, or pywin32's security APIs) is not implemented --
tracked as a known gap, not assumed to be covered by the POSIX-oriented
code above.

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
import os
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
    store.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # mkdir's mode= is ignored when the directory already exists (and
    # isn't applied to already-existing intermediate parents) -- a
    # directory from before this permissions fix would keep its original,
    # wider mode. Explicit chmod covers that case unconditionally.
    store.parent.chmod(0o700)
    payload = json.dumps(
        {"fingerprint": fingerprint, "pinned_at": datetime.now(timezone.utc).isoformat()},
        indent=2,
    ).encode("utf-8")
    # Create with the restrictive mode atomically at open time, not via a
    # write-then-chmod sequence -- write-then-chmod leaves a real (if
    # narrow) TOCTOU window on multi-user systems where the file is
    # readable at its default (umask-derived) permissions before the
    # chmod call lands. O_CREAT|O_TRUNC so this still works whether the
    # file is new or being overwritten.
    fd = os.open(str(store), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(payload)


def _cert_not_after_utc(cert: x509.Certificate) -> datetime:
    """Return the certificate expiry as a timezone-aware UTC datetime."""
    not_after = cert.not_valid_after
    if not_after.tzinfo is None:
        return not_after.replace(tzinfo=timezone.utc)
    return not_after.astimezone(timezone.utc)


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

    Binds to 127.0.0.1 ONLY -- never reachable from the LAN. Certificates
    are persisted under CERT_DIR and reused across restarts; fingerprint
    pinning (TOFU) is enforced on start() -- see module docstring.
    """

    upstream_port: int
    proxy_port: int = DEFAULT_PROXY_PORT
    proxy_timeout: float = 60.0
    _server: Optional[socketserver.ThreadingTCPServer] = None
    _thread: Optional[threading.Thread] = None
    fingerprint: str = ""

    def _generate_cert(self) -> tuple[Path, Path, str]:
        """Return cert paths plus how they were obtained.

        Modes:
        - ``reused``: existing on-disk cert is still valid -- caller must
          verify the TOFU pin against it.
        - ``rotated``: we regenerated because the prior cert was near
          expiry -- caller may update the pin (legitimate rotation).
        - ``renewed``: cert was missing or unreadable -- caller must treat
          an existing pin as a mismatch signal (possible tampering).
        """
        if not _CRYPTOGRAPHY_AVAILABLE:
            raise AlphaClawTlsUnavailable(
                "'cryptography' library not available -- cannot generate a "
                "TLS certificate. Install it, or fall back to your own "
                "existing HTTP behavior."
            )
        CERT_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        CERT_DIR.chmod(0o700)  # covers directories that predate this fix
        cert_path = CERT_DIR / "alphaclaw.crt"
        key_path = CERT_DIR / "alphaclaw.key"
        generation_mode = "renewed"

        # Reuse an existing, still-valid certificate rather than generating
        # a fresh one every process start -- TOFU fingerprint pinning is
        # meaningless if the pinned value changes on every restart. Only
        # regenerate when the cert is missing or genuinely close to expiry.
        if cert_path.is_file() and key_path.is_file():
            try:
                existing = x509.load_pem_x509_certificate(cert_path.read_bytes())
                remaining = _cert_not_after_utc(existing) - datetime.now(timezone.utc)
                if remaining.days > _MIN_REMAINING_DAYS_TO_REUSE:
                    _log.debug(
                        "AlphaClaw TLS: reusing existing certificate (expires in %d days)",
                        remaining.days,
                    )
                    # Covers files that predate this permissions fix.
                    key_path.chmod(0o600)
                    cert_path.chmod(0o600)
                    return cert_path, key_path, "reused"
                _log.info(
                    "AlphaClaw TLS: existing certificate expires in %d days, regenerating",
                    remaining.days,
                )
                generation_mode = "rotated"
            except (ValueError, OSError, AttributeError) as exc:
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
        key_bytes = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        # Atomic restrictive-mode creation for the private key -- a
        # write-then-chmod sequence leaves a real (if narrow) TOCTOU
        # window on multi-user systems where the key is readable at its
        # default (umask-derived) permissions before the chmod call
        # lands. The cert itself isn't sensitive, but kept at the same
        # mode immediately after write for consistency (no reason to
        # leave it wider even briefly).
        fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(key_bytes)
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        cert_path.chmod(0o600)
        return cert_path, key_path, generation_mode

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
        cert_path, key_path, generation_mode = self._generate_cert()
        if generation_mode == "rotated":
            current = _cert_fingerprint(cert_path)
            pinned = _load_pinned_fingerprint()
            if pinned is not None and pinned != current:
                _log.warning(
                    "AlphaClaw TLS: certificate rotated due to expiry; "
                    "updating pinned fingerprint from %s... to %s...",
                    pinned[:16],
                    current[:16],
                )
            _store_pinned_fingerprint(current)
            self.fingerprint = current
        elif generation_mode == "renewed" and _load_pinned_fingerprint() is not None:
            # Cert disappeared or became unreadable while a pin still exists.
            # Never silently re-pin -- that would mask cert substitution.
            current = _cert_fingerprint(cert_path)
            pinned = _load_pinned_fingerprint()
            if pinned != current:
                raise AlphaClawCertFingerprintMismatch(
                    f"AlphaClaw TLS certificate fingerprint changed: pinned={pinned[:16]}... "
                    f"current={current[:16]}... Certificate files were missing or "
                    "unreadable and were regenerated. Verify out-of-band, then delete "
                    f"{_fingerprint_store_path()} to accept the new certificate explicitly -- "
                    "this is never done automatically."
                )
            self.fingerprint = current
        else:
            self.fingerprint = verify_or_pin_fingerprint(cert_path)

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(str(cert_path), str(key_path))

        upstream = self.upstream_port
        timeout = self.proxy_timeout
        _HOP_BY_HOP_HEADERS = {
            "connection", "keep-alive", "proxy-authenticate",
            "proxy-authorization", "te", "trailers", "transfer-encoding",
            "upgrade",
        }
        _CHUNK_SIZE = 65536
        _MAX_BODY_SIZE = 100 * 1024 * 1024  # 100MB -- generous for AlphaClaw's own API payloads, bounds a malicious/buggy client's memory impact

        class _ProxyHandler(http.server.BaseHTTPRequestHandler):
            def _read_request_body(self) -> Optional[bytes]:
                """Read the client's request body, handling both
                Content-Length and Transfer-Encoding: chunked framing.

                http.server does not decode chunked request bodies for
                us -- a client sending chunked data (no Content-Length,
                which is legal and something a real HTTP client can
                legitimately do) would previously be silently dropped
                (Content-Length defaulted to 0, so no body was read at
                all, even though real body bytes were sitting on the
                wire). Fully de-chunks into a single buffer here, then
                forwards upstream with an explicit Content-Length --
                correct framing, not a streaming pass-through.

                Raises ValueError on any malformed framing (non-hex chunk
                size, negative/oversized Content-Length, an unexpectedly
                blank chunk-size line) and OSError on a read that comes up
                short (client disconnected mid-chunk) -- both signal a
                genuinely malformed or truncated request. An earlier
                version of this method treated a blank chunk-size line the
                same as the normal zero-size terminator, which silently
                forwarded a truncated body upstream instead of surfacing
                the problem; callers must not treat either exception as
                "no body", only as "this request is broken."
                """
                if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
                    chunks: list[bytes] = []
                    total = 0
                    while True:
                        size_line = self.rfile.readline()
                        if not size_line:
                            # Genuinely empty read (not just an empty chunk
                            # size) means the connection ended mid-frame --
                            # a truncated request, not a valid terminator.
                            raise OSError("connection ended while reading chunk size")
                        size_line = size_line.strip()
                        if not size_line:
                            raise ValueError("blank chunk-size line (malformed chunked framing)")
                        try:
                            chunk_size = int(size_line.split(b";", 1)[0], 16)
                        except ValueError as exc:
                            raise ValueError(f"non-hex chunk size {size_line!r}") from exc
                        if chunk_size < 0:
                            raise ValueError(f"negative chunk size {chunk_size}")
                        if chunk_size == 0:
                            self.rfile.readline()  # trailing CRLF after the 0-size chunk
                            break
                        total += chunk_size
                        if total > _MAX_BODY_SIZE:
                            raise ValueError(f"chunked body exceeds {_MAX_BODY_SIZE} byte limit")
                        data = self.rfile.read(chunk_size)
                        if len(data) != chunk_size:
                            raise OSError(
                                f"incomplete chunk read: expected {chunk_size} bytes, got {len(data)}"
                            )
                        chunks.append(data)
                        self.rfile.readline()  # CRLF after each chunk's data
                    return b"".join(chunks)
                raw_length = self.headers.get("Content-Length")
                if raw_length is None:
                    return None
                try:
                    length = int(raw_length)
                except ValueError as exc:
                    raise ValueError(f"non-numeric Content-Length {raw_length!r}") from exc
                if length < 0:
                    raise ValueError(f"negative Content-Length {length}")
                if length > _MAX_BODY_SIZE:
                    raise ValueError(f"Content-Length {length} exceeds {_MAX_BODY_SIZE} byte limit")
                if length == 0:
                    return None
                data = self.rfile.read(length)
                if len(data) != length:
                    raise OSError(f"incomplete body read: expected {length} bytes, got {len(data)}")
                return data

            def _forward(self, method: str) -> None:
                try:
                    body = self._read_request_body()
                except (ValueError, OSError) as exc:
                    # Malformed framing must never propagate out of this
                    # handler -- an uncaught exception here aborts the
                    # connection via socketserver's own error handling with
                    # no HTTP response at all, degrading a single bad
                    # request into a silent connection drop instead of a
                    # clean, diagnosable 400.
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(f"Malformed request body: {exc}".encode("utf-8"))
                    return
                url = f"http://127.0.0.1:{upstream}{self.path}"
                req = urllib.request.Request(url, method=method, data=body)
                for header, value in self.headers.items():
                    if header.lower() not in ("host", "content-length", "transfer-encoding"):
                        req.add_header(header, value)
                if body is not None:
                    req.add_header("Content-Length", str(len(body)))
                try:
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        self.send_response(resp.status)
                        for header, value in resp.getheaders():
                            # Hop-by-hop headers describe THIS connection's
                            # framing (upstream <-> proxy), not the one the
                            # proxy <-> client connection uses -- forwarding
                            # them verbatim (Transfer-Encoding especially)
                            # would desynchronize the client's framing from
                            # what this handler actually sends below.
                            if header.lower() not in _HOP_BY_HOP_HEADERS:
                                self.send_header(header, value)
                        self.end_headers()
                        # Stream in fixed-size chunks rather than resp.read()
                        # (unconditional full buffering) -- bounds peak
                        # memory for large AlphaClaw responses.
                        while True:
                            chunk = resp.read(_CHUNK_SIZE)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
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
