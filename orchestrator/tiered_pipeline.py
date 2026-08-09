"""Governed Tier-5 pipeline execution for Perpetua-Tools.

Policy selection remains owned by ``orchestrator.gate`` / ``frugality_router``.
This module executes only a route already classified as Tier 5, and only when:

1. the canonical gate permits Tier 5 for the request;
2. ``PIPELINE_TIERED_ENABLED=1``;
3. a live, purpose-bound human approval record covers the exact recipe; and
4. the configured recipe fits inside both repository and approval budgets.

No prompt/output content is persisted to telemetry. Provider credentials are read
from the environment at execution time and never serialized into config/results.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, Sequence

import httpx
import yaml

from orchestrator.gate import consult_gate


class PipelinePolicyError(RuntimeError):
    """Raised when Tier-5 execution violates a local governance contract."""


class PipelineConfigError(ValueError):
    """Raised when ``config/pipelines.yml`` violates the strict schema."""


@dataclass(frozen=True)
class PipelineApproval:
    """Human-bound authorization for one governed paid-pipeline purpose."""

    trace_id: str
    human_ref: str
    purpose: str
    recipe_id: str
    allowed_route_tier: int
    max_tokens: int
    max_cost_usd: float
    expires_at: datetime
    provider_scope: tuple[str, ...] = ("openrouter",)


@dataclass(frozen=True)
class StageResult:
    name: str
    model_class: str
    model: str
    output: str
    total_tokens: int
    cost_usd: float


@dataclass(frozen=True)
class PipelineResult:
    trace_id: str
    recipe_id: str
    output: str
    total_tokens: int
    cost_usd: float
    stages: tuple[StageResult, ...]


StageExecutor = Callable[[str, str, int, float], Awaitable[tuple[str, int, float]]]

_ALLOWED_TOP = {"schema_version", "limits", "models", "recipes"}
_ALLOWED_LIMITS = {
    "max_pipeline_stages",
    "max_total_tokens",
    "max_total_cost_usd",
    "request_timeout_seconds",
    "max_retries",
}
_ALLOWED_MODEL = {"provider", "model"}
_ALLOWED_STAGE = {"name", "model_class", "max_tokens", "inputs", "instruction"}


def pipelines_enabled() -> bool:
    return os.getenv("PIPELINE_TIERED_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _require_keys(obj: Mapping[str, Any], required: set[str], where: str) -> None:
    missing = sorted(required - set(obj))
    if missing:
        raise PipelineConfigError(f"{where} missing required keys: {', '.join(missing)}")


def _reject_unknown(obj: Mapping[str, Any], allowed: set[str], where: str) -> None:
    unknown = sorted(set(obj) - allowed)
    if unknown:
        raise PipelineConfigError(f"{where} has unknown keys: {', '.join(unknown)}")


def load_pipeline_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load and strictly validate the Tier-5 configuration."""
    config_path = (
        Path(path)
        if path is not None
        else Path(__file__).resolve().parents[1] / "config" / "pipelines.yml"
    )
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise PipelineConfigError("pipeline config must be a mapping")
    _reject_unknown(raw, _ALLOWED_TOP, "root")
    _require_keys(raw, _ALLOWED_TOP, "root")
    if raw["schema_version"] != 1:
        raise PipelineConfigError("unsupported pipeline schema_version")

    limits = raw["limits"]
    models = raw["models"]
    recipes = raw["recipes"]
    if not isinstance(limits, dict) or not isinstance(models, dict) or not isinstance(recipes, dict):
        raise PipelineConfigError("limits, models, and recipes must be mappings")
    _reject_unknown(limits, _ALLOWED_LIMITS, "limits")
    _require_keys(limits, _ALLOWED_LIMITS, "limits")

    for key in ("max_pipeline_stages", "max_total_tokens", "request_timeout_seconds", "max_retries"):
        if not isinstance(limits[key], int) or limits[key] < 0:
            raise PipelineConfigError(f"limits.{key} must be a non-negative integer")
    if limits["max_pipeline_stages"] < 1 or limits["max_total_tokens"] < 1:
        raise PipelineConfigError("pipeline stage/token limits must be positive")
    if not isinstance(limits["max_total_cost_usd"], (int, float)) or limits["max_total_cost_usd"] <= 0:
        raise PipelineConfigError("limits.max_total_cost_usd must be positive")

    for model_class, model_cfg in models.items():
        if not isinstance(model_cfg, dict):
            raise PipelineConfigError(f"model {model_class} must be a mapping")
        _reject_unknown(model_cfg, _ALLOWED_MODEL, f"model {model_class}")
        _require_keys(model_cfg, _ALLOWED_MODEL, f"model {model_class}")
        if model_cfg["provider"] != "openrouter":
            raise PipelineConfigError(f"model {model_class} provider must be openrouter")
        if not isinstance(model_cfg["model"], str) or "/" not in model_cfg["model"]:
            raise PipelineConfigError(f"model {model_class} must use an explicit provider/model slug")

    for recipe_id, recipe in recipes.items():
        if not isinstance(recipe, dict) or set(recipe) != {"stages"}:
            raise PipelineConfigError(f"recipe {recipe_id} must contain only stages")
        stages = recipe["stages"]
        if not isinstance(stages, list) or not stages:
            raise PipelineConfigError(f"recipe {recipe_id} stages must be a non-empty list")
        if len(stages) > limits["max_pipeline_stages"]:
            raise PipelineConfigError(f"recipe {recipe_id} exceeds max_pipeline_stages")
        seen: set[str] = set()
        token_sum = 0
        for index, stage in enumerate(stages):
            where = f"recipe {recipe_id} stage {index}"
            if not isinstance(stage, dict):
                raise PipelineConfigError(f"{where} must be a mapping")
            _reject_unknown(stage, _ALLOWED_STAGE, where)
            _require_keys(stage, _ALLOWED_STAGE, where)
            name = stage["name"]
            if not isinstance(name, str) or not name or name in seen or name == "original":
                raise PipelineConfigError(f"{where} has invalid/duplicate name")
            if stage["model_class"] not in models:
                raise PipelineConfigError(f"{where} references unknown model_class")
            if not isinstance(stage["max_tokens"], int) or stage["max_tokens"] <= 0:
                raise PipelineConfigError(f"{where}.max_tokens must be positive")
            if not isinstance(stage["instruction"], str) or not stage["instruction"].strip():
                raise PipelineConfigError(f"{where}.instruction must be non-empty")
            inputs = stage["inputs"]
            if not isinstance(inputs, list) or not inputs or not all(isinstance(v, str) for v in inputs):
                raise PipelineConfigError(f"{where}.inputs must be a non-empty string list")
            allowed_inputs = {"original", *seen}
            if any(source not in allowed_inputs for source in inputs):
                raise PipelineConfigError(f"{where} references an input that is not yet available")
            seen.add(name)
            token_sum += stage["max_tokens"]
        if token_sum > limits["max_total_tokens"]:
            raise PipelineConfigError(f"recipe {recipe_id} exceeds max_total_tokens")
    return raw


