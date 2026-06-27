#!/usr/bin/env python3
"""Positive allowlist for model IDs in config/models.yml and .env.example (T2-B)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def _rel(path: Path) -> str:
    """Return path relative to ROOT if possible, else the bare filename."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return path.name


# Only known-good IDs may appear in scanned config files.
# Add new IDs here when a model is adopted — never add partial strings.
ALLOWED_MODEL_IDS = {
    # Mac MLX / LM Studio
    "qwen3.5-9b-mlx",
    "qwen3.5-9b-mlx-4bit",
    # Mac/Linux Ollama
    "qwen3.5:9b-nvfp4",
    "bge-m3",
    # Windows GGUF / LM Studio
    "qwen3.5-27b-claude-4.6-opus-reasoning-distilled-v2",
    "gemma-4-26b-a4b-it-q4_k_m",
    "text-embedding-qwen3-embedding-8b-i1-gguf-q6-k",
    # Shared Ollama
    "qwen3.5:35b-a3b-q4_k_m",
    "qwen3-30b-autoresearch-critic",
    "glm-5.1:cloud",
    # Cloud / online
    "sonar-reasoning-pro",
    "claude-4-5-thinking",
    "claude-sonnet-4-5",
    "grok-4-1-thinking",
    # Remote / Nous / OpenRouter stack
    "qwen/qwen3-coder:free",
    "nvidia/nemotron-3-ultra:free",
    "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
    "openrouter/minimax/minimax-m2.5:free",
    "openrouter/deepseek/deepseek-v4-flash:free",
    "openrouter/openai/gpt-oss-120b:free",
    "openrouter/z-ai/glm-4.5-air:free",
    "openrouter/inclusionai/ling-2.6-flash:free",
}

_ALLOWED_LC = {m.lower() for m in ALLOWED_MODEL_IDS}

MODEL_YML = ROOT / "config" / "models.yml"
ENV_EXAMPLE = ROOT / ".env.example"

_NAME_RE = re.compile(r"^\s*-?\s*name:\s*[\"']?([^\"'\n#]+)", re.MULTILINE)
_API_MODEL_RE = re.compile(r"^\s*api_model:\s*[\"']?([^\"'\n#]+)", re.MULTILINE)
_ENV_MODEL_RE = re.compile(
    r"^(?:[A-Z][A-Z0-9_]*MODEL[A-Z0-9_]*)=([^\s#]+)",
    re.MULTILINE,
)


def _normalize(model_id: str) -> str:
    return model_id.strip().strip('"').strip("'").lower()


def _check_model_id(model_id: str, source: str, line_hint: str) -> str | None:
    norm = _normalize(model_id)
    if not norm or norm.startswith("${"):
        return None
    if norm in _ALLOWED_LC:
        return None
    return f"{source}: disallowed model ID {model_id!r} ({line_hint}) — add to ALLOWED_MODEL_IDS"


def scan_models_yml() -> list[str]:
    if not MODEL_YML.is_file():
        return [f"missing required file: {_rel(MODEL_YML)}"]
    text = MODEL_YML.read_text(encoding="utf-8")
    violations: list[str] = []
    for match in _NAME_RE.finditer(text):
        err = _check_model_id(match.group(1), str(_rel(MODEL_YML)), "name:")
        if err:
            violations.append(err)
    for match in _API_MODEL_RE.finditer(text):
        err = _check_model_id(match.group(1), str(_rel(MODEL_YML)), "api_model:")
        if err:
            violations.append(err)
    return violations


def scan_env_example() -> list[str]:
    if not ENV_EXAMPLE.is_file():
        return [f"missing required file: {_rel(ENV_EXAMPLE)}"]
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    violations: list[str] = []
    for match in _ENV_MODEL_RE.finditer(text):
        err = _check_model_id(match.group(1), str(_rel(ENV_EXAMPLE)), match.group(0).split("=")[0])
        if err:
            violations.append(err)
    return violations


def main() -> int:
    violations = scan_models_yml() + scan_env_example()
    if violations:
        print("\n".join(violations), file=sys.stderr)
        return 1
    print("OK: all model IDs in config/models.yml and .env.example are allowlisted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
