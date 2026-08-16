from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import orchestrator.lan_discovery as lan_discovery


def _assert_timezone_aware_utc(timestamp: str) -> None:
    parsed = datetime.fromisoformat(timestamp)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_ai_endpoint_defaults_last_seen_to_timezone_aware_utc():
    endpoint = lan_discovery.AIEndpoint(
        host="localhost",
        port=11434,
        server_type="ollama",
        models=["qwen3:8b"],
    )

    _assert_timezone_aware_utc(endpoint.last_seen)


def test_save_discovery_state_writes_timezone_aware_timestamp(tmp_path, monkeypatch):
    state_file = tmp_path / ".state" / "lan_discovery.json"
    monkeypatch.setattr(lan_discovery, "DISCOVERY_STATE_FILE", state_file)

    discovery = lan_discovery.LANDiscovery(subnet="127.0.0.0/30", ports=[11434])
    discovery.discovered = [
        lan_discovery.AIEndpoint(
            host="localhost",
            port=11434,
            server_type="ollama",
            models=["qwen3:8b"],
        )
    ]

    discovery.save_discovery_state()

    state = json.loads(state_file.read_text())
    _assert_timezone_aware_utc(state["discovered_at"])


def test_probe_endpoint_requires_httpx(monkeypatch):
    monkeypatch.setattr(lan_discovery, "httpx", None)
    discovery = lan_discovery.LANDiscovery(subnet="127.0.0.0/30", ports=[11434])

    with pytest.raises(RuntimeError, match="httpx not installed"):
        asyncio.run(discovery._probe_endpoint("localhost", 11434))


def test_pick_windows_lmstudio_host_prefers_configured_win_over_mac_mirror():
    chosen = lan_discovery.pick_windows_lmstudio_host(
        ["192.0.2.1", "192.0.2.2"],
        local_ip="192.0.2.1",
        preferred_win_ip="192.0.2.2",
    )
    assert chosen == "192.0.2.2"


def test_pick_windows_lmstudio_host_skips_local_when_multiple_remotes():
    chosen = lan_discovery.pick_windows_lmstudio_host(
        ["192.0.2.1", "192.0.2.2"],
        local_ip="192.0.2.1",
        preferred_win_ip="",
    )
    assert chosen == "192.0.2.2"


def test_pick_windows_lmstudio_host_uses_win_ip_env(monkeypatch):
    monkeypatch.setenv("WIN_IP", "192.0.2.2")
    chosen = lan_discovery.pick_windows_lmstudio_host(
        ["192.0.2.1", "192.0.2.2"],
        local_ip="192.0.2.1",
        preferred_win_ip="",
    )
    assert chosen == "192.0.2.2"


def test_detect_local_subnet_logs_warning_on_fallback(monkeypatch, caplog):
    import socket

    monkeypatch.setattr(socket, "gethostbyname", lambda _hostname: (_ for _ in ()).throw(OSError("dns down")))
    caplog.set_level("WARNING", logger="orchestrator.lan_discovery")

    subnet = lan_discovery.LANDiscovery(subnet=None, ports=[11434]).subnet

    assert subnet == "127.0.1.0/24"
    assert "Failed to auto-detect local subnet" in caplog.text


def test_read_discovery_win_url_rejects_malformed_timestamp(tmp_path, monkeypatch, caplog):
    snapshot = tmp_path / "last_discovery.json"
    snapshot.write_text(
        json.dumps({
            "watcher_heartbeat": "not-a-date",
            "endpoints": {
                "win": {
                    "ip": "127.0.1.2",
                    "port": 1234,
                    "reachable": True,
                }
            },
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(lan_discovery, "_OPENCLAW_DISCOVERY", snapshot)
    caplog.set_level("DEBUG", logger="orchestrator.lan_discovery")

    assert lan_discovery._read_discovery_win_url() is None
    assert "invalid discovery snapshot timestamp" in caplog.text


def test_read_discovery_win_url_rejects_missing_timestamp(tmp_path, monkeypatch, caplog):
    snapshot = tmp_path / "last_discovery.json"
    snapshot.write_text(
        json.dumps({
            "endpoints": {
                "win": {
                    "ip": "127.0.1.2",
                    "port": 1234,
                    "reachable": True,
                }
            },
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(lan_discovery, "_OPENCLAW_DISCOVERY", snapshot)
    caplog.set_level("DEBUG", logger="orchestrator.lan_discovery")

    assert lan_discovery._read_discovery_win_url() is None
    assert "missing timestamp" in caplog.text


def test_read_discovery_win_url_rejects_malformed_endpoints_shape(tmp_path, monkeypatch):
    snapshot = tmp_path / "last_discovery.json"
    snapshot.write_text(
        json.dumps({
            "watcher_heartbeat": "2026-06-24T12:00:00+00:00",
            "endpoints": "not-a-dict",
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(lan_discovery, "_OPENCLAW_DISCOVERY", snapshot)

    assert lan_discovery._read_discovery_win_url() is None


def _write_win_discovery_snapshot(path, ip_value: str, port: int = 1234) -> None:
    path.write_text(
        json.dumps({
            "watcher_heartbeat": datetime.now(timezone.utc).isoformat(),
            "endpoints": {
                "win": {"ip": ip_value, "port": port, "reachable": True},
            },
        }),
        encoding="utf-8",
    )


def test_read_discovery_win_url_normalizes_scheme_contaminated_ip(tmp_path, monkeypatch):
    """Regression: the "ip" field is written by a separate discovery
    process; the read side validated port range and timestamp freshness
    but never checked whether "ip" itself was already scheme-prefixed
    before the final f"http://{ip}:{port}" construction. A contaminated
    value (e.g. "http://192.168.1.5") would produce a double-scheme URL.
    """
    snapshot = tmp_path / "last_discovery.json"
    _write_win_discovery_snapshot(snapshot, "http://192.168.1.5")
    monkeypatch.setattr(lan_discovery, "_OPENCLAW_DISCOVERY", snapshot)

    result = lan_discovery._read_discovery_win_url()

    assert result == "http://192.168.1.5:1234"
    assert "http://http://" not in (result or "")


def test_read_discovery_win_url_rejects_malformed_ip(tmp_path, monkeypatch):
    snapshot = tmp_path / "last_discovery.json"
    _write_win_discovery_snapshot(snapshot, "http://user:pass@192.168.1.5")
    monkeypatch.setattr(lan_discovery, "_OPENCLAW_DISCOVERY", snapshot)

    assert lan_discovery._read_discovery_win_url() is None

