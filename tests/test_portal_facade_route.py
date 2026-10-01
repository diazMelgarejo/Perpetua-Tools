"""Orama portal facade: POST /models/route + swarm metadata on /v1/jobs."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from orchestrator.fastapi_app import (
    _backend_hint_from_target,
    _models_route_payload,
    _normalize_preferred_device,
    app,
)
from orchestrator.worker_registry import ROLE_BACKEND_MAP


@pytest.fixture
def offline_route(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep portal HTTP tests independent of LAN model discovery."""
    target = SimpleNamespace(
        backend="ollama",
        device="mac-studio",
        name="test-model",
        api_model="test-model",
    )
    monkeypatch.setattr(
        "orchestrator.fastapi_app.registry.route_task",
        lambda *args, **kwargs: [target],
    )


@pytest.fixture
def client(offline_route: None) -> Generator[TestClient, None, None]:
    """Yield a portal test client with model discovery replaced by offline routing."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_get_models_route_keeps_fallback_chain(client: TestClient):
    resp = client.get("/models/route", params={"task_type": "default"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body["fallback_chain"], list)
    assert "backend_hint" in body or body["fallback_chain"] == []


def test_post_models_route_requires_bearer_when_auth_enforced(
    monkeypatch: pytest.MonkeyPatch,
    offline_route: None,
) -> None:
    """Verify route requests require a matching bearer token when auth is enforced."""
    monkeypatch.setenv("ORAMA_INSECURE_DEV", "0")
    monkeypatch.setenv("ORAMA_CONTROL_PLANE_TOKEN", "portal-route-test-token")
    monkeypatch.setattr(
        "orchestrator.fastapi_app._models_route_payload",
        lambda **kwargs: {"fallback_chain": [], "backend_hint": "echo"},
    )

    with TestClient(app, raise_server_exceptions=False) as secured_client:
        denied = secured_client.post(
            "/models/route",
            json={"objective": "test", "task_type": "default"},
        )
        wrong = secured_client.post(
            "/models/route",
            json={"objective": "test", "task_type": "default"},
            headers={"Authorization": "Bearer wrong-token"},
        )
        allowed = secured_client.post(
            "/models/route",
            json={"objective": "test", "task_type": "default"},
            headers={"Authorization": "Bearer portal-route-test-token"},
        )

    assert denied.status_code == 401
    assert wrong.status_code == 401
    assert allowed.status_code == 200


def test_post_models_route_fails_closed_without_configured_token(
    monkeypatch: pytest.MonkeyPatch,
    offline_route: None,
) -> None:
    """Verify route requests return HTTP 503 when no control-plane token is configured."""
    monkeypatch.setenv("ORAMA_INSECURE_DEV", "0")
    monkeypatch.delenv("ORAMA_CONTROL_PLANE_TOKEN", raising=False)
    monkeypatch.delenv("ORAMA_CONTROL_PLANE_TOKEN_LOCAL", raising=False)
    monkeypatch.delenv("PT_CONTROL_PLANE_TOKEN", raising=False)
    monkeypatch.setattr(
        "orchestrator.control_plane_auth._read_persisted_token",
        lambda path=None: "",
    )
    monkeypatch.setattr(
        "orchestrator.control_plane_auth.accepted_control_plane_tokens",
        lambda scope="orama": frozenset(),
    )

    with TestClient(app, raise_server_exceptions=False) as secured_client:
        response = secured_client.post(
            "/models/route",
            json={"objective": "test", "task_type": "default"},
        )

    assert response.status_code == 503


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


def test_normalize_preferred_device_maps_portal_words():
    """Map portal-friendly device words to registry device ids."""
    assert _normalize_preferred_device("mac") == "mac-studio"
    assert _normalize_preferred_device("windows") == "win-rtx3080"
    assert _normalize_preferred_device("shared") == "shared-ollama"
    assert _normalize_preferred_device("win-rtx3080") == "win-rtx3080"
    assert _normalize_preferred_device("auto") is None


def test_post_models_route_passes_mapped_device_to_registry(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Normalize portal preferred_device before calling registry.route_task."""
    seen: list[str | None] = []

    def capture_route(task_type, preferred_device=None):
        """Record preferred_device passed through from the route handler."""
        seen.append(preferred_device)
        target = SimpleNamespace(
            backend="ollama",
            device=preferred_device or "mac-studio",
            name="test-model",
            api_model="test-model",
        )
        return [target]

    monkeypatch.setattr(
        "orchestrator.fastapi_app.registry.route_task",
        capture_route,
    )
    response = client.post(
        "/models/route",
        json={
            "objective": "Ship",
            "task_type": "implementation",
            "role": "context-agent",
            "preferred_device": "windows",
        },
    )
    assert response.status_code == 200
    assert seen == ["win-rtx3080"]


def test_backend_hint_maps_lm_studio_windows_device():
    target = SimpleNamespace(backend="lm-studio", device="win-rtx3080", name="qwen")
    assert _backend_hint_from_target(target) == "lmstudio-win"


def test_backend_hint_omits_unknown_or_empty_backend() -> None:
    """Verify a target with an empty backend produces no backend hint."""
    target = SimpleNamespace(backend="", device="mac", name="qwen")
    assert _backend_hint_from_target(target) is None


def test_post_models_route_omits_backend_hints_for_target_without_backend(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify missing backends omit provider hints while retaining model and chain data."""
    target = SimpleNamespace(
        backend="",
        device="mac",
        name="qwen",
        api_model="qwen",
        __dict__={"backend": "", "device": "mac", "name": "qwen", "api_model": "qwen"},
    )
    monkeypatch.setattr(
        "orchestrator.fastapi_app.registry.route_task",
        lambda *args, **kwargs: [target],
    )

    response = client.post(
        "/models/route",
        json={"task_type": "default"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["fallback_chain"]
    assert all(key not in body for key in ("backend_hint", "backend", "provider"))
    assert body.get("model_hint") == "qwen"


def test_post_models_route_uses_role_specialization(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify role specialization selects its registered backend and model hints."""
    monkeypatch.setitem(
        ROLE_BACKEND_MAP,
        ("context-agent", "codebase-map"),
        ("special-backend", "special-model"),
    )

    response = client.post(
        "/models/route",
        json={
            "objective": "Map the codebase",
            "task_type": "implementation",
            "role": "context-agent",
            "specialization": "codebase-map",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["backend_hint"] == "special-backend"
    assert response.json()["model_hint"] == "special-model"


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
    assert spec.lineage_trust == "caller_reported"
    assert spec.authenticated_lane == "insecure_dev"
    assert spec.metadata["artifact_policy"] == "summary_and_refs_only"
    assert spec.metadata.get("lineage_trust") == "caller_reported"


def test_whitespace_task_type_falls_back_to_constraints(
    client: TestClient, monkeypatch
):
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
            "task_type": "   ",
            "constraints": {"task_type": "implementation"},
        },
    )
    assert resp.status_code == 200, resp.text
    assert captured["spec"].task_type == "implementation"


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
