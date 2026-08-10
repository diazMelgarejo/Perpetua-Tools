"""Governed Tier-5 pipeline execution for the PT frugality stack.

This module deliberately does not choose a frugality tier. The canonical policy
owner remains orchestrator.gate / orchestrator.frugality_router. A pipeline may
execute only after that gate permits tier 5.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

import yaml

from orchestrator.gate import gate_permits

PIPELINE_FLAG = "PIPELINE_TIERED_ENABLED"
OPENROUTER_KEY_ENV = "OPENROUTER_API_KEY"
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "pipelines.yml"
DEFAULT_TIMEOUT_SECONDS = 120.0

Dispatcher = Callable[[str, str, int], Awaitable[str]]


class PipelineError(RuntimeError):
    """Base error for governed Tier-5 pipeline execution."""


class PipelineDisabledError(PipelineError):
    """Raised when the explicit feature flag is not enabled."""


class PipelineConfigError(PipelineError):
    """Raised when pipeline configuration is invalid or incomplete."""


class PipelinePolicyError(PipelineError):
    """Raised when the canonical frugality gate refuses Tier 5."""


class PipelineExecutionError(PipelineError):
    """Raised when a configured stage cannot complete."""


@dataclass(frozen=True)
class PipelineStage:
    name: str
    model_alias: str
    max_tokens: int
    input_from: Optional[str] = None


@dataclass(frozen=True)
class PipelineResult:
    recipe: str
    output: str
    stage_outputs: Dict[str, str]


def tiered_pipeline_enabled() -> bool:
    """Feature is opt-in. Key presence never enables paid execution."""
    return os.getenv(PIPELINE_FLAG, "0") == "1"


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise PipelineConfigError("cannot read pipeline config: %s" % path) from exc
    except yaml.YAMLError as exc:
        raise PipelineConfigError("invalid pipeline YAML: %s" % path) from exc
    if not isinstance(raw, dict):
        raise PipelineConfigError("pipeline config root must be a mapping")
    return raw


def _resolve_model(models: Dict[str, Any], alias: str) -> str:
    spec = models.get(alias)
    if not isinstance(spec, dict):
        raise PipelineConfigError("unknown model alias: %s" % alias)
    env_name = spec.get("env")
    literal = spec.get("id")
    if env_name:
        value = os.getenv(str(env_name), "").strip()
        if not value:
            raise PipelineConfigError(
                "model alias %s requires environment variable %s" % (alias, env_name)
            )
        return value
    if literal:
        return str(literal)
    raise PipelineConfigError("model alias %s requires env or id" % alias)


def _parse_recipe(raw: Dict[str, Any], recipe: str) -> tuple[List[PipelineStage], Dict[str, Any]]:
    models = raw.get("models")
    recipes = raw.get("recipes")
    if not isinstance(models, dict) or not isinstance(recipes, dict):
        raise PipelineConfigError("config requires models and recipes mappings")
    rows = recipes.get(recipe)
    if not isinstance(rows, list) or not rows:
        raise PipelineConfigError("unknown or empty recipe: %s" % recipe)

    stages: List[PipelineStage] = []
    seen = set()
    total_tokens = 0
    for row in rows:
        if not isinstance(row, dict):
            raise PipelineConfigError("recipe stages must be mappings")
        name = str(row.get("name", "")).strip()
        model_alias = str(row.get("model", "")).strip()
        try:
            max_tokens = int(row.get("max_tokens", 0))
        except (TypeError, ValueError) as exc:
            raise PipelineConfigError("stage max_tokens must be an integer") from exc
        input_from = row.get("input_from")
        input_from = str(input_from).strip() if input_from else None
        if not name or name in seen:
            raise PipelineConfigError("stage names must be unique and non-empty")
        if not model_alias or model_alias not in models:
            raise PipelineConfigError("stage %s references unknown model alias" % name)
        if max_tokens <= 0:
            raise PipelineConfigError("stage %s max_tokens must be positive" % name)
        if input_from and input_from not in seen:
            raise PipelineConfigError(
                "stage %s input_from must reference an earlier stage" % name
            )
        seen.add(name)
        total_tokens += max_tokens
        stages.append(PipelineStage(name, model_alias, max_tokens, input_from))

    limits = raw.get("limits") or {}
    if not isinstance(limits, dict):
        raise PipelineConfigError("limits must be a mapping")
    max_total = int(limits.get("max_total_tokens", 8192))
    if total_tokens > max_total:
        raise PipelineConfigError(
            "recipe %s token budget %d exceeds max_total_tokens %d"
            % (recipe, total_tokens, max_total)
        )
    return stages, models


async def _dispatch_openrouter(model: str, prompt: str, max_tokens: int) -> str:
    """Default paid dispatcher. Secrets stay in environment, never config."""
    key = os.getenv(OPENROUTER_KEY_ENV, "").strip()
    if not key:
        raise PipelineExecutionError("OPENROUTER_API_KEY is not configured")

    try:
        import aiohttp
    except ImportError as exc:  # pragma: no cover - packaging/environment guard
        raise PipelineExecutionError("aiohttp is required for OpenRouter execution") from exc

    headers = {
        "Authorization": "Bearer %s" % key,
        "Content-Type": "application/json",
    }
    referer = os.getenv("OPENROUTER_HTTP_REFERER", "").strip()
    title = os.getenv("OPENROUTER_APP_TITLE", "Perpetua-Tools").strip()
    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-Title"] = title

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }
    timeout = float(os.getenv("PIPELINE_TIERED_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS)))
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
            ) as response:
                if response.status >= 400:
                    detail = (await response.text())[:500]
                    raise PipelineExecutionError(
                        "OpenRouter stage failed HTTP %d: %s" % (response.status, detail)
                    )
                data = await response.json()
    except PipelineExecutionError:
        raise
    except Exception as exc:
        raise PipelineExecutionError("OpenRouter request failed: %s" % exc) from exc

    try:
        output = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise PipelineExecutionError("OpenRouter response missing message content") from exc
    if not isinstance(output, str) or not output:
        raise PipelineExecutionError("OpenRouter returned empty message content")
    return output


def _emit_trace(
    trace_path: Optional[Path], *, recipe: str, stage: PipelineStage, model: str, status: str
) -> None:
    if trace_path is None:
        return
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "timestamp": time.time(),
        "name": "tiered_pipeline.stage",
        "attributes": {
            "ot.tool.tier": 5,
            "pipeline.recipe": recipe,
            "pipeline.stage": stage.name,
            "pipeline.model_alias": stage.model_alias,
            "pipeline.model": model,
            "pipeline.max_tokens": stage.max_tokens,
            "status": status,
        },
    }
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, separators=(",", ":")) + "\n")


class TieredPipelineRunner:
    """Execute an explicitly enabled recipe after the canonical Tier-5 gate."""

    def __init__(
        self,
        config_path: Optional[Path] = None,
        dispatcher: Optional[Dispatcher] = None,
        trace_path: Optional[Path] = None,
    ) -> None:
        self.config_path = config_path or DEFAULT_CONFIG
        self.dispatcher = dispatcher or _dispatch_openrouter
        self.trace_path = trace_path

    async def run(
        self,
        recipe: str,
        prompt: str,
        *,
        task_type: str = "reasoning",
        privacy_critical: bool = False,
    ) -> PipelineResult:
        if not tiered_pipeline_enabled():
            raise PipelineDisabledError(
                "%s=1 is required for Tier-5 pipeline execution" % PIPELINE_FLAG
            )
        if not prompt:
            raise PipelineConfigError("pipeline prompt must be non-empty")

        allowed, denied_reason = gate_permits(
            5,
            task_type=task_type,
            privacy_critical=privacy_critical,
        )
        if not allowed:
            raise PipelinePolicyError(denied_reason or "Tier 5 denied by frugality gate")

        raw = _load_yaml(self.config_path)
        stages, models = _parse_recipe(raw, recipe)
        outputs: Dict[str, str] = {}

        for stage in stages:
            stage_input = outputs[stage.input_from] if stage.input_from else prompt
            model = _resolve_model(models, stage.model_alias)
            _emit_trace(
                self.trace_path,
                recipe=recipe,
                stage=stage,
                model=model,
                status="started",
            )
            try:
                output = await self.dispatcher(model, stage_input, stage.max_tokens)
            except Exception:
                _emit_trace(
                    self.trace_path,
                    recipe=recipe,
                    stage=stage,
                    model=model,
                    status="failed",
                )
                raise
            outputs[stage.name] = output
            _emit_trace(
                self.trace_path,
                recipe=recipe,
                stage=stage,
                model=model,
                status="completed",
            )

        return PipelineResult(recipe=recipe, output=outputs[stages[-1].name], stage_outputs=outputs)
