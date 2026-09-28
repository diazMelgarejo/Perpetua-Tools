"""Orama portal co-install facade (orama-system #368 / stacked #369).

POST /models/route must return the keys the portal reads
(backend_hint|backend|provider and model_hint|model|model_id).
POST /v1/jobs must forward §5.1 JobSpec fields Orama sends top-level.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from orchestrator import fastapi_app
from orchestrator.fastapi_app import (
    _JobSubmitRequest,
    _LINEAGE_TRUST_CALLER_REPORTED,
    _backend_hint_from_target,
    _model_hint_from_target,
    _models_route_payload,
    app,
)
from orchestrator.supervisor import JobSpec


def _candidate(**overrides) -> SimpleNamespace:
    base = dict(
        name="qwen-win",
        backend="lm-studio",
        device="win-rtx3080",
        host="http://lmstudio.example",
        port=1234,
        context_window=32768,
        roles=["coder", "general"],
        priority=10,
        online=True,
        reasoning="general",
        api_model="Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-v2",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestBackendHintMapping:
    def test_lm_studio_win_device_maps_to_lmstudio_win(self):
        assert _backend_hint_from_target(_candidate()) == "lmstudio-win"

    def test_lm_studio_mac_device_maps_to_lmstudio_mac(self):
        t = _candidate(device="mac-studio", name="qwen-mac", api_model="Qwen3.5-9B-MLX-4bit")
        assert _backend_hint_from_target(t) == "lmstudio-mac"

    def test_registry_backend_passthrough(self):
        t = _candidate(backend="ollama", device="mac-studio")
        assert _backend_hint_from_target(t) == "ollama"

    def test_model_hint_prefers_api_model(self):
        t = _candidate()
        assert _model_hint_from_target(t) == t.api_model

    def test_model_hint_falls_back_to_name(self):
        t = _candidate(api_model="")
        assert _model_hint_from_target(t) == "qwen-win"


class TestOramaRoutePayload:
    def test_payload_includes_keys_orama_reads(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            fastapi_app.registry,
            "route_task",
            lambda task_type, preferred_device=None: [_candidate()],
        )
        payload = _models_route_payload(task_type="code_analysis")
        assert payload["backend_hint"] == "lmstudio-win"
        assert payload["backend"] == "lmstudio-win"
        assert payload["provider"] == "lmstudio-win"
        assert payload["model_hint"] == (
            "Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-v2"
        )
        assert payload["model"] == payload["model_hint"]
        assert payload["model_id"] == payload["model_hint"]
        assert payload["fallback_chain"]


class TestPostModelsRoute:
    def test_post_body_returns_orama_shape(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            fastapi_app.registry,
            "route_task",
            lambda task_type, preferred_device=None: [_candidate()],
        )
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(
                "/models/route",
                json={
                    "objective": "preview assignment",
                    "task_type": "code_analysis",
                    "role": "coder",
                    "preferred_device": "win-rtx3080",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["backend_hint"] == "lmstudio-win"
        assert body["backend"] == body["backend_hint"]
        assert body["provider"] == body["backend_hint"]
        assert body["model_hint"]
        assert body["model"] == body["model_hint"]
        assert body["model_id"] == body["model_hint"]
        assert isinstance(body["fallback_chain"], list)
        assert body["fallback_chain"]

    def test_get_route_keeps_fallback_chain(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            fastapi_app.registry,
            "route_task",
            lambda task_type, preferred_device=None: [_candidate()],
        )
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/models/route", params={"task_type": "default"})
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["fallback_chain"], list)
        assert body["fallback_chain"]
        assert body["backend_hint"] == "lmstudio-win"

    def test_empty_chain_returns_hints_absent(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            fastapi_app.registry,
            "route_task",
            lambda task_type, preferred_device=None: [],
        )
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(
                "/models/route",
                json={"objective": "none", "task_type": "unknown-task"},
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["fallback_chain"] == []
        assert "backend_hint" not in body

    def test_missing_objective_is_accepted(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            fastapi_app.registry,
            "route_task",
            lambda task_type, preferred_device=None: [],
        )
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(
                "/models/route",
                json={"task_type": "default"},
            )
        assert resp.status_code == 200, resp.text


class TestJobSubmitRequestSection51:
    def test_request_model_accepts_orama_fields(self):
        req = _JobSubmitRequest(
            intent="coding",
            prompt="implement the shim",
            backend_hint="lmstudio-win",
            task_type="code_analysis",
            role="coder",
            specialization="python-coding",
            session_id="sess-1",
            parent_orchestrator_id="portal-1",
            artifact_policy="default",
            metadata={"role": "coder", "model": "win-qwen"},
        )
        assert req.role == "coder"
        assert req.specialization == "python-coding"
        assert req.session_id == "sess-1"
        assert req.parent_orchestrator_id == "portal-1"
        assert req.artifact_policy == "default"
        assert req.metadata["model"] == "win-qwen"

    def test_post_v1_jobs_forwards_fields_into_jobspec(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        captured: list[JobSpec] = []

        async def _capture(spec: JobSpec) -> str:
            captured.append(spec)
            return spec.job_id

        fake = SimpleNamespace(submit_job=AsyncMock(side_effect=_capture))
        monkeypatch.setattr(fastapi_app, "_get_supervisor", lambda: fake)

        payload = {
            "intent": "coding",
            "prompt": "preview dispatch",
            "backend_hint": "lmstudio-win",
            "task_type": "code_analysis",
            "role": "coder",
            "specialization": "python-coding",
            "session_id": "sess-orama",
            "parent_orchestrator_id": "portal",
            "artifact_policy": "default",
            "constraints": {"max_tokens": 128},
            "metadata": {
                "role": "coder",
                "model": "win-qwen",
                "lineage_trust": "verified",
            },
        }
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post("/v1/jobs", json=payload)
        assert resp.status_code == 200, resp.text
        assert captured, "submit_job was not called"
        spec = captured[0]
        assert spec.role == "coder"
        assert spec.specialization == "python-coding"
        assert spec.session_id == "sess-orama"
        assert spec.parent_orchestrator_id == "portal"
        assert spec.metadata.get("lineage_trust") == _LINEAGE_TRUST_CALLER_REPORTED
        assert spec.artifact_policy == "default"
        assert spec.metadata.get("model") == "win-qwen"
        assert spec.task_type == "code_analysis"
        assert spec.backend_hint == "lmstudio-win"
