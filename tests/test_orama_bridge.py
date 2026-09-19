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
    CONTROL_PLANE_DEPTH_HEADER,
    _is_local_oramasys_endpoint,
    call_oramasys_bridge,
    normalize_oramasys_endpoint,
    parse_oramasys_timeout,
    build_oramasys_http_payload,
    resolve_oramasys_endpoint,
    resolve_oramasys_timeout,
)

# Product default (config/routing.yml, .env.example, CI ORAMA_ENDPOINT).
# CI injects ORAMA_ENDPOINT which resolve_oramasys_endpoint() prefers over the
# endpoint= argument; tests that pass an explicit URL must drop those env vars
# or they silently test the CI loopback default instead.
CANONICAL_LOCAL_ENDPOINT = "http://localhost:8001"
CANONICAL_LOCAL_BRIDGE_URL = "http://localhost:8001/oramasys"
LOOPBACK_IP_ENDPOINT = "http://127.0.0.1:8001"
LOOPBACK_IP_BRIDGE_URL = "http://127.0.0.1:8001/oramasys"
REMOTE_PUBLIC_ENDPOINT = "https://orama.example.com"
REMOTE_PUBLIC_BRIDGE_URL = "https://orama.example.com/oramasys"

_ENDPOINT_ENV_KEYS = (
    "ORAMASYS_ENDPOINT",
    "ORAMA_ENDPOINT",
    "ULTRATHINK_ENDPOINT",
)


@pytest.fixture
def isolate_oramasys_endpoint_env(monkeypatch):
    for key in _ENDPOINT_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_is_local_oramasys_endpoint_requires_tls_for_private_http():
    """Regression for a real finding: a private (RFC1918) HTTP endpoint
    must NOT classify as local, since that routes it through
    _dispatch_oramasys_http's direct, unencrypted transport where a network
    observer on that LAN could read or modify the payload. Loopback HTTP
    stays local (orama's typical deployment); RFC1918 HTTPS stays local
    (TLS satisfies the requirement); only RFC1918 HTTP changes."""
    assert _is_local_oramasys_endpoint("http://localhost:8001") is True
    assert _is_local_oramasys_endpoint("http://127.0.0.1:8001") is True
    assert _is_local_oramasys_endpoint("https://192.168.1.50:8001") is True
    assert _is_local_oramasys_endpoint("http://192.168.1.50:8001") is False
    assert _is_local_oramasys_endpoint("http://10.0.0.5:8001") is False


def test_bridge_does_not_duplicate_adapter_deny_telemetry():
    """The pinned adapter owns telemetry for its own validation denial;
    bridge-level exception handling must not emit that same failure again."""
    import orchestrator.orama_bridge as bridge
    from utils.ssrf_pinned_adapter import SSRFPolicyError

    denied = SSRFPolicyError("scheme not allowed")
    setattr(denied, "_egress_telemetry_emitted", True)

    with (
        patch("utils.ssrf_pinned_adapter.ssrf_request", side_effect=denied),
        patch.object(bridge, "emit") as emit,
        pytest.raises(SSRFPolicyError),
    ):
        bridge._dispatch_oramasys_http(
            "https://orama.example.com/oramasys", {"task": "test"}, 1.0
        )

    emit.assert_not_called()


def test_remote_http_bridge_refuses_to_send_bearer_credentials(monkeypatch):
    """Remote plaintext transport is permitted only when it carries no bearer."""
    import orchestrator.orama_bridge as bridge

    monkeypatch.setattr(bridge, "auth_headers", lambda: {"Authorization": "Bearer secret"})
    with (
        patch("utils.ssrf_pinned_adapter.ssrf_request") as request,
        pytest.raises(ValueError, match="remote HTTP endpoint with bearer credentials"),
    ):
        bridge._dispatch_oramasys_http(
            "http://orama.example.com/oramasys", {"task": "test"}, 1.0
        )

    request.assert_not_called()


