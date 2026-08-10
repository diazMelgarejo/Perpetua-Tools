"""Governed Tier-5 pipeline execution for Perpetua-Tools.

The frugality router remains the policy source of truth. This module only
sequences configured Tier-5 stages after the canonical gate permits them, and
it delegates actual provider execution to an injected async dispatcher.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Mapping

import yaml

from orchestrator.gate import gate_permits, load_frugality_tier_by_name

PIPELINE_TIER = 5
PIPELINE_ENABLED_ENV = "PIPELINE_TIERED_ENABLED"
_TRUE = {"1", "true", "yes", "on"}

Dispatch = Callable[[str, str, int, str], Awaitable[str]]


class PipelineError(RuntimeError):
    """Base error for governed pipeline execution."""


class PipelineDisabledError(PipelineError):
    """Raised when Tier-5 pipeline execution is not explicitly enabled."""


class PipelineConfigError(PipelineError):
    """Raised when pipeline configuration violates the execution contract."""


class PipelinePolicyError(PipelineError):
    """Raised when the canonical frugality gate denies Tier 5."""


@dataclass(frozen=True)
class StageSpec:
    name: str
    model: str
    max_tokens: int
    input_from: str | None = None
    instruction: str = ""


@dataclass(frozen=True)
class RecipeSpec:
    name: str
    stages: tuple[StageSpec, ...]
    max_total_tokens: int


@dataclass(frozen=True)
class PipelineRun:
    recipe: str
    outputs: Mapping[str, str]
    final_output: str
    requested_tokens: int


def pipeline_enabled() -> bool:
    """Return True only for an explicit opt-in flag."""
    return os.getenv(PIPELINE_ENABLED_ENV, "0").strip().lower() in _TRUE


class TieredPipelineRunner:
    """Load, validate, and execute configured Tier-5 recipes.

    The runner never chooses providers and never performs HTTP calls itself.
    Configured model aliases must resolve to models classified as frugality
    tier 5 in ``config/models.yml``. Each execution consults ``gate_permits``
    before the first stage, then calls the injected dispatcher sequentially.
    """

    def __init__(
        self,
        *,
        config_path: str | Path | None = None,
        models_path: str | Path | None = None,
        trace_path: str | Path | None = None,
    ) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        self.config_path = Path(config_path) if config_path else repo_root / "config/pipelines.yml"
        self.models_path = Path(models_path) if models_path else repo_root / "config/models.yml"
        configured_trace_path = os.getenv("PT_PIPELINE_TRACE_PATH", "").strip()
        self.trace_path = (
            Path(trace_path)
            if trace_path is not None
            else (
                Path(configured_trace_path)
                if configured_trace_path
                else repo_root / ".state/frugality_pipeline.jsonl"
            )
        )
        self._models, self._recipes = self._load_and_validate()

    def _load_and_validate(self) -> tuple[dict[str, str], dict[str, RecipeSpec]]:
        if not self.config_path.is_file():
            raise PipelineConfigError(f"pipeline config missing: {self.config_path}")
        if not self.models_path.is_file():
            raise PipelineConfigError(f"model registry missing: {self.models_path}")

        try:
            raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise PipelineConfigError(f"invalid pipeline config: {exc}") from exc
        if not isinstance(raw, dict):
            raise PipelineConfigError("pipeline config root must be a mapping")

        model_aliases = raw.get("models", {})
        recipe_rows = raw.get("recipes", {})
        if not isinstance(model_aliases, dict) or not model_aliases:
            raise PipelineConfigError("pipeline config requires a non-empty models mapping")
        if not isinstance(recipe_rows, dict) or not recipe_rows:
            raise PipelineConfigError("pipeline config requires a non-empty recipes mapping")

        models = {str(alias): str(name) for alias, name in model_aliases.items()}
        tiers = load_frugality_tier_by_name(str(self.models_path.parent))
        for alias, model_name in models.items():
            tier = tiers.get(model_name)
            if tier != PIPELINE_TIER:
                raise PipelineConfigError(
                    f"pipeline model {alias}={model_name!r} must be frugality tier {PIPELINE_TIER}; found {tier!r}"
                )

        recipes: dict[str, RecipeSpec] = {}
        for recipe_name, recipe_row in recipe_rows.items():
            if not isinstance(recipe_row, dict):
                raise PipelineConfigError(f"recipe {recipe_name!r} must be a mapping")
            rows = recipe_row.get("stages")
            if not isinstance(rows, list) or not rows:
                raise PipelineConfigError(f"recipe {recipe_name!r} requires non-empty stages")

            seen: set[str] = set()
            stages: list[StageSpec] = []
            for row in rows:
                if not isinstance(row, dict):
                    raise PipelineConfigError(f"recipe {recipe_name!r} contains a non-mapping stage")
                name = str(row.get("name", "")).strip()
                alias = str(row.get("model", "")).strip()
                if not name or name in seen:
                    raise PipelineConfigError(f"recipe {recipe_name!r} has missing/duplicate stage name {name!r}")
                if alias not in models:
                    raise PipelineConfigError(f"stage {name!r} references unknown model alias {alias!r}")
                try:
                    max_tokens = int(row.get("max_tokens", 0))
                except (TypeError, ValueError) as exc:
                    raise PipelineConfigError(f"stage {name!r} has invalid max_tokens") from exc
                if max_tokens <= 0:
                    raise PipelineConfigError(f"stage {name!r} max_tokens must be positive")
                input_from = row.get("input_from")
                if input_from is not None:
                    input_from = str(input_from)
                    if input_from not in seen:
                        raise PipelineConfigError(
                            f"stage {name!r} input_from must reference an earlier stage; got {input_from!r}"
                        )
                stages.append(
                    StageSpec(
                        name=name,
                        model=models[alias],
                        max_tokens=max_tokens,
                        input_from=input_from,
                        instruction=str(row.get("instruction", "")).strip(),
                    )
                )
                seen.add(name)

            requested = sum(stage.max_tokens for stage in stages)
            try:
                cap = int(recipe_row.get("max_total_tokens", requested))
            except (TypeError, ValueError) as exc:
                raise PipelineConfigError(f"recipe {recipe_name!r} has invalid max_total_tokens") from exc
            if cap <= 0 or requested > cap:
                raise PipelineConfigError(
                    f"recipe {recipe_name!r} requests {requested} tokens but cap is {cap}"
                )
            recipes[str(recipe_name)] = RecipeSpec(str(recipe_name), tuple(stages), cap)

        return models, recipes

    def recipe(self, name: str) -> RecipeSpec:
        try:
            return self._recipes[name]
        except KeyError as exc:
            raise PipelineConfigError(f"unknown pipeline recipe: {name}") from exc

    @staticmethod
    def _stage_prompt(original: str, stage: StageSpec, outputs: Mapping[str, str]) -> str:
        if stage.input_from is None:
            context = f"Original request:\n{original}"
        else:
            context = (
                f"Original request:\n{original}\n\n"
                f"Output from stage {stage.input_from}:\n{outputs[stage.input_from]}"
            )
        return f"{stage.instruction}\n\n{context}" if stage.instruction else context

    def _emit_trace(self, *, recipe: str, stage: StageSpec, elapsed_ms: int) -> None:
        payload = {
            "timestamp": time.time(),
            "name": "tiered_pipeline.stage",
            "attributes": {
                "ot.tool.tier": PIPELINE_TIER,
                "pipeline.recipe": recipe,
                "pipeline.stage": stage.name,
                "pipeline.model": stage.model,
                "pipeline.max_tokens": stage.max_tokens,
                "elapsed_ms": elapsed_ms,
            },
        }
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":")) + "\n")

    async def run(
        self,
        recipe_name: str,
        prompt: str,
        *,
        dispatch: Dispatch,
        task_type: str = "reasoning",
        privacy_critical: bool = False,
        override_confirmed: bool = False,
        override_reason: str | None = None,
    ) -> PipelineRun:
        if not pipeline_enabled():
            raise PipelineDisabledError(
                f"Tier-5 pipelines are disabled; set {PIPELINE_ENABLED_ENV}=1 explicitly to opt in"
            )
        if not prompt.strip():
            raise PipelineError("pipeline prompt must be non-empty")

        allowed, denied_reason = gate_permits(
            PIPELINE_TIER,
            task_type=task_type,
            privacy_critical=privacy_critical,
            override_confirmed=override_confirmed,
            override_reason=override_reason,
        )
        if not allowed:
            raise PipelinePolicyError(denied_reason or "canonical frugality gate denied Tier 5")

        recipe = self.recipe(recipe_name)
        outputs: dict[str, str] = {}
        requested_tokens = 0
        for stage in recipe.stages:
            stage_prompt = self._stage_prompt(prompt, stage, outputs)
            started = time.monotonic()
            output = await dispatch(stage.model, stage_prompt, stage.max_tokens, stage.name)
            if not isinstance(output, str) or not output.strip():
                raise PipelineError(f"stage {stage.name!r} returned an empty/non-text result")
            outputs[stage.name] = output
            requested_tokens += stage.max_tokens
            self._emit_trace(
                recipe=recipe.name,
                stage=stage,
                elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
            )

        return PipelineRun(
            recipe=recipe.name,
            outputs=dict(outputs),
            final_output=outputs[recipe.stages[-1].name],
            requested_tokens=requested_tokens,
        )
