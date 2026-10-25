"""Exercise the requirements gate without installing into the developer environment."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.unit
@pytest.mark.parametrize("install_status", [0, 7])
def test_requirements_targets_pipless_reusable_environment(
    tmp_path: Path, install_status: int
) -> None:
    """A uv environment needs no pip wrapper, and failed installs fail the gate."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "scripts/ensure_requirements.sh", repo / "scripts")
    (repo / "requirements.txt").write_text("example\n")
    venv = tmp_path / "runtime with spaces"
    (venv / "bin").mkdir(parents=True)
    python = venv / "bin/python"
    python.write_text('#!/bin/sh\n[ "$1" = "-c" ] && exit 0\nexit 1\n')
    python.chmod(0o755)
    bins = tmp_path / "bin"
    bins.mkdir()
    uv = bins / "uv"
    uv.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$@" > "$UV_ARGS"\n'
        f"exit {install_status}\n"
    )
    uv.chmod(0o755)
    env = dict(os.environ, PT_VENV_DIR=str(venv), UV_ARGS=str(tmp_path / "args"))
    env["PATH"] = str(bins) + os.pathsep + env["PATH"]
    result = subprocess.run(
        ["/bin/bash", str(repo / "scripts/ensure_requirements.sh")],
        env=env, capture_output=True, text=True, timeout=15,
    )
    assert (result.returncode == 0) is (install_status == 0), result.stdout + result.stderr
    assert "--python\n" + str(python) in (tmp_path / "args").read_text()
    assert (venv / ".pt-requirements.stamp").exists() is (install_status == 0)
