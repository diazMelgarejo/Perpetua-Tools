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
from src.observability.otel_exporter import export_observation_to_otel, project_to_otel_attributes


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

    def test_export_observation_returns_false_when_unconfigured(self, sample_agent, sample_source) -> None:
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
        # Without OTEL_EXPORTER_OTLP_ENDPOINT set, export safely returns False non-blockingly
        assert export_observation_to_otel(obs) is False