class TestNormalizeEndpoint:
    def test_appends_ultrathink_path(self):
        assert normalize_oramasys_endpoint("http://localhost:8001") == "http://localhost:8001/oramasys"

    def test_replaces_legacy_orama_path(self):
        assert normalize_oramasys_endpoint("http://localhost:8001/orama") == "http://localhost:8001/oramasys"

    def test_replaces_legacy_ultrathink_path(self):
        assert normalize_oramasys_endpoint("http://localhost:8001/ultrathink") == "http://localhost:8001/oramasys"

    def test_does_not_double_append(self):
        assert normalize_oramasys_endpoint("http://localhost:8001/oramasys") == "http://localhost:8001/oramasys"

    def test_strips_trailing_slash(self):
        assert normalize_oramasys_endpoint("http://localhost:8001/") == "http://localhost:8001/oramasys"

    def test_empty_returns_empty(self):
        assert normalize_oramasys_endpoint("") == ""


class TestResolveEndpoint:
    def test_canonical_env_overrides_config_and_legacy_envs(self, monkeypatch):
        monkeypatch.setenv("ORAMASYS_ENDPOINT", "http://localhost:8101/oramasys")
        monkeypatch.setenv("ORAMA_ENDPOINT", "http://localhost:8102/orama")
        monkeypatch.setenv("ULTRATHINK_ENDPOINT", "http://localhost:8103/ultrathink")

        assert resolve_oramasys_endpoint("http://localhost:8001/oramasys") == (
            "http://localhost:8101/oramasys"
        )

    def test_legacy_ultrathink_env_remains_compatible(self, monkeypatch):
        monkeypatch.delenv("ORAMASYS_ENDPOINT", raising=False)
        monkeypatch.delenv("ORAMA_ENDPOINT", raising=False)
        monkeypatch.setenv("ULTRATHINK_ENDPOINT", "http://localhost:8103/ultrathink")

        assert resolve_oramasys_endpoint("http://localhost:8001/oramasys") == (
            "http://localhost:8103/oramasys"
        )

    def test_rejects_public_env_endpoint_override(self, monkeypatch):
        monkeypatch.setenv("ORAMASYS_ENDPOINT", "https://example.com/oramasys")

        with pytest.raises(ValueError, match="not permitted"):
            resolve_oramasys_endpoint("http://localhost:8001/oramasys")

    def test_configured_public_endpoint_is_not_revalidated(self, monkeypatch):
        monkeypatch.delenv("ORAMASYS_ENDPOINT", raising=False)
        monkeypatch.delenv("ORAMA_ENDPOINT", raising=False)
        monkeypatch.delenv("ULTRATHINK_ENDPOINT", raising=False)

        assert resolve_oramasys_endpoint("https://orama.example.com") == (
            "https://orama.example.com/oramasys"
        )


