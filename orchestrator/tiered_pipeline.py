"""Governed Tier-5 pipeline execution for Perpetua-Tools.

The frugality router and gate remain the policy authorities. This module only
validates configured Tier-5 stages, sequences them after the canonical gate
permits execution, and delegates provider I/O to an injected dispatcher.
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
PIPELINE_FLAG = "PIPELINE_TIERED_ENABLED"
TRACE_PATH_ENV = "PT_PIPELINE_TRACE_PATH"
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "pipelines.yml"
DEFAULT_MODELS = Path(__file__).resolve().parent.parent / "config" / "models.yml"
DEFAULT_TRACE = Path(__file__).resolve().parent.parent / ".state" / "frugality_pipeline.jsonl"

Dispatcher = Callable[[str, str, int, str], Awaitable[str]]


class PipelineError(RuntimeError):
    """Base error for governed Tier-5 pipeline execution."""


class PipelineDisabledError(PipelineError):
    """Raised when the explicit feature flag is not enabled."""


class PipelineConfigError(PipelineError):
    """Raised when pipeline configuration is invalid or incomplete."""


class PipelinePolicyError(PipelineError):
    """Raised when the canonical frugality gate refuses Tier 5."""


class PipelineExecutionError(PipelineError):
    """Raised when an injected provider dispatcher cannot complete a stage."""


@dataclass(frozen=True)
class PipelineStage:
    name: str
    model: str
    max_tokens: int
    input_from: str | None = None
    instruction: str = ""


@dataclass(frozen=True)
class PipelineRecipe:
    name: str
    stages: tuple[PipelineStage, ...]
    max_total_tokens: int
    max_input_tokens: int
    cost_reservation_usd: float


@dataclass(frozen=True)
class PipelineResult:
    recipe: str
    output: str
    stage_outputs: Mapping[str, str]
    requested_tokens: int


def tiered_pipeline_enabled() -> bool:
    """Return True only for the literal opt-in value ``1``."""
    return os.getenv(PIPELINE_FLAG, "0").strip() == "1"


def _input_token_upper_bound(value: str) -> int:
    """Conservatively bound tokens without a provider-specific tokenizer."""
    return len(value.encode("utf-8"))


class TieredPipelineRunner:
    """Load, validate, and execute a configured Tier-5 recipe.

    The runner has no provider client or credential handling. Its caller owns
    provider selection and passes an async dispatcher once a guarded pipeline
    run is appropriate.
    """

    def __init__(
        self,
        *,
        config_path: str | Path | None = None,
        models_path: str | Path | None = None,
        trace_path: str | Path | None = None,
    ) -> None:
        self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG
        self.models_path = Path(models_path) if models_path else DEFAULT_MODELS
        configured_trace_path = os.getenv(TRACE_PATH_ENV, "").strip()
        self.trace_path = (
            Path(trace_path)
            if trace_path is not None
            else Path(configured_trace_path)
            if configured_trace_path
            else DEFAULT_TRACE
        )
        self._models, self._recipes = self._load_and_validate()

    def _load_and_validate(self) -> tuple[dict[str, str], dict[str, PipelineRecipe]]:
        if not self.config_path.is_file():
            raise PipelineConfigError("pipeline config missing: %s" % self.config_path)
        if not self.models_path.is_file():
            raise PipelineConfigError("model registry missing: %s" % self.models_path)
        try:
            raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise PipelineConfigError("invalid pipeline config: %s" % exc) from exc
        if not isinstance(raw, dict):
            raise PipelineConfigError("pipeline config root must be a mapping")

        model_aliases = raw.get("models")
        recipe_rows = raw.get("recipes")
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
                    "pipeline model %s=%r must be frugality tier %d; found %r"
                    % (alias, model_name, PIPELINE_TIER, tier)
                )

        recipes: dict[str, PipelineRecipe] = {}
        for recipe_name, recipe_row in recipe_rows.items():
            if not isinstance(recipe_row, dict):
                raise PipelineConfigError("recipe %r must be a mapping" % recipe_name)
            rows = recipe_row.get("stages")
            if not isinstance(rows, list) or not rows:
                raise PipelineConfigError("recipe %r requires non-empty stages" % recipe_name)

            seen: set[str] = set()
            stages: list[PipelineStage] = []
            requested_tokens = 0
            for row in rows:
                if not isinstance(row, dict):
                    raise PipelineConfigError(
                        "recipe %r contains a non-mapping stage" % recipe_name
                    )
                name = str(row.get("name", "")).strip()
                alias = str(row.get("model", "")).strip()
                if not name or name in seen:
                    raise PipelineConfigError(
                        "recipe %r has missing/duplicate stage name %r" % (recipe_name, name)
                    )
                if alias not in models:
                    raise PipelineConfigError(
                        "stage %r references unknown model alias %r" % (name, alias)
                    )
                try:
                    max_tokens = int(row.get("max_tokens", 0))
                except (TypeError, ValueError) as exc:
                    raise PipelineConfigError(
                        "stage %r max_tokens must be an integer" % name
                    ) from exc
                if max_tokens <= 0:
                    raise PipelineConfigError("stage %r max_tokens must be positive" % name)
                input_from = row.get("input_from")
                if input_from is not None:
                    input_from = str(input_from).strip()
                    if input_from not in seen:
                        raise PipelineConfigError(
                            "stage %r input_from must reference an earlier stage; got %r"
                            % (name, input_from)
                        )
                stages.append(
                    PipelineStage(
                        name=name,
                        model=models[alias],
                        max_tokens=max_tokens,
                        input_from=input_from,
                        instruction=str(row.get("instruction", "")).strip(),
                    )
                )
                seen.add(name)
                requested_tokens += max_tokens

            try:
                max_total_tokens = int(
                    recipe_row.get("max_total_tokens", requested_tokens)
                )
            except (TypeError, ValueError) as exc:
                raise PipelineConfigError(
                    "recipe %r max_total_tokens must be an integer" % recipe_name
                ) from exc
            try:
                max_input_tokens = int(
                    recipe_row.get("max_input_tokens", max_total_tokens)
                )
            except (TypeError, ValueError) as exc:
                raise PipelineConfigError(
                    "recipe %r max_input_tokens must be an integer" % recipe_name
                ) from exc
            if max_total_tokens <= 0 or max_input_tokens <= 0:
                raise PipelineConfigError("recipe %r token limits must be positive" % recipe_name)
            if requested_tokens > max_total_tokens:
                raise PipelineConfigError(
                    "recipe %r requests %d tokens but cap is %d"
                    % (recipe_name, requested_tokens, max_total_tokens)
                )
            try:
                cost_reservation_usd = float(recipe_row.get("cost_reservation_usd", 0))
            except (TypeError, ValueError) as exc:
                raise PipelineConfigError(
                    "recipe %r cost_reservation_usd must be a number" % recipe_name
                ) from exc
            if cost_reservation_usd <= 0:
                raise PipelineConfigError(
                    "recipe %r cost_reservation_usd must be positive" % recipe_name
                )
            recipes[str(recipe_name)] = PipelineRecipe(
                name=str(recipe_name),
                stages=tuple(stages),
                max_total_tokens=max_total_tokens,
                max_input_tokens=max_input_tokens,
                cost_reservation_usd=cost_reservation_usd,
            )

        return models, recipes

    def recipe(self, name: str) -> PipelineRecipe:
        try:
            return self._recipes[name]
        except KeyError as exc:
            raise PipelineConfigError("unknown pipeline recipe: %s" % name) from exc

    @staticmethod
    def _stage_prompt(
        original: str, stage: PipelineStage, outputs: Mapping[str, str]
    ) -> str:
        if stage.input_from is None:
            context = "Original request:\n%s" % original
        else:
            context = "Original request:\n%s\n\nOutput from stage %s:\n%s" % (
                original,
                stage.input_from,
                outputs[stage.input_from],
            )
        return "%s\n\n%s" % (stage.instruction, context) if stage.instruction else context

    def _emit_trace(
        self, *, recipe: str, stage: PipelineStage, elapsed_ms: int, status: str
    ) -> None:
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
                "status": status,
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
        dispatch: Dispatcher,
        task_type: str = "reasoning",
        privacy_critical: bool = False,
        override_confirmed: bool = False,
        override_reason: str | None = None,
    ) -> PipelineResult:
        if not tiered_pipeline_enabled():
            raise PipelineDisabledError(
                "%s=1 is required for Tier-5 pipeline execution" % PIPELINE_FLAG
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
            if _input_token_upper_bound(stage_prompt) > recipe.max_input_tokens:
                raise PipelinePolicyError(
                    "stage %s input exceeds max_input_tokens %d"
                    % (stage.name, recipe.max_input_tokens)
                )
            started = time.monotonic()
            try:
                output = await dispatch(stage.model, stage_prompt, stage.max_tokens, stage.name)
            except Exception:
                self._emit_trace(
                    recipe=recipe.name,
                    stage=stage,
                    elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
                    status="failed",
                )
                raise
            if not isinstance(output, str) or not output.strip():
                raise PipelineExecutionError(
                    "stage %r returned an empty/non-text result" % stage.name
                )
            outputs[stage.name] = output
            requested_tokens += stage.max_tokens
            self._emit_trace(
                recipe=recipe.name,
                stage=stage,
                elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
                status="completed",
            )

        return PipelineResult(
            recipe=recipe.name,
            output=outputs[recipe.stages[-1].name],
            stage_outputs=dict(outputs),
            requested_tokens=requested_tokens,
        )
