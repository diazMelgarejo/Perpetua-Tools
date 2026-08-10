from __future__ import annotations

import json
from pathlib import Path

import pytest

from orchestrator.tiered_pipeline import (
    PipelineConfigError,
    PipelineDisabledError,
    PipelinePolicyError,
    TieredPipelineRunner,
)


@pytest.fixture
def pipeline_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    models = tmp_path / "models.yml"
    models.write_text(
        """models:
  - name: paid-fast
    frugality_tier: 5
  - name: paid-strong
    frugality_tier: 5
  - name: local-model
    frugality_tier: 1
""",
        encoding="utf-8",
    )
    pipelines = tmp_path / "pipelines.yml"
    pipelines.write_text(
        """version: 1
models:
  fast: paid-fast
  strong: paid-strong
recipes:
  classify_then_generate:
    max_total_tokens: 30
    stages:
      - name: classify
        model: fast
        max_tokens: 10
        instruction: classify
      - name: generate
        model: strong
        max_tokens: 20
        input_from: classify
        instruction: generate
""",
        encoding="utf-8",
    )
    return pipelines, models, tmp_path / "trace.jsonl"


def _runner(files: tuple[Path, Path, Path]) -> TieredPipelineRunner:
    pipelines, models, trace = files
    return TieredPipelineRunner(config_path=pipelines, models_path=models, trace_path=trace)


@pytest.mark.asyncio
async def test_flag_defaults_off_and_never_dispatches(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PIPELINE_TIERED_ENABLED", raising=False)
    calls: list[str] = []

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        calls.append(stage)
        return "unexpected"

    with pytest.raises(PipelineDisabledError):
        await _runner(pipeline_files).run("classify_then_generate", "hello", dispatch=dispatch)
    assert calls == []


@pytest.mark.asyncio
async def test_pipeline_runs_in_order_preserves_original_and_dependency(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "1")
    monkeypatch.delenv("ORAMASYS_OFFLINE", raising=False)
    calls: list[tuple[str, str, int, str]] = []

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        calls.append((model, prompt, max_tokens, stage))
        return "classification-result" if stage == "classify" else "final-result"

    runner = _runner(pipeline_files)
    result = await runner.run("classify_then_generate", "ORIGINAL-REQUEST", dispatch=dispatch)

    assert [row[3] for row in calls] == ["classify", "generate"]
    assert calls[0][0] == "paid-fast"
    assert calls[1][0] == "paid-strong"
    assert calls[1][2] == 20
    assert "ORIGINAL-REQUEST" in calls[1][1]
    assert "classification-result" in calls[1][1]
    assert result.final_output == "final-result"
    assert result.requested_tokens == 30

    trace_text = pipeline_files[2].read_text(encoding="utf-8")
    trace_lines = [json.loads(line) for line in trace_text.splitlines()]
    assert [line["attributes"]["pipeline.stage"] for line in trace_lines] == ["classify", "generate"]
    assert all(line["attributes"]["ot.tool.tier"] == 5 for line in trace_lines)
    assert "ORIGINAL-REQUEST" not in trace_text


@pytest.mark.asyncio
async def test_offline_policy_blocks_tier5_before_dispatch(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "1")
    monkeypatch.setenv("ORAMASYS_OFFLINE", "1")
    called = False

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        nonlocal called
        called = True
        return "no"

    with pytest.raises(PipelinePolicyError, match="ORAMASYS_OFFLINE"):
        await _runner(pipeline_files).run("classify_then_generate", "hello", dispatch=dispatch)
    assert called is False


@pytest.mark.asyncio
async def test_privacy_critical_requires_existing_explicit_override_contract(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "1")
    monkeypatch.delenv("ORAMASYS_OFFLINE", raising=False)

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        return stage

    runner = _runner(pipeline_files)
    with pytest.raises(PipelinePolicyError, match="override_confirmed"):
        await runner.run(
            "classify_then_generate", "hello", dispatch=dispatch, privacy_critical=True
        )

    result = await runner.run(
        "classify_then_generate",
        "hello",
        dispatch=dispatch,
        privacy_critical=True,
        override_confirmed=True,
        override_reason="operator explicitly approved paid cloud execution",
    )
    assert result.final_output == "generate"


def test_unknown_recipe_fails_closed(pipeline_files: tuple[Path, Path, Path]) -> None:
    with pytest.raises(PipelineConfigError, match="unknown pipeline recipe"):
        _runner(pipeline_files).recipe("missing")


def test_model_alias_must_resolve_to_tier5(
    pipeline_files: tuple[Path, Path, Path]
) -> None:
    pipelines, models, trace = pipeline_files
    text = pipelines.read_text(encoding="utf-8").replace("fast: paid-fast", "fast: local-model")
    pipelines.write_text(text, encoding="utf-8")
    with pytest.raises(PipelineConfigError, match="must be frugality tier 5"):
        TieredPipelineRunner(config_path=pipelines, models_path=models, trace_path=trace)


def test_token_cap_and_dependency_order_fail_closed(
    pipeline_files: tuple[Path, Path, Path]
) -> None:
    pipelines, models, trace = pipeline_files
    text = pipelines.read_text(encoding="utf-8").replace("max_total_tokens: 30", "max_total_tokens: 29")
    pipelines.write_text(text, encoding="utf-8")
    with pytest.raises(PipelineConfigError, match="requests 30 tokens but cap is 29"):
        TieredPipelineRunner(config_path=pipelines, models_path=models, trace_path=trace)

    pipelines.write_text(
        text.replace("max_total_tokens: 29", "max_total_tokens: 30").replace(
            "input_from: classify", "input_from: future"
        ),
        encoding="utf-8",
    )
    with pytest.raises(PipelineConfigError, match="earlier stage"):
        TieredPipelineRunner(config_path=pipelines, models_path=models, trace_path=trace)