class TestParseTimeout:
    def test_valid_number(self):
        assert parse_oramasys_timeout("120") == 120.0

    def test_default_on_empty(self):
        assert parse_oramasys_timeout("") == 120.0

    def test_default_on_none(self):
        assert parse_oramasys_timeout(None) == 120.0

    def test_custom_default(self):
        assert parse_oramasys_timeout("", default=60.0) == 60.0

    def test_non_positive_timeout_uses_default(self):
        assert parse_oramasys_timeout("0") == 120.0
        assert parse_oramasys_timeout("-1", default=60.0) == 60.0

    def test_resolver_prefers_canonical_env_and_accepts_legacy(self, monkeypatch):
        monkeypatch.setenv("ORAMASYS_TIMEOUT", "42")
        monkeypatch.setenv("ORAMA_TIMEOUT", "43")
        assert resolve_oramasys_timeout(120) == 42.0

        monkeypatch.delenv("ORAMASYS_TIMEOUT")
        assert resolve_oramasys_timeout(120) == 43.0


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
    # imports ssrf_request locally inside _dispatch_oramasys_http, so the patch
    # target is the adapter module. Patch httpx.post as a tripwire so a local
    # mis-route (e.g. CI ORAMA_ENDPOINT override) cannot open a live socket.
    @pytest.fixture(autouse=True)
    def _isolate_endpoint_env(self, isolate_oramasys_endpoint_env):
        return isolate_oramasys_endpoint_env

    @patch("httpx.post")
    @patch("utils.ssrf_pinned_adapter.ssrf_request")
    def test_success_returns_response(self, mock_ssrf_request, mock_httpx_post):
        mock_httpx_post.side_effect = AssertionError(
            "remote public endpoints must use ssrf_request, not direct httpx"
        )
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": "analysis complete", "status": "ok"}
        mock_resp.raise_for_status.return_value = None
        mock_ssrf_request.return_value = mock_resp

        result = call_oramasys_bridge(
            endpoint=REMOTE_PUBLIC_ENDPOINT,
            timeout=120.0,
            task="Test task",
            task_type="deep_reasoning",
        )
        assert "response" in result
        assert result["response"]["result"] == "analysis complete"
        mock_ssrf_request.assert_called_once()
        mock_httpx_post.assert_not_called()

    @patch("httpx.post")
    @patch("utils.ssrf_pinned_adapter.ssrf_request")
    def test_failure_raises_exception(self, mock_ssrf_request, mock_httpx_post):
        mock_httpx_post.side_effect = AssertionError(
            "remote public endpoints must use ssrf_request, not direct httpx"
        )
        mock_ssrf_request.side_effect = RuntimeError("mocked remote transport failure")

        with pytest.raises(RuntimeError, match="mocked remote transport failure"):
            call_oramasys_bridge(
                endpoint=REMOTE_PUBLIC_ENDPOINT,
                timeout=120.0,
                task="Test task",
                task_type="deep_reasoning",
            )
        mock_ssrf_request.assert_called_once()
        mock_httpx_post.assert_not_called()

    @patch("httpx.post")
    @patch("utils.ssrf_pinned_adapter.ssrf_request")
    def test_uses_scoped_control_plane_auth_headers(
        self, mock_ssrf_request, mock_httpx_post, monkeypatch
    ):
        mock_httpx_post.side_effect = AssertionError(
            "remote public endpoints must use ssrf_request, not direct httpx"
        )
        monkeypatch.setenv("ORAMA_CONTROL_PLANE_TOKEN", "orama-test-token")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": "ok"}
        mock_resp.raise_for_status.return_value = None
        mock_ssrf_request.return_value = mock_resp

        call_oramasys_bridge(
            endpoint=REMOTE_PUBLIC_ENDPOINT,
            timeout=3.0,
            task="Test task",
            task_type="deep_reasoning",
        )

        mock_ssrf_request.assert_called_once_with(
            "POST",
            REMOTE_PUBLIC_BRIDGE_URL,
            json=build_oramasys_http_payload("Test task", "deep_reasoning"),
            headers={
                "Authorization": "Bearer orama-test-token",
                CONTROL_PLANE_DEPTH_HEADER: "1",
            },
            timeout=3.0,
        )
        mock_httpx_post.assert_not_called()


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

    @pytest.fixture(autouse=True)
    def _isolate_endpoint_env(self, isolate_oramasys_endpoint_env):
        return isolate_oramasys_endpoint_env

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
            endpoint=LOOPBACK_IP_ENDPOINT,
            timeout=120.0,
            task="Test task",
            task_type="deep_reasoning",
        )

        from orchestrator.control_plane_auth import auth_headers

        mock_httpx_post.assert_called_once_with(
            LOOPBACK_IP_BRIDGE_URL,
            json=build_oramasys_http_payload("Test task", "deep_reasoning"),
            headers={
                **auth_headers(),
                CONTROL_PLANE_DEPTH_HEADER: "1",
            },
            timeout=120.0,
        )
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
            endpoint=CANONICAL_LOCAL_ENDPOINT,
            timeout=120.0,
            task="Test task",
            task_type="deep_reasoning",
        )

        from orchestrator.control_plane_auth import auth_headers

        mock_httpx_post.assert_called_once_with(
            CANONICAL_LOCAL_BRIDGE_URL,
            json=build_oramasys_http_payload("Test task", "deep_reasoning"),
            headers={
                **auth_headers(),
                CONTROL_PLANE_DEPTH_HEADER: "1",
            },
            timeout=120.0,
        )
        mock_ssrf_request.assert_not_called()


