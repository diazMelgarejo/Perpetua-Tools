"""Redacted egress telemetry: proves the L1/L2/L3 SSRF boundary is working.

One event type, emitted from exactly two dispatch points --
``ssrf_pinned_adapter.py`` and ``orchestrator/orama_bridge.py``'s
``_dispatch_oramasys_http()`` -- so there is one source of truth, not
scattered logging. See orama-system docs/v2/54-tri-stack-observability-and-l3-egress-v2.md
§ 3 for the design.

Hard redaction rules (never relaxed): no raw hostname, IP, prompt text,
response body, API key, or file path is ever written. Host/IP are hashed
with a per-process salt that is never persisted, so correlation works
within a session but stored hashes are not reversible.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import secrets
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

DenyReason = Literal[
    "metadata_ip",
    "rfc1918_unapproved",
    "link_local",
    "loopback",
    "multicast",
    "ula",
    "cgnat",
    "redirect_limit",
    "scheme_disallowed",
    "userinfo_present",
    "dns_resolution_failed",
    "other",
]

_SINK_DIR_ENV = "PERPETUA_TELEMETRY_DIR"
_DEFAULT_SINK_DIR = Path.home() / ".perpetua" / "telemetry"

# Per-process salt, generated once at import time and never persisted or
# logged -- this is what keeps stored host/IP hashes non-reversible while
# still letting repeated requests to the same host correlate within one
# process's lifetime.
_SALT = secrets.token_hex(16)


def _hash(value: str) -> str:
    return "sha256:" + hashlib.sha256((_SALT + value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EgressEvent:
    endpoint_class: Literal["local", "remote"]
    host: str
    port: int
    scheme: str
    event_kind: Literal["validation", "complete"] = "validation"
    resolved_ip: str | None = None
    redirect_count: int = 0
    deny_reason: DenyReason | None = None
    provider_route: str | None = None
    duration_ms: float | None = None
    validation_duration_ms: float | None = None
    status_code: int | None = None
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_redacted_dict(self) -> dict:
        event_label = "egress_validation" if self.event_kind == "validation" else "egress_request_complete"
        payload = {
            "ts": self.ts,
            "event": event_label,
            "event_kind": self.event_kind,
            "endpoint_class": self.endpoint_class,
            "host_hash": _hash(self.host) if self.host else None,
            "resolved_ip_hash": _hash(self.resolved_ip) if self.resolved_ip else None,
            "port": self.port,
            "scheme": self.scheme,
            "redirect_count": self.redirect_count,
            "deny_reason": self.deny_reason,
            "provider_route": self.provider_route,
            "duration_ms": self.duration_ms,
            "validation_duration_ms": self.validation_duration_ms,
            "status_code": self.status_code,
        }
        return payload


def _sink_dir() -> Path:
    import os

    override = os.getenv(_SINK_DIR_ENV, "").strip()
    return Path(override) if override else _DEFAULT_SINK_DIR


def _sink_path(now: float | None = None) -> Path:
    day = datetime.fromtimestamp(now if now is not None else time.time(), tz=timezone.utc)
    return _sink_dir() / f"egress-events-{day:%Y-%m-%d}.jsonl"


def emit(event: EgressEvent) -> None:
    """Append a redacted egress event to the local JSONL sink.

    Fire-and-forget: never raises into the caller's request path. A sink
    failure (permissions, disk full, missing dir) is swallowed silently --
    telemetry must never be able to break a live dispatch.
    """
    try:
        payload = event.to_redacted_dict()
        path = _sink_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, sort_keys=True) + "\n")
    except Exception:  # noqa: BLE001 -- telemetry must never raise into the request path
        pass


_ADDR_IN_MESSAGE = re.compile(r"blocked address:\s*(\S+)")


def _classify_denied_address(message: str) -> DenyReason:
    """Parse the actual denied IP out of an AddressDenied message and
    classify it by real IP-family membership rather than a substring match
    on message text, so link-local/loopback/multicast/ULA/CGNAT addresses
    outside the three literal IMDS strings aren't all bucketed into the
    RFC1918-specific label."""
    match = _ADDR_IN_MESSAGE.search(message)
    if not match:
        return "rfc1918_unapproved"
    try:
        addr = ipaddress.ip_address(match.group(1))
    except ValueError:
        return "rfc1918_unapproved"
    if addr.is_loopback:
        return "loopback"
    if addr.is_multicast:
        return "multicast"
    if isinstance(addr, ipaddress.IPv6Address) and addr.is_link_local:
        return "link_local"
    if isinstance(addr, ipaddress.IPv4Address) and addr.is_link_local:
        return "link_local"
    if isinstance(addr, ipaddress.IPv6Address) and (addr.is_private and not addr.is_link_local):
        # fc00::/7 unique local addresses -- is_private is broader (also
        # covers loopback/link-local, already handled above) but nothing
        # left in this branch by elimination is anything but ULA.
        return "ula"
    if isinstance(addr, ipaddress.IPv4Address) and addr in ipaddress.ip_network("100.64.0.0/10"):
        return "cgnat"
    if addr.is_private:
        return "rfc1918_unapproved"
    return "rfc1918_unapproved"


def classify_deny_reason(exc: BaseException) -> DenyReason:
    """Map a raised SSRF-policy exception to a closed deny_reason enum.

    Never returns a raw exception message -- only the enum value, so a
    caller cannot accidentally leak a URL/hostname into telemetry via
    ``str(exc)``.
    """
    message = str(exc).lower()
    name = type(exc).__name__

    if name == "RedirectDenied":
        return "redirect_limit"
    if "dns failed" in message or "no addresses for" in message:
        return "dns_resolution_failed"
    if "169.254.169.254" in message or "fd00:ec2::254" in message or "169.254.170.2" in message:
        return "metadata_ip"
    if name == "AddressDenied":
        return _classify_denied_address(message)
    if name == "SSRFPolicyError":
        if "scheme" in message:
            return "scheme_disallowed"
        if "userinfo" in message:
            return "userinfo_present"
    return "other"
