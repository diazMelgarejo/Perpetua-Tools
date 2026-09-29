"""test_ultrathink_integration.py — Unified integration test (SYNC_ANALYSIS OPT 3)

Verifies the end-to-end contract between Perpetua-Tools and orama-system:
  POST /orchestrate with task_type="deep_reasoning"  →  ultrathink endpoint in response
  POST /orchestrate with task_type="code_analysis"   →  ultrathink endpoint in response
  Response structure matches the MCP-first bridge contract, with HTTP `/ultrathink`
  available as an implemented backup bridge when explicitly enabled

All HTTP calls to ultrathink (port 8001) and Ollama are mocked — runs fully offline in CI.
No version bump — rolling changes pre-v1.0 RC.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure repo root is on PYTHONPATH
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Helpers: build a minimal ModelCandidate-like mock so ModelRegistry doesn't
# need live YAML when the test imports the app.
# ---------------------------------------------------------------------------

def _make_candidate(name="ultrathink", backend="ultrathink", device="any",
                    host="localhost", port=8001, online=False,
                    reasoning=True):
    """Return a MagicMock shaped like a ModelCandidate."""
    c = MagicMock()
    c.name = name
    c.backend = backend
    c.device = device
    c.host = host
    c.port = port
    c.online = online
    c.reasoning = reasoning
    return c


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DEEP_REASONING_CHAIN = (
    "glm-5.1:cloud",
    "Qwen3.5-9B-MLX-4bit",
    "claude-sonnet-5",
)


@pytest.fixture(scope="module")
def client():
    """TestClient with CostGuard and bridge calls mocked for offline CI."""
    with (
        patch(
            "orchestrator.fastapi_app.resolve_routing_state",
            new=lambda: __import__("asyncio").sleep(
                0,
                result={
                    "manager_endpoint": "http://127.0.1.2:11434",
                    "manager_model": "glm-5.1:cloud",
                    "manager_backend": "mac-ollama",
                    "coder_endpoint": "http://127.0.1.1:1234",
                    "coder_model": "Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-v2",
                    "coder_backend": "windows-lmstudio",
                    "distributed": True,
                },
            ),
        ),
        patch(
            "orchestrator.cost_guard.CostGuard.can_spend",
            return_value=True,
        ),
        patch(
            "orchestrator.cost_guard.CostGuard.alert_approaching",
            return_value=False,
        ),
        patch(
            "orchestrator.cost_guard.CostGuard.record_spend",
            return_value=None,
        ),
        patch(
            "orchestrator.ecc_tools_sync.sync_ecc_tools",
            return_value={"status": "ok", "message": "mocked"},
        ),
        patch(
            "orchestrator.ecc_tools_sync.get_sync_status",
            return_value={"status": "ok"},
        ),
    ):
        from orchestrator.fastapi_app import app
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------

class TestDeepReasoningRouting:
    """Verify PT routes deep_reasoning through the Mac-first model pool."""

    def test_deep_reasoning_selects_glm_cloud_primary(self, client: TestClient):
        resp = client.post(
            "/orchestrate",
            json={
                "task": "Analyze the distributed caching architecture for edge cases.",
                "task_type": "deep_reasoning",
                "force": True,
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "created"
        assert body["selected_model"]["name"] == "glm-5.1:cloud"

    def test_deep_reasoning_selected_model_is_mac_ollama_lane(self, client: TestClient):
        resp = client.post(
            "/orchestrate",
            json={
                "task": "Ultra-deep multi-step reasoning task for privacy-critical data.",
                "task_type": "deep_reasoning",
                "force": True,
            },
        )
        assert resp.status_code == 200, resp.text
        selected = resp.json()["selected_model"]
        assert selected["backend"] == "ollama"
        assert selected["device"] == "mac-studio"

    def test_code_analysis_still_uses_coding_lane(self, client: TestClient):
        resp = client.post(
            "/orchestrate",
            json={
                "task": "Full codebase audit: identify security vulnerabilities in auth module.",
                "task_type": "code_analysis",
                "preferred_device": "win-rtx3080",
                "force": True,
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "created"
        assert body["selected_model"]["device"] == "win-rtx3080"

    # ---- 3. Response structure matches BRIDGE spec ----------------------

    def test_orchestrate_response_structure_matches_bridge_spec(self, client: TestClient):
        """Response must contain all fields specified in PERPLEXITY_BRIDGE.md:
        status, agent, selected_model, fallback_chain."""
        resp = client.post("/orchestrate", json={
            "task": "Verify bridge spec compliance.",
            "task_type": "deep_reasoning",
            "force": True,
        })
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # Top-level fields
        assert "status" in body
        assert "agent" in body
        assert "selected_model" in body
        assert "fallback_chain" in body
        # selected_model fields (BRIDGE spec)
        sm = body["selected_model"]
        for field in ("name", "backend", "device", "host", "online", "reasoning"):
            assert field in sm, f"selected_model missing BRIDGE-spec field: '{field}'"
        # agent fields
        agent = body["agent"]
        for field in ("agent_id", "role", "model", "status"):
            assert field in agent, f"agent missing expected field: '{field}'"
        assert agent["status"] == "idle"
        # fallback_chain is a list
        assert isinstance(body["fallback_chain"], list)

    def test_deep_reasoning_fallback_chain_order(self, client: TestClient):
        resp = client.post(
            "/orchestrate",
            json={
                "task": "Fallback chain verification task.",
                "task_type": "deep_reasoning",
                "force": True,
            },
        )
        assert resp.status_code == 200, resp.text
        fallback_names = [entry["name"] for entry in resp.json()["fallback_chain"]]
        assert fallback_names == list(_DEEP_REASONING_CHAIN[1:])

    # ---- 6. Idempotency: same task → conflict on second call ------------

    def test_idempotency_same_deep_reasoning_task_returns_conflict(self, client: TestClient):
        """Sending the exact same task twice (force=False) must return a
        conflict on the second call — idempotency contract from BRIDGE spec."""
        payload = {
            "task": "Idempotency test: identical deep reasoning task.",
            "task_type": "deep_reasoning",
            "force": False,
        }
        r1 = client.post("/orchestrate", json=payload)
        assert r1.status_code == 200
        assert r1.json()["status"] == "created"

        r2 = client.post("/orchestrate", json=payload)
        assert r2.status_code == 200
        assert r2.json()["status"] == "conflict", (
            "Second identical call must return conflict (idempotency guard)"
        )


# ---------------------------------------------------------------------------
# Routing.yml contract tests (offline, no TestClient needed)
# ---------------------------------------------------------------------------

class TestRoutingYmlUltrathinkContract:
    """Verify canonical oramasys routing while v1 fallback behavior remains.

    Runs against the YAML file directly — no server needed.
    """

    @pytest.fixture(scope="class")
    def routing(self):
        import yaml
        routing_yml = REPO_ROOT / "config" / "routing.yml"
        assert routing_yml.exists(), f"Missing: {routing_yml}"
        with open(routing_yml) as f:
            return yaml.safe_load(f)

    def test_deep_reasoning_has_oramasys_default_endpoint(self, routing: dict):
        routes = routing["routes"]
        assert "deep_reasoning" in routes
        route = routes["deep_reasoning"]
        assert route["endpoint"] == "http://localhost:8001/oramasys"
        assert route["timeout"] == 120

    def test_code_analysis_has_oramasys_default_endpoint(self, routing: dict):
        routes = routing["routes"]
        assert "code_analysis" in routes
        route = routes["code_analysis"]
        assert route["endpoint"] == "http://localhost:8001/oramasys"
        assert route["timeout"] == 120

    def test_deep_reasoning_has_mac_lm_studio_fallback(self, routing: dict):
        route = routing["routes"]["deep_reasoning"]
        assert route.get("fallback") == "Qwen3.5-9B-MLX-4bit"

    def test_code_analysis_has_ultrathink_fallback(self, routing: dict):
        route = routing["routes"]["code_analysis"]
        assert "fallback" in route
        assert route["fallback"] == "local_qwen30b"

    def test_deep_reasoning_requires_orama_available(self, routing: dict):
        route = routing["routes"]["deep_reasoning"]
        assert "requires" in route
        assert "orama_available" in route["requires"]

    def test_code_analysis_requires_orama_available(self, routing: dict):
        route = routing["routes"]["code_analysis"]
        assert "requires" in route
        assert "orama_available" in route["requires"]
