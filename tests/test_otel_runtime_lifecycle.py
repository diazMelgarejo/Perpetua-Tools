"""Lifecycle and delivery-barrier tests for PT OpenTelemetry runtime support."""
from __future__ import annotations

import json

import pytest

import src.observability.otel_exporter as exporter_module
import src.observability.runtime as runtime
from src.observability.otel_exporter import (
    _reset_otel_for_testing,
    configure_otel_exporter,
)
from utils.egress_telemetry import EgressEvent

try:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    HAS_OTEL_TEST_EXPORTER = True
except ImportError:
    HAS_OTEL_TEST_EXPORTER = False

_COMMIT = "b" * 40


@pytest.fixture(autouse=True)
def reset_pt_otel_state():
    _reset_otel_for_testing()
    yield
    _reset_otel_for_testing()


def test_force_flush_and_shutdown_use_active_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[object] = []

    class Provider:
        def force_flush(self, timeout_millis: int) -> bool:
            calls.append(("flush", timeout_millis))
            return True

        def shutdown(self) -> None:
            calls.append("shutdown")

    provider = Provider()
    monkeypatch.setattr(exporter_module, "_ACTIVE_PROVIDER", provider)
    monkeypatch.setattr(exporter_module, "_IS_CONFIGURED", True)

    assert exporter_module.force_flush_otel(1234) is True
    assert exporter_module.shutdown_otel(1234) is True
    assert ("flush", 1234) in calls
    assert "shutdown" in calls
    assert exporter_module._ACTIVE_PROVIDER is None
    assert exporter_module._IS_CONFIGURED is False


@pytest.mark.skipif(not HAS_OTEL_TEST_EXPORTER, reason="OpenTelemetry SDK in-memory exporter required")
def test_runtime_bridge_reaches_in_memory_exporter_after_flush(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PERPETUA_TOOLS_COMMIT", _COMMIT)
    memory_exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(memory_exporter)
    provider = TracerProvider()
    assert configure_otel_exporter(
        custom_span_processor=processor,
        tracer_provider=provider,
    ) is True
    monkeypatch.setattr(
        runtime,
        "initialize_observability",
        lambda: runtime.ObservabilityRuntimeState(True, "configured"),
    )

    event = EgressEvent(
        event_kind="complete",
        endpoint_class="remote",
        host="privacy-canary-host.example.com",
        resolved_ip="203.0.113.77",
        port=443,
        scheme="https",
        duration_ms=7.0,
        status_code=204,
    )
    assert runtime.observe_egress_event(event) is True
    assert runtime.force_flush_observability(1000) is True

    spans = memory_exporter.get_finished_spans()
    assert len(spans) == 1
    attrs = dict(spans[0].attributes)
    rendered = json.dumps(attrs, sort_keys=True)
    assert attrs["service.name"] == "perpetua-tools"
    assert attrs["oramasys.egress.endpoint_class"] == "remote"
    assert attrs["oramasys.destination.hash"].startswith("sha256:")
    assert attrs["oramasys.egress.outcome"] == "completed"
    assert "server.address" not in attrs
    assert "privacy-canary-host" not in rendered
    assert "203.0.113.77" not in rendered
