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
    config = alphaclaw_bootstrap.build_openclaw_config(pt={})
    ollama_mac = config["models"]["providers"]["ollama-mac"]
    assert ollama_mac["baseUrl"] == "http://localhost:11434"


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
