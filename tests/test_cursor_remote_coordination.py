"""I2 truthful status helper — no fake event-relay cosmetics.

Contract (plan I2 + Addendum D):
- status is always safe and non-fatal
- never claim a remote relay is configured or that pulse/log are forwarded
- GOSSIP_PEERS / GOSSIP_SHARED_SECRET must not enable misleading cosmetics
- pulse/log are refused (status-only helper); queue ops remain unsupported
- status should surface advisory topology_probe fields when the probe exists
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "cursor" / "remote-coordination.sh"


def _run(*args: str, **updates: str | None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("GOSSIP_PEERS", None)
    env.pop("GOSSIP_SHARED_SECRET", None)
    for key, value in updates.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_status_exits_zero_and_prints_truthful_json() -> None:
    result = _run("status")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["remote_relay"] is False
    assert payload["forwards_events"] is False
    assert payload["queue_write_authority"] is False
    assert payload["helper"] == "status-only"
    assert "relay configured" not in result.stdout.lower()
    assert "forwarded" not in result.stdout.lower()


def test_status_ignores_gossip_env_cosmetics() -> None:
    """Setting relay env vars must not make status claim a live relay."""
    result = _run(
        "status",
        GOSSIP_PEERS="https://coord.example",
        GOSSIP_SHARED_SECRET="test-secret",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["remote_relay"] is False
    assert payload["forwards_events"] is False
    assert payload.get("gossip_env_present") is True
    assert "relay configured" not in result.stdout.lower()
    assert "forwarded" not in result.stdout.lower()


def test_status_embeds_advisory_topology_probe() -> None:
    result = _run("status")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    topo = payload["topology"]
    assert "mode" in topo
    assert topo["queue_write_authority"] is False
    assert "topology_match" in topo


def test_status_redacts_local_topology_paths() -> None:
    """A remote-facing status envelope must not disclose workstation topology."""
    result = _run("status")

    assert result.returncode == 0, result.stderr
    topology = json.loads(result.stdout)["topology"]
    assert "cwd" not in topology
    assert "toplevel" not in topology
    assert "git_common_dir" not in topology


def test_pulse_is_refused_even_with_https_gossip_env() -> None:
    result = _run(
        "pulse",
        "cursor-cloud-test",
        GOSSIP_PEERS="https://coord.example",
        GOSSIP_SHARED_SECRET="test-secret",
    )

    assert result.returncode == 64
    assert "status-only" in result.stderr.lower() or "not implemented" in result.stderr.lower()
    assert "forward" not in result.stdout.lower()


def test_log_is_refused() -> None:
    result = _run("log", "cursor-cloud-test", "hello")

    assert result.returncode == 64
    assert "status-only" in result.stderr.lower() or "not implemented" in result.stderr.lower()


def test_queue_operations_remain_unsupported() -> None:
    result = _run("queue")

    assert result.returncode == 64
    assert "unsupported" in result.stderr.lower()


def test_bootstrap_calls_status_only_never_pulse() -> None:
    bootstrap = (ROOT / "scripts" / "cursor" / "cloud-bootstrap.sh").read_text(
        encoding="utf-8"
    )

    assert "remote-coordination.sh status" in bootstrap
    assert "remote-coordination.sh pulse" not in bootstrap


def test_cursor_rule_forbids_fake_relay_and_queue_claims() -> None:
    rule = (ROOT / ".cursor" / "rules" / "remote-coordination.mdc").read_text(
        encoding="utf-8"
    )

    assert "status-only" in rule.lower() or "truthful" in rule.lower()
    assert "queue claim" in rule.lower() or "queue claim" in rule
    assert "does not forward" in rule.lower() or "no remote event relay" in rule.lower()
    assert "GOSSIP_PEERS" in rule
    # Must not instruct agents that env vars enable a live relay
    assert "forwarded" not in rule.lower() or "not forwarded" in rule.lower()