def _validate_approval(
    approval: PipelineApproval,
    *,
    recipe_id: str,
    config: Mapping[str, Any],
) -> None:
    now = datetime.now(timezone.utc)
    expiry = approval.expires_at
    if expiry.tzinfo is None:
        raise PipelinePolicyError("approval expires_at must be timezone-aware")
    if expiry <= now:
        raise PipelinePolicyError("pipeline approval is expired")
    if not approval.trace_id.strip() or not approval.human_ref.strip() or not approval.purpose.strip():
        raise PipelinePolicyError("approval trace_id, human_ref, and purpose are required")
    if approval.recipe_id != recipe_id:
        raise PipelinePolicyError("approval recipe does not match requested recipe")
    if approval.allowed_route_tier != 5:
        raise PipelinePolicyError("approval must explicitly authorize route tier 5")
    if "openrouter" not in approval.provider_scope:
        raise PipelinePolicyError("approval provider scope does not include openrouter")
    limits = config["limits"]
    if approval.max_tokens < limits["max_total_tokens"]:
        raise PipelinePolicyError("approval token budget is below the configured recipe ceiling")
    if approval.max_cost_usd < float(limits["max_total_cost_usd"]):
        raise PipelinePolicyError("approval cost budget is below the configured recipe ceiling")


def _build_prompt(
    instruction: str,
    inputs: Sequence[str],
    values: Mapping[str, str],
) -> str:
    sections = [instruction.strip()]
    for source in inputs:
        sections.append(f"[{source}]\n{values[source]}")
    return "\n\n".join(sections)


def _append_trace(trace_path: Path | None, payload: Mapping[str, Any]) -> None:
    if trace_path is None:
        return
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n")


