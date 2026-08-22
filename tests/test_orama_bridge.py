"""test_oramasys_bridge.py - HTTP bridge unit tests

Tests the ultrathink HTTP bridge module independently:
  - Bridge fires when ultrathink route is selected and endpoint configured
  - Bridge failure surfaces error gracefully (no crash)
  - Bridge skipped when route does not select ultrathink
  - Payload mapping (task_type -> optimize_for -> reasoning_depth) is correct

All HTTP calls are mocked - runs fully offline in CI.
"""
from __future__ import annotations

import os
from unittest.mock import patch, MagicMock

import pytest

# Ensure imports work
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.orama_bridge import (
    call_oramasys_bridge,
    normalize_oramasys_endpoint,
    parse_oramasys_timeout,
    build_oramasys_http_payload,
)


class TestNormalizeEndpoint:
    def test_appends_ultrathink_path(self):
        assert normalize_oramasys_endpoint("http://localhost:8001") == "http://localhost:8001/oramasys"

    def test_does_not_double_append(self):
        assert normalize_oramasys_endpoint("http://localhost:8001/oramasys") == "http://localhost:8001/oramasys"

    def test_strips_trailing_slash(self):
        assert normalize_oramasys_endpoint("http://localhost:8001/") == "http://localhost:8001/oramasys"

    def test_empty_returns_empty(self):
        assert normalize_oramasys_endpoint("") == ""


class TestParseTimeout:
    def test_valid_number(self):
        assert parse_oramasys_timeout("120") == 120.0

    def test_default_on_empty(self):
        assert parse_oramasys_timeout("") == 120.0

    def test_default_on_none(self):
        assert parse_oramasys_timeout(None) == 120.0

    def test_custom_default(self):
        assert parse_oramasys_timeout("", default=60.0) == 60.0


class TestBuildPayload:
    def test_deep_reasoning_payload(self):
        payload = build_oramasys_http_payload("Analyze X", "deep_reasoning")
        assert payload["task_description"] == "Analyze X"
        assert payload["optimize_for"] == "reliability"
        assert payload["reasoning_depth"] == "ultra"
        assert payload["task_type"] == "analysis"

    def test_code_analysis_payload(self):
        payload = build_oramasys_http_payload("Review code", "code_analysis")
        assert payload["optimize_for"] == "reliability"
        assert payload["reasoning_depth"] == "ultra"
        assert payload["task_type"] == "code"

    def test_unknown_task_type_defaults_to_reliability(self):
        payload = build_oramasys_http_payload("Something", "unknown")
        assert payload["optimize_for"] == "reliability"


class TestCallBridgeRemote:
    # A genuinely PUBLIC endpoint routes through utils.ssrf_pinned_adapter.ssrf_request
    # (the Layer-2 pinned transport, PT PR #359), not a bare httpx.post -- it
    # imports ssrf_request locally inside the function body, so the patch
    # target is the function's own module, not orchestrator.orama_bridge.
    @patch("utils.ssrf_pinned_adapter.ssrf_request")
    def test_success_returns_response(self, mock_ssrf_request):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": "analysis complete", "status": "ok"}
        mock_resp.raise_for_status.return_value = None
        mock_ssrf_request.return_value = mock_resp

        result = call_oramasys_bridge(
            endpoint="https://orama.example.com",
            timeout=120.0,
            task="Test task",
            task_type="deep_reasoning",
        )
        assert "response" in result
        assert result["response"]["result"] == "analysis complete"
        mock_ssrf_request.assert_called_once()

    @patch("utils.ssrf_pinned_adapter.ssrf_request")
    def test_failure_raises_exception(self, mock_ssrf_request):
        mock_ssrf_request.side_effect = Exception("Connection refused")

        with pytest.raises(Exception, match="Connection refused"):
            call_oramasys_bridge(
                endpoint="https://orama.example.com",
                timeout=120.0,
                task="Test task",
                task_type="deep_reasoning",
            )


class TestCallBridgeLocal:
    """Regression coverage for CodeRabbit finding on orchestrator/orama_bridge.py:68-72
    (PT PR #359, discussion 3834992455): routing every orama call through
    ssrf_request denied orama's own default deployment (loopback), since
    ssrf_request's deny-by-default policy blocks 127.0.0.0/8 by design.
    The old mocked-ssrf_request tests above never caught this because the
    mock replaced ssrf_request entirely, so its real AddressDenied for
    loopback never fired -- a false green. These tests exercise the real
    classification (validate_model_endpoint_url), mocking only the
    outermost HTTP call, so a regression that routed local traffic back
    through ssrf_request would fail loudly here.
    """

    @patch("httpx.post")
    @patch("utils.ssrf_pinned_adapter.ssrf_request")
    def test_loopback_endpoint_uses_direct_transport_not_ssrf_pinned(
        self, mock_ssrf_request, mock_httpx_post
    ):
        mock_ssrf_request.side_effect = AssertionError(
            "ssrf_request must not be called for a loopback orama endpoint "
            "-- it denies loopback/RFC1918 by design and would make the "
            "default local orama deployment permanently unreachable"
        )
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": "ok"}
        mock_resp.raise_for_status.return_value = None
        mock_httpx_post.return_value = mock_resp

        result = call_oramasys_bridge(
            endpoint="http://127.0.0.1:8001",
            timeout=120.0,
            task="Test task",
            task_type="deep_reasoning",
        )

        mock_httpx_post.assert_called_once()
        mock_ssrf_request.assert_not_called()
        assert result["response"]["result"] == "ok"

    @patch("httpx.post")
    @patch("utils.ssrf_pinned_adapter.ssrf_request")
    def test_localhost_hostname_also_classified_local(self, mock_ssrf_request, mock_httpx_post):
        mock_ssrf_request.side_effect = AssertionError("must not use the deny-by-default transport")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": "ok"}
        mock_resp.raise_for_status.return_value = None
        mock_httpx_post.return_value = mock_resp

        call_oramasys_bridge(
            endpoint="http://localhost:8001",
            timeout=120.0,
            task="Test task",
            task_type="deep_reasoning",
        )

        mock_httpx_post.assert_called_once()
        mock_ssrf_request.assert_not_called()


class TestCallBridgeAsyncLocal:
    @pytest.mark.asyncio
    async def test_loopback_endpoint_uses_direct_async_transport(self):
        from orchestrator.orama_bridge import call_oramasys_mcp_or_bridge

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": "ok"}
        mock_resp.raise_for_status.return_value = None

        with (
            patch("utils.ssrf_pinned_adapter.ssrf_request") as mock_ssrf_request,
            patch("httpx.AsyncClient.post", new=MagicMock()) as mock_post,
            patch.dict(os.environ, {}, clear=False),
        ):
            mock_ssrf_request.side_effect = AssertionError("must not use the deny-by-default transport")

            async def fake_post(*args, **kwargs):
                return mock_resp

            mock_post.side_effect = fake_post

            result = await call_oramasys_mcp_or_bridge(
                endpoint="http://127.0.0.1:8001",
                timeout=5.0,
                task="Test task",
                task_type="deep_reasoning",
            )

        mock_ssrf_request.assert_not_called()
        assert result["response"]["result"] == "ok"

