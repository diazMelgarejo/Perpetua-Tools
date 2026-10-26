"""orchestrator/portal_tls_proxy.py -- Perpetua-Tools

TLS front end for the orama Portal (plain HTTP on loopback), so a LAN peer
can send authenticated requests over https to this node.

A thin configuration layer over ``AlphaClawTlsProxy`` using CA mode
(``lan_control_plane_pki``): a dedicated local CA, a 30-day leaf signed by it
(reissued automatically when it nears expiry or the host's addresses change),
a local pin on the CA (a different CA is refused, exit 3), WebSocket upgrade
pass-through, and a key store outside any checkout. The proxy is transport
only: every request header, including Authorization, reaches the Portal
untouched and nothing about the request is logged.

Opt-in via ``PORTAL_TLS_ENABLED`` (off by default). State directory:
``PORTAL_TLS_STATE_DIR`` (alias ``PORTAL_TLS_CERT_DIR``), default
``~/.local/share/oramasys/lan-control-plane`` on every OS (see
``portal_tls_dir`` for why Windows does not use ``%LOCALAPPDATA%``).

Run: ``python -m orchestrator.portal_tls_proxy --listen-port 8443
--upstream-port 8002``; ``--print-fingerprint`` prints ``ca_sha256_file=`` and
``ca_public_path=`` and exits.

``--self-check`` is the evidence gate a caller runs before telling peers to
trust the endpoint. It reads only the public CA certificate from the store
(never a private key, never creating or rotating anything), then verifies
with that CA alone: ``check_tls_health`` (GET /health is 200),
``check_protected_unauth`` (GET /api/peer-inbox with no Authorization header
is 401 or 403), ``check_leaf_san`` (the presented leaf names the host),
``check_leaf_expiry`` (more than 7 days left is PASS, fewer is WARN, expired
is FAIL; notAfter is printed as UTC ISO-8601) and
``check_upstream_loopback_only`` (the upstream port refuses connections on
every non-loopback local address). Each prints ``check_<name>=PASS|WARN|FAIL
<detail>``, followed by ``ca_sha256_file=<hex>`` and ``self_check=PASS|FAIL``.
Exit 0 when nothing FAILs (WARN is allowed), 1 on any FAIL, 2 on a usage
error. ``--host`` defaults to the first non-loopback local address.
"""
from __future__ import annotations

import argparse
import ipaddress
import logging
import os
import signal
import hashlib
import http.client
import socket
import ssl
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional

from orchestrator import alphaclaw_tls_proxy as _base
from orchestrator.alphaclaw_tls_proxy import AlphaClawTlsProxy
from orchestrator.lan_control_plane_pki import build_pki

_log = logging.getLogger(__name__)

DEFAULT_LISTEN_PORT = 8443
DEFAULT_UPSTREAM_PORT = 8002
_PT_ROOT = Path(__file__).resolve().parent.parent
_ALL_INTERFACES = str(ipaddress.IPv4Address(0))
_TRUTHY = ("1", "true", "yes", "on")
_NET_TIMEOUT = 5.0  # seconds, every self-check network call
_PROBE_TIMEOUT = 1.0  # seconds, the upstream exposure connect probe
_EXPIRY_WARN_DAYS = 7
_PEER_INBOX_PATH = "/api/peer-inbox"


def portal_tls_enabled() -> bool:
    """Env gate; off by default (same parsing as alphaclaw_tls_enabled)."""
    return (os.environ.get("PORTAL_TLS_ENABLED") or "").strip().lower() in _TRUTHY


def portal_tls_dir() -> Path:
    """State store (private/ + public/), outside any checkout by default.
    PORTAL_TLS_STATE_DIR wins; PORTAL_TLS_CERT_DIR is accepted as an alias.

    The default is ``~/.local/share/oramasys/lan-control-plane`` on every OS,
    the same layout the Mac peer uses. Windows deliberately avoids
    ``%LOCALAPPDATA%``: a process started from an MSIX-packaged app (a desktop
    agent host) has its AppData writes redirected into that package's private
    store, so a CA created there is invisible to an ordinary terminal launch,
    which would mint a second CA and break the trust the peer pinned. The
    user profile outside AppData is not redirected, so every launch context
    shares one CA."""
    for var in ("PORTAL_TLS_STATE_DIR", "PORTAL_TLS_CERT_DIR"):
        override = (os.environ.get(var) or "").strip()
        if override:
            return Path(override)
    return Path.home() / ".local" / "share" / "oramasys" / "lan-control-plane"


