"""Orama portal facade: POST /models/route + swarm metadata on /v1/jobs."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from orchestrator.fastapi_app import (
    _backend_hint_from_target,
    _models_route_payload,
    app,
)
from orchestrator.worker_registry import ROLE_BACKEND_MAP


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_get_models_route_keeps_fallback_chain(client: TestClient):
    resp = client.get("/models/route", params={"task_type": "default"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body["fallback_chain"], list)
    assert "backend_hint" in body or body["fallback_chain"] == []


def test_post_models_route_returns_portal_hints_for_swarm_role(client: TestClient):
    resp = client.post(
        "/models/route",
        json={
            "objective": "Ship launch",
            "task_type": "implementation",
            "role": "context-agent",
            "preferred_device": "auto",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    expected_backend, expected_model = ROLE_BACKEND_MAP[("context-agent", None)]
    assert body["backend_hint"] == expected_backend
    assert body["model_hint"] == expected_model
    assert body["routing_source"] == "pt:/models/route"
    assert isinstance(body["fallback_chain"], list)


def test_backend_hint_maps_lm_studio_windows_device():
    target = SimpleNamespace(backend="lm-studio", device="win-rtx3080", name="qwen")
    assert _backend_hint_from_target(target) == "lmstudio-win"


def test_models_route_payload_ignores_empty_role(monkeypatch):
    dummy = SimpleNamespace(
        backend="ollama",
        device="mac-studio",
        name="qwen3.5:9b-nvfp4",
        api_model="qwen3.5:9b-nvfp4",
        __dict__={"name": "qwen3.5:9b-nvfp4", "backend": "ollama"},
    )
    monkeypatch.setattr(
        "orchestrator.fastapi_app.registry.route_task",
        lambda *args, **kwargs: [dummy],
    )
    payload = _models_route_payload(task_type="default", role=None)
    assert payload["backend_hint"] == "ollama"
    assert payload["model_hint"] == "qwen3.5:9b-nvfp4"


def test_portal_launch_metadata_hoists_onto_jobspec(client: TestClient, monkeypatch):
    captured: dict = {}

    class _FakeSupervisor:
        async def submit_job(self, spec):
            captured["spec"] = spec
            return spec.job_id

    monkeypatch.setattr("orchestrator.fastapi_app._supervisor", _FakeSupervisor())
    resp = client.post(
        "/v1/jobs",
        json={
            "intent": "Map relevant files, contracts, risks, and existing patterns.",
            "prompt": "Ship launch",
            "backend_hint": "ollama",
            "constraints": {
                "task_type": "implementation",
                "optimize_for": "reliability",
                "preferred_device": "auto",
            },
            "metadata": {
                "role": "context-agent",
                "specialization": "codebase-map",
                "session_id": "swarm-abc",
                "parent_orchestrator_id": "orama-portal",
                "artifact_policy": "summary_and_refs_only",
                "expected_output_shape": "compact_context_brief",
                "verification_rubric": "Cites concrete files.",
                "routing_source": "pt:/models/route",
            },
        },
    )
    assert resp.status_code == 200, resp.text
    spec = captured["spec"]
    assert spec.role == "context-agent"
    assert spec.specialization == "codebase-map"
    assert spec.session_id == "swarm-abc"
    assert spec.parent_orchestrator_id == "orama-portal"
    assert spec.artifact_policy == "summary_and_refs_only"
    assert spec.task_type == "implementation"
    assert spec.metadata["artifact_policy"] == "summary_and_refs_only"


def test_top_level_role_wins_over_metadata(client: TestClient, monkeypatch):
    captured: dict = {}

    class _FakeSupervisor:
        async def submit_job(self, spec):
            captured["spec"] = spec
            return spec.job_id

    monkeypatch.setattr("orchestrator.fastapi_app._supervisor", _FakeSupervisor())
    resp = client.post(
        "/v1/jobs",
        json={
            "intent": "apply",
            "prompt": "Ship launch",
            "backend_hint": "ollama",
            "task_type": "implementation",
            "role": "executor-agent",
            "metadata": {"role": "context-agent", "model": "Qwen3.5-9B-MLX-4bit"},
        },
    )
    assert resp.status_code == 200, resp.text
    assert captured["spec"].role == "executor-agent"
    assert captured["spec"].metadata["model"] == "Qwen3.5-9B-MLX-4bit"
