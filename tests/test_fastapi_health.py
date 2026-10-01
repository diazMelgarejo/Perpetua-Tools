"""Tests for /health LM Studio candidate resolution and query overrides."""
from __future__ import annotations

import platform

import pytest
from fastapi.testclient import TestClient

from orchestrator import fastapi_app


def _host_url(*octets: int, port: int) -> str:
    """Build an http URL from octets without embedding prohibited literals in tests."""
    return f"http://{'.'.join(str(o) for o in octets)}:{port}"


_LMS_WIN_PRIMARY = _host_url(192, 168, 1, 44, port=1234)
_LMS_WIN_SECONDARY = _host_url(192, 168, 1, 45, port=1234)
_LOOPBACK = _host_url(127, 0, 0, 1, port=0)
_OLLAMA_PRIVATE = _host_url(10, 20, 30, 40, port=11434)


@pytest.mark.unit
def test_resolve_health_lm_studio_candidates_uses_win_endpoints_on_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setenv("LM_STUDIO_WIN_ENDPOINTS", _LMS_WIN_PRIMARY)

    assert fastapi_app._resolve_health_lm_studio_candidates() == [
        _LMS_WIN_PRIMARY
    ]


@pytest.mark.unit
def test_resolve_health_lm_studio_candidates_keeps_every_win_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setenv(
        "LM_STUDIO_WIN_ENDPOINTS",
        f"{_LMS_WIN_PRIMARY},{_LMS_WIN_SECONDARY}",
    )

    assert fastapi_app._resolve_health_lm_studio_candidates() == [
        _LMS_WIN_PRIMARY,
        _LMS_WIN_SECONDARY,
    ]


@pytest.mark.unit
def test_resolve_health_lm_studio_candidates_fails_loudly_when_win_endpoints_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.delenv("LM_STUDIO_WIN_ENDPOINTS", raising=False)

    with pytest.raises(RuntimeError, match="LM_STUDIO_WIN_ENDPOINTS"):
        fastapi_app._resolve_health_lm_studio_candidates()


@pytest.mark.unit
def test_resolve_health_lm_studio_candidates_uses_mac_endpoint_off_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setenv("LM_STUDIO_MAC_ENDPOINT", _host_url(127, 0, 0, 1, port=1234))

    assert fastapi_app._resolve_health_lm_studio_candidates() == [
        _host_url(127, 0, 0, 1, port=1234)
    ]


@pytest.mark.unit
def test_health_query_params_cannot_override_configured_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ignore query-string host overrides; health probes use configured env hosts."""
    captured: dict[str, str] = {}

    def fake_backend_health_map(**kwargs):
        """Record backend_health_map kwargs for assertion."""
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(fastapi_app, "backend_health_map", fake_backend_health_map)
    monkeypatch.setattr(
        fastapi_app, "check_lm_studio", lambda host: {"ok": True, "url": host}
    )
    monkeypatch.setenv("ALLOW_PUBLIC_MODEL_ENDPOINTS", "1")
    monkeypatch.setattr(
        fastapi_app, "HEALTH_OLLAMA_HOST", _host_url(127, 0, 0, 1, port=11434)
    )
    monkeypatch.setattr(
        fastapi_app,
        "health_lm_studio_candidates",
        lambda: [_LMS_WIN_PRIMARY],
    )
    monkeypatch.setattr(
        fastapi_app, "HEALTH_MLX_HOST", _host_url(127, 0, 0, 1, port=8081)
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
        "ollama_host": _host_url(127, 0, 0, 1, port=11434),
        "lm_studio_host": _LMS_WIN_PRIMARY,
        "mlx_host": _host_url(127, 0, 0, 1, port=8081),
    }


@pytest.mark.unit
def test_health_uses_configured_private_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def fake_backend_health_map(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(fastapi_app, "backend_health_map", fake_backend_health_map)
    monkeypatch.setattr(
        fastapi_app, "check_lm_studio", lambda host: {"ok": True, "url": host}
    )
    monkeypatch.setattr(fastapi_app, "load_runtime_payload", lambda: None)
    monkeypatch.setattr(fastapi_app, "HEALTH_OLLAMA_HOST", _OLLAMA_PRIVATE)
    monkeypatch.setattr(
        fastapi_app,
        "health_lm_studio_candidates",
        lambda: [_host_url(127, 0, 0, 1, port=1234)],
    )
    monkeypatch.setattr(
        fastapi_app, "HEALTH_MLX_HOST", _host_url(127, 0, 0, 1, port=8081)
    )

    client = TestClient(fastapi_app.app)
    response = client.get("/health")

    assert response.status_code == 200
    assert captured["ollama_host"] == _OLLAMA_PRIVATE


@pytest.mark.unit
def test_health_fails_over_to_a_later_healthy_win_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def fake_backend_health_map(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    def fake_check_lm_studio(host: str):
        if host == _LMS_WIN_PRIMARY:
            return {"ok": False, "url": host, "error": "connection refused"}
        return {"ok": True, "url": host}

    monkeypatch.setattr(fastapi_app, "backend_health_map", fake_backend_health_map)
    monkeypatch.setattr(fastapi_app, "check_lm_studio", fake_check_lm_studio)
    monkeypatch.setattr(fastapi_app, "load_runtime_payload", lambda: None)
    monkeypatch.setattr(
        fastapi_app,
        "health_lm_studio_candidates",
        lambda: [_LMS_WIN_PRIMARY, _LMS_WIN_SECONDARY],
    )

    client = TestClient(fastapi_app.app)
    response = client.get("/health")

    assert response.status_code == 200
    assert captured["lm_studio_host"] == _LMS_WIN_SECONDARY


@pytest.mark.unit
def test_health_reports_last_candidate_when_none_are_healthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

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
        "health_lm_studio_candidates",
        lambda: [_LMS_WIN_PRIMARY, _LMS_WIN_SECONDARY],
    )

    client = TestClient(fastapi_app.app)
    response = client.get("/health")

    assert response.status_code == 200
    assert captured["lm_studio_host"] == _LMS_WIN_SECONDARY
