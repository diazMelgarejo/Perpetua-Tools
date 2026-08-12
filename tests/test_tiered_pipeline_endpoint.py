"""Integration coverage for the explicit paid Tier-5 control-plane route."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import orchestrator.fastapi_app as app_module
from orchestrator.model_transport import ProviderTransportRegistry
from orchestrator.tiered_pipeline import PipelineResult, TieredPipelineRunner


class _Runner:
    def recipe(self, name: str):
        assert name == "classify_then_generate"
        return type("Recipe", (), {"cost_reservation_usd": 0.25})()

    async def run(self, recipe_name, prompt, **kwargs):
        assert recipe_name == "classify_then_generate"
        assert prompt == "do the work"
        assert callable(kwargs["dispatch"])
        return PipelineResult(
            recipe=recipe_name,
            output="final answer",
            stage_outputs={"classify": "internal", "generate": "final answer"},
            requested_tokens=512,
        )


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
        "/pipelines/classify_then_generate/run", json={"prompt": "do the work"}
    )
    assert response.status_code == 401


@pytest.mark.integration
def test_pipeline_run_returns_final_output_without_internal_stage_payload(
    control_plane_client, monkeypatch
) -> None:
    monkeypatch.setattr(app_module.cost_guard, "can_spend", lambda amount: amount == 0.25)
    recorded: list[float] = []
    monkeypatch.setattr(app_module.cost_guard, "record_spend", recorded.append)

    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work"},
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


@pytest.mark.integration
def test_pipeline_run_fails_closed_when_feature_is_disabled(control_plane_client, monkeypatch) -> None:
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "0")
    response = control_plane_client.post(
        "/pipelines/classify_then_generate/run",
        json={"prompt": "do the work"},
        headers={"Authorization": "Bearer pt-test-token"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Tier-5 pipelines are disabled"
