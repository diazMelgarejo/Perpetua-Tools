"""install-openclaw-runtime.sh reproduces the 2026-11-25 OpenClaw/AlphaClaw baseline: check, plan, apply."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install-openclaw-runtime.sh"


def _run(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "NVM_DIR": str(home / ".nvm")}
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env)


def test_the_script_parses_under_the_macos_system_bash() -> None:
    assert subprocess.run(["/bin/bash", "-n", str(SCRIPT)], capture_output=True).returncode == 0


def test_check_is_the_default_read_only_and_reports_drift_on_an_empty_home(tmp_path: Path) -> None:
    done = _run(tmp_path)
    assert done.returncode == 1 and "DRIFT" in done.stdout
    for created in (".nvm", ".alphaclaw", ".local", ".openclaw"):
        assert not (tmp_path / created).exists(), f"--check must not create {created}"


def test_plan_prints_every_step_in_order_and_executes_nothing(tmp_path: Path) -> None:
    done = _run(tmp_path, "--plan", "--node", "24.22.3", "--openclaw", "2026.10.6", "--migrate-globals-from", "24.14.1",
                "--alphaclaw-tarball", "/pack/alphaclaw-0.9.39-9.tgz", "--fresh-gateway", "--accept-risk")
    assert done.returncode == 0, done.stderr
    out = done.stdout
    expected = ["nvm install 24.22.3 --reinstall-packages-from=24.14.1", "nvm alias default 24.22.3",
                "npm install -g openclaw@2026.10.6", "cp /pack/alphaclaw-0.9.39-9.tgz", "npm install --prefix",
                "npm uninstall --prefix", "@chrysb/alphaclaw", "launchctl bootout", ".openclaw.pre-clean-",
                "openclaw onboard --non-interactive --accept-risk --flow quickstart --mode local",
                "--gateway-bind loopback", "--gateway-auth token", "--auth-choice skip", "--skip-channels"]
    positions = [out.index(item) for item in expected]
    assert positions == sorted(positions), "steps must run in dependency order"
    assert out.rindex("perpetua_tools.openclaw_runtime --apply") > out.index("openclaw onboard"), \
        "onboarding rewrites the service file, so the link is applied again after it"
    for created in (".nvm", ".alphaclaw", ".local", ".openclaw", ".openclaw.pre-clean-"):
        assert not any(tmp_path.glob(f"{created}*")), f"--plan must not create {created}"


def test_the_destructive_fresh_gateway_step_refuses_without_an_explicit_accept_risk(tmp_path: Path) -> None:
    done = _run(tmp_path, "--plan", "--fresh-gateway")
    assert done.returncode == 2 and "--accept-risk" in done.stderr


def test_the_fresh_gateway_step_is_never_part_of_a_plain_apply_or_plan(tmp_path: Path) -> None:
    done = _run(tmp_path, "--plan")
    assert "launchctl bootout" not in done.stdout and "onboard" not in done.stdout


@pytest.mark.parametrize("flag", ["--bogus", "--node"])
def test_bad_arguments_exit_2_with_usage(tmp_path: Path, flag: str) -> None:
    assert _run(tmp_path, flag).returncode == 2


def test_fresh_gateway_defers_link_until_after_onboarding(tmp_path: Path) -> None:
    done = _run(tmp_path, "--plan", "--fresh-gateway", "--accept-risk")
    assert done.returncode == 0
    out = done.stdout
    # openclaw_runtime --apply appears only once, after onboarding
    assert out.count("perpetua_tools.openclaw_runtime --apply") == 1
    assert out.index("perpetua_tools.openclaw_runtime --apply") > out.index("openclaw onboard")


def test_aside_collision_preflight_fails_before_bootout(tmp_path: Path) -> None:
    import datetime
    today = datetime.date.today().strftime("%Y%m%d")
    aside = tmp_path / f".openclaw.pre-clean-{today}"
    aside.mkdir(parents=True)
    done = _run(tmp_path, "--apply", "--fresh-gateway", "--accept-risk")
    assert done.returncode == 2
    assert "already exists; move it aside first" in done.stderr


def test_tarball_pin_without_explicit_openclaw(tmp_path: Path) -> None:
    import json, tarfile, io
    tar_path = tmp_path / "alphaclaw-test.tgz"
    pkg_json = json.dumps({"name": "@diazmelgarejo/alphaclaw", "version": "0.9.40", "dependencies": {"openclaw": "2026.11.1"}}).encode()
    with tarfile.open(tar_path, "w:gz") as tf:
        ti = tarfile.TarInfo("package/package.json")
        ti.size = len(pkg_json)
        tf.addfile(ti, io.BytesIO(pkg_json))
    done = _run(tmp_path, "--plan", "--alphaclaw-tarball", str(tar_path))
    assert done.returncode == 0
    assert "npm install -g openclaw@2026.11.1" in done.stdout


def test_explicit_openclaw_mismatching_tarball_pin_is_rejected_before_mutate(tmp_path: Path) -> None:
    import json, tarfile, io
    tar_path = tmp_path / "alphaclaw-test.tgz"
    pkg_json = json.dumps({"name": "@diazmelgarejo/alphaclaw", "version": "0.9.40", "dependencies": {"openclaw": "2026.11.1"}}).encode()
    with tarfile.open(tar_path, "w:gz") as tf:
        ti = tarfile.TarInfo("package/package.json")
        ti.size = len(pkg_json)
        tf.addfile(ti, io.BytesIO(pkg_json))
    done = _run(tmp_path, "--plan", "--openclaw", "2026.10.6", "--alphaclaw-tarball", str(tar_path))
    assert done.returncode == 2
    assert "mismatches AlphaClaw pin 2026.11.1" in done.stderr
    assert "nvm install" not in done.stdout


def test_explicit_openclaw_matching_tarball_pin_is_allowed(tmp_path: Path) -> None:
    import json, tarfile, io
    tar_path = tmp_path / "alphaclaw-test.tgz"
    pkg_json = json.dumps({"name": "@diazmelgarejo/alphaclaw", "version": "0.9.40", "dependencies": {"openclaw": "2026.11.1"}}).encode()
    with tarfile.open(tar_path, "w:gz") as tf:
        ti = tarfile.TarInfo("package/package.json")
        ti.size = len(pkg_json)
        tf.addfile(ti, io.BytesIO(pkg_json))
    done = _run(tmp_path, "--plan", "--openclaw", "2026.11.1", "--alphaclaw-tarball", str(tar_path))
    assert done.returncode == 0
    assert "npm install -g openclaw@2026.11.1" in done.stdout
