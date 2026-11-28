"""No test, in this process or a child of it, can load a model on the machine that runs the suite."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Assembled so the tracked-address gate sees no literal.
LOOPBACK_V4 = ".".join(("127", "0", "0", "1"))
LOOPBACK_V6 = ":" * 2 + "1"


@pytest.mark.parametrize("host", [LOOPBACK_V4, LOOPBACK_V6, "localhost"])
@pytest.mark.parametrize("port", [11434, 1234])
def test_connections_to_the_engine_ports_are_refused(host: str, port: int) -> None:
    with pytest.raises(OSError, match="tests may not reach a local model engine"):
        socket.create_connection((host, port), timeout=2)


def test_the_block_covers_every_test_directory() -> None:
    assert (ROOT / "conftest.py").is_file(), "the guard must sit above tests/ and src/tests/"


def test_a_child_process_cannot_use_a_real_engine_through_the_gate() -> None:
    code = (
        "from perpetua_tools import local_model_gate as g\n"
        "try:\n    g.require_local_slot('ollama', 'bge-m3', 'http://localhost:11434')\n"
        "except g.LocalModelRefused as exc:\n    print('refused:', exc)\n"
    )
    env = {**os.environ, "PYTHONPATH": os.pathsep.join((str(ROOT), str(ROOT / "src")))}

    done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True,
                          timeout=60, check=True)

    assert done.stdout.startswith("refused:") and "test" in done.stdout, done.stdout + done.stderr
