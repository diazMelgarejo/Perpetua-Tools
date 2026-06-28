"""Regression: POST /runtime/bootstrap must not leak raw bootstrap secrets over HTTP."""
from __future__ import annotations

from fastapi.testclient import TestClient

from orchestrator import fastapi_app


def test_runtime_bootstrap_redacts_credentials_and_gateway_config(monkeypatch):
    fake_payload = {
        "schema_version": 1,
        "generated_at": 123.0,
        "stages": [{"stage": "gateway", "status": "ready"}],
        "autoresearch": {"ready": True, "sha": "abc1234"},
        "credentials": {"configured": True, "api_key": "super-secret"},
        "paths": {"pt_root": "/tmp/perpetua-tools"},
        "gateway": {
            "gateway_ready": True,
            "openclaw_config": {"auth": {"token": "gateway-secret"}},
        },
        "routing": {"distributed": True, "manager_endpoint": "http://127.0.0.1:11434"},
    }

    async def fake_bootstrap(**_kwargs):
        return fake_payload

    monkeypatch.setattr(fastapi_app, "bootstrap_runtime", fake_bootstrap)
    monkeypatch.setenv("ORAMA_INSECURE_DEV", "0")
    monkeypatch.setenv("ORAMA_CONTROL_PLANE_TOKEN", "bootstrap-redaction-test-bearer")

    with TestClient(fastapi_app.app, raise_server_exceptions=False) as client:
        response = client.post(
            "/runtime/bootstrap",
            headers={"Authorization": "Bearer bootstrap-redaction-test-bearer"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "credentials" not in body
    assert "paths" not in body
    assert "gateway" not in body
    assert "super-secret" not in response.text
    assert "gateway-secret" not in response.text
    assert body["runtime"]["distributed"] is True
    assert body["stages"] == fake_payload["stages"]
    assert body["autoresearch"] == fake_payload["autoresearch"]
