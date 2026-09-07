from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from orchestrator import fastapi_app


@pytest.mark.unit
def test_health_ignores_host_query_overrides_and_uses_server_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def fake_backend_health_map(*, ollama_host, lm_studio_host, mlx_host):
        captured["ollama_host"] = ollama_host
        captured["lm_studio_host"] = lm_studio_host
        captured["mlx_host"] = mlx_host
        return {"ok": True}

    monkeypatch.setattr(fastapi_app, "backend_health_map", fake_backend_health_map)
    monkeypatch.setenv("ALLOW_PUBLIC_MODEL_ENDPOINTS", "1")
    monkeypatch.setattr(
        fastapi_app, "HEALTH_OLLAMA_HOST", "http://127.0.0.1:11434"
    )
    monkeypatch.setattr(
        fastapi_app, "HEALTH_LM_STUDIO_HOST", "http://192.168.1.44:1234"
    )
    monkeypatch.setattr(
        fastapi_app, "HEALTH_MLX_HOST", "http://127.0.0.1:8081"
    )
    monkeypatch.setattr(
        fastapi_app,
        "load_runtime_payload",
        lambda: {
            "gateway": {"gateway_ready": True},
            "routing": {"distributed": True},
        },
    )

    client = TestClient(fastapi_app.app)
    response = client.get(
        "/health?ollama_host=https://metadata-rebind.test"
        "&lm_studio_host=https://metadata-rebind.test"
        "&mlx_host=https://metadata-rebind.test"
    )

    assert response.status_code == 200
    assert captured == {
        "ollama_host": "http://127.0.0.1:11434",
        "lm_studio_host": "http://192.168.1.44:1234",
        "mlx_host": "http://127.0.0.1:8081",
    }


@pytest.mark.unit
def test_health_uses_configured_private_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def fake_backend_health_map(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(fastapi_app, "backend_health_map", fake_backend_health_map)
    monkeypatch.setattr(fastapi_app, "load_runtime_payload", lambda: None)
    monkeypatch.setattr(
        fastapi_app, "HEALTH_OLLAMA_HOST", "http://10.20.30.40:11434"
    )
    monkeypatch.setattr(
        fastapi_app, "HEALTH_LM_STUDIO_HOST", "http://127.0.0.1:1234"
    )
    monkeypatch.setattr(
        fastapi_app, "HEALTH_MLX_HOST", "http://127.0.0.1:8081"
    )

    client = TestClient(fastapi_app.app)
    response = client.get("/health")

    assert response.status_code == 200
    assert captured["ollama_host"] == "http://10.20.30.40:11434"
