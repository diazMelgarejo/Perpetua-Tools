"""Validate and normalize model server base URLs behind one typed error.

Ported behavior-identically from the parity-checked mirror
``src/utils/model_endpoint_url.py`` (Perpetua-Tools / orama-system) per
coord-023: single ``ModelEndpointPolicyError``, wrapped ``ParseResult.port``
access (it raises ``ValueError`` lazily), IPv4-mapped-IPv6 unwrap, link-local
metadata block.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse

from .errors import ModelEndpointPolicyError
from .hosts import host_allowed, redact_endpoint_for_log

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def allow_public_model_endpoints() -> bool:
    """Return True when public model endpoints are explicitly allowed."""
    return os.getenv("ALLOW_PUBLIC_MODEL_ENDPOINTS", "").strip().lower() in _TRUTHY


def validate_model_endpoint_url(
    url: str,
    *,
    allow_public: bool | None = None,
) -> str:
    """Validate and normalize a model server base URL (no path).

    Returns scheme://host[:port] without a trailing slash.
    """
    if allow_public is None:
        allow_public = allow_public_model_endpoints()

    raw = (url or "").strip()
    if not raw:
        raise ModelEndpointPolicyError("empty endpoint URL")
    # Match agent_launcher / alphaclaw_bootstrap: bare host:port env values are valid.
    if "://" not in raw:
        raw = f"http://{raw}"

    try:
        parsed = urlparse(raw)
        scheme = (parsed.scheme or "").lower()
        if scheme not in _ALLOWED_SCHEMES:
            raise ModelEndpointPolicyError(
                f"endpoint scheme {scheme!r} not allowed (http/https only)"
            )
        if parsed.username or parsed.password:
            raise ModelEndpointPolicyError("credentials in endpoint URL are not allowed")

        host = parsed.hostname
        if not host:
            raise ModelEndpointPolicyError("endpoint URL missing hostname")

        # Accessing ParseResult.port validates numeric/range syntax and may raise ValueError.
        port = parsed.port
    except ModelEndpointPolicyError:
        raise
    except ValueError as exc:
        raise ModelEndpointPolicyError(f"invalid endpoint URL: {exc}") from exc

    if not host_allowed(host, allow_public=allow_public):
        raise ModelEndpointPolicyError(
            "endpoint host is not loopback or RFC1918 private "
            f"({redact_endpoint_for_log(raw)}); set ALLOW_PUBLIC_MODEL_ENDPOINTS=1 "
            "to allow public hosts"
        )

    if port is None:
        port = 443 if scheme == "https" else 80

    # Bracket IPv6 literals for urlparse-compatible reconstruction.
    if ":" in host and not host.startswith("["):
        netloc = f"[{host}]:{port}"
    else:
        netloc = f"{host}:{port}"

    return f"{scheme}://{netloc}".rstrip("/")


def parse_model_endpoint_list(
    raw: str,
    *,
    allow_public: bool | None = None,
    skip_invalid: bool = False,
) -> list[str]:
    """Parse a comma-separated endpoint list and validate each base URL."""
    if not raw or not raw.strip():
        return []

    out: list[str] = []
    for part in raw.split(","):
        candidate = part.strip()
        if not candidate or candidate == "REQUIRED_SET_IN_ENV":
            continue
        try:
            out.append(validate_model_endpoint_url(candidate, allow_public=allow_public))
        except ModelEndpointPolicyError:
            if skip_invalid:
                continue
            raise
    return out