def _inside_checkout(path: Path) -> bool:
    """True when ``path`` or any parent directory contains a .git entry."""
    try:
        resolved = path.resolve()
    except OSError:
        return False
    return any((p / ".git").exists() for p in (resolved, *resolved.parents))


def san_names_from_env() -> tuple:
    """The extra DNS names from PORTAL_TLS_SAN_NAMES (comma separated, blanks dropped)."""
    raw = os.environ.get("PORTAL_TLS_SAN_NAMES") or ""
    return tuple(n.strip() for n in raw.split(",") if n.strip())


def local_ipv4_addresses() -> tuple:
    """This host's current IPv4 addresses (sorted, de-duplicated, includes
    loopback). Best-effort and offline: name resolution plus a UDP connect
    to a documentation address, which sends no packets."""
    found: set = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.add(info[4][0])
    except OSError:
        pass
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))
        found.add(probe.getsockname()[0])
    except OSError:
        pass
    finally:
        probe.close()
    found.add(str(ipaddress.IPv4Address((127 << 24) | 1)))
    found.discard(_ALL_INTERFACES)
    return tuple(sorted(found, key=lambda a: ipaddress.ip_address(a)))


def build_portal_proxy(
    listen_port: int = DEFAULT_LISTEN_PORT,
    upstream_port: int = DEFAULT_UPSTREAM_PORT,
    listen_host: str = "",
    cert_dir: Optional[Path] = None,
    san_names: Optional[Iterable[str]] = None,
    ip_source: Callable[[], Iterable[str]] = local_ipv4_addresses,
    hostname: str = "",
    ws_idle_timeout: float = 300.0,
) -> AlphaClawTlsProxy:
    """Configured proxy; nothing is bound until start(). ``cert_dir`` is the
    state directory (private/ + public/)."""
    names = tuple(san_names) if san_names is not None else san_names_from_env()
    dns = tuple(dict.fromkeys(("localhost",) + names))
    ips = tuple(ip_source())
    state_dir = cert_dir if cert_dir is not None else portal_tls_dir()
    pki = build_pki(state_dir, san_names=dns, ips=ips, label="Portal", hostname=hostname,
                    ip_source=ip_source)
    return AlphaClawTlsProxy(
        upstream_port=upstream_port,
        proxy_port=listen_port,
        listen_host=listen_host or os.environ.get("PORTAL_TLS_LISTEN_HOST", "") or _ALL_INTERFACES,
        cert_dir=Path(state_dir),
        cert_basename="portal",
        label="Portal",
        common_name=names[0] if names else "localhost",
        san_dns=dns,
        san_ips=ips,
        reissue_on_san_change=True,
        pki=pki,
        websocket_passthrough=True,
        ws_idle_timeout=ws_idle_timeout,
    )


def _default_self_check_host() -> str:
    """First non-loopback local IPv4 address, else loopback."""
    for addr in local_ipv4_addresses():
        if not ipaddress.ip_address(addr).is_loopback:
            return addr
    return str(ipaddress.IPv4Address((127 << 24) | 1))


def _san_covers(cert: dict, host: str) -> bool:
    """True when the peer-cert dict's SAN lists ``host`` (IP SAN for an IP
    literal, DNS SAN for a name)."""
    sans = cert.get("subjectAltName", ())
    try:
        want = ipaddress.ip_address(host)
    except ValueError:
        return any(k == "DNS" and v.lower() == host.lower() for k, v in sans)
    for kind, value in sans:
        if kind != "IP Address":
            continue
        try:
            if ipaddress.ip_address(value) == want:
                return True
        except ValueError:
            continue
    return False


