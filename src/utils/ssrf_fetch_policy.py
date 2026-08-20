"""Layer-1 pre-flight SSRF policy for outbound fetches of arbitrary/remote URLs.

Deny-by-default: rejects userinfo, non-http(s) schemes, control characters, and
IP literals in loopback/private/link-local/CGNAT/multicast/reserved ranges.
Env override only (never a UI toggle): SSRF_ALLOW_PRIVATE_TARGETS=1/true/yes/on.

Scope and limits (see docs/2026-08-20-ssrf-defense-in-depth.md):
  - This module cannot stop DNS rebinding (TOCTOU) or redirect-based SSRF --
    those require a connection-time-pinning transport (Layer 2) and are out
    of scope here by design. Do not add DNS resolution to this module.
  - This is the *opposite* policy from utils.model_endpoint_url, which
    allowlists private/loopback addresses for trusted LAN model servers.
    Do not merge the two -- they protect different, opposite-polarity cases.
"""
from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_TRUTHY = frozenset({"1", "true", "yes", "on"})

# Fixed vendor hosts with known-safe DNS: skip the denylist maze entirely
# rather than fail-closed on "cannot resolve DNS". Do not add hosts here
# whose resolution could be attacker-influenced (e.g. anything from a
# discovery/config value); this is for hardcoded, code-reviewed vendor APIs
# only.
_VENDOR_HOSTNAME_ALLOWLIST = frozenset({
    "api.perplexity.ai",
    "api.x.ai",
})

# AWS ECS task metadata; not covered by ipaddress.is_link_local (169.254.170.2
# is link-local range but listed explicitly per the source spec for clarity).
_ECS_METADATA_IPV4 = ipaddress.ip_address("169.254.170.2")
# AWS IMDS IPv6 endpoint; not covered by any built-in ipaddress predicate.
_AWS_IMDS_IPV6 = ipaddress.ip_address("fd00:ec2::254")
# RFC 6598 Carrier-Grade NAT; not covered by is_private/is_reserved in Python's ipaddress.
_CGNAT_RANGE = ipaddress.ip_network("100.64.0.0/10")


class SSRFPolicyError(ValueError):
    """Raised when a fetch target URL violates SSRF egress policy."""


def allow_private_fetch_targets() -> bool:
    """Return True when private/internal fetch targets are explicitly allowed."""
    return os.getenv("SSRF_ALLOW_PRIVATE_TARGETS", "").strip().lower() in _TRUTHY


def _is_denied_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True if addr falls in any range this policy denies by default."""
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    if addr == _AWS_IMDS_IPV6:
        return True
    if isinstance(addr, ipaddress.IPv4Address):
        if addr == _ECS_METADATA_IPV4 or addr in _CGNAT_RANGE:
            return True
    return bool(
        addr.is_loopback
        or addr.is_private
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def _host_denied(host: str, *, allow_private: bool) -> bool:
    """True if this host must be rejected under current policy."""
    if allow_private:
        return False
    normalized = host.strip().lower()
    if not normalized:
        return True
    if normalized in ("localhost", "::1") or normalized.endswith(".localhost"):
        return True
    if normalized.startswith("127."):
        return True
    if normalized in _VENDOR_HOSTNAME_ALLOWLIST:
        return False
    try:
        addr = ipaddress.ip_address(normalized)
    except ValueError:
        # Bare hostname: this module cannot resolve DNS (see module docstring).
        # Fail closed -- hostnames must go through the Layer-2 pinning
        # transport, which resolves, validates every A/AAAA record, and pins
        # the connection. A pure pre-flight check has no way to safely allow
        # an unresolved hostname without reintroducing the TOCTOU gap.
        return True
    return _is_denied_ip(addr)


def validate_fetch_url(url: str, *, allow_private: bool | None = None) -> str:
    """Validate an outbound fetch target URL against Layer-1 SSRF policy.

    Returns the original URL unchanged on success; raises SSRFPolicyError on
    any policy violation. Does not resolve DNS and cannot stop rebinding or
    redirect-based SSRF -- callers fetching arbitrary/remote URLs must use
    the Layer-2 pinning transport, not this function alone.
    """
    if allow_private is None:
        allow_private = allow_private_fetch_targets()

    raw = (url or "").strip()
    if not raw:
        raise SSRFPolicyError("empty fetch URL")
    if any(ord(ch) < 0x20 for ch in raw):
        raise SSRFPolicyError("control characters are not allowed in fetch URL")

    try:
        parsed = urlparse(raw)
    except ValueError as exc:
        raise SSRFPolicyError(f"invalid fetch URL: {exc}") from exc

    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise SSRFPolicyError(f"fetch URL scheme {scheme!r} not allowed (http/https only)")
    if parsed.username or parsed.password:
        raise SSRFPolicyError("credentials in fetch URL are not allowed")

    host = parsed.hostname
    if not host:
        raise SSRFPolicyError("fetch URL missing hostname")

    if _host_denied(host, allow_private=allow_private):
        raise SSRFPolicyError(
            f"fetch target host {host!r} is denied by SSRF policy "
            "(loopback/private/link-local/CGNAT/multicast/reserved, or an "
            "unresolved hostname); set SSRF_ALLOW_PRIVATE_TARGETS=1 to override"
        )

    return raw
