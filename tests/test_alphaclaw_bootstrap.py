from __future__ import annotations

import asyncio
import builtins
import importlib
from pathlib import Path

import perpetua_tools.alphaclaw_bootstrap as alphaclaw_bootstrap


def test_resolve_endpoint_self_heals_stale_lan_ip_on_mac(monkeypatch):
    monkeypatch.setenv("ORAMA_PLATFORM", "mac")
    monkeypatch.setenv("OLLAMA_MAC_ENDPOINT", "http://192.168.254.110:11434")
    import perpetua_tools.alphaclaw_bootstrap as mod

    mod = importlib.reload(mod)
    assert mod.OLLAMA_MAC == "http://localhost:11434"


def test_build_openclaw_config_prefers_routing_state_for_ollama_mac():
    pt = {
        "manager_backend": "mac-ollama",
        "manager_endpoint": "http://localhost:11434",
        "manager_model": "glm-5.1:cloud",
        "coder_backend": "mac-degraded",
        "mac_lmstudio_ok": False,
    }
    config = alphaclaw_bootstrap.build_openclaw_config(pt)
    assert config["models"]["providers"]["ollama-mac"]["baseUrl"] == "http://localhost:11434"


def test_build_openclaw_config_heals_stale_lan_routing_json_on_mac(monkeypatch):
    monkeypatch.setenv("ORAMA_PLATFORM", "mac")
    pt = {
        "manager_backend": "mac-ollama",
        "manager_endpoint": "http://192.168.254.110:11434",
        "manager_model": "glm-5.1:cloud",
        "mac_lmstudio_endpoint": "http://192.168.254.110:1234",
        "coder_backend": "mac-degraded",
        "mac_lmstudio_ok": True,
    }
    config = alphaclaw_bootstrap.build_openclaw_config(pt)
    providers = config["models"]["providers"]
    assert providers["ollama-mac"]["baseUrl"] == "http://localhost:11434"
    assert providers["lmstudio-mac"]["baseUrl"] == "http://localhost:1234/v1"


def test_start_openclaw_gateway_closes_log_handle_when_popen_fails(tmp_path, monkeypatch):
    real_open = builtins.open
    opened = []

    class TrackingFile:
        def __init__(self, fh):
            self._fh = fh
            self.closed_by_wrapper = False

        def close(self):
            self.closed_by_wrapper = True
            return self._fh.close()

        def __getattr__(self, name):
            return getattr(self._fh, name)

    def tracking_open(file, *args, **kwargs):
        fh = TrackingFile(real_open(file, *args, **kwargs))
        opened.append(fh)
        return fh

    def fail_popen(*_args, **_kwargs):
        raise OSError("boom")

    monkeypatch.setattr(alphaclaw_bootstrap.shutil, "which", lambda _name: "openclaw")
    monkeypatch.setattr(alphaclaw_bootstrap.subprocess, "Popen", fail_popen)
    monkeypatch.setattr(builtins, "open", tracking_open)

    result = asyncio.run(
        alphaclaw_bootstrap._start_openclaw_gateway(
            Path(tmp_path),
            setup_password="secret",
            timeout=0,
        )
    )

    assert result is None
    assert opened
    assert opened[0].closed_by_wrapper is True
