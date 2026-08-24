"""OpenTelemetry Projection & OTLP Exporter for pt-orama.

Projects Pydantic v2 DomainObservation instances into real OpenTelemetry
traces, spans, and log-based EventRecords. Enforces two-tier privacy boundaries
(refusing to export internal_only observations) and names custom attributes
under the oramasys.* namespace.
Reference: orama-system docs/v2/55-oramasys-agent-observability-contract-adr.md
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, Optional

from src.observability.core import (
    BaseObservation,
    BiasAdvisoryObservation,
    DomainObservation,
    EgressCompleteObservation,
    EgressValidationObservation,
    TaskLifecycleObservation,
)

logger = logging.getLogger(__name__)

# Check if official OpenTelemetry SDK is installed
try:
    import opentelemetry.trace as otel_trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        HAS_OTLP_EXPORTER = True
    except ImportError:
        OTLPSpanExporter = None  # type: ignore
        HAS_OTLP_EXPORTER = False

    HAS_OTEL = True
except ImportError:
    HAS_OTEL = False
    HAS_OTLP_EXPORTER = False

_CONFIG_LOCK = threading.Lock()
_IS_CONFIGURED = False
_ACTIVE_PROVIDER: Optional[Any] = None


def configure_otel_exporter(
    endpoint: Optional[str] = None,
    custom_span_processor: Optional[Any] = None,
    force_reconfigure: bool = False,
) -> bool:
    """Configure one OTLP/HTTP Protobuf trace pipeline per process.

    Thread-safe and idempotent. Reuses an existing global TracerProvider if
    already installed by the runtime, or registers a new TracerProvider with
    safe resource metadata and OTLPSpanExporter (or custom processor).
    """
    global _IS_CONFIGURED, _ACTIVE_PROVIDER
    if not HAS_OTEL:
        return False

    with _CONFIG_LOCK:
        if _IS_CONFIGURED and not force_reconfigure:
            return True

        target_endpoint = (
            endpoint
            if endpoint is not None
            else (
                os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
                or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
            )
        )

        if not target_endpoint and custom_span_processor is None:
            return False

        try:
            current_provider = otel_trace.get_tracer_provider()

            # If an existing TracerProvider is already active in the process,
            # attach processors to it to preserve global trace continuity.
            if isinstance(current_provider, TracerProvider) and not force_reconfigure:
                if custom_span_processor is not None:
                    current_provider.add_span_processor(custom_span_processor)
                elif HAS_OTLP_EXPORTER and target_endpoint:
                    exporter = OTLPSpanExporter(endpoint=target_endpoint)
                    current_provider.add_span_processor(BatchSpanProcessor(exporter))
                else:
                    logger.debug("OTLP exporter requested but opentelemetry-exporter-otlp-proto-http unavailable")
                    return False

                _ACTIVE_PROVIDER = current_provider
                _IS_CONFIGURED = True
                return True

            # Otherwise, instantiate a fresh TracerProvider with safe resource metadata
            resource = Resource.create(
                {
                    "service.name": "perpetua-tools",
                    "telemetry.sdk.language": "python",
                }
            )
            provider = TracerProvider(resource=resource)

            if custom_span_processor is not None:
                provider.add_span_processor(custom_span_processor)
            elif HAS_OTLP_EXPORTER and target_endpoint:
                exporter = OTLPSpanExporter(endpoint=target_endpoint)
                provider.add_span_processor(BatchSpanProcessor(exporter))
            else:
                logger.debug("OTLP exporter requested but opentelemetry-exporter-otlp-proto-http unavailable")
                return False

            otel_trace.set_tracer_provider(provider)
            active = otel_trace.get_tracer_provider()

            # Ensure provider was actually accepted or is a functional TracerProvider
            if active is provider or isinstance(active, TracerProvider):
                _ACTIVE_PROVIDER = active if isinstance(active, TracerProvider) else provider
                _IS_CONFIGURED = True
                return True
            else:
                logger.debug("TracerProvider registration was ignored and active provider is not functional")
                _ACTIVE_PROVIDER = None
                _IS_CONFIGURED = False
                return False
        except Exception as exc:
            logger.debug("Failed to configure OTel exporter: %s", exc)
            return False


def _reset_otel_for_testing() -> None:
    """Reset configuration state for isolated unit tests."""
    global _IS_CONFIGURED, _ACTIVE_PROVIDER
    with _CONFIG_LOCK:
        _IS_CONFIGURED = False
        _ACTIVE_PROVIDER = None
        if HAS_OTEL:
            try:
                otel_trace._TRACER_PROVIDER = None
                if hasattr(otel_trace, "_TRACER_PROVIDER_SET_ONCE"):
                    otel_trace._TRACER_PROVIDER_SET_ONCE._done = False
            except Exception:
                pass


def project_to_otel_attributes(observation: BaseObservation) -> Dict[str, Any]:
    """Map a DomainObservation to compliant OpenTelemetry attributes.

    Enforces the privacy contract: rejects internal_only records, never
    populates server.address with hash strings, and scopes custom fields under
    the oramasys.* namespace.
    """
    if observation.privacy.classification != "redacted":
        raise PermissionError(
            f"Cannot project observation with privacy classification '{observation.privacy.classification}' "
            "to remote OpenTelemetry export -- only 'redacted' records are eligible."
        )

    attrs: Dict[str, Any] = {
        "service.name": "perpetua-tools",
        "service.instance.id": observation.agent.instance_id,
        "gen_ai.agent.id": observation.agent.id,
        "oramasys.harness": observation.agent.harness,
        "oramasys.provenance.repo": observation.source.repo,
        "oramasys.provenance.commit": observation.source.commit,
        "oramasys.provenance.component": observation.source.component,
        "oramasys.schema_version": observation.schema_version,
    }

    if observation.task_id:
        attrs["oramasys.task_id"] = observation.task_id
    if observation.run_id:
        attrs["oramasys.run_id"] = observation.run_id

    if isinstance(observation, EgressValidationObservation):
        attrs.update(
            {
                "event.name": "egress.validation",
                "oramasys.destination.hash": observation.destination_hash,
                "oramasys.egress.endpoint_class": observation.endpoint_class,
                "oramasys.egress.transport": observation.transport,
                "oramasys.egress.outcome": observation.outcome,
                "oramasys.egress.port": observation.port,
                "oramasys.egress.validation_ms": observation.validation_ms,
                "oramasys.egress.redirect_hop": observation.redirect_hop,
            }
        )
        if observation.deny_reason:
            attrs["oramasys.egress.deny_reason"] = str(observation.deny_reason)

    elif isinstance(observation, EgressCompleteObservation):
        attrs.update(
            {
                "event.name": "egress.request.complete",
                "oramasys.destination.hash": observation.destination_hash,
                "oramasys.egress.endpoint_class": observation.endpoint_class,
                "oramasys.egress.transport": observation.transport,
                "oramasys.egress.outcome": observation.outcome,
                "oramasys.duration_ms": observation.duration_ms,
            }
        )
        if observation.status_code is not None:
            attrs["http.response.status_code"] = observation.status_code

    elif isinstance(observation, TaskLifecycleObservation):
        attrs.update(
            {
                "event.name": "task.lifecycle",
                "oramasys.task.stage": observation.lifecycle_stage,
                "oramasys.task.name": observation.task_name,
                "oramasys.task.phase": observation.phase,
                "oramasys.task.priority": observation.priority,
                "oramasys.task.notes_present": observation.notes_present,
            }
        )
        if observation.assigned_agent:
            attrs["oramasys.task.assigned_agent"] = observation.assigned_agent
        if observation.source_ref:
            attrs["oramasys.task.source_ref"] = observation.source_ref
        if observation.expected_base_sha:
            attrs["oramasys.task.expected_base_sha"] = observation.expected_base_sha

    elif isinstance(observation, BiasAdvisoryObservation):
        attrs.update(
            {
                "event.name": "coordination.bias_advisory",
                "oramasys.bias.risk": observation.coordination_risk,
                "oramasys.bias.confidence_mean": observation.confidence_mean,
                "oramasys.bias.confidence_stdev": observation.confidence_stdev,
                "oramasys.bias.distinct_agent_count": observation.distinct_agent_count,
                "oramasys.bias.window_size": observation.evidence_window_size,
                "oramasys.bias.rationale_codes": ",".join(observation.rationale_codes),
            }
        )

    return attrs


def export_observation_to_otel(observation: BaseObservation) -> bool:
    """Project a DomainObservation and export it via OpenTelemetry if enabled.

    Returns True if successfully exported, False if OTel is not enabled or unconfigured.
    Raises PermissionError if observation is internal_only.
    """
    # 1. Project attributes first (raises PermissionError if internal_only)
    attrs = project_to_otel_attributes(observation)

    if not HAS_OTEL:
        return False

    # 2. Ensure pipeline is configured
    if not _IS_CONFIGURED:
        configured = configure_otel_exporter()
        if not configured:
            return False

    try:
        if _ACTIVE_PROVIDER is not None:
            tracer = _ACTIVE_PROVIDER.get_tracer("oramasys.observability")
        else:
            tracer = otel_trace.get_tracer("oramasys.observability")
        span_name = getattr(observation, "event_name", "domain.observation")
        with tracer.start_as_current_span(span_name, attributes=attrs):
            pass
        return True
    except Exception as exc:
        logger.debug("OTel export failed non-blockingly: %s", exc)
        return False
