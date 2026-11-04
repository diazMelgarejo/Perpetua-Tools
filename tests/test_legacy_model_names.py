"""Retired GLM model names in operator overrides map to the current registry names."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

from orchestrator.legacy_model_names import LEGACY_MODEL_NAMES, canonical_model_name
from orchestrator.tiered_pipeline import PipelineConfigError, TieredPipelineRunner

ROOT = Path(__file__).resolve().parents[1]
RECIPE = "classify_then_generate"


@pytest.mark.parametrize("retired, current", sorted(LEGACY_MODEL_NAMES.items()))
def test_retired_names_map_to_their_current_names(retired: str, current: str) -> None:
    """Each retired name maps forward, ignoring case and surrounding whitespace."""
    assert canonical_model_name(retired) == current
    assert canonical_model_name(f"  {retired.upper()} ") == current


@pytest.mark.parametrize("name", ["glm-5.3-flash", "glm-5.3-flash:cloud", "glm-4.7", "claude-sonnet-5-5", ""])
def test_current_unknown_and_empty_names_pass_through_unchanged(name: str) -> None:
    """Only the retired names are rewritten; anything else keeps its own validation."""
    assert canonical_model_name(name) == name


def test_a_mapped_name_logs_a_warning_naming_its_source(caplog: pytest.LogCaptureFixture) -> None:
    """The deprecation warning names the override that carried the retired name."""
    with caplog.at_level(logging.WARNING, logger="orchestrator.legacy_model_names"):
        canonical_model_name("glm-5.2", "PIPELINE_FAST_MODEL")
    assert any("PIPELINE_FAST_MODEL" in r.getMessage() and "glm-5.3-flash" in r.getMessage()
               for r in caplog.records)


@pytest.mark.parametrize("override", ["glm-5.2", "GLM-5.2", " glm-5.1 "])
def test_pipeline_override_with_a_retired_name_still_resolves(monkeypatch: pytest.MonkeyPatch, override: str) -> None:
    """An old PIPELINE_FAST_MODEL value no longer makes every recipe unavailable."""
    monkeypatch.delenv("PIPELINE_STRONG_MODEL", raising=False)
    monkeypatch.setenv("PIPELINE_FAST_MODEL", override)
    runner = TieredPipelineRunner()
    assert runner.recipe(RECIPE).stages[0].models[0] == "glm-5.3-flash"


def test_pipeline_override_with_the_retired_cloud_tag_resolves_to_the_cloud_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    """The retired Ollama cloud tag maps to the current cloud tag, not the BigModel name."""
    monkeypatch.delenv("PIPELINE_STRONG_MODEL", raising=False)
    monkeypatch.setenv("PIPELINE_FAST_MODEL", "glm-5.1:cloud")
    runner = TieredPipelineRunner()
    assert runner.recipe(RECIPE).stages[0].models[0] == "glm-5.3-flash:cloud"


def test_pipeline_override_with_an_unknown_name_still_fails_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """The mapping is not a catch-all: an unregistered name is still rejected by the registry check."""
    monkeypatch.delenv("PIPELINE_STRONG_MODEL", raising=False)
    monkeypatch.setenv("PIPELINE_FAST_MODEL", "glm-4.7")
    with pytest.raises(PipelineConfigError):
        TieredPipelineRunner()


def test_mac_manager_override_with_a_retired_name_resolves_at_import() -> None:
    """MAC_MANAGER_MODEL set to a retired tag is mapped when the launcher module loads."""
    env = {**os.environ, "MAC_MANAGER_MODEL": "glm-5.1:cloud",
           "PYTHONPATH": os.pathsep.join([str(ROOT), str(ROOT / "src")])}
    result = subprocess.run(
        [sys.executable, "-c", "from perpetua_tools import agent_launcher as a; print(a.MAC_MANAGER_MODEL)"],
        capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=120,
    )
    assert result.returncode == 0, result.stderr[-400:]
    assert result.stdout.strip().splitlines()[-1] == "glm-5.3-flash:cloud"
