"""Host classification: loopback/RFC1918 allowed, link-local (metadata SSRF) blocked.

Ported behavior-identically from the parity-checked mirror
``src/utils/model_endpoint_url.py`` (Perpetua-Tools / orama-system).
"""
from __future__ import annotations

import ipaddress
from urllib.parse import urlparse


def host_allowed(host: str, *, allow_public: bool) -> bool:
    """True if *host* is an allowed egress target for a local model endpoint."""
    normalized = host.strip().lower()
    if not normalized:
        return False
    if normalized in ("localhost", "::1") or normalized.endswith(".localhost"):
        return True
    if normalized.startswith("127."):
        return True
    try:
        addr = ipaddress.ip_address(normalized)
    except ValueError:
        return allow_public
    # IPv4-mapped IPv6 (::ffff:x.x.x.x) reports is_link_local=False on the wrapper.
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    # Link-local (169.254.0.0/16) is not RFC1918 — block cloud metadata SSRF (e.g. 169.254.169.254).
    if addr.is_link_local:
        return False
    if addr.is_loopback or addr.is_private:
        return True
    return allow_public


def redact_endpoint_for_log(url: str) -> str:
    """Return a log-safe endpoint string (host topology partially hidden)."""
    try:
        parsed = urlparse(url.strip())
        host = (parsed.hostname or "?").lower()
        if host in ("localhost", "127.0.0.1", "::1") or host.endswith(".localhost"):
            display = host
        else:
            try:
                ip = ipaddress.ip_address(host)
                if ip.is_private or ip.is_loopback:
                    if isinstance(ip, ipaddress.IPv4Address):
                        parts = str(ip).split(".")
                        display = ".".join(parts[:3]) + ".*" if len(parts) == 4 else "[private-ip]"
                    else:
                        display = "[private-ipv6]"
                else:
                    display = "[public-ip]"
            except ValueError:
                display = "[hostname]"
        port = parsed.port
        if port is None:
            port = 443 if parsed.scheme == "https" else 80
        scheme = parsed.scheme or "http"
        return f"{scheme}://{display}:{port}"
    except Exception:
        return "[invalid-endpoint]"
