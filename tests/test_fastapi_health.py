from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from orchestrator import fastapi_app


def test_resolve_health_lm_studio_candidates_uses_win_endpoints_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CodeRabbit finding: /health only ever read LM_STUDIO_MAC_ENDPOINT, so
    on a Windows deployment where LM_STUDIO_WIN_ENDPOINTS differs from
    localhost:1234, /health silently reported status for the wrong backend."""
    monkeypatch.setattr(fastapi_app.platform, "system", lambda: "Windows")
    monkeypatch.setenv("LM_STUDIO_WIN_ENDPOINTS", "http://192.168.1.44:1234")

    assert fastapi_app._resolve_health_lm_studio_candidates() == [
        "http://192.168.1.44:1234"
    ]


def test_resolve_health_lm_studio_candidates_keeps_every_win_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CodeRabbit finding: /health must keep the full candidate list for
    failover probing, not collapse to just the first configured host --
    worker_registry.py's own dispatch path already fails over to a later
    healthy candidate when the first is down."""
    monkeypatch.setattr(fastapi_app.platform, "system", lambda: "Windows")
    monkeypatch.setenv(
        "LM_STUDIO_WIN_ENDPOINTS", "http://192.168.1.44:1234,http://192.168.1.45:1234"
    )

    assert fastapi_app._resolve_health_lm_studio_candidates() == [
        "http://192.168.1.44:1234",
        "http://192.168.1.45:1234",
    ]


def test_resolve_health_lm_studio_candidates_fails_loudly_when_win_endpoints_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fastapi_app.platform, "system", lambda: "Windows")
    monkeypatch.delenv("LM_STUDIO_WIN_ENDPOINTS", raising=False)

    with pytest.raises(RuntimeError, match="LM_STUDIO_WIN_ENDPOINTS"):
        fastapi_app._resolve_health_lm_studio_candidates()


def test_resolve_health_lm_studio_candidates_uses_mac_endpoint_off_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fastapi_app.platform, "system", lambda: "Darwin")
    monkeypatch.setenv("LM_STUDIO_MAC_ENDPOINT", "http://localhost:1234")

    assert fastapi_app._resolve_health_lm_studio_candidates() == [
        "http://localhost:1234"
    ]


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
    monkeypatch.setattr(
        fastapi_app, "check_lm_studio", lambda host: {"ok": True, "url": host}
    )
    monkeypatch.setenv("ALLOW_PUBLIC_MODEL_ENDPOINTS", "1")
    monkeypatch.setattr(
        fastapi_app, "HEALTH_OLLAMA_HOST", "http://127.0.0.1:11434"
    )
    monkeypatch.setattr(
        fastapi_app, "HEALTH_LM_STUDIO_CANDIDATES", ["http://192.168.1.44:1234"]
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
    monkeypatch.setattr(
        fastapi_app, "check_lm_studio", lambda host: {"ok": True, "url": host}
    )
    monkeypatch.setattr(fastapi_app, "load_runtime_payload", lambda: None)
    monkeypatch.setattr(
        fastapi_app, "HEALTH_OLLAMA_HOST", "http://10.20.30.40:11434"
    )
    monkeypatch.setattr(
        fastapi_app, "HEALTH_LM_STUDIO_CANDIDATES", ["http://127.0.0.1:1234"]
    )
    monkeypatch.setattr(
        fastapi_app, "HEALTH_MLX_HOST", "http://127.0.0.1:8081"
    )

    client = TestClient(fastapi_app.app)
    response = client.get("/health")

    assert response.status_code == 200
    assert captured["ollama_host"] == "http://10.20.30.40:11434"


@pytest.mark.unit
def test_health_fails_over_to_a_later_healthy_win_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CodeRabbit finding: if the first LM_STUDIO_WIN_ENDPOINTS candidate is
    unreachable and a later one is healthy, /health must report the healthy
    one -- not the down one -- matching worker_registry.py's own dispatch
    failover, so a load balancer doesn't remove a healthy instance."""
    captured = {}

    def fake_backend_health_map(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    def fake_check_lm_studio(host: str):
        if host == "http://192.168.1.44:1234":
            return {"ok": False, "url": host, "error": "connection refused"}
        return {"ok": True, "url": host}

    monkeypatch.setattr(fastapi_app, "backend_health_map", fake_backend_health_map)
    monkeypatch.setattr(fastapi_app, "check_lm_studio", fake_check_lm_studio)
    monkeypatch.setattr(fastapi_app, "load_runtime_payload", lambda: None)
    monkeypatch.setattr(
        fastapi_app,
        "HEALTH_LM_STUDIO_CANDIDATES",
        ["http://192.168.1.44:1234", "http://192.168.1.45:1234"],
    )

    client = TestClient(fastapi_app.app)
    response = client.get("/health")

    assert response.status_code == 200
    assert captured["lm_studio_host"] == "http://192.168.1.45:1234"


@pytest.mark.unit
def test_health_reports_last_candidate_when_none_are_healthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def fake_backend_health_map(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(fastapi_app, "backend_health_map", fake_backend_health_map)
    monkeypatch.setattr(
        fastapi_app, "check_lm_studio", lambda host: {"ok": False, "url": host}
    )
    monkeypatch.setattr(fastapi_app, "load_runtime_payload", lambda: None)
    monkeypatch.setattr(
        fastapi_app,
        "HEALTH_LM_STUDIO_CANDIDATES",
        ["http://192.168.1.44:1234", "http://192.168.1.45:1234"],
    )

    client = TestClient(fastapi_app.app)
    response = client.get("/health")

    assert response.status_code == 200
    assert captured["lm_studio_host"] == "http://192.168.1.45:1234"
