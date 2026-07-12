from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from orchestrator import fastapi_app


def test_health_forwards_validated_hosts_to_backend_map(monkeypatch):
    captured = {}

    def fake_backend_health_map(*, ollama_host, lm_studio_host, mlx_host):
        captured["ollama_host"] = ollama_host
        captured["lm_studio_host"] = lm_studio_host
        captured["mlx_host"] = mlx_host
        return {"ok": True}

    monkeypatch.setattr(fastapi_app, "backend_health_map", fake_backend_health_map)
    monkeypatch.setattr(
        fastapi_app,
        "load_runtime_payload",
        lambda: {
            "gateway": {"gateway_ready": True},
            "routing": {"distributed": True},
        },
    )

    response = fastapi_app.health(
        ollama_host="http://127.0.0.1:11434",
        lm_studio_host="http://127.0.0.1:1234",
        mlx_host="http://127.0.0.1:8081",
    )

    assert response["status"] == "ok"
    assert captured == {
        "ollama_host": "http://127.0.0.1:11434",
        "lm_studio_host": "http://127.0.0.1:1234",
        "mlx_host": "http://127.0.0.1:8081",
    }


def test_health_accepts_bare_host_port_env_style(monkeypatch):
    monkeypatch.setattr(fastapi_app, "backend_health_map", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(fastapi_app, "load_runtime_payload", lambda: None)

    response = fastapi_app.health(
        ollama_host="127.0.1.1:11434",
        lm_studio_host="localhost:1234",
        mlx_host="127.0.0.1:8081",
    )

    assert response["status"] == "ok"


def test_health_rejects_link_local_ssrf_target():
    with pytest.raises(HTTPException) as exc:
        fastapi_app.health(ollama_host="http://169.254.169.254/latest/meta-data/")
    assert exc.value.status_code == 400


def test_health_rejects_malformed_port_as_client_error():
    with pytest.raises(HTTPException) as exc:
        fastapi_app.health(ollama_host="http://127.0.0.1:notaport")
    assert exc.value.status_code == 400


def test_health_rejects_metadata_via_test_client(monkeypatch):
    monkeypatch.setattr(fastapi_app, "backend_health_map", lambda **kwargs: {"ollama": {"ok": False}})
    monkeypatch.setattr(fastapi_app, "load_runtime_payload", lambda: None)
    with TestClient(fastapi_app.app, raise_server_exceptions=False) as client:
        resp = client.get("/health?ollama_host=http://169.254.169.254/latest/meta-data/")
    assert resp.status_code == 400


def test_health_rejects_malformed_port_via_test_client(monkeypatch):
    monkeypatch.setattr(fastapi_app, "backend_health_map", lambda **kwargs: {"ollama": {"ok": False}})
    monkeypatch.setattr(fastapi_app, "load_runtime_payload", lambda: None)
    with TestClient(fastapi_app.app, raise_server_exceptions=False) as client:
        resp = client.get("/health?ollama_host=http://127.0.0.1:notaport")
    assert resp.status_code == 400
