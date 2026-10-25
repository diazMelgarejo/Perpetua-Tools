"""orchestrator/lan_control_plane_pki.py -- Perpetua-Tools

Local CA plus short-lived leaf for the LAN control plane (Portal TLS front end).

Model (the Mac consolidated contract):

* One dedicated local CA per node (CA:TRUE critical, pathlen 0, keyCertSign +
  cRLSign critical, ~2 years). It is stable across DHCP changes. Its public
  certificate and the SHA-256 of that exact file are what the operator hands
  to a peer over a separate channel; trust stays process-scoped on the peer.
* A 30-day leaf signed by that CA (CA:FALSE, digitalSignature +
  keyEncipherment critical, serverAuth, SKI + AKI). It is reissued
  automatically (and logged) when fewer than 7 days remain, when its SANs no
  longer cover the configured names or the current local addresses, or when it
  was not issued by the current CA. Leaf rotation needs no re-pin.
* The CA certificate fingerprint is pinned locally on first start. A later
  start with a different CA is refused: a CA change is an explicit two-sided
  migration, never an automatic one.

Store layout (outside any checkout)::

    <state_dir>/private/   ca.key ca.crt leaf.key leaf.pem ca-pin.json
    <state_dir>/public/    orama-lan-ca-<hostname>.pem  SHA256SUMS

``private/`` and its files are restricted with the shared ``_secure_path``
helpers. ``public/`` only ever receives the public CA certificate and its
checksum; no private key is ever written there.
"""
from __future__ import annotations

import contextlib
import hashlib
import ipaddress
import json
import logging
import os
import re
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional

from orchestrator.alphaclaw_tls_proxy import (
    _CRYPTOGRAPHY_AVAILABLE,
    AlphaClawCertFingerprintMismatch,
    AlphaClawTlsUnavailable,
    _secure_path,
)

if _CRYPTOGRAPHY_AVAILABLE:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

_log = logging.getLogger(__name__)

CA_VALIDITY_DAYS = 730
LEAF_VALIDITY_DAYS = 30
LEAF_MIN_REMAINING_DAYS = 7
CA_WARN_REMAINING_DAYS = 60
_CLOCK_SKEW = timedelta(minutes=5)
_LOOPBACK_V4 = str(ipaddress.IPv4Address((127 << 24) | 1))


def _utc_after(cert: "x509.Certificate") -> datetime:
    """The certificate's notAfter as a timezone-aware UTC datetime."""
    value = getattr(cert, "not_valid_after_utc", None)
    if value is None:
        value = cert.not_valid_after.replace(tzinfo=timezone.utc)
    return value


def der_sha256(cert: "x509.Certificate") -> str:
    """SHA-256 hex digest of the certificate's DER encoding."""
    return hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()


