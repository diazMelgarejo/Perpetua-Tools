from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from orchestrator import tiered_pipeline as tp


@pytest.fixture
def candidate_pipeline_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    models = tmp_path / "models.yml"
    models.write_text(
        """models:
  - name: fast-primary
    backend: openrouter
    frugality_tier: 5
  - name: fast-fallback
    backend: anthropic
    frugality_tier: 5
  - name: strong-primary
    backend: openrouter
    frugality_tier: 5
  - name: strong-fallback
    backend: anthropic
    frugality_tier: 5
""",
        encoding="utf-8",
    )
    pipelines = tmp_path / "pipelines.yml"
    pipelines.write_text(
        """version: 1
models:
  fast:
    candidates: [fast-primary, fast-fallback]
  strong:
    candidates: [strong-primary, strong-fallback]
recipes:
  classify_then_generate:
    max_total_tokens: 30
    cost_reservation_usd: 0.25
    max_input_tokens: 512
    stages:
      - name: classify
        model: fast
        max_tokens: 10
      - name: generate
        model: strong
        max_tokens: 20
        input_from: classify
""",
        encoding="utf-8",
    )
    return pipelines, models, tmp_path / "trace.jsonl"


def _runner(files: tuple[Path, Path, Path]) -> tp.TieredPipelineRunner:
    return tp.TieredPipelineRunner(
        config_path=files[0],
        models_path=files[1],
        trace_path=files[2],
    )


def _approval(**overrides: object) -> tp.PipelineApproval:
    fields: dict[str, object] = {
        "trace_id": "candidate-fallback-test",
        "approved_by": "operator",
        "purpose": "verify configured model fallbacks",
        "recipe": "classify_then_generate",
        "route_tier": 5,
        "max_tokens": 30,
        "max_cost_usd": 0.25,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "scope": ("openrouter", "anthropic", "bigmodel"),
    }
    fields.update(overrides)
    return tp.PipelineApproval(**fields)


def test_candidate_pools_are_ordered_and_env_override_is_preferred(
    candidate_pipeline_files: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PIPELINE_FAST_MODEL", "fast-fallback")

    recipe = _runner(candidate_pipeline_files).recipe("classify_then_generate")

    assert recipe.stages[0].models == ("fast-fallback", "fast-primary")
    assert recipe.stages[0].model == "fast-fallback"
    assert recipe.stages[1].models == ("strong-primary", "strong-fallback")


@pytest.mark.asyncio
async def test_unready_primary_falls_back_and_reports_selected_models(
    candidate_pipeline_files: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "1")
    monkeypatch.delenv("ORAMASYS_OFFLINE", raising=False)
    attempts: list[tuple[str, str]] = []

    async def dispatch(
        model: str, prompt: str, max_tokens: int, stage: str
    ) -> tp.DispatchResult:
        del prompt, max_tokens
        attempts.append((stage, model))
        if model in {"fast-primary", "strong-primary"}:
            raise tp.PipelineCandidateUnavailableError(model)
        return tp.DispatchResult(
            text=f"{stage}-result",
            total_tokens=5,
            cost_usd=0.01,
        )

    result = await _runner(candidate_pipeline_files).run(
        "classify_then_generate",
        "original",
        approval=_approval(),
        dispatch=dispatch,
    )

    assert attempts == [
        ("classify", "fast-primary"),
        ("classify", "fast-fallback"),
        ("generate", "strong-primary"),
        ("generate", "strong-fallback"),
    ]
    assert result.output == "generate-result"
    assert result.models_used == {
        "classify": "fast-fallback",
        "generate": "strong-fallback",
    }
    trace_rows = [
        json.loads(line)
        for line in candidate_pipeline_files[2].read_text(encoding="utf-8").splitlines()
    ]
    assert [
        (row["attributes"]["pipeline.model"], row["attributes"]["status"])
        for row in trace_rows
    ] == [
        ("fast-primary", "unavailable"),
        ("fast-fallback", "completed"),
        ("strong-primary", "unavailable"),
        ("strong-fallback", "completed"),
    ]


def test_candidate_pool_rejects_non_tier_five_fallback(
    candidate_pipeline_files: tuple[Path, Path, Path],
) -> None:
    pipelines, models, trace = candidate_pipeline_files
    models.write_text(
        models.read_text(encoding="utf-8")
        + "  - name: local-model\n    frugality_tier: 1\n",
        encoding="utf-8",
    )
    pipelines.write_text(
        pipelines.read_text(encoding="utf-8").replace(
            "candidates: [fast-primary, fast-fallback]",
            "candidates: [fast-primary, local-model]",
        ),
        encoding="utf-8",
    )

    with pytest.raises(tp.PipelineConfigError, match="must be frugality tier 5"):
        tp.TieredPipelineRunner(
            config_path=pipelines,
            models_path=models,
            trace_path=trace,
        )


@pytest.mark.asyncio
async def test_ambiguous_paid_failure_never_dispatches_a_second_candidate(
    candidate_pipeline_files: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "1")
    monkeypatch.delenv("ORAMASYS_OFFLINE", raising=False)
    attempts: list[str] = []

    async def dispatch(
        model: str, prompt: str, max_tokens: int, stage: str
    ) -> tp.DispatchResult:
        del prompt, max_tokens, stage
        attempts.append(model)
        raise tp.PipelineCandidateUnavailableError(
            "ambiguous timeout",
            fallback_safe=False,
        )

    with pytest.raises(tp.PipelineCandidateUnavailableError):
        await _runner(candidate_pipeline_files).run(
            "classify_then_generate",
            "original",
            approval=_approval(),
            dispatch=dispatch,
        )

    assert attempts == ["fast-primary"]


@pytest.mark.asyncio
async def test_out_of_scope_candidate_is_rejected_before_dispatch(
    candidate_pipeline_files: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "1")
    monkeypatch.delenv("ORAMASYS_OFFLINE", raising=False)
    attempts: list[str] = []

    async def dispatch(
        model: str, prompt: str, max_tokens: int, stage: str
    ) -> tp.DispatchResult:
        del prompt, max_tokens, stage
        attempts.append(model)
        return tp.DispatchResult(text="ok", total_tokens=1, cost_usd=0.01)

    narrow_approval = _approval(scope=("anthropic",))

    with pytest.raises(tp.PipelineApprovalError, match="does not authorize provider"):
        await _runner(candidate_pipeline_files).run(
            "classify_then_generate",
            "original",
            approval=narrow_approval,
            dispatch=dispatch,
        )

    assert attempts == []
