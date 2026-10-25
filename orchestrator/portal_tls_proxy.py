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
"""
from __future__ import annotations

import argparse
import ipaddress
import logging
import os
import signal
import socket
import sys
import threading
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
    try:
        resolved = path.resolve()
    except OSError:
        return False
    return any((p / ".git").exists() for p in (resolved, *resolved.parents))


def san_names_from_env() -> tuple:
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


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m orchestrator.portal_tls_proxy")
    ap.add_argument("--listen-host", default="", help="bind address (default: all interfaces)")
    ap.add_argument("--listen-port", type=int, default=DEFAULT_LISTEN_PORT)
    ap.add_argument("--upstream-port", type=int, default=DEFAULT_UPSTREAM_PORT)
    ap.add_argument("--state-dir", "--cert-dir", dest="state_dir", default="",
                    help="override the state directory (private/ + public/)")
    ap.add_argument("--print-fingerprint", action="store_true",
                    help="ensure the CA and leaf exist, print the public CA file hash and path, exit")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    state_dir = Path(args.state_dir) if args.state_dir else portal_tls_dir()
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
