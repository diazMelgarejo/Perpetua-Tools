from __future__ import annotations

import asyncio
import builtins
import importlib
import json
from pathlib import Path

import pytest

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


def test_validate_pt_state_accepts_valid_routing_json():
    state = {
        "mac_lmstudio_endpoint": "http://localhost:1234",
        "manager_endpoint": "http://192.168.254.110:11434",
        "coder_backend": "mac-degraded",
        "mac_lmstudio_ok": True,
        "future_field": "tolerated",
    }
    assert alphaclaw_bootstrap._validate_pt_state(state) == state


def test_validate_pt_state_rejects_non_rfc1918_endpoint():
    with pytest.raises(ValueError, match="non-RFC-1918"):
        alphaclaw_bootstrap._validate_pt_state(
            {"manager_endpoint": "http://8.8.8.8:11434"}
        )


@pytest.mark.parametrize(
    ("state", "backend"),
    [
        (
            {
                "manager_endpoint": "http://localhost:11434",
                "coder_endpoint": "https://api.perplexity.ai",
                "coder_backend": "perplexity",
            },
            "perplexity",
        ),
        (
            {
                "manager_endpoint": "http://localhost:11434",
                "coder_endpoint": "https://api.anthropic.com",
                "coder_backend": "anthropic",
            },
            "anthropic",
        ),
    ],
)
def test_validate_pt_state_accepts_cloud_fallback_routing(state, backend):
    """agent_launcher cloud fallback must not crash alphaclaw bootstrap."""
    assert alphaclaw_bootstrap._validate_pt_state(state) == state


def test_validate_pt_state_rejects_spoofed_cloud_coder_endpoint():
    with pytest.raises(ValueError, match="disallowed cloud host"):
        alphaclaw_bootstrap._validate_pt_state(
            {
                "coder_endpoint": "https://evil.example.com",
                "coder_backend": "perplexity",
            }
        )


