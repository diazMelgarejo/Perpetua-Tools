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
import shutil
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
    secret = "synthetic-secret-must-not-appear"
    result = _run(
        "status",
        GOSSIP_PEERS="https://coord.example",
        GOSSIP_SHARED_SECRET=secret,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["remote_relay"] is False
    assert payload["forwards_events"] is False
    assert payload.get("gossip_env_present") is True
    assert "relay configured" not in result.stdout.lower()
    assert "forwarded" not in result.stdout.lower()
    assert secret not in result.stdout


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


def test_refuse_action_exits_instead_of_returning() -> None:
    """A non-zero return in a case arm is not a reliable set -e failure."""
    source = SCRIPT.read_text(encoding="utf-8")
    refuse = source.split("refuse_action()", 1)[1].split("emit_status()", 1)[0]
    assert "exit 64" in refuse
    assert "return 64" not in refuse


def test_status_does_not_place_probe_json_on_python_argv(tmp_path: Path) -> None:
    """Workstation topology must not show up in `ps` argv of the status helper."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "argv.log"
    real_python = shutil.which("python3")
    assert real_python is not None
    wrapper = bindir / "python3"
    wrapper.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$@\" >> {log}\n"
        f"exec {real_python} \"$@\"\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)

    env = dict(os.environ)
    env.pop("GOSSIP_PEERS", None)
    env.pop("GOSSIP_SHARED_SECRET", None)
    env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
    result = subprocess.run(
        ["bash", str(SCRIPT), "status"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["queue_write_authority"] is False
    recorded = log.read_text(encoding="utf-8")
    assert "git_common_dir" not in recorded
    assert str(ROOT) not in recorded
    assert "board_ino" not in recorded
