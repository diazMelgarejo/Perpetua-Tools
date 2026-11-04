"""beam:cloud is registered as an Ollama cloud free-tier (tier 4) model that never preempts a first choice."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from orchestrator.gate import load_frugality_tier_by_name

MODELS_YML = Path(__file__).resolve().parents[1] / "config" / "models.yml"
FREE_PROPRIETARY_TIER = 4
LAST_CURRENT_FIRST_CHOICE_PRIORITY = 10


def _models() -> dict[str, dict[str, Any]]:
    """Return the registry entries from config/models.yml keyed by model name."""
    data = yaml.safe_load(MODELS_YML.read_text(encoding="utf-8"))
    return {m["name"]: m for m in data["models"]}


def test_beam_cloud_is_an_ollama_cloud_free_proprietary_model() -> None:
    """beam:cloud sits on the Mac Ollama client at the same tier as glm-5.3-flash:cloud."""
    models = _models()
    assert "beam:cloud" in models
    beam, glm = models["beam:cloud"], models["glm-5.3-flash:cloud"]
    assert beam["backend"] == "ollama"
    assert beam["frugality_tier"] == FREE_PROPRIETARY_TIER
    for key in ("device", "port"):
        assert beam[key] == glm[key]
    assert beam["host"].startswith("${OLLAMA_HOST") and glm["host"].startswith("${OLLAMA_HOST")
    assert load_frugality_tier_by_name()["beam:cloud"] == FREE_PROPRIETARY_TIER


def test_beam_cloud_ranks_after_every_current_first_choice() -> None:
    """Priority above 10 keeps beam:cloud behind the existing first choices and local fallbacks."""
    models = _models()
    beam = models["beam:cloud"]
    assert beam["priority"] > LAST_CURRENT_FIRST_CHOICE_PRIORITY
    assert beam["priority"] > models["glm-5.3-flash:cloud"]["priority"]
    assert beam["priority"] > models["Qwen3.5-9B-MLX-4bit"]["priority"]
    assert beam["roles"], "beam:cloud must declare at least one routing role"
    assert set(beam["roles"]) <= set(models["glm-5.3-flash:cloud"]["roles"])
