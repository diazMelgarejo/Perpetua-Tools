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


def test_alphaclaw_install_dir_expands_tilde_from_env(monkeypatch):
    """Literal ~/.alphaclaw from dotenv must resolve under the user home, not PT cwd."""
    _reload_bootstrap(monkeypatch, ALPHACLAW_INSTALL_DIR="~/.alphaclaw")
    assert alphaclaw_bootstrap.ALPHACLAW_INSTALL_DIR.is_absolute()
    assert alphaclaw_bootstrap.ALPHACLAW_INSTALL_DIR == (
        Path.home() / ".alphaclaw"
    ).resolve()


def test_invalid_openclaw_gateway_port_does_not_crash_import(monkeypatch):
    """Malformed OPENCLAW_GATEWAY_PORT must fall back instead of crashing at import."""
    _reload_bootstrap(monkeypatch, OPENCLAW_GATEWAY_PORT="notaport")
    assert alphaclaw_bootstrap.OPENCLAW_GATEWAY_PORT == 18789


def test_invalid_openclaw_extra_ports_skipped(monkeypatch):
    """Invalid tokens in OPENCLAW_EXTRA_PORTS must be skipped, not crash import."""
    _reload_bootstrap(monkeypatch, OPENCLAW_EXTRA_PORTS="99999,abc,8081")
    assert 8081 in alphaclaw_bootstrap.OPENCLAW_CANDIDATE_PORTS
    assert 99999 not in alphaclaw_bootstrap.OPENCLAW_CANDIDATE_PORTS


def test_locality_resolve_endpoint_heals_stale_lan_on_mac(monkeypatch):
    """Explicit OLLAMA_MAC_ENDPOINT LAN IP on Mac must normalize to localhost."""
    _reload_bootstrap(
        monkeypatch,
        ORAMA_PLATFORM="mac",
        OLLAMA_MAC_ENDPOINT="http://127.0.9.3:11434",
    )
    assert alphaclaw_bootstrap.RUNNING_ON_MAC is True
    assert alphaclaw_bootstrap.OLLAMA_MAC == "http://localhost:11434"


def test_locality_resolve_endpoint_heals_stale_lan_on_windows(monkeypatch):
    """Explicit OLLAMA_WINDOWS_ENDPOINT LAN IP on Windows must normalize to localhost."""
    _reload_bootstrap(
        monkeypatch,
        ORAMA_PLATFORM="windows",
        OLLAMA_WINDOWS_ENDPOINT="http://127.0.9.2:11434",
    )
    assert alphaclaw_bootstrap.RUNNING_ON_WINDOWS is True
    assert alphaclaw_bootstrap.OLLAMA_WIN == "http://localhost:11434"


def test_locality_resolve_endpoint_heals_csv_lms_win_on_windows(monkeypatch):
    """Comma-separated LM_STUDIO_WIN_ENDPOINTS must not crash import on Windows."""
    _reload_bootstrap(
        monkeypatch,
        ORAMA_PLATFORM="windows",
        LM_STUDIO_WIN_ENDPOINTS=(
            "http://127.0.9.2:1234,http://127.0.9.1:1234"
        ),
    )
    assert alphaclaw_bootstrap.RUNNING_ON_WINDOWS is True
    assert alphaclaw_bootstrap.LMS_WIN == "http://localhost:1234"


def test_locality_resolve_endpoint_preserves_lan_when_remote(monkeypatch):
    """Mac bootstrap must keep Windows LAN endpoint when not running on Windows."""
    _reload_bootstrap(
        monkeypatch,
        ORAMA_PLATFORM="mac",
        OLLAMA_WINDOWS_ENDPOINT="http://127.0.9.2:11434",
    )
    assert alphaclaw_bootstrap.OLLAMA_WIN == "http://127.0.9.2:11434"


def test_locality_resolve_endpoint_rejects_link_local_metadata_target(monkeypatch):
    """Regression: _locality_resolve_endpoint's env-var/default chain (also
    reachable via MAC_IP/WIN_IP) had no SSRF host-classification at all --
    only a loopback-vs-not locality check. An operator (or a compromised
    startup script) setting OLLAMA_MAC_ENDPOINT=http://169.254.169.254:11434
    would have this node construct and later probe that endpoint with zero
    validation. Must fall back to the safe loopback default instead."""
    _reload_bootstrap(
        monkeypatch,
        ORAMA_PLATFORM="win",  # not running on mac -> remote LAN branch, no locality heal
        OLLAMA_MAC_ENDPOINT="http://169.254.169.254:11434",
    )
    assert "169.254.169.254" not in alphaclaw_bootstrap.OLLAMA_MAC
    assert alphaclaw_bootstrap.OLLAMA_MAC == "http://localhost:11434"