def _safe_host(name: str) -> str:
    """Make a host name safe for a file name; returns ``node`` when nothing is left."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "-", name).strip(".-")
    return cleaned or "node"


_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_LOCK_WAIT_SECONDS = 60.0


def _write_private(path: Path, data: bytes) -> None:
    """Atomic: write a private temp file next to ``path`` then os.replace it,
    so a concurrent reader never sees a torn file."""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        _secure_path(tmp, is_directory=False)
        os.replace(str(tmp), str(path))
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        if path.exists():
            _secure_path(path, is_directory=False)


def _write_public(path: Path, data: bytes) -> None:
    """Atomically write a public file: temp file next to ``path``, then os.replace."""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_bytes(data)
        os.replace(str(tmp), str(path))
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


@contextlib.contextmanager
def _exclusive_lock(lock_path: Path):
    """Cross-process (and cross-thread) exclusive lock on ``lock_path``."""
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
    locked = False
    try:
        if os.name == "nt":
            import msvcrt

            deadline = time.monotonic() + _LOCK_WAIT_SECONDS
            while True:
                try:
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    locked = True
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise AlphaClawTlsUnavailable(
                            "timed out waiting for the PKI state lock"
                        ) from None
                    time.sleep(0.05)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX)
            locked = True
        yield
    finally:
        if locked:
            try:
                if os.name == "nt":
                    import msvcrt

                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
        os.close(fd)


@dataclass
class LanControlPlanePki:
    """The Portal's local CA and leaf store: paths, CA pinning and leaf issuance under ``state_dir``."""
    state_dir: Path
    hostname: str = ""
    san_dns: tuple = ("localhost",)
    san_ips: tuple = ()
    label: str = "Portal"
    # Optional callable returning the host's current IPv4 addresses; when set,
    # every ensure() refreshes san_ips from it so a long-running proxy follows
    # DHCP changes.
    ip_source: Optional[Callable[[], Iterable[str]]] = None
    # Filled in by ensure():
    ca_fingerprint: str = ""
    leaf_fingerprint: str = ""
    ca_file_sha256: str = ""
    leaf_event: str = ""  # "created" | "reused" | "rotated" | "san_reissued" | "reissued"

    # -- paths -----------------------------------------------------------
    @property
    def private_dir(self) -> Path:
        """Directory holding the CA and leaf private material."""
        return Path(self.state_dir) / "private"

    @property
    def public_dir(self) -> Path:
        """Directory holding the public CA file and its checksum line."""
        return Path(self.state_dir) / "public"

    @property
    def ca_key_path(self) -> Path:
        """Path of the CA private key."""
        return self.private_dir / "ca.key"

    @property
    def ca_cert_path(self) -> Path:
        """Path of the CA certificate kept in the private directory."""
        return self.private_dir / "ca.crt"

    @property
    def leaf_key_path(self) -> Path:
        """Path of the leaf private key."""
        return self.private_dir / "leaf.key"

    @property
    def leaf_chain_path(self) -> Path:
        """Path of the served chain (leaf followed by the CA)."""
        return self.private_dir / "leaf.pem"

    @property
    def pin_path(self) -> Path:
        """Path of the CA pin file."""
        return self.private_dir / "ca-pin.json"

    @property
    def ca_public_path(self) -> Path:
        """Path of the public CA file handed to peers, named after the host."""
        host = _safe_host(self.hostname or socket.gethostname())
        return self.public_dir / f"orama-lan-ca-{host}.pem"

    @property
    def sums_path(self) -> Path:
        """Path of the SHA256SUMS file for the public CA file."""
        return self.public_dir / "SHA256SUMS"

    # -- helpers ---------------------------------------------------------
    def _want_ips(self) -> set:
        """The addresses the leaf must cover: refreshed from ``ip_source`` when set, plus loopback."""
        if self.ip_source is not None:
            try:
                self.san_ips = tuple(self.ip_source())
            except OSError:
                pass
        ips = {ipaddress.ip_address(i) for i in self.san_ips}
        ips.add(ipaddress.ip_address(_LOOPBACK_V4))
        return ips

    def _want_dns(self) -> list:
        """The DNS names the leaf must cover: localhost plus ``san_dns``, de-duplicated."""
        return list(dict.fromkeys(d for d in ("localhost",) + tuple(self.san_dns) if d))

    def _load_pin(self) -> Optional[str]:
        """None only when no pin file exists. A pin file that is present but
        unreadable or invalid fails closed (never treated as 'no pin')."""
        try:
            raw = self.pin_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise self._mismatch("", "", f"pin file unreadable: {exc}") from exc
        try:
            value = json.loads(raw)
        except ValueError as exc:
            raise self._mismatch("", "", "pin file is not valid JSON") from exc
        fp = value.get("ca_fingerprint") if isinstance(value, dict) else None
        if not isinstance(fp, str) or not _HEX64.match(fp):
            raise self._mismatch("", "", "pin file does not hold a SHA-256 fingerprint")
        return fp

    def _store_pin(self, fingerprint: str) -> None:
        """Persist the CA fingerprint pin with a UTC timestamp as a private file."""
        payload = json.dumps(
            {"ca_fingerprint": fingerprint, "pinned_at": datetime.now(timezone.utc).isoformat()},
            indent=2,
        ).encode("utf-8")
        _write_private(self.pin_path, payload)

    def _mismatch(self, pinned: str, current: str, why: str) -> AlphaClawCertFingerprintMismatch:
        """Build the refusal error for a CA pin mismatch, with the migration steps."""
        return AlphaClawCertFingerprintMismatch(
            f"{self.label} CA fingerprint check failed ({why}): pinned={pinned[:16]}... "
            f"current={current[:16] or 'none'}... A CA change is an explicit two-sided "
            "migration. Verify out of band, then remove the private/ca-pin.json file and the "
            "CA files under the state directory to start a new CA; peers must then be given "
            "the new public CA and its SHA-256."
        )

    def _load_ca(self):
        """Load the CA certificate and key; None when missing, unreadable or not a matching pair."""
        try:
            cert = x509.load_pem_x509_certificate(self.ca_cert_path.read_bytes())
            key = serialization.load_pem_private_key(self.ca_key_path.read_bytes(), password=None)
            pub = lambda k: k.public_bytes(  # noqa: E731
                serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
            )
            if pub(cert.public_key()) != pub(key.public_key()):
                return None
            return cert, key
        except (OSError, ValueError, TypeError):
            return None

    def _new_ca(self):
        """Create a new self-signed CA (3072-bit RSA, path length 0) and return (cert, key)."""
        key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        host = self.hostname or socket.gethostname()
        name = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, f"Orama LAN Control Plane CA ({host})"[:64])]
        )
        now = datetime.now(timezone.utc)
        ski = x509.SubjectKeyIdentifier.from_public_key(key.public_key())
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - _CLOCK_SKEW)
            .not_valid_after(now + timedelta(days=CA_VALIDITY_DAYS))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=False, content_commitment=False, key_encipherment=False,
                    data_encipherment=False, key_agreement=False, key_cert_sign=True,
                    crl_sign=True, encipher_only=False, decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(ski, critical=False)
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )
        return cert, key

    def _ensure_ca(self):
        """Load or create the CA, enforce the pin, and check CA expiry; returns (cert, key)."""
        loaded = self._load_ca()
        pinned = self._load_pin()
        if loaded is None:
            if pinned is not None:
                # Never regenerate behind an existing pin.
                raise self._mismatch(pinned, "", "CA files missing or unreadable")
            cert, key = self._new_ca()
            _write_private(
                self.ca_key_path,
                key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                ),
            )
            _write_private(self.ca_cert_path, cert.public_bytes(serialization.Encoding.PEM))
            _log.info("%s TLS: created a new local CA (%s...)", self.label, der_sha256(cert)[:16])
        else:
            cert, key = loaded
            _secure_path(self.ca_key_path, is_directory=False)
            _secure_path(self.ca_cert_path, is_directory=False)
        current = der_sha256(cert)
        if pinned is None:
            self._store_pin(current)
            _log.info("%s TLS: pinned CA fingerprint (first start): %s...", self.label, current[:16])
        elif pinned != current:
            raise self._mismatch(pinned, current, "CA certificate differs from the pin")
        remaining = _utc_after(cert) - datetime.now(timezone.utc)
        if remaining <= timedelta(0):
            raise AlphaClawTlsUnavailable(
                "the local CA has expired; renewing a CA is an explicit two-sided migration"
            )
        if remaining.days < CA_WARN_REMAINING_DAYS:
            _log.warning(
                "%s TLS: the local CA expires in %d days; plan a two-sided CA migration",
                self.label, remaining.days,
            )
        return cert, key

    def _leaf_problem(self, ca_cert) -> str:
        """Return '' when the on-disk leaf is reusable, else a reason code."""
        try:
            chain = x509.load_pem_x509_certificates(self.leaf_chain_path.read_bytes())
            leaf = chain[0]
            key = serialization.load_pem_private_key(self.leaf_key_path.read_bytes(), password=None)
        except (OSError, ValueError, TypeError, IndexError):
            return "missing"
        pub = lambda k: k.public_bytes(  # noqa: E731
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        if pub(leaf.public_key()) != pub(key.public_key()):
            return "missing"
        try:
            leaf.verify_directly_issued_by(ca_cert)
        except (AttributeError, ValueError, TypeError):
            if leaf.issuer != ca_cert.subject:
                return "reissued"
        except Exception:  # noqa: BLE001 - signature/name mismatch
            return "reissued"
        if (_utc_after(leaf) - datetime.now(timezone.utc)).days < LEAF_MIN_REMAINING_DAYS:
            return "rotated"
        try:
            san = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        except x509.ExtensionNotFound:
            return "san_reissued"
        have_dns = {d.lower() for d in san.get_values_for_type(x509.DNSName)}
        have_ips = set(san.get_values_for_type(x509.IPAddress))
        if not ({d.lower() for d in self._want_dns()} <= have_dns and self._want_ips() <= have_ips):
            return "san_reissued"
        return ""

    def _issue_leaf(self, ca_cert, ca_key) -> None:
        """Issue a new leaf signed by the CA, covering the wanted names and addresses, and write its key and chain."""
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        dns = self._want_dns()
        cn = (self.san_dns[0] if self.san_dns else "") or self.hostname or "localhost"
        now = datetime.now(timezone.utc)
        not_after = min(now + timedelta(days=LEAF_VALIDITY_DAYS), _utc_after(ca_cert))
        names = [x509.DNSName(d) for d in dns]
        names += [x509.IPAddress(i) for i in sorted(self._want_ips())]
        ca_ski = ca_cert.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value
        cert = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn[:64])]))
            .issuer_name(ca_cert.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - _CLOCK_SKEW)
            .not_valid_after(not_after)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True, content_commitment=False, key_encipherment=True,
                    data_encipherment=False, key_agreement=False, key_cert_sign=False,
                    crl_sign=False, encipher_only=False, decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False
            )
            .add_extension(x509.SubjectAlternativeName(names), critical=False)
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(ca_ski),
                critical=False,
            )
            .sign(ca_key, hashes.SHA256())
        )
        _write_private(
            self.leaf_key_path,
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
        )
        pem = cert.public_bytes(serialization.Encoding.PEM) + ca_cert.public_bytes(
            serialization.Encoding.PEM
        )
        _write_private(self.leaf_chain_path, pem)

    def _publish(self, ca_cert) -> None:
        """Write the public CA file and its SHA256SUMS line (only when changed) and record the file hash."""
        self.public_dir.mkdir(parents=True, exist_ok=True)
        data = ca_cert.public_bytes(serialization.Encoding.PEM)
        path = self.ca_public_path
        if not path.is_file() or path.read_bytes() != data:
            _write_public(path, data)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        sums = f"{digest}  {path.name}\n".encode("ascii")
        if not self.sums_path.is_file() or self.sums_path.read_bytes() != sums:
            _write_public(self.sums_path, sums)
        self.ca_file_sha256 = digest

    # -- public API ------------------------------------------------------
    def ensure(self) -> "LanControlPlanePki":
        """Create or reuse the CA and leaf, enforce the CA pin, publish the
        public CA. Raises AlphaClawCertFingerprintMismatch on a CA change."""
        if not _CRYPTOGRAPHY_AVAILABLE:
            raise AlphaClawTlsUnavailable("'cryptography' library not available")
        Path(self.state_dir).mkdir(parents=True, exist_ok=True)
        self.private_dir.mkdir(parents=True, exist_ok=True)
        _secure_path(self.private_dir, is_directory=True)
        # One writer at a time: concurrent first starts must not each create a
        # CA. Everything below (including re-reading the CA and pin) runs under
        # the lock, so the first process wins and later ones reuse its CA.
        with _exclusive_lock(self.private_dir / ".lock"):
            return self._ensure_locked()

    def _ensure_locked(self) -> "LanControlPlanePki":
        """Create or reuse the CA and leaf and publish the public CA; the caller holds the lock."""
        ca_cert, ca_key = self._ensure_ca()
        problem = self._leaf_problem(ca_cert)
        if problem:
            self._issue_leaf(ca_cert, ca_key)
            self.leaf_event = "created" if problem == "missing" else problem
            if problem == "san_reissued":
                _log.warning(
                    "%s TLS: leaf SANs no longer cover the configured names/addresses; "
                    "reissued the leaf (the CA is unchanged, no re-pin needed)", self.label,
                )
            elif problem == "rotated":
                _log.info("%s TLS: leaf had under %d days left; rotated", self.label,
                          LEAF_MIN_REMAINING_DAYS)
            elif problem == "reissued":
                _log.warning("%s TLS: leaf was not issued by the current CA; reissued", self.label)
            else:
                _log.info("%s TLS: issued a new leaf", self.label)
        else:
            self.leaf_event = "reused"
            _secure_path(self.leaf_key_path, is_directory=False)
            _secure_path(self.leaf_chain_path, is_directory=False)
        leaf = x509.load_pem_x509_certificates(self.leaf_chain_path.read_bytes())[0]
        self.leaf_fingerprint = der_sha256(leaf)
        self.ca_fingerprint = der_sha256(ca_cert)
        self._publish(ca_cert)
        return self


def build_pki(
    state_dir: Path,
    san_names: Iterable[str] = (),
    ips: Iterable[str] = (),
    label: str = "Portal",
    hostname: str = "",
    ip_source: Optional[Callable[[], Iterable[str]]] = None,
) -> LanControlPlanePki:
    """Build a LanControlPlanePki for ``state_dir``; nothing is created until ensure()."""
    return LanControlPlanePki(
        state_dir=Path(state_dir),
        hostname=hostname,
        san_dns=tuple(san_names),
        san_ips=tuple(ips),
        label=label,
        ip_source=ip_source,
    )