def test_load_pt_state_accepts_cloud_fallback_file(tmp_path, monkeypatch):
    routing = tmp_path / "routing.json"
    routing.write_text(
        json.dumps(
            {
                "manager_endpoint": "http://localhost:11434",
                "coder_endpoint": "https://api.perplexity.ai",
                "coder_backend": "perplexity",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PT_AGENTS_STATE", str(routing))
    state = alphaclaw_bootstrap._load_pt_state()
    assert state is not None
    assert state["coder_backend"] == "perplexity"


def test_load_pt_state_validates_file(tmp_path, monkeypatch):
    routing = tmp_path / "routing.json"
    routing.write_text(
        '{"manager_endpoint": "http://8.8.8.8:11434"}', encoding="utf-8"
    )
    monkeypatch.setenv("PT_AGENTS_STATE", str(routing))
    with pytest.raises(ValueError, match="non-RFC-1918"):
        alphaclaw_bootstrap._load_pt_state()


def test_module_constants_canonicalize_bare_env_scheme(monkeypatch):
    """Bare host:port env vars must gain http:// at import (T1-B)."""
    _reload_bootstrap(
        monkeypatch,
        ORAMA_PLATFORM="mac",
        OLLAMA_WINDOWS_ENDPOINT="192.168.254.108:11434",
    )
    assert alphaclaw_bootstrap.OLLAMA_WIN == "http://192.168.254.108:11434"

# ---------------------------------------------------------------------------
# Additional tests for PR additions: _validate_pt_state, _ALLOWED_ENDPOINT_HOST_RE,
# _heal_pt_endpoint_url (canonical return fix), _load_pt_state edge cases
# ---------------------------------------------------------------------------


def test_validate_pt_state_accepts_empty_dict():
    """An empty routing.json dict must pass validation (all properties optional)."""
    assert alphaclaw_bootstrap._validate_pt_state({}) == {}


def test_validate_pt_state_accepts_all_rfc1918_ranges():
    """All RFC-1918 address ranges must be accepted by _validate_pt_state."""
    for host in ("10.0.0.1", "172.16.0.1", "172.31.255.255", "192.168.1.100"):
        state = {"manager_endpoint": f"http://{host}:11434"}
        result = alphaclaw_bootstrap._validate_pt_state(state)
        assert result["manager_endpoint"] == f"http://{host}:11434"


def test_validate_pt_state_accepts_localhost_variants():
    """localhost and 127.x.x.x must be accepted."""
    for host in ("localhost", "127.0.0.1", "127.1.2.3"):
        state = {"manager_endpoint": f"http://{host}:11434"}
        assert alphaclaw_bootstrap._validate_pt_state(state) == state


def test_validate_pt_state_rejects_172_15_non_rfc1918():
    """172.15.x.x is outside RFC-1918 range and must be rejected."""
    with pytest.raises(ValueError, match="non-RFC-1918"):
        alphaclaw_bootstrap._validate_pt_state(
            {"manager_endpoint": "http://172.15.0.1:11434"}
        )


def test_validate_pt_state_rejects_172_32_non_rfc1918():
    """172.32.x.x is outside RFC-1918 range and must be rejected."""
    with pytest.raises(ValueError, match="non-RFC-1918"):
        alphaclaw_bootstrap._validate_pt_state(
            {"manager_endpoint": "http://172.32.0.1:11434"}
        )


def test_validate_pt_state_rejects_all_four_endpoint_keys():
    """Non-RFC-1918 host must be caught for each of the four endpoint fields."""
    for key in ("mac_lmstudio_endpoint", "lmstudio_endpoint", "manager_endpoint", "coder_endpoint"):
        with pytest.raises(ValueError, match="non-RFC-1918"):
            alphaclaw_bootstrap._validate_pt_state({key: "http://1.2.3.4:1234"})


def test_validate_pt_state_rejects_invalid_coder_backend():
    """coder_backend must be one of the schema enum values."""
    with pytest.raises(ValueError, match="schema violation"):
        alphaclaw_bootstrap._validate_pt_state({"coder_backend": "invalid-backend"})


def test_validate_pt_state_rejects_non_http_endpoint():
    """Endpoint URLs must start with http:// or https:// per schema pattern."""
    with pytest.raises(ValueError, match="schema violation"):
        alphaclaw_bootstrap._validate_pt_state(
            {"manager_endpoint": "ftp://localhost:21"}
        )


def test_validate_pt_state_rejects_wrong_type_for_mac_lmstudio_ok():
    """mac_lmstudio_ok must be a boolean; string must fail schema validation."""
    with pytest.raises(ValueError, match="schema violation"):
        alphaclaw_bootstrap._validate_pt_state({"mac_lmstudio_ok": "yes"})


def test_validate_pt_state_accepts_additional_properties():
    """additionalProperties=True means unknown keys must pass without error."""
    state = {"future_feature": "tolerated", "unknown_key": 42}
    assert alphaclaw_bootstrap._validate_pt_state(state) == state


def test_validate_pt_state_skips_empty_endpoint_strings():
    """An empty string for an endpoint key must not trigger the host regex check."""
    state = {"manager_endpoint": ""}
    # Schema allows empty string if no pattern (actually schema pattern requires http, so
    # an empty string fails pattern validation) — skip key if empty string after get()
    # The code does `if not url: continue`, and `state.get(key, "")` → empty → skipped
    # But actually the schema has pattern ^https?:// so empty string violates schema
    # The code skips via `url = state.get(key, ""); if not url: continue`
    # Empty string IS falsy → skip host check; BUT schema validation runs first
    # Empty string does NOT match pattern ^https?:// → schema error
    # So this should raise ValueError
    with pytest.raises(ValueError, match="schema violation"):
        alphaclaw_bootstrap._validate_pt_state({"manager_endpoint": ""})


def test_validate_pt_state_returns_same_dict_object():
    """_validate_pt_state must return the same dict that was passed in."""
    state = {"mac_lmstudio_endpoint": "http://localhost:1234", "mac_lmstudio_ok": False}
    result = alphaclaw_bootstrap._validate_pt_state(state)
    assert result is state


def test_load_pt_state_returns_none_when_env_not_set(monkeypatch):
    """When PT_AGENTS_STATE is not set, _load_pt_state must return None."""
    monkeypatch.delenv("PT_AGENTS_STATE", raising=False)
    assert alphaclaw_bootstrap._load_pt_state() is None


def test_load_pt_state_returns_none_when_file_missing(tmp_path, monkeypatch):
    """When PT_AGENTS_STATE points to a nonexistent file, return None."""
    monkeypatch.setenv("PT_AGENTS_STATE", str(tmp_path / "nonexistent.json"))
    assert alphaclaw_bootstrap._load_pt_state() is None


def test_load_pt_state_raises_when_json_is_list(tmp_path, monkeypatch):
    """When routing.json contains a JSON list, _load_pt_state must raise ValueError."""
    routing = tmp_path / "routing.json"
    routing.write_text('[{"key": "value"}]', encoding="utf-8")
    monkeypatch.setenv("PT_AGENTS_STATE", str(routing))
    with pytest.raises(ValueError, match="JSON object"):
        alphaclaw_bootstrap._load_pt_state()


def test_load_pt_state_raises_when_json_is_string(tmp_path, monkeypatch):
    """When routing.json is a bare JSON string, _load_pt_state must raise ValueError."""
    routing = tmp_path / "routing.json"
    routing.write_text('"just a string"', encoding="utf-8")
    monkeypatch.setenv("PT_AGENTS_STATE", str(routing))
    with pytest.raises(ValueError, match="JSON object"):
        alphaclaw_bootstrap._load_pt_state()


def test_load_pt_state_accepts_valid_routing_json(tmp_path, monkeypatch):
    """A valid routing.json dict must be returned without modification."""
    routing = tmp_path / "routing.json"
    routing.write_text(
        '{"mac_lmstudio_endpoint": "http://localhost:1234", "mac_lmstudio_ok": true}',
        encoding="utf-8",
    )
    monkeypatch.setenv("PT_AGENTS_STATE", str(routing))
    state = alphaclaw_bootstrap._load_pt_state()
    assert state is not None
    assert state["mac_lmstudio_endpoint"] == "http://localhost:1234"
    assert state["mac_lmstudio_ok"] is True


def test_heal_pt_endpoint_url_returns_canonical_not_raw(monkeypatch):
    """_heal_pt_endpoint_url must return canonical URL (with scheme), not the raw input."""
    # The fix in this PR changes `return url` to `return canonical`
    # When running_on_target=False and a bare host:port is given,
    # _canonical_endpoint adds http:// — the fix ensures we return that.
    _reload_bootstrap(monkeypatch, ORAMA_PLATFORM="mac")
    # On Mac, running_on_target=False for Windows endpoint — so it returns canonical
    result = alphaclaw_bootstrap._heal_pt_endpoint_url(
        "192.168.254.110:11434",
        running_on_target=False,
        port=11434,
    )
    # Should have http:// prefix (canonical), not bare host:port
    assert result.startswith("http://")
    assert "192.168.254.110:11434" in result


def test_heal_pt_endpoint_url_empty_returns_empty(monkeypatch):
    """Empty URL input must return empty string."""
    _reload_bootstrap(monkeypatch, ORAMA_PLATFORM="mac")
    result = alphaclaw_bootstrap._heal_pt_endpoint_url(
        "",
        running_on_target=False,
        port=11434,
    )
    assert result == ""


def test_heal_pt_endpoint_url_heals_to_localhost_when_on_target(monkeypatch):
    """When running on the target machine, LAN IP must be healed to localhost."""
    _reload_bootstrap(monkeypatch, ORAMA_PLATFORM="mac")
    result = alphaclaw_bootstrap._heal_pt_endpoint_url(
        "http://192.168.254.110:11434",
        running_on_target=True,
        port=11434,
    )
    assert result == "http://localhost:11434"


def test_allowed_endpoint_host_re_accepts_rfc1918():
    """_ALLOWED_ENDPOINT_HOST_RE must accept all valid RFC-1918 ranges."""
    regex = alphaclaw_bootstrap._ALLOWED_ENDPOINT_HOST_RE
    for host in (
        "localhost",
        "127.0.0.1",
        "10.0.0.1",
        "10.255.255.255",
        "172.16.0.1",
        "172.24.0.1",
        "172.31.255.255",
        "192.168.0.1",
        "192.168.254.110",
    ):
        assert regex.match(host), f"Expected {host!r} to match RFC-1918 regex"


def test_allowed_endpoint_host_re_rejects_public():
    """_ALLOWED_ENDPOINT_HOST_RE must reject public IPs and external hostnames."""
    regex = alphaclaw_bootstrap._ALLOWED_ENDPOINT_HOST_RE
    for host in (
        "8.8.8.8",
        "1.1.1.1",
        "172.15.0.1",
        "172.32.0.1",
        "192.169.0.1",
        "google.com",
        "evil.example.com",
        "169.254.0.1",  # link-local (not RFC-1918)
    ):
        assert not regex.match(host), f"Expected {host!r} to NOT match RFC-1918 regex"


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