def test_locality_resolve_endpoint_still_accepts_lan_ip(monkeypatch):
    """Confirm the fix isn't over-broad -- a genuine RFC1918 LAN IP must
    still pass through unchanged."""
    _reload_bootstrap(
        monkeypatch,
        ORAMA_PLATFORM="win",
        OLLAMA_MAC_ENDPOINT="http://192.168.1.50:11434",
    )
    assert alphaclaw_bootstrap.OLLAMA_MAC == "http://192.168.1.50:11434"


def test_build_openclaw_config_ollama_mac_uses_healed_localhost(monkeypatch):
    """openclaw.json ollama-mac baseUrl must use healed localhost, not stale LAN env."""
    _reload_bootstrap(
        monkeypatch,
        ORAMA_PLATFORM="mac",
        OLLAMA_MAC_ENDPOINT="http://127.0.9.3:11434",
    )
    monkeypatch.setattr(alphaclaw_bootstrap, "_load_pt_state", lambda: {})
    config = alphaclaw_bootstrap.build_openclaw_config()
    ollama_mac = config["models"]["providers"]["ollama-mac"]
    assert ollama_mac["baseUrl"] == "http://localhost:11434"


def test_build_openclaw_config_heals_stale_win_lms_from_routing_json(monkeypatch):
    """Stale routing.json lmstudio_endpoint must not bypass Windows localhost heal."""
    _reload_bootstrap(monkeypatch, ORAMA_PLATFORM="windows")
    config = alphaclaw_bootstrap.build_openclaw_config(
        pt={"lmstudio_endpoint": "http://127.0.9.2:1234"}
    )
    win_lms = config["models"]["providers"]["lmstudio-win"]
    assert win_lms["baseUrl"] == "http://localhost:1234/v1"


def test_build_openclaw_config_heals_stale_mac_lms_from_routing_json(monkeypatch):
    """Stale routing.json mac_lmstudio_endpoint must not bypass Mac localhost heal."""
    _reload_bootstrap(monkeypatch, ORAMA_PLATFORM="mac")
    config = alphaclaw_bootstrap.build_openclaw_config(
        pt={"mac_lmstudio_endpoint": "http://127.0.9.3:1234"}
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
            "manager_endpoint": "http://127.0.9.3:11434",
            "manager_model": "glm-5.1:cloud",
            "mac_lmstudio_endpoint": "http://127.0.9.3:1234",
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
        "manager_endpoint": "http://127.0.9.3:11434",
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
        OLLAMA_WINDOWS_ENDPOINT="127.0.9.2:11434",
    )
    assert alphaclaw_bootstrap.OLLAMA_WIN == "http://127.0.9.2:11434"

# ---------------------------------------------------------------------------
# Additional tests for PR additions: _validate_pt_state, _validate_endpoint_host,
# _heal_pt_endpoint_url (canonical return fix), _load_pt_state edge cases
# ---------------------------------------------------------------------------


def test_validate_pt_state_accepts_empty_dict():
    """An empty routing.json dict must pass validation (all properties optional)."""
    assert alphaclaw_bootstrap._validate_pt_state({}) == {}


def test_validate_pt_state_accepts_all_rfc1918_ranges():
    """All RFC-1918 address ranges must be accepted by _validate_pt_state."""
    for host in ("10.0.0.1", "10.255.255.1", "172.16.0.1", "172.31.255.1",
                 "192.168.0.1", "192.168.254.1"):
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


def test_validate_pt_state_rejects_http_cloud_coder_endpoint():
    with pytest.raises(ValueError, match="must use https"):
        alphaclaw_bootstrap._validate_pt_state(
            {
                "coder_endpoint": "http://api.perplexity.ai",
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
        "127.0.9.3:11434",
        running_on_target=False,
        port=11434,
    )
    # Should have http:// prefix (canonical), not bare host:port
    assert result.startswith("http://")
    assert "127.0.9.3:11434" in result


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
        "http://127.0.9.3:11434",
        running_on_target=True,
        port=11434,
    )
    assert result == "http://localhost:11434"


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
def test_validate_endpoint_host_accepts_rfc1918():
    """_validate_endpoint_host must accept all valid RFC-1918 and loopback ranges."""
    for host in (
        "localhost",
        "127.0.0.1",
        "127.0.1.1",
        "127.0.9.3",
        "10.0.0.1",
        "10.255.255.1",
        "172.16.0.1",
        "172.31.255.1",
        "192.168.0.1",
        "192.168.254.1",
    ):
        alphaclaw_bootstrap._validate_endpoint_host(
            "manager_endpoint", f"http://{host}:11434"
        )


def test_validate_endpoint_host_rejects_public():
    """_validate_endpoint_host must reject public IPs and external hostnames."""
    for host in (
        "8.8.8.8",
        "1.1.1.1",
        "172.15.0.1",
        "172.32.0.1",
        "192.169.0.1",
        "169.254.0.1",
        "169.254.169.254",
        "google.com",
        "evil.example.com",
    ):
        with pytest.raises(ValueError):
            alphaclaw_bootstrap._validate_endpoint_host(
                "manager_endpoint", f"http://{host}:11434"
            )


