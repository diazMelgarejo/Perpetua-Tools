"""Runtime bridge from PT redacted egress telemetry to OpenTelemetry.

This module is deliberately narrow: it consumes the existing ``EgressEvent``
redacted projection and turns validation/completion events into the typed
DomainObservation models already enforced by the OTLP exporter.  It never
accepts raw prompt/task/path data and never weakens the global egress policy.
"""
from __future__ import annotations

import atexit
import os
import re
import subprocess
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from src.observability.core import (
    AgentIdentity,
    EgressCompleteObservation,
    EgressValidationObservation,
    SourceProvenance,
)
from src.observability.otel_exporter import (
    HAS_OTEL,
    configure_otel_exporter,
    export_observation_to_otel,
    force_flush_otel,
    shutdown_otel,
)
from utils.egress_telemetry import EgressEvent

_REPO = "diazMelgarejo/Perpetua-Tools"
_COMPONENT = "utils.egress_telemetry"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_LIFECYCLE_LOCK = threading.Lock()
_ATEXIT_REGISTERED = False
_AGENT = AgentIdentity(id="pt-runtime-egress", harness="standalone")


@dataclass(frozen=True)
class ObservabilityRuntimeState:
    enabled: bool
    reason: str


def _configured_endpoint() -> str:
    traces = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
    if traces:
        return traces
    return os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()


@lru_cache(maxsize=1)
def _resolve_source_commit() -> str | None:
    """Return an auditable 40-character source commit or fail closed.

    Operators may supply ``PERPETUA_TOOLS_COMMIT`` for packaged deployments.
    Source checkouts fall back to ``git rev-parse HEAD``.  We never invent a
    placeholder SHA because provenance is part of the observability contract.
    The result is stable for the process lifetime and therefore resolved once.
    """
    configured = os.getenv("PERPETUA_TOOLS_COMMIT", "").strip().lower()
    if _SHA40.fullmatch(configured):
        return configured

    repo_root = Path(__file__).resolve().parents[2]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    commit = result.stdout.strip().lower()
    return commit if _SHA40.fullmatch(commit) else None


def _is_collector_transport(event: EgressEvent) -> bool:
    """Prevent telemetry-of-telemetry recursion for the OTLP connection.

    The pinned Requests adapter emits normal redacted egress telemetry for all
    remote connections, including the collector itself.  Re-exporting that
    collector event would create an unbounded BatchSpanProcessor feedback loop.
    The event remains in the local redacted JSONL sink; it is merely excluded
    from remote OTLP projection.
    """
    endpoint = _configured_endpoint()
    if not endpoint or event.endpoint_class != "remote":
        return False
    parsed = urlparse(endpoint)
    hostname = (parsed.hostname or "").casefold()
    port = parsed.port or (443 if parsed.scheme.casefold() == "https" else 80)
    return bool(hostname) and event.host.casefold() == hostname and event.port == port


def initialize_observability() -> ObservabilityRuntimeState:
    """Configure the existing OTel pipeline once when explicitly requested."""
    global _ATEXIT_REGISTERED
    if not _configured_endpoint():
        return ObservabilityRuntimeState(False, "endpoint_absent")
    if not HAS_OTEL:
        return ObservabilityRuntimeState(False, "dependency_absent")

    enabled = configure_otel_exporter()
    if not enabled:
        return ObservabilityRuntimeState(False, "configuration_rejected")

    with _LIFECYCLE_LOCK:
        if not _ATEXIT_REGISTERED:
            atexit.register(_shutdown_at_exit)
            _ATEXIT_REGISTERED = True
    return ObservabilityRuntimeState(True, "configured")


def build_egress_observation(event: EgressEvent) -> EgressValidationObservation | EgressCompleteObservation | None:
    """Build a typed observation using only ``EgressEvent.to_redacted_dict``."""
    if _is_collector_transport(event):
        return None

    redacted = event.to_redacted_dict()
    destination_hash = redacted.get("host_hash")
    commit = _resolve_source_commit()
    if not isinstance(destination_hash, str) or not commit:
        return None

    source = SourceProvenance(repo=_REPO, commit=commit, component=_COMPONENT)
    transport = "local_http" if redacted["endpoint_class"] == "local" else "pinned_requests"

    if redacted["event_kind"] == "validation":
        deny_reason = redacted.get("deny_reason")
        return EgressValidationObservation(
            agent=_AGENT,
            source=source,
            endpoint_class=redacted["endpoint_class"],
            transport=transport,
            outcome="denied" if deny_reason else "allowed",
            deny_reason=deny_reason,
            port=int(redacted["port"]),
            validation_ms=float(redacted.get("validation_duration_ms") or 0.0),
            redirect_hop=int(redacted.get("redirect_count") or 0),
            destination_hash=destination_hash,
        )

    return EgressCompleteObservation(
        agent=_AGENT,
        source=source,
        endpoint_class=redacted["endpoint_class"],
        transport=transport,
        outcome="failed" if redacted.get("deny_reason") else "completed",
        status_code=redacted.get("status_code"),
        duration_ms=float(redacted.get("duration_ms") or 0.0),
        destination_hash=destination_hash,
    )


def observe_egress_event(event: EgressEvent) -> bool:
    """Export one existing redacted egress event without affecting its caller."""
    try:
        state = initialize_observability()
        if not state.enabled:
            return False
        observation = build_egress_observation(event)
        if observation is None:
            return False
        return bool(export_observation_to_otel(observation))
    except Exception:
        # Runtime telemetry is strictly non-blocking.  Privacy violations from
        # caller-supplied observations are enforced in the exporter; this bridge
        # only constructs redacted observations itself.
        return False


def force_flush_observability(timeout_ms: int = 5000) -> bool:
    return force_flush_otel(timeout_millis=max(1, int(timeout_ms)))


def shutdown_observability(timeout_ms: int = 5000) -> bool:
    return shutdown_otel(timeout_millis=max(1, int(timeout_ms)))


def _shutdown_at_exit() -> None:
    shutdown_observability(timeout_ms=2000)
