"""Core transport identity helpers for model endpoint reconstruction.

This module owns the narrow boundary where discovery output becomes a runtime
transport URL. Keep allow/deny network policy in ``utils.model_endpoint_url``;
this module only preserves and reconstructs endpoint identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv6Address, ip_address
from typing import Optional
from urllib.parse import urlparse

_ALLOWED_SCHEMES = frozenset({"http", "https"})


@dataclass(frozen=True)
class TransportIdentity:
    """Parsed endpoint identity used before backend-specific port routing."""

    scheme: str
    hostname: str
    port: Optional[int] = None

    def with_port(self, port: int) -> str:
        """Return ``scheme://host:port`` with IPv6 literals bracketed."""
        host = self.hostname
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return f"{self.scheme}://{host}:{int(port)}"


def parse_transport_identity(
    source: str,
    *,
    default_scheme: str = "http",
) -> Optional[TransportIdentity]:
    """Parse discovery output into scheme + hostname + optional port.

    Bare host/host:port values are interpreted with ``default_scheme``. Unknown
    schemes, credentials, missing hostnames, and malformed ports return ``None``
    so callers can fall back to configured hosts rather than fabricating an
    unsafe or malformed URL.
    """
    raw = (source or "").strip()
    if not raw:
        return None

    normalized_scheme = (default_scheme or "http").lower()
    if normalized_scheme not in _ALLOWED_SCHEMES:
        return None

    if "://" in raw:
        candidate = raw
    else:
        try:
            host = f"[{raw}]" if isinstance(ip_address(raw), IPv6Address) else raw
        except ValueError:
            host = raw
        candidate = f"{normalized_scheme}://{host}"
    try:
        parsed = urlparse(candidate)
        scheme = (parsed.scheme or normalized_scheme).lower()
        if scheme not in _ALLOWED_SCHEMES:
            return None
        if parsed.username or parsed.password:
            return None
        hostname = parsed.hostname
        if not hostname:
            return None
        port = parsed.port
    except ValueError:
        return None

    return TransportIdentity(scheme=scheme, hostname=hostname, port=port)


def build_transport_url(
    source: str,
    port: int,
    *,
    default_scheme: str = "http",
) -> Optional[str]:
    """Rebuild ``scheme://hostname:port`` while preserving transport scheme."""
    identity = parse_transport_identity(source, default_scheme=default_scheme)
    if identity is None:
        return None
    return identity.with_port(port)
