"""A live subnet sweep for the Windows host is slow, so one result serves a short window; fresher sources still win."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import orchestrator.lan_discovery as lan
import orchestrator.model_registry as model_registry
from packages.net_utils import network_autoconfig

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def sweeps(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[str]:
    """No override, snapshot or env endpoint, and a fake scanner that records each sweep instead of doing one."""
    done: list[str] = []

    class FakeScanner:
        preferred_ips: dict[str, str] = {}

        def get_working_local_ip(self) -> str:
            return "192.0.2.10"

        def discover_lan_agents(self, **kwargs: object) -> dict[str, list[str]]:
            done.append(str(kwargs.get("subnet_prefix")))
            return {"lmstudio": []}

    for name in ("LAN_GPU_IP_OVERRIDE", "LM_STUDIO_WIN_ENDPOINTS", "PT_DISABLE_LIVE_MODEL_PROBES"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(network_autoconfig, "NetworkAutoConfig", FakeScanner)
    monkeypatch.setattr(lan, "_OPENCLAW_DISCOVERY", tmp_path / "last_discovery.json")
    monkeypatch.setattr(lan, "_sync_win_endpoint_env", lambda url: None)
    monkeypatch.setattr(lan, "_probe_cache", None, raising=False)
    return done


def test_one_sweep_serves_repeated_calls_within_the_window(sweeps: list[str]) -> None:
    results = {lan.detect_active_tilting_ip() for _ in range(3)}

    assert len(results) == 1
    assert len(sweeps) == 1


def test_the_sweep_runs_again_once_the_window_has_passed(sweeps: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [1000.0]
    monkeypatch.setattr(lan.time, "monotonic", lambda: clock[0])
    lan.detect_active_tilting_ip()
    clock[0] += lan._PROBE_TTL_S + 1

    lan.detect_active_tilting_ip()

    assert len(sweeps) == 2


def test_an_override_or_a_fresh_snapshot_wins_over_a_cached_sweep(
    sweeps: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    swept = lan.detect_active_tilting_ip()
    lan._OPENCLAW_DISCOVERY.write_text(json.dumps({
        "watcher_heartbeat": datetime.now(timezone.utc).isoformat(),
        "endpoints": {"win": {"ip": "192.0.2.50", "port": 1234, "reachable": True}},
    }), encoding="utf-8")
    from_snapshot = lan.detect_active_tilting_ip()
    monkeypatch.setenv("LAN_GPU_IP_OVERRIDE", "192.0.2.60")

    assert from_snapshot == "http://192.0.2.50:1234" != swept
    assert lan.detect_active_tilting_ip() == "http://192.0.2.60"
    assert len(sweeps) == 1


def test_routing_a_task_sweeps_the_subnet_at_most_once(sweeps: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ORAMASYS_OFFLINE", raising=False)
    monkeypatch.setattr(model_registry, "_endpoint_online", lambda *args, **kwargs: False)

    model_registry.ModelRegistry(config_dir=str(ROOT / "config")).route_task("default")

    assert len(sweeps) == 1