async def _openrouter_execute(
    model: str,
    prompt: str,
    max_tokens: int,
    timeout_seconds: float,
) -> tuple[str, int, float]:
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        raise PipelinePolicyError("OPENROUTER_API_KEY is required when Tier-5 pipelines are enabled")
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens},
        )
        response.raise_for_status()
        payload = response.json()
    try:
        output = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise PipelinePolicyError("OpenRouter response missing assistant content") from exc
    usage = payload.get("usage") or {}
    total_tokens = int(usage.get("total_tokens") or 0)
    cost_usd = float(usage.get("cost") or 0.0)
    return str(output), total_tokens, cost_usd


async def execute_tier5_pipeline(
    original: str,
    *,
    recipe_id: str,
    approval: PipelineApproval,
    task_type: str = "reasoning",
    privacy_critical: bool = False,
    config_path: str | Path | None = None,
    trace_path: str | Path | None = None,
    stage_executor: StageExecutor | None = None,
) -> PipelineResult:
    """Execute one approved Tier-5 recipe behind the canonical frugality gate."""
    if not pipelines_enabled():
        raise PipelinePolicyError("Tier-5 pipelines are disabled; set PIPELINE_TIERED_ENABLED=1 explicitly")

    gate = consult_gate(
        task_type,
        privacy_critical=privacy_critical,
        frugality_tier=5,
        model_hint="openrouter-pipeline",
    )
    if not gate.has_route:
        raise PipelinePolicyError(gate.denied_reason or "canonical frugality gate denied Tier 5")

    config = load_pipeline_config(config_path)
    if recipe_id not in config["recipes"]:
        raise PipelineConfigError(f"unknown pipeline recipe: {recipe_id}")
    _validate_approval(approval, recipe_id=recipe_id, config=config)

    limits = config["limits"]
    timeout_seconds = float(limits["request_timeout_seconds"])
    max_retries = int(limits["max_retries"])
    max_tokens = min(int(limits["max_total_tokens"]), approval.max_tokens)
    max_cost = min(float(limits["max_total_cost_usd"]), approval.max_cost_usd)
    trace = Path(trace_path) if trace_path is not None else None
    executor = stage_executor or _openrouter_execute

    values: dict[str, str] = {"original": original}
    results: list[StageResult] = []
    cumulative_tokens = 0
    cumulative_cost = 0.0

    _append_trace(trace, {"event": "pipeline_start", "trace_id": approval.trace_id, "tier": 5, "recipe_id": recipe_id})

    for stage in config["recipes"][recipe_id]["stages"]:
        model_cfg = config["models"][stage["model_class"]]
        prompt = _build_prompt(stage["instruction"], stage["inputs"], values)
        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                output, used_tokens, cost_usd = await executor(
                    model_cfg["model"], prompt, int(stage["max_tokens"]), timeout_seconds
                )
                break
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code == 429 or exc.response.status_code >= 500
                if attempt >= max_retries or not retryable:
                    raise
                await asyncio.sleep(0)
        else:  # pragma: no cover - loop either breaks or raises
            assert last_error is not None
            raise last_error

        if used_tokens < 0 or cost_usd < 0:
            raise PipelinePolicyError("provider returned invalid negative usage")
        cumulative_tokens += used_tokens
        cumulative_cost += cost_usd
        if cumulative_tokens > max_tokens:
            raise PipelinePolicyError("Tier-5 pipeline exceeded approved/configured token budget")
        if cumulative_cost > max_cost:
            raise PipelinePolicyError("Tier-5 pipeline exceeded approved/configured cost budget")

        result = StageResult(
            name=stage["name"],
            model_class=stage["model_class"],
            model=model_cfg["model"],
            output=output,
            total_tokens=used_tokens,
            cost_usd=cost_usd,
        )
        results.append(result)
        values[stage["name"]] = output
        _append_trace(
            trace,
            {
                "event": "pipeline_stage",
                "trace_id": approval.trace_id,
                "tier": 5,
                "recipe_id": recipe_id,
                "stage": stage["name"],
                "model_class": stage["model_class"],
                "model": model_cfg["model"],
                "total_tokens": used_tokens,
                "cost_usd": cost_usd,
            },
        )

    final = results[-1]
    _append_trace(trace, {"event": "pipeline_complete", "trace_id": approval.trace_id, "tier": 5, "recipe_id": recipe_id, "total_tokens": cumulative_tokens, "cost_usd": cumulative_cost})
    return PipelineResult(
        trace_id=approval.trace_id,
        recipe_id=recipe_id,
        output=final.output,
        total_tokens=cumulative_tokens,
        cost_usd=cumulative_cost,
        stages=tuple(results),
    )
