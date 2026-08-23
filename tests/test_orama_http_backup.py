from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))


def _make_candidate(
    name="ultrathink",
    backend="ultrathink",
    device="any",
    host="localhost",
    port=8001,
    online=False,
    reasoning=True,
):
    candidate = MagicMock()
    candidate.name = name
    candidate.backend = backend
    candidate.device = device
    candidate.host = host
    candidate.port = port
    candidate.online = online
    candidate.reasoning = reasoning
    return candidate


def test_orchestrate_calls_oramasys_bridge_with_mapped_depth(monkeypatch):
    monkeypatch.setenv("ORAMA_ENDPOINT", "http://localhost:8001")

    ultrathink_candidate = _make_candidate()
    fallback_candidate = _make_candidate(
        name="local_qwen30b",
        backend="ollama",
        device="win-rtx3080",
        port=11434,
        reasoning=False,
    )
    captured = {}

    fake_json_response = {
        "status": "success",
        "result": "backup ok",
        "reasoning_depth": "ultra",
    }

    mock_http_response = MagicMock()
    mock_http_response.raise_for_status = MagicMock()
    mock_http_response.json.return_value = fake_json_response

    # ORAMA_ENDPOINT above is http://localhost:8001 -- a loopback target.
    # call_oramasys_mcp_or_bridge's async HTTP fallback classifies loopback
    # endpoints as local and routes them through a direct httpx.AsyncClient
    # call, NOT ssrf_request (whose deny-by-default policy would otherwise
    # make orama's own default deployment unreachable -- see
    # orchestrator/orama_bridge.py's _is_local_oramasys_endpoint()).
    async def fake_post(*args, **kwargs):
        return mock_http_response

    mock_post = MagicMock(side_effect=fake_post)

    with (
        patch(
            "orchestrator.model_registry.ModelRegistry.route_task",
            return_value=[ultrathink_candidate, fallback_candidate],
        ),
        patch("orchestrator.cost_guard.CostGuard.can_spend", return_value=True),
        patch("orchestrator.cost_guard.CostGuard.alert_approaching", return_value=False),
        patch("orchestrator.cost_guard.CostGuard.record_spend", return_value=None),
        patch(
            "orchestrator.ecc_tools_sync.sync_ecc_tools",
            return_value={"status": "ok", "message": "mocked"},
        ),
        patch(
            "orchestrator.ecc_tools_sync.get_sync_status",
            return_value={"status": "ok"},
        ),
        patch("httpx.AsyncClient.post", mock_post),
        # Ensure no MCP subprocess is attempted
        patch.dict("os.environ", {"ORAMASYS_MCP_SERVER_CMD": ""}),
    ):
        from orchestrator.fastapi_app import app

        with TestClient(app, raise_server_exceptions=True) as client:
            response = client.post(
                "/orchestrate",
                json={
                    "task": "Analyze a privacy-critical distributed system failure.",
                    "task_type": "deep_reasoning",
                    "force": True,
                },
            )

    assert response.status_code == 200, response.text
    body = response.json()
    # Verify HTTP path was taken (MCP cmd is unset)
    assert body["oramasys_bridge"]["transport"] == "http"
    # Verify the payload sent to HTTP bridge has correct contract mapping
    mock_post.assert_called_once()
    _, call_kwargs = mock_post.call_args
    assert call_kwargs["json"]["optimize_for"] == "reliability"
    assert call_kwargs["json"]["reasoning_depth"] == "ultra"
    assert body["oramasys_bridge"]["request"]["reasoning_depth"] == "ultra"
    assert body["oramasys_bridge"]["response"]["reasoning_depth"] == "ultra"

