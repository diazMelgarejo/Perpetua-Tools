"""Tests for OpenTelemetry projection and privacy gating in src/observability/otel_exporter.py."""
from __future__ import annotations

import pytest

from src.observability.core import (
    AgentIdentity,
    BiasAdvisoryObservation,
    EgressCompleteObservation,
    EgressValidationObservation,
    PrivacyEnvelope,
    SourceProvenance,
    TaskLifecycleObservation,
)
from src.observability.otel_exporter import (
    _reset_otel_for_testing,
    configure_otel_exporter,
    export_observation_to_otel,
    project_to_otel_attributes,
)

try:
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    HAS_OTEL_TEST_EXPORTER = True
except ImportError:
    HAS_OTEL_TEST_EXPORTER = False


@pytest.fixture(autouse=True)
def reset_otel():
    _reset_otel_for_testing()
    yield
    _reset_otel_for_testing()


@pytest.fixture
def sample_agent() -> AgentIdentity:
    return AgentIdentity(id="pt-test-agent", harness="gemini")


@pytest.fixture
def sample_source() -> SourceProvenance:
    return SourceProvenance(
        repo="diazMelgarejo/Perpetua-Tools",
        commit="38ad105116fedcf22959f373d259890c6508849a",
        component="orchestrator.orama_bridge",
    )


