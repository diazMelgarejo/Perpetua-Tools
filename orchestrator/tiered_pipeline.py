"""Governed, default-off Tier-5 pipeline execution.

This module is deliberately subordinate to the canonical frugality gate. It
accepts only an already-approved tier-5 route and a bounded human approval
record; it never decides whether paid egress is allowed.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

import yaml

from orchestrator.frugality_router import ResolvedRoute, ToolCallSpec, is_offline_mode


class PipelinePolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class ApprovalRecord:
    trace_id: str
    human_ref: str
    purpose: str
    recipe_id: str
    allowed_route_tier: int
    max_tokens: int
    max_cost_usd: float
    expires_at: float
    provider_scope: tuple[str, ...] = ("openrouter",)


@dataclass(frozen=True)
class PipelineResult:
    status: str
    trace_id: str
    recipe_id: str
    output: str
    tokens_used: int
    cost_usd: float
    stages: tuple[Mapping[str, Any], ...]


def pipelines_enabled() -> bool:
    return os.getenv("PIPELINE_TIERED_ENABLED", "0") == "1"


def _load_config(path: str | Path) -> dict[str, Any]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    allowed_top = {"schema_version", "limits", "recipes"}
    unknown = set(raw) - allowed_top
    if unknown:
        raise PipelinePolicyError(f"unknown pipeline config keys: {sorted(unknown)}")
    if raw.get("schema_version") != 1:
        raise PipelinePolicyError("unsupported pipeline schema_version")
    limits = raw.get("limits") or {}
    recipes = raw.get("recipes") or {}
    if not isinstance(limits, dict) or not isinstance(recipes, dict):
        raise PipelinePolicyError("limits and recipes must be mappings")
    for key in ("max_pipeline_stages", "max_total_tokens"):
        if int(limits.get(key, 0)) <= 0:
            raise PipelinePolicyError(f"{key} must be positive")
    if float(limits.get("max_total_cost_usd", 0)) <= 0:
        raise PipelinePolicyError("max_total_cost_usd must be positive")
    return raw


def _validate_recipe(config: Mapping[str, Any], recipe_id: str) -> list[dict[str, Any]]:
    recipes = config["recipes"]
    if recipe_id not in recipes:
        raise PipelinePolicyError(f"unknown recipe: {recipe_id}")
    recipe = recipes[recipe_id]
    allowed_recipe = {"description", "stages"}
    if set(recipe) - allowed_recipe:
        raise PipelinePolicyError("unknown recipe keys")
    stages = recipe.get("stages") or []
    limit = int(config["limits"]["max_pipeline_stages"])
    if not stages or len(stages) > limit:
        raise PipelinePolicyError("invalid pipeline stage count")
    seen: set[str] = set()
    total = 0
    for stage in stages:
        allowed = {"name", "model_class", "max_tokens", "input", "input_from"}
        if set(stage) - allowed:
            raise PipelinePolicyError(f"unknown stage keys in {stage.get('name', '?')}")
        name = str(stage.get("name", "")).strip()
        if not name or name in seen:
            raise PipelinePolicyError("stage names must be unique and non-empty")
        model_class = stage.get("model_class")
        if model_class not in {"fast", "strong"}:
            raise PipelinePolicyError("model_class must be a governed alias: fast|strong")
        cap = int(stage.get("max_tokens", 0))
        if cap <= 0:
            raise PipelinePolicyError("stage max_tokens must be positive")
        total += cap
        source = stage.get("input_from")
        if source is not None and source not in seen:
            raise PipelinePolicyError("input_from must reference a prior stage")
        if source is None and stage.get("input", "original") != "original":
            raise PipelinePolicyError("stage input must be original or input_from a prior stage")
        seen.add(name)
    if total > int(config["limits"]["max_total_tokens"]):
        raise PipelinePolicyError("aggregate stage token cap exceeds pipeline limit")
    return stages


class TieredPipelineRunner:
    """Execute a router-approved paid recipe with bounded injected provider I/O.

    `invoke` is injected so provider credentials and model resolution stay in the
    existing PT runtime. Signature: invoke(model_class, prompt, max_tokens) ->
    mapping with `text`, `tokens`, and `cost_usd`.
    """

    def __init__(self, config_path: str | Path, invoke: Callable[[str, str, int], Mapping[str, Any]]):
        self.config_path = Path(config_path)
        self.invoke = invoke

    def run(self, *, route: ResolvedRoute, spec: ToolCallSpec, recipe_id: str,
            task_input: str, approval: ApprovalRecord) -> PipelineResult:
        if not pipelines_enabled():
            raise PipelinePolicyError("PIPELINE_TIERED_ENABLED is disabled")
        if is_offline_mode() or spec.privacy_critical:
            raise PipelinePolicyError("Tier-5 egress blocked by offline/privacy policy")
        if route.tier != 5 or route.backend != "openrouter":
            raise PipelinePolicyError("runner requires a router-approved Tier-5 openrouter route")
        if not os.getenv("OPENROUTER_API_KEY"):
            raise PipelinePolicyError("OPENROUTER_API_KEY is required when Tier-5 is enabled")
        now = time.time()
        if approval.expires_at <= now:
            raise PipelinePolicyError("approval expired")
        if approval.recipe_id != recipe_id or approval.allowed_route_tier != 5:
            raise PipelinePolicyError("approval does not match recipe/tier")
        if "openrouter" not in approval.provider_scope:
            raise PipelinePolicyError("approval provider scope does not include openrouter")

        config = _load_config(self.config_path)
        stages = _validate_recipe(config, recipe_id)
        config_tokens = int(config["limits"]["max_total_tokens"])
        config_cost = float(config["limits"]["max_total_cost_usd"])
        max_tokens = min(config_tokens, approval.max_tokens)
        max_cost = min(config_cost, approval.max_cost_usd)
        if max_tokens <= 0 or max_cost <= 0:
            raise PipelinePolicyError("approval budget must be positive")

        outputs: dict[str, str] = {}
        stage_records: list[Mapping[str, Any]] = []
        used_tokens = 0
        used_cost = 0.0
        terminal = ""
        for stage in stages:
            prompt = outputs[stage["input_from"]] if stage.get("input_from") else task_input
            cap = int(stage["max_tokens"])
            if used_tokens + cap > max_tokens:
                raise PipelinePolicyError("approved aggregate token budget would be exceeded")
            result = self.invoke(str(stage["model_class"]), prompt, cap)
            text = str(result.get("text", ""))
            tokens = int(result.get("tokens", 0))
            cost = float(result.get("cost_usd", 0.0))
            if tokens < 0 or tokens > cap or used_tokens + tokens > max_tokens:
                raise PipelinePolicyError("provider token accounting exceeds approved cap")
            if cost < 0 or used_cost + cost > max_cost:
                raise PipelinePolicyError("provider cost accounting exceeds approved cap")
            used_tokens += tokens; used_cost += cost; outputs[stage["name"]] = text; terminal = text
            stage_records.append({"trace_id": approval.trace_id, "tier": 5, "recipe_id": recipe_id,
                                  "stage_id": stage["name"], "model_class": stage["model_class"],
                                  "tokens": tokens, "cost_usd": cost, "status": "ok"})
        return PipelineResult("ok", approval.trace_id, recipe_id, terminal, used_tokens, used_cost, tuple(stage_records))
