"""Tests for alphaclaw_manager.py's TLS-in-front-of-AlphaClaw wiring.

Companion plan (deferred full design): orama-system
docs/v2/49-peer-mesh-auth-tls-v2-plan.md.
"""
from __future__ import annotations

import http.server
import socketserver
import threading

import pytest

from orchestrator.alphaclaw_manager import (
    AlphaClawState,
    alphaclaw_tls_enabled,
    _maybe_wrap_gateway_with_tls,
)
from orchestrator.alphaclaw_tls_proxy import _CRYPTOGRAPHY_AVAILABLE


def test_alphaclaw_tls_enabled_defaults_off(monkeypatch):
    """Off by default -- new opt-in infrastructure must never change
    behavior for a deployment that hasn't explicitly asked for it."""
    monkeypatch.delenv("ALPHACLAW_TLS_ENABLED", raising=False)
    assert alphaclaw_tls_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_alphaclaw_tls_enabled_accepts_truthy_forms(monkeypatch, value):
    monkeypatch.setenv("ALPHACLAW_TLS_ENABLED", value)
    assert alphaclaw_tls_enabled() is True


def test_wrap_is_noop_when_disabled(monkeypatch):
    """The env gate is checked first, before anything else -- a disabled
    gate must not even attempt to import the proxy module."""
    monkeypatch.delenv("ALPHACLAW_TLS_ENABLED", raising=False)
    state = AlphaClawState(running=True, port=18789, gateway_url="http://127.0.0.1:18789")

    result = _maybe_wrap_gateway_with_tls(state)

    assert result is state  # same object, untouched
    assert result.gateway_url == "http://127.0.0.1:18789"
    assert result.tls_enabled is False


def test_wrap_is_noop_when_gateway_not_running(monkeypatch):
    """Even with TLS enabled, a gateway that isn't running/has no port
    yet has nothing to wrap -- must not attempt to start a proxy pointed
    at a nonexistent upstream."""
    monkeypatch.setenv("ALPHACLAW_TLS_ENABLED", "1")
    state = AlphaClawState(running=False, port=0, error="not started yet")

    result = _maybe_wrap_gateway_with_tls(state)

    assert result is state
    assert result.tls_enabled is False


@pytest.mark.skipif(
    not _CRYPTOGRAPHY_AVAILABLE, reason="'cryptography' library not installed"
)
def test_wrap_replaces_gateway_url_with_https_when_enabled(monkeypatch, tmp_path):
    """The real end-to-end wiring case: a genuine upstream HTTP server,
    TLS enabled, gateway_url comes back as https:// with tls_enabled=True
    and a real fingerprint -- proving PT (not orama) made this decision,
    since this test never touches anything orama-side."""
    import orchestrator.alphaclaw_tls_proxy as tls_mod

    monkeypatch.setattr(tls_mod, "CERT_DIR", tmp_path / "alphaclaw_tls")
    monkeypatch.setenv("ALPHACLAW_TLS_ENABLED", "1")

    class _FakeAlphaClaw(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        def log_message(self, *a):
            pass

    upstream = socketserver.TCPServer(("127.0.0.1", 0), _FakeAlphaClaw)
    upstream_port = upstream.server_address[1]
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()

    try:
        state = AlphaClawState(
            running=True,
            port=upstream_port,
            gateway_url=f"http://127.0.0.1:{upstream_port}",
        )
        result = _maybe_wrap_gateway_with_tls(state)

        assert result.gateway_url.startswith("https://")
        assert result.tls_enabled is True
        assert result.tls_fingerprint  # non-empty
        # Everything else about the state must be preserved unchanged.
        assert result.running == state.running
        assert result.port == state.port
    finally:
        upstream.shutdown()
        upstream.server_close()


def test_wrap_degrades_gracefully_on_proxy_failure(monkeypatch, tmp_path):
    """A TLS failure must never block gateway resolution -- degrade to the
    original (HTTP) state with the error logged, matching
    bootstrap_alphaclaw's own established non-fatal-error convention."""
    import orchestrator.alphaclaw_tls_proxy as tls_mod

    monkeypatch.setattr(tls_mod, "_CRYPTOGRAPHY_AVAILABLE", False)
    monkeypatch.setattr(tls_mod, "CERT_DIR", tmp_path / "alphaclaw_tls")
    monkeypatch.setenv("ALPHACLAW_TLS_ENABLED", "1")

    state = AlphaClawState(running=True, port=18789, gateway_url="http://127.0.0.1:18789")
    result = _maybe_wrap_gateway_with_tls(state)

    assert result.gateway_url == "http://127.0.0.1:18789"  # unchanged
    assert result.tls_enabled is False
    assert result.running is True  # gateway resolution itself unaffected


def test_wrap_populates_error_field_on_failure(monkeypatch, tmp_path):
    """Regression: a TLS start failure must be visible in the returned
    state's own error field, not just logged -- a fingerprint mismatch in
    particular is a real security signal that must reach the resolved
    runtime payload, where an operator not watching logs can still see it."""
    import orchestrator.alphaclaw_tls_proxy as tls_mod
    import orchestrator.alphaclaw_manager as manager_mod

    monkeypatch.setattr(manager_mod, "_active_tls_proxy", None)
    monkeypatch.setattr(tls_mod, "_CRYPTOGRAPHY_AVAILABLE", False)
    monkeypatch.setattr(tls_mod, "CERT_DIR", tmp_path / "alphaclaw_tls")
    monkeypatch.setenv("ALPHACLAW_TLS_ENABLED", "1")

    state = AlphaClawState(running=True, port=18789, gateway_url="http://127.0.0.1:18789")
    result = _maybe_wrap_gateway_with_tls(state)

    assert result.error, "failure must populate the error field, not just log it"
    assert "TLS" in result.error


def test_wrap_stops_previous_proxy_instance_before_replacing(monkeypatch, tmp_path):
    """Regression: calling this repeatedly (re-resolution, retries) must
    not leak a new socket + daemon thread per call -- the previous active
    proxy instance must be stopped before a new one starts."""
    import orchestrator.alphaclaw_tls_proxy as tls_mod
    import orchestrator.alphaclaw_manager as manager_mod

    monkeypatch.setattr(tls_mod, "CERT_DIR", tmp_path / "alphaclaw_tls")
    monkeypatch.setenv("ALPHACLAW_TLS_ENABLED", "1")

    stopped = {"n": 0}

    class _FakeProxy:
        def __init__(self, upstream_port):
            self.fingerprint = "aabbccdd" * 8

        def start(self):
            return "https://127.0.0.1:9999"

        def stop(self):
            stopped["n"] += 1

    monkeypatch.setattr(tls_mod, "AlphaClawTlsProxy", _FakeProxy)

    state = AlphaClawState(running=True, port=18789, gateway_url="http://127.0.0.1:18789")
    _maybe_wrap_gateway_with_tls(state)
    assert stopped["n"] == 0  # nothing to stop on the first call

    _maybe_wrap_gateway_with_tls(state)
    assert stopped["n"] == 1  # the first instance was stopped before the second started

    manager_mod._active_tls_proxy = None  # don't leak into other tests
