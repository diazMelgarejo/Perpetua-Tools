from __future__ import annotations

import asyncio
import builtins
import importlib
from pathlib import Path

import perpetua_tools.alphaclaw_bootstrap as alphaclaw_bootstrap


def _reload_bootstrap(monkeypatch, **env: str) -> None:
    """Reload alphaclaw_bootstrap with a fresh env (module-level endpoint constants)."""
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    importlib.reload(alphaclaw_bootstrap)


def test_locality_resolve_endpoint_heals_stale_lan_on_mac(monkeypatch):
    """Explicit OLLAMA_MAC_ENDPOINT LAN IP on Mac must normalize to localhost."""
    _reload_bootstrap(
        monkeypatch,
        ORAMA_PLATFORM="mac",
        OLLAMA_MAC_ENDPOINT="http://192.168.254.110:11434",
    )
    assert alphaclaw_bootstrap.RUNNING_ON_MAC is True
    assert alphaclaw_bootstrap.OLLAMA_MAC == "http://localhost:11434"


def test_locality_resolve_endpoint_heals_stale_lan_on_windows(monkeypatch):
    """Explicit OLLAMA_WINDOWS_ENDPOINT LAN IP on Windows must normalize to localhost."""
    _reload_bootstrap(
        monkeypatch,
        ORAMA_PLATFORM="windows",
        OLLAMA_WINDOWS_ENDPOINT="http://192.168.254.108:11434",
    )
    assert alphaclaw_bootstrap.RUNNING_ON_WINDOWS is True
    assert alphaclaw_bootstrap.OLLAMA_WIN == "http://localhost:11434"


def test_locality_resolve_endpoint_heals_csv_lms_win_on_windows(monkeypatch):
    """Comma-separated LM_STUDIO_WIN_ENDPOINTS must not crash import on Windows."""
    _reload_bootstrap(
        monkeypatch,
        ORAMA_PLATFORM="windows",
        LM_STUDIO_WIN_ENDPOINTS=(
            "http://192.168.254.108:1234,http://192.168.254.100:1234"
        ),
    )
    assert alphaclaw_bootstrap.RUNNING_ON_WINDOWS is True
    assert alphaclaw_bootstrap.LMS_WIN == "http://localhost:1234"


def test_locality_resolve_endpoint_preserves_lan_when_remote(monkeypatch):
    """Mac bootstrap must keep Windows LAN endpoint when not running on Windows."""
    _reload_bootstrap(
        monkeypatch,
        ORAMA_PLATFORM="mac",
        OLLAMA_WINDOWS_ENDPOINT="http://192.168.254.108:11434",
    )
    assert alphaclaw_bootstrap.OLLAMA_WIN == "http://192.168.254.108:11434"


def test_build_openclaw_config_ollama_mac_uses_healed_localhost(monkeypatch):
    """openclaw.json ollama-mac baseUrl must use healed localhost, not stale LAN env."""
    _reload_bootstrap(
        monkeypatch,
        ORAMA_PLATFORM="mac",
        OLLAMA_MAC_ENDPOINT="http://192.168.254.110:11434",
    )
    monkeypatch.setattr(alphaclaw_bootstrap, "_load_pt_state", lambda: {})
    config = alphaclaw_bootstrap.build_openclaw_config()
    ollama_mac = config["models"]["providers"]["ollama-mac"]
    assert ollama_mac["baseUrl"] == "http://localhost:11434"


def test_build_openclaw_config_heals_stale_win_lms_from_routing_json(monkeypatch):
    """Stale routing.json lmstudio_endpoint must not bypass Windows localhost heal."""
    _reload_bootstrap(monkeypatch, ORAMA_PLATFORM="windows")
    config = alphaclaw_bootstrap.build_openclaw_config(
        pt={"lmstudio_endpoint": "http://192.168.254.108:1234"}
    )
    win_lms = config["models"]["providers"]["lmstudio-win"]
    assert win_lms["baseUrl"] == "http://localhost:1234/v1"


def test_build_openclaw_config_heals_stale_mac_lms_from_routing_json(monkeypatch):
    """Stale routing.json mac_lmstudio_endpoint must not bypass Mac localhost heal."""
    _reload_bootstrap(monkeypatch, ORAMA_PLATFORM="mac")
    config = alphaclaw_bootstrap.build_openclaw_config(
        pt={"mac_lmstudio_endpoint": "http://192.168.254.110:1234"}
    )
    mac_lms = config["models"]["providers"]["lmstudio-mac"]
    assert mac_lms["baseUrl"] == "http://localhost:1234/v1"



def test_build_openclaw_config_prefers_routing_state_for_ollama_mac(monkeypatch):
    """routing.json manager_endpoint must feed ollama-mac when backend is mac-ollama."""
    _reload_bootstrap(monkeypatch, ORAMA_PLATFORM="mac")
    config = alphaclaw_bootstrap.build_openclaw_config(
        pt={
            "manager_backend": "mac-ollama",
            "manager_endpoint": "http://localhost:11434",
            "manager_model": "glm-5.1:cloud",
            "coder_backend": "mac-degraded",
            "mac_lmstudio_ok": False,
        }
    )
    assert config["models"]["providers"]["ollama-mac"]["baseUrl"] == "http://localhost:11434"


def test_build_openclaw_config_heals_stale_lan_routing_json_on_mac(monkeypatch):
    """Stale routing.json LAN endpoints for ollama + LMS must heal on Mac."""
    _reload_bootstrap(monkeypatch, ORAMA_PLATFORM="mac")
    config = alphaclaw_bootstrap.build_openclaw_config(
        pt={
            "manager_backend": "mac-ollama",
            "manager_endpoint": "http://192.168.254.110:11434",
            "manager_model": "glm-5.1:cloud",
            "mac_lmstudio_endpoint": "http://192.168.254.110:1234",
            "coder_backend": "mac-degraded",
            "mac_lmstudio_ok": True,
        }
    )
    providers = config["models"]["providers"]
    assert providers["ollama-mac"]["baseUrl"] == "http://localhost:11434"
    assert providers["lmstudio-mac"]["baseUrl"] == "http://localhost:1234/v1"


def test_locality_resolve_endpoint_canonicalizes_bare_loopback_on_target(monkeypatch):
    """Bare localhost:port on the target machine must still gain http:// scheme."""
    _reload_bootstrap(
        monkeypatch,
        ORAMA_PLATFORM="mac",
        LM_STUDIO_MAC_ENDPOINT="localhost:1234",
    )
    assert alphaclaw_bootstrap.LMS_MAC == "http://localhost:1234"


def test_heal_pt_endpoint_url_canonicalizes_bare_loopback_on_target(monkeypatch):
    """routing.json bare loopback endpoints must not bypass _canonical_endpoint."""
    _reload_bootstrap(monkeypatch, ORAMA_PLATFORM="mac")
    result = alphaclaw_bootstrap._heal_pt_endpoint_url(
        "localhost:11434",
        running_on_target=True,
        port=11434,
    )
    assert result == "http://localhost:11434"


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
