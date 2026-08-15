"""Integration coverage for the explicit paid Tier-5 control-plane route."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import orchestrator.fastapi_app as app_module
from orchestrator.model_transport import ProviderTransportRegistry
from orchestrator.tiered_pipeline import (
    PipelineApproval,
    PipelineApprovalError,
    PipelineResult,
    TieredPipelineRunner,
)


def _valid_approval(**overrides: object) -> PipelineApproval:
    fields: dict[str, object] = {
        "trace_id": "endpoint-test-trace",
        "approved_by": "operator@example.com",
        "purpose": "integration test",
        "recipe": "classify_then_generate",
        "route_tier": 5,
        "max_tokens": 8192,
        "max_cost_usd": 0.25,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "scope": ("openrouter",),
    }
    fields.update(overrides)
    return PipelineApproval(**fields)


class _Runner:
    captured_run_kwargs: dict[str, object] = {}

    def recipe(self, name: str):
        assert name == "classify_then_generate"
        return type("Recipe", (), {"cost_reservation_usd": 0.25})()

    async def run(self, recipe_name, prompt, **kwargs):
        assert recipe_name == "classify_then_generate"
        assert prompt == "do the work"
        assert callable(kwargs["dispatch"])
        _Runner.captured_run_kwargs = kwargs
        return PipelineResult(
            recipe=recipe_name,
            output="final answer",
            stage_outputs={"classify": "internal", "generate": "final answer"},
            requested_tokens=512,
            total_tokens_used=480,
            total_cost_usd=0.1,
        )


class _RunnerRaisesApprovalError:
    def recipe(self, name: str):
        return type("Recipe", (), {"cost_reservation_usd": 0.25})()

    async def run(self, recipe_name, prompt, **kwargs):
        raise PipelineApprovalError("approval is expired")


class _Transport:
    async def dispatch(self, model, prompt, max_tokens, stage):
        raise AssertionError("runner stub should not dispatch")


@pytest.fixture
def control_plane_client(monkeypatch):
    monkeypatch.setenv("ORAMA_INSECURE_DEV", "0")
    monkeypatch.setenv("ORAMA_CONTROL_PLANE_TOKEN", "pt-test-token")
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "1")
    app_module.app.dependency_overrides[app_module.get_tiered_pipeline_runner] = _Runner
    app_module.app.dependency_overrides[app_module.get_provider_transport] = _Transport
    try:
        with TestClient(app_module.app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app_module.app.dependency_overrides.clear()


@pytest.mark.integration
def test_pipeline_run_requires_control_plane_auth(control_plane_client) -> None:
    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": "any-trace"},
    )
    assert response.status_code == 401


@pytest.mark.integration
def test_pipeline_run_returns_final_output_without_internal_stage_payload(
    control_plane_client, monkeypatch
) -> None:
    monkeypatch.setattr(app_module.cost_guard, "can_spend", lambda amount: amount == 0.25)
    recorded: list[float] = []
    monkeypatch.setattr(app_module.cost_guard, "record_spend", recorded.append)
    approval = _valid_approval()
    monkeypatch.setattr(app_module, "load_pipeline_approval", lambda trace_id: approval)

    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": approval.trace_id},
        headers={"Authorization": "Bearer pt-test-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "completed",
        "recipe": "classify_then_generate",
        "output": "final answer",
        "requested_tokens": 512,
        "cost_reservation_usd": 0.25,
    }
    assert recorded == [0.25]
    assert _Runner.captured_run_kwargs["approval"] is approval


@pytest.mark.integration
def test_pipeline_run_fails_closed_when_feature_is_disabled(control_plane_client, monkeypatch) -> None:
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "0")
    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": "any-trace"},
        headers={"Authorization": "Bearer pt-test-token"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Tier-5 pipelines are disabled"


@pytest.mark.integration
def test_pipeline_run_requires_trace_id_in_request_body(control_plane_client) -> None:
    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work"},
        headers={"Authorization": "Bearer pt-test-token"},
    )
    assert response.status_code == 422


@pytest.mark.integration
def test_pipeline_run_rejects_unregistered_trace_id(control_plane_client, monkeypatch) -> None:
    monkeypatch.setattr(app_module.cost_guard, "can_spend", lambda amount: True)

    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": "never-registered"},
        headers={"Authorization": "Bearer pt-test-token"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Pipeline approval invalid, expired, or revoked"


@pytest.mark.integration
def test_pipeline_run_maps_runner_approval_error_to_403(control_plane_client, monkeypatch) -> None:
    monkeypatch.setattr(app_module.cost_guard, "can_spend", lambda amount: True)
    approval = _valid_approval()
    monkeypatch.setattr(app_module, "load_pipeline_approval", lambda trace_id: approval)
    app_module.app.dependency_overrides[app_module.get_tiered_pipeline_runner] = (
        _RunnerRaisesApprovalError
    )

    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": approval.trace_id},
        headers={"Authorization": "Bearer pt-test-token"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Pipeline approval invalid, expired, or revoked"


@pytest.mark.integration
def test_register_approval_requires_control_plane_auth(control_plane_client) -> None:
    response = control_plane_client.post(
        "/pipelines/approvals",
        json={
            "trace_id": "t1-auth-check",
            "approved_by": "op",
            "purpose": "p",
            "recipe": "classify_then_generate",
            "route_tier": 5,
            "max_tokens": 8192,
            "max_cost_usd": 0.25,
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "scope": ["openrouter"],
        },
    )
    assert response.status_code == 401


@pytest.mark.integration
def test_register_approval_then_run_end_to_end(control_plane_client, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(app_module.cost_guard, "can_spend", lambda amount: True)
    monkeypatch.setattr(app_module.cost_guard, "record_spend", lambda amount: None)
    monkeypatch.setenv("PT_PIPELINE_APPROVAL_DIR", str(tmp_path / "approvals"))

    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    register_response = control_plane_client.post(
        "/pipelines/approvals",
        json={
            "trace_id": "e2e-trace",
            "approved_by": "operator@example.com",
            "purpose": "end to end test",
            "recipe": "classify_then_generate",
            "route_tier": 5,
            "max_tokens": 8192,
            "max_cost_usd": 0.25,
            "expires_at": expires_at,
            "scope": ["openrouter"],
        },
        headers={"Authorization": "Bearer pt-test-token"},
    )
    assert register_response.status_code == 200
    assert register_response.json()["trace_id"] == "e2e-trace"

    run_response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": "e2e-trace"},
        headers={"Authorization": "Bearer pt-test-token"},
    )
    assert run_response.status_code == 200
    assert _Runner.captured_run_kwargs["approval"].trace_id == "e2e-trace"


@pytest.mark.integration
def test_register_approval_rejects_naive_expires_at(control_plane_client) -> None:
    response = control_plane_client.post(
        "/pipelines/approvals",
        json={
            "trace_id": "t2-naive-expiry",
            "approved_by": "op",
            "purpose": "p",
            "recipe": "classify_then_generate",
            "route_tier": 5,
            "max_tokens": 8192,
            "max_cost_usd": 0.25,
            "expires_at": datetime.now().isoformat(),  # naive, no offset
            "scope": ["openrouter"],
        },
        headers={"Authorization": "Bearer pt-test-token"},
    )
    assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.parametrize(
    "malicious_trace_id",
    [
        "../../etc/cron.d/evil",
        "../escape",
        "..\\escape",
        "/etc/passwd",
        "a/../../b",
        "has spaces",
        "control\x00char",
        "short",  # also exercises min_length=8 in the same parametrized pass
    ],
)
def test_register_approval_rejects_malicious_trace_id(
    control_plane_client, malicious_trace_id, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("PT_PIPELINE_APPROVAL_DIR", str(tmp_path / "approvals"))
    response = control_plane_client.post(
        "/pipelines/approvals",
        json={
            "trace_id": malicious_trace_id,
            "approved_by": "op",
            "purpose": "p",
            "recipe": "classify_then_generate",
            "route_tier": 5,
            "max_tokens": 8192,
            "max_cost_usd": 0.25,
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "scope": ["openrouter"],
        },
        headers={"Authorization": "Bearer pt-test-token"},
    )
    assert response.status_code == 422
    # No file was written outside (or even inside) the approval directory --
    # Pydantic rejects the request body before the handler ever runs.
    assert not any((tmp_path).glob("**/*.json"))


@pytest.mark.integration
@pytest.mark.parametrize(
    "malicious_trace_id",
    ["../../etc/cron.d/evil", "../escape", "a/../../b"],
)
def test_pipeline_run_rejects_malicious_trace_id(
    control_plane_client, malicious_trace_id
) -> None:
    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work", "trace_id": malicious_trace_id},
        headers={"Authorization": "Bearer pt-test-token"},
    )
    assert response.status_code == 422