def _https_status(host: str, port: int, ctx: ssl.SSLContext, path: str):
    """One verified GET with no Authorization header. Returns (status, leaf)
    where ``leaf`` is the presented certificate dict."""
    conn = http.client.HTTPSConnection(host, port, timeout=_NET_TIMEOUT, context=ctx)
    try:
        conn.connect()
        leaf = conn.sock.getpeercert() or {}
        conn.request("GET", path, headers={"Connection": "close"})
        resp = conn.getresponse()
        resp.read(1)
        return resp.status, leaf
    finally:
        conn.close()


def _check_upstream_loopback_only(upstream_port: int) -> tuple:
    """(status, detail): the upstream must refuse every non-loopback local
    address. Only an explicit refusal counts as evidence: a successful
    connect is FAIL (naming the exposed address); a timeout or other error,
    or having no non-loopback address to probe at all, is WARN because
    loopback-only binding was not established either way."""
    exposed, inconclusive = [], []
    refused = 0
    for addr in local_ipv4_addresses():
        if ipaddress.ip_address(addr).is_loopback:
            continue
        try:
            with socket.create_connection((addr, upstream_port), timeout=_PROBE_TIMEOUT):
                exposed.append(addr)
        except ConnectionRefusedError:
            refused += 1
        except OSError as exc:
            inconclusive.append(f"{addr} ({type(exc).__name__})")
    if exposed:
        return "FAIL", f"upstream port {upstream_port} accepts connections on {', '.join(exposed)}"
    if inconclusive:
        return "WARN", (f"upstream port {upstream_port} probe inconclusive on "
                        f"{', '.join(inconclusive)}; refused on {refused}")
    if refused == 0:
        return "WARN", (f"upstream port {upstream_port} exposure not established: "
                        "no non-loopback address enumerated")
    return "PASS", f"upstream port {upstream_port} refused on {refused} non-loopback address(es)"


def _expiry_result(leaf: dict) -> tuple:
    """(status, detail) for the leaf's notAfter: PASS beyond 7 days, WARN
    within 7 days, FAIL when expired or unreadable."""
    try:
        expires = datetime.fromtimestamp(ssl.cert_time_to_seconds(leaf["notAfter"]),
                                         tz=timezone.utc)
    except (KeyError, ValueError) as exc:
        return "FAIL", f"notAfter unreadable ({type(exc).__name__})"
    left = expires - datetime.now(timezone.utc)
    if left <= timedelta(0):
        level = "FAIL"
    elif left <= timedelta(days=_EXPIRY_WARN_DAYS):
        level = "WARN"
    else:
        level = "PASS"
    return level, f"notAfter={expires.strftime('%Y-%m-%dT%H:%M:%SZ')} ({left.days} days left)"


def run_self_check(host: str, listen_port: int, upstream_port: int, state_dir: Path) -> tuple:
    """Run the evidence gate. Returns (exit_code, output_lines).

    Reads only the public CA file; never creates, reissues or rotates
    anything and never reads a private key or any token."""
    results: dict = {}
    ca_path = build_pki(Path(state_dir), label="Portal").ca_public_path
    ca_hash = ""
    names = ("tls_health", "protected_unauth", "leaf_san", "leaf_expiry")
    ctx = None
    try:
        ca_hash = hashlib.sha256(ca_path.read_bytes()).hexdigest()
        ctx = ssl.create_default_context(cafile=str(ca_path))
    except (OSError, ssl.SSLError, ValueError) as exc:
        why = ("public CA certificate missing" if isinstance(exc, FileNotFoundError)
               else f"public CA certificate unusable ({type(exc).__name__})")
        for name in names:
            results[name] = ("FAIL", f"{why} in the store; start the proxy once or run "
                                     "--print-fingerprint to create it")
    if ctx is not None:
        leaf: dict = {}
        try:
            status, leaf = _https_status(host, listen_port, ctx, "/health")
            results["tls_health"] = ("PASS" if status == 200 else "FAIL",
                                     f"GET /health returned {status}")
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            results["tls_health"] = ("FAIL", "verified handshake or request failed "
                                             f"({type(exc).__name__}: {exc})")
        try:
            status, _ = _https_status(host, listen_port, ctx, _PEER_INBOX_PATH)
            results["protected_unauth"] = (
                "PASS" if status in (401, 403) else "FAIL",
                f"GET {_PEER_INBOX_PATH} without Authorization returned {status}")
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            results["protected_unauth"] = ("FAIL", f"request failed ({type(exc).__name__}: {exc})")
        if leaf:
            covered = _san_covers(leaf, host)
            results["leaf_san"] = ("PASS" if covered else "FAIL",
                                   f"SAN {'contains' if covered else 'does not contain'} {host}")
            results["leaf_expiry"] = _expiry_result(leaf)
        else:
            results["leaf_san"] = ("FAIL", "no verified leaf certificate was presented")
            results["leaf_expiry"] = ("FAIL", "no verified leaf certificate was presented")
    results["upstream_loopback_only"] = _check_upstream_loopback_only(upstream_port)
    order = names + ("upstream_loopback_only",)
    lines = [f"check_{n}={results[n][0]} {results[n][1]}" for n in order]
    failed = any(results[n][0] == "FAIL" for n in order)
    if ca_hash:
        lines.append(f"ca_sha256_file={ca_hash}")
    lines.append(f"self_check={'FAIL' if failed else 'PASS'}")
    return (1 if failed else 0), lines


