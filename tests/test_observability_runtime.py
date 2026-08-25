"""Runtime producer tests for the PT-P5 egress-to-OTLP vertical slice."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import src.observability.runtime as runtime
from src.observability.otel_exporter import project_to_otel_attributes
from utils.egress_telemetry import EgressEvent, _sink_path, emit

_COMMIT = "a" * 40


def test_build_validation_observation_is_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_host = "privacy-canary-host.example.com"
    raw_ip = "203.0.113.77"
    monkeypatch.setenv("PERPETUA_TOOLS_COMMIT", _COMMIT)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    observation = runtime.build_egress_observation(
        EgressEvent(
            endpoint_class="remote",
            host=raw_host,
            resolved_ip=raw_ip,
            port=443,
            scheme="https",
            validation_duration_ms=2.5,
        )
    )

    assert observation is not None
    assert observation.event_name == "egress.validation"
    assert observation.transport == "pinned_requests"
    assert observation.outcome == "allowed"
    attrs = project_to_otel_attributes(observation)
    rendered = json.dumps(attrs, sort_keys=True)
    assert raw_host not in rendered
    assert raw_ip not in rendered
    assert attrs["oramasys.destination.hash"].startswith("sha256:")
    assert "server.address" not in attrs


def test_build_complete_observation_maps_local_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PERPETUA_TOOLS_COMMIT", _COMMIT)
    observation = runtime.build_egress_observation(
        EgressEvent(
            event_kind="complete",
            endpoint_class="local",
            host="localhost",
            port=8001,
            scheme="http",
            duration_ms=12.0,
            status_code=200,
        )
    )
    assert observation is not None
    assert observation.event_name == "egress.request.complete"
    assert observation.transport == "local_http"
    assert observation.outcome == "completed"


def test_collector_transport_is_not_reexported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PERPETUA_TOOLS_COMMIT", _COMMIT)
    monkeypatch.setenv(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "https://otel-collector.example.com:4318/v1/traces",
    )
    event = EgressEvent(
        endpoint_class="remote",
        host="otel-collector.example.com",
        port=4318,
        scheme="https",
    )
    assert runtime.build_egress_observation(event) is None


def test_initialize_disabled_without_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    state = runtime.initialize_observability()
    assert state.enabled is False
    assert state.reason == "endpoint_absent"


def test_observe_is_nonblocking_on_export_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PERPETUA_TOOLS_COMMIT", _COMMIT)
    monkeypatch.setattr(
        runtime,
        "initialize_observability",
        lambda: runtime.ObservabilityRuntimeState(True, "configured"),
    )

    def fail_export(_observation: object) -> bool:
        raise RuntimeError("collector unavailable")

    monkeypatch.setattr(runtime, "export_observation_to_otel", fail_export)
    event = EgressEvent(
        event_kind="complete",
        endpoint_class="remote",
        host="api.example.com",
        port=443,
        scheme="https",
        duration_ms=3.0,
    )
    assert runtime.observe_egress_event(event) is False


def test_canonical_emit_invokes_runtime_bridge_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PERPETUA_TELEMETRY_DIR", str(tmp_path))
    seen: list[EgressEvent] = []
    monkeypatch.setattr(runtime, "observe_egress_event", lambda event: seen.append(event) or True)
    event = EgressEvent(
        event_kind="complete",
        endpoint_class="remote",
        host="api.example.com",
        port=443,
        scheme="https",
        duration_ms=4.0,
        status_code=204,
    )

    emit(event)

    assert seen == [event]
    records = _sink_path().read_text(encoding="utf-8").splitlines()
    assert len(records) == 1
    assert json.loads(records[0])["event_kind"] == "complete"


def test_remote_export_is_independent_of_local_sink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("PERPETUA_TELEMETRY_DIR", str(blocker / "nested"))
    seen: list[EgressEvent] = []
    monkeypatch.setattr(runtime, "observe_egress_event", lambda event: seen.append(event) or True)
    event = EgressEvent(endpoint_class="remote", host="api.example.com", port=443, scheme="https")

    emit(event)

    assert seen == [event]
