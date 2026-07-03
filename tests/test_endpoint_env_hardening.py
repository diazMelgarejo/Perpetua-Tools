"""Regression tests: malformed endpoint env vars must never escape as bare ValueError.

Invariant (endpoint transport policy): a model endpoint is either a valid,
normalized string or a single ModelEndpointPolicyError — ``urlparse().port``
raises ValueError lazily and every access outside the policy boundary must be
guarded. These tests pin the 2026-07-02 hardening of agent_launcher.py,
fastapi_app.py (_candidate_base_url), and alphaclaw_bootstrap.py.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

MALFORMED_ENDPOINTS = [
    "http://localhost:notaport",
    "http://localhost:99999999999999",
]


@pytest.mark.parametrize("endpoint", MALFORMED_ENDPOINTS)
def test_agent_launcher_import_survives_malformed_env(endpoint):
    """Importing agent_launcher with a malformed endpoint env must not crash.

    Uses subprocess isolation: the failure mode is a ValueError at module
    import time, which in-process importlib.reload cannot cleanly reproduce.
    """
    env = dict(os.environ)
    env.update(
        OLLAMA_MAC_ENDPOINT=endpoint,
        LM_STUDIO_MAC_ENDPOINT=endpoint,
        PYTHONIOENCODING="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, 'src'); "
            "import perpetua_tools.agent_launcher; print('IMPORT_OK')",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
        timeout=60,
    )
    assert "IMPORT_OK" in proc.stdout, (
        f"agent_launcher import crashed with {endpoint!r}:\n{proc.stderr[-2000:]}"
    )
    assert "ValueError" not in proc.stderr


def test_candidate_base_url_survives_malformed_host():
    """fastapi_app._candidate_base_url must never raise on malformed host strings."""
    sys.path.insert(0, str(REPO_ROOT))
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from orchestrator.fastapi_app import _candidate_base_url

    for host in ("http://gpu:notaport", "http://gpu:99999999", "gpu-box", ""):
        result = _candidate_base_url(host, 1234)
        assert isinstance(result, str)

    # Contract: backend-specific port governs (transport-identity semantics).
    assert _candidate_base_url("http://gpu-box:9999", 1234) == "http://gpu-box:1234"
    assert _candidate_base_url("https://gpu-box", 1234) == "https://gpu-box:1234"


def test_gateway_port_from_url_falls_back_on_malformed_port():
    """alphaclaw_bootstrap._gateway_port_from_url must fall back, not raise."""
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from perpetua_tools.alphaclaw_bootstrap import (
        OPENCLAW_GATEWAY_PORT,
        _gateway_port_from_url,
    )

    assert _gateway_port_from_url("http://localhost:notaport") == OPENCLAW_GATEWAY_PORT
    assert _gateway_port_from_url("http://localhost:18789") == 18789


def test_safe_port_guards_lazy_valueerror():
    """agent_launcher._safe_port returns the default for malformed/out-of-range ports."""
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from urllib.parse import urlparse

    from perpetua_tools.agent_launcher import _safe_port

    assert _safe_port(urlparse("http://h:notaport"), 11434) == 11434
    assert _safe_port(urlparse("http://h:70000"), 11434) == 11434
    assert _safe_port(urlparse("http://h:1234"), 11434) == 1234
    assert _safe_port(urlparse("http://h"), 11434) == 11434