def main(argv: Optional[list] = None) -> int:
    """CLI entry point. Returns the exit code: 0 ok, 1 self-check FAIL, 2 cannot start, 3 CA pin mismatch."""
    ap = argparse.ArgumentParser(prog="python -m orchestrator.portal_tls_proxy")
    ap.add_argument("--listen-host", default="", help="bind address (default: all interfaces)")
    ap.add_argument("--listen-port", type=int, default=DEFAULT_LISTEN_PORT)
    ap.add_argument("--upstream-port", type=int, default=DEFAULT_UPSTREAM_PORT)
    ap.add_argument("--state-dir", "--cert-dir", dest="state_dir", default="",
                    help="override the state directory (private/ + public/)")
    ap.add_argument("--print-fingerprint", action="store_true",
                    help="ensure the CA and leaf exist, print the public CA file hash and path, exit")
    ap.add_argument("--self-check", action="store_true", dest="self_check",
                    help="verify the running endpoint against the public CA only, print "
                         "check_<name>=PASS|WARN|FAIL lines, exit 0 (no FAIL) or 1")
    ap.add_argument("--host", default="",
                    help="--self-check target (default: first non-loopback local address)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    state_dir = Path(args.state_dir) if args.state_dir else portal_tls_dir()
    if args.self_check:
        code, lines = run_self_check(args.host or _default_self_check_host(),
                                     args.listen_port, args.upstream_port, state_dir)
        print("\n".join(lines), flush=True)
        return code
    if _inside_checkout(state_dir):
        _log.warning("portal-tls-proxy: state directory %s is inside a checkout; keys should "
                     "live outside any repository", state_dir)
    try:
        proxy = build_portal_proxy(
            listen_port=args.listen_port,
            upstream_port=args.upstream_port,
            listen_host=args.listen_host,
            cert_dir=state_dir,
        )
        if args.print_fingerprint:
            proxy.ensure_certificate()
            print(f"ca_sha256_file={proxy.pki.ca_file_sha256}")
            print(f"ca_public_path={proxy.pki.ca_public_path.resolve()}")
            return 0
        url = proxy.start()
    except _base.AlphaClawCertFingerprintMismatch as exc:
        _log.error("portal-tls-proxy refused to start: %s", exc)
        return 3
    except (_base.AlphaClawTlsUnavailable, OSError, ValueError) as exc:
        _log.error("portal-tls-proxy cannot start: %s", exc)
        return 2

    print(f"portal-tls-proxy pid={os.getpid()} listening {url} upstream={args.upstream_port} "
          f"ca_sha256_file={proxy.pki.ca_file_sha256}", flush=True)
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, lambda *_: stop.set())
        except (ValueError, OSError):
            pass
    try:
        while not stop.wait(1.0):
            pass
    finally:
        proxy.stop()
        _log.info("portal-tls-proxy pid=%d stopped", os.getpid())
    return 0


if __name__ == "__main__":
    sys.exit(main())