class TestOTelProjection:
    def test_egress_validation_projection_attributes(self, sample_agent, sample_source) -> None:
        obs = EgressValidationObservation(
            agent=sample_agent,
            source=sample_source,
            endpoint_class="remote",
            transport="pinned_requests",
            outcome="allowed",
            port=443,
            validation_ms=3.14,
            destination_hash="sha256:123456",
        )
        attrs = project_to_otel_attributes(obs)
        assert attrs["event.name"] == "egress.validation"
        assert attrs["oramasys.destination.hash"] == "sha256:123456"
        assert attrs["oramasys.egress.port"] == 443
        assert attrs["oramasys.egress.validation_ms"] == 3.14
        assert attrs["gen_ai.agent.id"] == "pt-test-agent"
        # Invariant: server.address must NEVER be emitted in redacted projections
        assert "server.address" not in attrs

    def test_egress_complete_projection_attributes(self, sample_agent, sample_source) -> None:
        obs = EgressCompleteObservation(
            agent=sample_agent,
            source=sample_source,
            endpoint_class="remote",
            transport="pinned_requests",
            outcome="completed",
            status_code=200,
            duration_ms=120.5,
            destination_hash="sha256:123456",
        )
        attrs = project_to_otel_attributes(obs)
        assert attrs["event.name"] == "egress.request.complete"
        assert attrs["http.response.status_code"] == 200
        assert attrs["oramasys.duration_ms"] == 120.5

    def test_task_lifecycle_projection_attributes(self, sample_agent, sample_source) -> None:
        obs = TaskLifecycleObservation(
            agent=sample_agent,
            source=sample_source,
            lifecycle_stage="claimed",
            task_name="test-task",
            phase="phase-1",
            priority="P1",
            notes_present=True,
        )
        attrs = project_to_otel_attributes(obs)
        assert attrs["event.name"] == "task.lifecycle"
        assert attrs["oramasys.task.stage"] == "claimed"
        assert attrs["oramasys.task.notes_present"] is True

    def test_bias_advisory_projection_attributes(self, sample_agent, sample_source) -> None:
        obs = BiasAdvisoryObservation(
            agent=sample_agent,
            source=sample_source,
            coordination_risk="high",
            confidence_mean=0.92,
            confidence_stdev=0.03,
            distinct_agent_count=3,
            evidence_window_size=10,
            rationale_codes=["agreement_collapse"],
        )
        attrs = project_to_otel_attributes(obs)
        assert attrs["event.name"] == "coordination.bias_advisory"
        assert attrs["oramasys.bias.risk"] == "high"
        assert attrs["oramasys.bias.distinct_agent_count"] == 3

    def test_internal_only_observation_raises_permission_error(self, sample_agent, sample_source) -> None:
        obs = EgressValidationObservation(
            agent=sample_agent,
            source=sample_source,
            privacy=PrivacyEnvelope(classification="internal_only"),
            endpoint_class="local",
            transport="local_http",
            outcome="allowed",
            port=8001,
            validation_ms=0.5,
            destination_hash="sha256:local",
        )
        with pytest.raises(PermissionError) as exc:
            project_to_otel_attributes(obs)
        assert "only 'redacted' records are eligible" in str(exc.value)

    def test_export_observation_returns_false_when_unconfigured(self, sample_agent, sample_source, monkeypatch) -> None:
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        obs = EgressValidationObservation(
            agent=sample_agent,
            source=sample_source,
            endpoint_class="remote",
            transport="pinned_requests",
            outcome="allowed",
            port=443,
            validation_ms=1.0,
            destination_hash="sha256:test",
        )
        # Without endpoint configured, export safely returns False non-blockingly
        assert export_observation_to_otel(obs) is False

    @pytest.mark.skipif(not HAS_OTEL_TEST_EXPORTER, reason="OpenTelemetry SDK in-memory exporter required")
    def test_in_memory_exporter_receives_finished_span(self, sample_agent, sample_source) -> None:
        memory_exporter = InMemorySpanExporter()
        span_processor = SimpleSpanProcessor(memory_exporter)
        configured = configure_otel_exporter(custom_span_processor=span_processor, force_reconfigure=True)
        assert configured is True

        obs = EgressCompleteObservation(
            agent=sample_agent,
            source=sample_source,
            endpoint_class="remote",
            transport="pinned_requests",
            outcome="completed",
            status_code=200,
            duration_ms=45.6,
            destination_hash="sha256:fedcba987654",
        )

        exported = export_observation_to_otel(obs)
        assert exported is True

        spans = memory_exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        assert span.name == "egress.request.complete"
        assert span.attributes["oramasys.destination.hash"] == "sha256:fedcba987654"
        assert span.attributes["http.response.status_code"] == 200
        assert span.attributes["oramasys.duration_ms"] == 45.6
        assert "server.address" not in span.attributes

    @pytest.mark.skipif(not HAS_OTEL_TEST_EXPORTER, reason="OpenTelemetry SDK in-memory exporter required")
    def test_internal_only_observation_never_reaches_exporter(self, sample_agent, sample_source) -> None:
        memory_exporter = InMemorySpanExporter()
        span_processor = SimpleSpanProcessor(memory_exporter)
        configure_otel_exporter(custom_span_processor=span_processor, force_reconfigure=True)

        obs = EgressValidationObservation(
            agent=sample_agent,
            source=sample_source,
            privacy=PrivacyEnvelope(classification="internal_only"),
            endpoint_class="local",
            transport="local_http",
            outcome="allowed",
            port=8001,
            validation_ms=0.5,
            destination_hash="sha256:local",
        )

        with pytest.raises(PermissionError):
            export_observation_to_otel(obs)

        # Invariant: exporter buffer has 0 spans
        assert len(memory_exporter.get_finished_spans()) == 0

    def test_repeated_configuration_is_idempotent(self) -> None:
        if not HAS_OTEL_TEST_EXPORTER:
            pytest.skip("OpenTelemetry SDK not installed")
        memory_exporter = InMemorySpanExporter()
        processor = SimpleSpanProcessor(memory_exporter)
        assert configure_otel_exporter(custom_span_processor=processor, force_reconfigure=True) is True
        # Second call without force_reconfigure should return True immediately without reconfiguring
        assert configure_otel_exporter(custom_span_processor=processor, force_reconfigure=False) is True

    @pytest.mark.skipif(not HAS_OTEL_TEST_EXPORTER, reason="OpenTelemetry SDK in-memory exporter required")
    def test_reuses_existing_global_tracer_provider(self, sample_agent, sample_source) -> None:
        import opentelemetry.trace as otel_trace
        from opentelemetry.sdk.trace import TracerProvider

        # Simulate an external harness having already installed a TracerProvider
        external_provider = TracerProvider()
        otel_trace.set_tracer_provider(external_provider)

        memory_exporter = InMemorySpanExporter()
        processor = SimpleSpanProcessor(memory_exporter)

        # configure_otel_exporter should attach processor to the existing TracerProvider
        configured = configure_otel_exporter(custom_span_processor=processor, force_reconfigure=False)
        assert configured is True

        obs = EgressCompleteObservation(
            agent=sample_agent,
            source=sample_source,
            endpoint_class="remote",
            transport="pinned_requests",
            outcome="completed",
            status_code=200,
            duration_ms=50.0,
            destination_hash="sha256:abcd",
        )

        exported = export_observation_to_otel(obs)
        assert exported is True
        spans = memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "egress.request.complete"
