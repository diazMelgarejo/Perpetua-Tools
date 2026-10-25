"""orchestrator/portal_tls_proxy.py -- Perpetua-Tools

TLS front end for the orama Portal (plain HTTP on loopback), so a LAN peer
can send authenticated requests over https to this node.

This is a thin configuration layer over ``AlphaClawTlsProxy`` (the
generalized proxy in ``alphaclaw_tls_proxy``): same certificate persistence,
SHA-256 fingerprint TOFU pinning with hard reject on mismatch, restrictive
key-store permissions and bounded streaming forwarder. The proxy is
transport only: every request header, including Authorization, is forwarded
to the Portal untouched and nothing about the request is logged.

Opt-in via ``PORTAL_TLS_ENABLED`` (off by default). The certificate covers
``PORTAL_TLS_SAN_NAMES`` (comma list of DNS names) plus this host's current
local IPv4 addresses. When the address set changes (for example after a DHCP
change) the leaf is reissued, a warning is logged and the pin is updated
explicitly, never silently; the operator then hands the new public cert and
fingerprint to peers.

Run: ``python -m orchestrator.portal_tls_proxy --listen-port 8443
--upstream-port 8002 [--print-fingerprint]``
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
    """Cert/pin store, separate from AlphaClaw's. Under the PT state dir."""
    override = (os.environ.get("PORTAL_TLS_CERT_DIR") or "").strip()
    return Path(override) if override else _PT_ROOT / ".state" / "portal_tls"


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
) -> AlphaClawTlsProxy:
    """Configured proxy; nothing is bound until start()."""
    names = tuple(san_names) if san_names is not None else san_names_from_env()
    dns = tuple(dict.fromkeys(("localhost",) + names))
    return AlphaClawTlsProxy(
        upstream_port=upstream_port,
        proxy_port=listen_port,
        listen_host=listen_host or os.environ.get("PORTAL_TLS_LISTEN_HOST", "") or _ALL_INTERFACES,
        cert_dir=cert_dir if cert_dir is not None else portal_tls_dir(),
        cert_basename="portal",
        label="Portal",
        common_name=names[0] if names else "localhost",
        san_dns=dns,
        san_ips=tuple(ip_source()),
        reissue_on_san_change=True,
    )


def _pem_path(proxy: AlphaClawTlsProxy) -> Path:
    return proxy._dir() / f"{proxy.cert_basename}.crt"


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m orchestrator.portal_tls_proxy")
    ap.add_argument("--listen-host", default="", help="bind address (default: all interfaces)")
    ap.add_argument("--listen-port", type=int, default=DEFAULT_LISTEN_PORT)
    ap.add_argument("--upstream-port", type=int, default=DEFAULT_UPSTREAM_PORT)
    ap.add_argument("--cert-dir", default="", help="override the cert/pin store directory")
    ap.add_argument("--print-fingerprint", action="store_true",
                    help="ensure the leaf exists, print its SHA-256 and PUBLIC cert, then exit")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    proxy = build_portal_proxy(
        listen_port=args.listen_port,
        upstream_port=args.upstream_port,
        listen_host=args.listen_host,
        cert_dir=Path(args.cert_dir) if args.cert_dir else None,
    )
    try:
        if args.print_fingerprint:
            proxy.ensure_certificate()
            print(f"sha256:{proxy.fingerprint}")
            print(_pem_path(proxy).read_text(encoding="ascii"), end="")
            return 0
        url = proxy.start()
    except _base.AlphaClawCertFingerprintMismatch as exc:
        _log.error("portal-tls-proxy refused to start: %s", exc)
        return 3
    except (_base.AlphaClawTlsUnavailable, OSError) as exc:
        _log.error("portal-tls-proxy cannot start: %s", exc)
        return 2

    _log.info("portal-tls-proxy pid=%d listening %s upstream_port=%d fingerprint=sha256:%s",
              os.getpid(), url, args.upstream_port, proxy.fingerprint)
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