class TestCallBridgeAsyncLocal:
    @pytest.fixture(autouse=True)
    def _isolate_endpoint_env(self, isolate_oramasys_endpoint_env):
        return isolate_oramasys_endpoint_env

    @pytest.mark.asyncio
    async def test_loopback_endpoint_uses_direct_async_transport(self):
        from orchestrator.orama_bridge import call_oramasys_mcp_or_bridge

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"result": "ok"}
        mock_resp.raise_for_status.return_value = None

        with (
            patch("utils.ssrf_pinned_adapter.ssrf_request") as mock_ssrf_request,
            patch("httpx.post", new=MagicMock()) as mock_post,
            patch.dict(os.environ, {}, clear=False),
        ):
            # patch.dict restores the original environment on exit, so
            # removing these here (rather than an earlier empty update,
            # which changed nothing) reliably forces the HTTP path
            # regardless of what's set in the ambient environment.
            os.environ.pop("ORAMASYS_MCP_SERVER_CMD", None)
            os.environ.pop("ULTRATHINK_MCP_SERVER_CMD", None)
            mock_ssrf_request.side_effect = AssertionError("must not use the deny-by-default transport")
            mock_post.return_value = mock_resp

            result = await call_oramasys_mcp_or_bridge(
                endpoint=CANONICAL_LOCAL_ENDPOINT,
                timeout=5.0,
                task="Test task",
                task_type="deep_reasoning",
            )

        mock_ssrf_request.assert_not_called()
        mock_post.assert_called_once()
        assert mock_post.call_args.args[0] == CANONICAL_LOCAL_BRIDGE_URL
        assert result["response"]["result"] == "ok"


def test_sync_and_async_bridge_share_one_dispatch_implementation(
    isolate_oramasys_endpoint_env,
):
    """GitHub issue #361: the async fallback must wrap the SAME sync helper
    (asyncio.to_thread around it), not maintain a second, separately-written
    HTTP-call implementation that could drift into a different local/remote
    classification for the same URL.

    Asserts this at RUNTIME, not via source-text inspection: source-text
    checks (the previous version of this test) don't prove the two code
    paths actually invoke the same function object -- a stale docstring, a
    dead branch, or a second dispatcher elsewhere could satisfy a text
    search while runtime behavior regresses. Patches
    orama_bridge._dispatch_oramasys_http directly and calls both
    call_oramasys_bridge() (sync) and call_oramasys_mcp_or_bridge()'s HTTP
    fallback (async), asserting the SAME mock received the expected URL,
    payload, and timeout for each -- proof they route through one shared
    implementation, not equivalent-looking twins."""
    from unittest.mock import MagicMock, patch

    from orchestrator import orama_bridge

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": "ok"}
    mock_resp.raise_for_status.return_value = None

    with patch.object(
        orama_bridge, "_dispatch_oramasys_http", return_value=mock_resp
    ) as mock_dispatch:
        sync_result = orama_bridge.call_oramasys_bridge(
            endpoint=CANONICAL_LOCAL_ENDPOINT,
            timeout=42.0,
            task="sync task",
            task_type="deep_reasoning",
        )

    assert sync_result["response"]["result"] == "ok"
    mock_dispatch.assert_called_once_with(
        CANONICAL_LOCAL_BRIDGE_URL,
        orama_bridge.build_oramasys_http_payload("sync task", "deep_reasoning"),
        42.0,
    )


@pytest.mark.asyncio
async def test_async_bridge_calls_the_same_dispatch_helper_with_matching_args(
    isolate_oramasys_endpoint_env,
):
    from unittest.mock import MagicMock, patch

    from orchestrator import orama_bridge

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": "ok"}
    mock_resp.raise_for_status.return_value = None

    with (
        patch.dict(os.environ, {}, clear=False),
        patch.object(orama_bridge, "_dispatch_oramasys_http", return_value=mock_resp) as mock_dispatch,
    ):
        os.environ.pop("ORAMASYS_MCP_SERVER_CMD", None)
        os.environ.pop("ULTRATHINK_MCP_SERVER_CMD", None)
        async_result = await orama_bridge.call_oramasys_mcp_or_bridge(
            endpoint=CANONICAL_LOCAL_ENDPOINT,
            timeout=42.0,
            task="async task",
            task_type="deep_reasoning",
        )

    assert async_result["response"]["result"] == "ok"
    mock_dispatch.assert_called_once_with(
        CANONICAL_LOCAL_BRIDGE_URL,
        orama_bridge.build_oramasys_http_payload("async task", "deep_reasoning"),
        42.0,
    )