def test_validate_endpoint_host_rejects_ipv4_mapped_link_local():
    """IPv4-mapped IPv6 must not bypass link-local rejection (cloud metadata SSRF)."""
    with pytest.raises(ValueError, match="link-local"):
        alphaclaw_bootstrap._validate_endpoint_host(
            "manager_endpoint", "http://[::ffff:169.254.169.254]"
        )
def test_validate_endpoint_host_rejects_missing_hostname():
    with pytest.raises(ValueError, match="missing a hostname"):
        alphaclaw_bootstrap._validate_endpoint_host("manager_endpoint", "http://")


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


def test_gateway_port_from_url_extracts_non_default_port():
    assert alphaclaw_bootstrap._gateway_port_from_url("http://127.0.0.1:19001") == 19001


@pytest.mark.asyncio
async def test_bootstrap_commandeer_sets_gateway_port(monkeypatch, tmp_path):
    async def _find_gateway():
        return "http://127.0.0.1:19001"

    monkeypatch.setattr(alphaclaw_bootstrap, "_find_any_gateway", _find_gateway)
    monkeypatch.setattr(alphaclaw_bootstrap, "_load_pt_state", lambda: {})
    monkeypatch.setattr(alphaclaw_bootstrap, "_write_openclaw_config", lambda _d, _f: {"gateway": {}})
    monkeypatch.setattr(alphaclaw_bootstrap, "build_role_routing", lambda _pt: {})
    monkeypatch.setattr(alphaclaw_bootstrap, "_ensure_agent_workspaces", lambda _d: None)
    monkeypatch.setattr(alphaclaw_bootstrap, "_ensure_autoresearch", lambda: None)
    config_dir = tmp_path / ".openclaw"
    config_dir.mkdir()
    monkeypatch.setattr(alphaclaw_bootstrap.Path, "home", lambda: tmp_path)

    result = await alphaclaw_bootstrap.bootstrap_alphaclaw()

    assert result["ok"] is True
    assert result["gateway_url"] == "http://127.0.0.1:19001"
    assert result["gateway_port"] == 19001


@pytest.mark.asyncio
async def test_bootstrap_tries_bare_openclaw_before_npm_check(monkeypatch, tmp_path):
    calls: list[str] = []

    async def _no_gateway():
        return None

    async def _openclaw_ok(*_args, **_kwargs):
        calls.append("openclaw")
        return {
            "ok": True,
            "gateway_ready": True,
            "gateway_url": "http://127.0.0.1:19001",
            "gateway_port": 19001,
        }

    def _no_npm(_name):
        if _name == "npm":
            calls.append("npm")
        return None

    monkeypatch.setattr(alphaclaw_bootstrap, "_find_any_gateway", _no_gateway)
    monkeypatch.setattr(alphaclaw_bootstrap, "_bootstrap_via_bare_openclaw", _openclaw_ok)
    monkeypatch.setattr(alphaclaw_bootstrap.shutil, "which", _no_npm)
    monkeypatch.setattr(alphaclaw_bootstrap.Path, "home", lambda: tmp_path)

    result = await alphaclaw_bootstrap.bootstrap_alphaclaw()

    assert result["gateway_port"] == 19001
    assert calls == ["openclaw"]
    assert "npm" not in calls


def test_build_openclaw_config_wires_perplexity_cloud_coder(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-test-key-12345")
    pt = {
        "coder_backend": "perplexity",
        "coder_endpoint": "https://api.perplexity.ai",
        "coder_model": "sonar-reasoning-pro",
    }
    config = alphaclaw_bootstrap.build_openclaw_config(pt)
    providers = config["models"]["providers"]
    assert "perplexity" in providers
    assert providers["perplexity"]["baseUrl"] == "https://api.perplexity.ai"
    assert providers["perplexity"]["apiKey"] == "pplx-test-key-12345"
    assert providers["perplexity"]["models"][0]["id"] == "sonar-reasoning-pro"

    # Verify coder agent primary model assignment
    coder_agent = next(a for a in config["agents"]["list"] if a["id"] == "coder")
    assert coder_agent["model"]["primary"] == "perplexity/sonar-reasoning-pro"


def test_build_openclaw_config_wires_anthropic_cloud_coder(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-67890")
    pt = {
        "coder_backend": "anthropic",
        "coder_endpoint": "https://api.anthropic.com",
        "coder_model": "claude-sonnet-5",
    }
    config = alphaclaw_bootstrap.build_openclaw_config(pt)
    providers = config["models"]["providers"]
    assert "anthropic" in providers
    assert providers["anthropic"]["baseUrl"] == "https://api.anthropic.com"
    assert providers["anthropic"]["apiKey"] == "sk-ant-test-key-67890"
    assert providers["anthropic"]["models"][0]["id"] == "claude-sonnet-5"

    coder_agent = next(a for a in config["agents"]["list"] if a["id"] == "coder")
    assert coder_agent["model"]["primary"] == "anthropic/claude-sonnet-5"


