"""Pre-merge lifecycle and operator-smoke regressions for PT-P5."""
from __future__ import annotations

import json

import pytest

import src.observability.otel_exporter as exporter_module
import src.observability.runtime as runtime
import src.observability.smoke as smoke

try:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    HAS_OTEL_TEST_EXPORTER = True
except ImportError:
    HAS_OTEL_TEST_EXPORTER = False

_COMMIT = "c" * 40
_ENDPOINT = "https://otel-collector.example.com:4318/v1/traces"


@pytest.fixture(autouse=True)
def reset_pt_otel_state():
    exporter_module._reset_otel_for_testing()
    yield
    exporter_module._reset_otel_for_testing()


def test_missing_deploy_provenance_disables_before_exporter_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", _ENDPOINT)
    monkeypatch.delenv("PERPETUA_TOOLS_COMMIT", raising=False)
    monkeypatch.setattr(runtime, "HAS_OTEL", True)
    calls: list[object] = []
    monkeypatch.setattr(
        runtime,
        "configure_otel_exporter",
        lambda: calls.append(object()) or True,
    )

    state = runtime.initialize_observability()

    assert state == runtime.ObservabilityRuntimeState(False, "provenance_unavailable")
    assert calls == []


def test_invalid_deploy_provenance_disables_before_exporter_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", _ENDPOINT)
    monkeypatch.setenv("PERPETUA_TOOLS_COMMIT", "not-a-commit")
    monkeypatch.setattr(runtime, "HAS_OTEL", True)
    calls: list[object] = []
    monkeypatch.setattr(
        runtime,
        "configure_otel_exporter",
        lambda: calls.append(object()) or True,
    )

    state = runtime.initialize_observability()

    assert state == runtime.ObservabilityRuntimeState(False, "provenance_unavailable")
    assert calls == []


@pytest.mark.asyncio
async def test_fastapi_lifespan_owns_observability_startup_and_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import orchestrator.fastapi_app as fastapi_app

    calls: list[object] = []

    class _FakeLoop:
        def run_in_executor(self, _executor, fn, *args):
            fn(*args)
            return None

    class _FakeTask:
        def add_done_callback(self, callback) -> None:
            callback(self)

    def _fake_create_task(coro, *, name=None):
        del name
        coro.close()
        return _FakeTask()

    monkeypatch.setattr(fastapi_app.asyncio, "get_event_loop", lambda: _FakeLoop())
    monkeypatch.setattr(fastapi_app.asyncio, "create_task", _fake_create_task)
    monkeypatch.setattr(fastapi_app, "ensure_control_plane_token", lambda: None)
    monkeypatch.setattr(fastapi_app, "_init_gossip_db", lambda: None)
    monkeypatch.setattr(fastapi_app, "_run_ecc_sync_bg", lambda: None)
    monkeypatch.setattr(
        fastapi_app,
        "initialize_observability",
        lambda: calls.append("initialize")
        or runtime.ObservabilityRuntimeState(True, "configured"),
    )
    monkeypatch.setattr(
        fastapi_app,
        "shutdown_observability",
        lambda timeout_ms=5000: calls.append(("shutdown", timeout_ms)) or True,
    )

    async with fastapi_app._lifespan(fastapi_app.app):
        assert calls == ["initialize"]

    assert calls == ["initialize", ("shutdown", 2000)]


def test_smoke_main_reports_endpoint_absent_and_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("PERPETUA_TOOLS_COMMIT", _COMMIT)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    exit_code = smoke.main()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["configured"] is False
    assert payload["reason"] == "endpoint_absent"
    assert payload["export_submitted"] is False
    assert payload["flushed"] is False
    assert payload["internal_only_rejected"] is True


@pytest.mark.skipif(
    not HAS_OTEL_TEST_EXPORTER,
    reason="OpenTelemetry SDK in-memory exporter required",
)
def test_run_smoke_reaches_in_memory_exporter_without_raw_canary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PERPETUA_TOOLS_COMMIT", _COMMIT)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", _ENDPOINT)

    memory_exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(memory_exporter)
    provider = TracerProvider()
    assert exporter_module.configure_otel_exporter(
        custom_span_processor=processor,
        tracer_provider=provider,
    ) is True

    result = smoke.run_smoke()

    assert result["configured"] is True
    assert result["observation_constructed"] is True
    assert result["export_submitted"] is True
    assert result["flushed"] is True
    assert result["privacy_classification"] == "redacted"
    assert result["internal_only_rejected"] is True
    assert result["reason"] == "configured"

    spans = memory_exporter.get_finished_spans()
    assert len(spans) == 1
    rendered = json.dumps(dict(spans[0].attributes), sort_keys=True)
    assert "pt-otel-smoke.invalid" not in rendered
    assert "server.address" not in rendered
