"""Tests for OpenTelemetry projection and privacy gating in src/observability/otel_exporter.py."""
from __future__ import annotations

from types import SimpleNamespace

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


class _FakeTracerProvider:
    def __init__(self, resource=None) -> None:
        self.resource = resource
        self.processors: list[object] = []

    def add_span_processor(self, processor: object) -> None:
        self.processors.append(processor)


def test_optional_otel_dependency_surface_is_stable() -> None:
    import src.observability.otel_exporter as exporter_module

    for name in (
        "otel_trace",
        "Resource",
        "TracerProvider",
        "BatchSpanProcessor",
        "OTLPSpanExporter",
    ):
        assert hasattr(exporter_module, name)


def _install_fake_otel(monkeypatch: pytest.MonkeyPatch):
    import src.observability.otel_exporter as exporter_module

    state = {"provider": object()}
    exporter_calls: list[dict[str, object]] = []

    class FakeExporter:
        def __init__(self, **kwargs: object) -> None:
            exporter_calls.append(kwargs)

    class FakeBatchSpanProcessor:
        def __init__(self, exporter: object) -> None:
            self.exporter = exporter

    monkeypatch.setattr(exporter_module, "HAS_OTEL", True)
    monkeypatch.setattr(exporter_module, "HAS_OTLP_EXPORTER", True)
    monkeypatch.setattr(exporter_module, "TracerProvider", _FakeTracerProvider)
    monkeypatch.setattr(exporter_module, "OTLPSpanExporter", FakeExporter)
    monkeypatch.setattr(exporter_module, "BatchSpanProcessor", FakeBatchSpanProcessor)
    monkeypatch.setattr(
        exporter_module,
        "Resource",
        SimpleNamespace(create=lambda attributes: dict(attributes)),
    )
    monkeypatch.setattr(
        exporter_module,
        "otel_trace",
        SimpleNamespace(
            get_tracer_provider=lambda: state["provider"],
            set_tracer_provider=lambda provider: state.__setitem__("provider", provider),
        ),
    )
    return exporter_module, state, exporter_calls


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


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://collector.example/v1/traces",
        "https://169.254.169.254/v1/traces",
        "https://10.0.0.10/v1/traces",
        "https://[::ffff:169.254.169.254]/v1/traces",
        "https://localhost/v1/traces",
        "https://user:password@collector.example/v1/traces",
        "https://collector.example/v1/traces?token=secret",
        "https://collector.example:99999/v1/traces",
    ],
)
def test_otlp_endpoint_policy_rejects_unsafe_destinations_before_exporter_creation(
    endpoint: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exporter_module, _state, exporter_calls = _install_fake_otel(monkeypatch)

    assert exporter_module.configure_otel_exporter(endpoint=endpoint) is False
    assert exporter_calls == []


def test_otlp_exporter_uses_connection_time_pinned_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exporter_module, _state, exporter_calls = _install_fake_otel(monkeypatch)

    assert (
        exporter_module.configure_otel_exporter(
            endpoint="https://collector.example/v1/traces"
        )
        is True
    )

    assert len(exporter_calls) == 1
    session = exporter_calls[0]["session"]
    from utils.ssrf_pinned_adapter import SSRFPinnedHTTPAdapter

    assert isinstance(
        session.get_adapter("https://collector.example"),
        SSRFPinnedHTTPAdapter,
    )
    assert session.max_redirects == 0
    assert session.trust_env is False


def test_generic_otlp_endpoint_appends_trace_export_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exporter_module, _state, exporter_calls = _install_fake_otel(monkeypatch)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://collector.example/base")

    assert exporter_module.configure_otel_exporter() is True
    assert (
        exporter_calls[0]["endpoint"]
        == "https://collector.example/base/v1/traces"
    )


def test_test_reset_does_not_mutate_opentelemetry_private_globals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exporter_module, state, _exporter_calls = _install_fake_otel(monkeypatch)
    sentinel = state["provider"]

    exporter_module._reset_otel_for_testing()

    assert state["provider"] is sentinel
    assert not hasattr(exporter_module.otel_trace, "_TRACER_PROVIDER")
    assert not hasattr(exporter_module.otel_trace, "_TRACER_PROVIDER_SET_ONCE")


def test_force_reconfigure_attaches_to_an_existing_global_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.observability.otel_exporter as exporter_module

    external_provider = _FakeTracerProvider()
    processor = object()
    monkeypatch.setattr(exporter_module, "HAS_OTEL", True)
    monkeypatch.setattr(exporter_module, "TracerProvider", _FakeTracerProvider)
    monkeypatch.setattr(
        exporter_module,
        "otel_trace",
        SimpleNamespace(
            get_tracer_provider=lambda: external_provider,
            # OpenTelemetry accepts one global provider; later registrations
            # are ignored. The configurator must therefore attach to the
            # provider it found instead of constructing an orphan provider.
            set_tracer_provider=lambda _provider: None,
        ),
    )

    assert (
        exporter_module.configure_otel_exporter(
            custom_span_processor=processor,
            force_reconfigure=True,
        )
        is True
    )
    assert external_provider.processors == [processor]


def test_injected_provider_does_not_replace_the_global_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exporter_module, state, _exporter_calls = _install_fake_otel(monkeypatch)
    global_provider = state["provider"]
    injected_provider = _FakeTracerProvider()
    processor = object()

    assert (
        exporter_module.configure_otel_exporter(
            custom_span_processor=processor,
            tracer_provider=injected_provider,
        )
        is True
    )

    assert injected_provider.processors == [processor]
    assert state["provider"] is global_provider
    assert exporter_module._ACTIVE_PROVIDER is injected_provider


def test_injected_processor_does_not_consume_endpoint_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exporter_module, _state, _exporter_calls = _install_fake_otel(monkeypatch)
    injected_provider = _FakeTracerProvider()
    processor = object()
    monkeypatch.setenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "https://169.254.169.254",
    )

    assert (
        exporter_module.configure_otel_exporter(
            custom_span_processor=processor,
            tracer_provider=injected_provider,
        )
        is True
    )
    assert injected_provider.processors == [processor]
