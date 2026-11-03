"""Mac Ollama model checks in scripts/install-claude-desktop-llm.sh.

The functions are read from the real script, so these tests cannot drift from it. They run under
the system bash (3.2 on macOS) and any newer bash on PATH.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "install-claude-desktop-llm.sh"
FUNCTIONS = ("mac_required_ollama_models", "ollama_model_names", "ollama_has_model")
BASHES = sorted({b for b in ("/bin/bash", shutil.which("bash")) if b and os.path.exists(b)})

TAGS = (
    '{"models":[{"name":"qwen3.5:9b-mlx-bf16","model":"qwen3.5:9b-mlx-bf16"},'
    '{"name":"bge-m3:latest","model":"bge-m3:latest"},{"name":"Gemma-4-E4B-IT"}]}'
)


def _functions() -> str:
    text = SCRIPT.read_text(encoding="utf-8")
    default = re.search(r"^DEFAULT_MAC_REQUIRED_OLLAMA_MODELS=.*$", text, re.M).group(0)
    bodies = [re.search(rf"^{name}\(\) \{{\n.*?^\}}\n", text, re.M | re.S).group(0) for name in FUNCTIONS]
    return "set -euo pipefail\n" + default + "\n" + "".join(bodies)


def _run(bash: str, call: str, env_value: str | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "MAC_REQUIRED_OLLAMA_MODELS"}
    if env_value is not None:
        env["MAC_REQUIRED_OLLAMA_MODELS"] = env_value
    return subprocess.run(
        [bash, "-c", _functions() + call], env=env, capture_output=True, text=True, timeout=10
    )


@pytest.mark.parametrize("bash", BASHES)
def test_required_models_default_is_mlx_and_bge(bash):
    assert _run(bash, "mac_required_ollama_models").stdout.split() == ["qwen3.5:9b-mlx", "bge-m3"]


@pytest.mark.parametrize("bash", BASHES)
def test_required_models_follow_the_configured_set(bash):
    out = _run(bash, "mac_required_ollama_models", " qwen3.5:9b-mlx-bf16 , bge-m3 ,").stdout.split()
    assert out == ["qwen3.5:9b-mlx-bf16", "bge-m3"]


@pytest.mark.parametrize("bash", BASHES)
def test_empty_configured_set_requires_nothing(bash):
    result = _run(bash, "mac_required_ollama_models", "")
    assert result.returncode == 0 and result.stdout == ""


@pytest.mark.parametrize("bash", BASHES)
@pytest.mark.parametrize(
    ("required", "present"),
    [
        ("qwen3.5:9b-mlx", False),  # only the separate bf16 model is served
        ("qwen3.5:9b-mlx-bf16", True),
        ("bge-m3", True),  # served as bge-m3:latest
        ("gemma-4-e4b-it", True),  # case-insensitive
        ("qwen3.5", True),  # a bare name accepts any tag, as the launcher does
        ("qwen3", False),
    ],
)
def test_model_check_matches_complete_names(bash, required, present):
    call = f"names=\"$(ollama_model_names '{TAGS}')\"; ollama_has_model \"$names\" '{required}'"
    assert (_run(bash, call).returncode == 0) is present


@pytest.mark.parametrize("bash", BASHES)
def test_no_served_models_matches_nothing(bash):
    call = "names=\"$(ollama_model_names '{\"models\":[]}')\"; ollama_has_model \"$names\" bge-m3"
    assert _run(bash, call).returncode == 1
