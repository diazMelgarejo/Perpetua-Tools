from __future__ import annotations

import json
from pathlib import Path

import pytest

from orchestrator import tiered_pipeline as tp


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
    cost_reservation_usd: 0.25
    max_input_tokens: 512
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


def _runner(files: tuple[Path, Path, Path]) -> tp.TieredPipelineRunner:
    pipelines, models, trace = files
    return tp.TieredPipelineRunner(
        config_path=pipelines,
        models_path=models,
        trace_path=trace,
    )


@pytest.mark.asyncio
async def test_flag_defaults_off_and_never_dispatches(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(tp.PIPELINE_FLAG, raising=False)
    calls: list[str] = []

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        calls.append(stage)
        return "unexpected"

    with pytest.raises(tp.PipelineDisabledError):
        await _runner(pipeline_files).run("classify_then_generate", "hello", dispatch=dispatch)
    assert calls == []


def test_flag_requires_literal_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "true")
    assert tp.tiered_pipeline_enabled() is False
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    assert tp.tiered_pipeline_enabled() is True


@pytest.mark.asyncio
async def test_pipeline_runs_in_order_and_preserves_original_request(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    monkeypatch.delenv("ORAMASYS_OFFLINE", raising=False)
    calls: list[tuple[str, str, int, str]] = []

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        calls.append((model, prompt, max_tokens, stage))
        return "classification-result" if stage == "classify" else "final-result"

    result = await _runner(pipeline_files).run(
        "classify_then_generate", "ORIGINAL-REQUEST", dispatch=dispatch
    )

    assert [row[3] for row in calls] == ["classify", "generate"]
    assert calls[0][0] == "paid-fast"
    assert calls[1][0] == "paid-strong"
    assert calls[1][2] == 20
    assert "ORIGINAL-REQUEST" in calls[1][1]
    assert "classification-result" in calls[1][1]
    assert result.output == "final-result"
    assert result.requested_tokens == 30

    trace_text = pipeline_files[2].read_text(encoding="utf-8")
    trace_lines = [json.loads(line) for line in trace_text.splitlines()]
    assert [line["attributes"]["pipeline.stage"] for line in trace_lines] == [
        "classify",
        "generate",
    ]
    assert {line["attributes"]["status"] for line in trace_lines} == {"completed"}
    assert "ORIGINAL-REQUEST" not in trace_text
    assert "classification-result" not in trace_text


@pytest.mark.asyncio
async def test_gate_receives_explicit_override_contract(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    calls = []

    def deny(tier: int, **kwargs: object) -> tuple[bool, str]:
        calls.append((tier, kwargs))
        return False, "policy denied"

    monkeypatch.setattr(tp, "gate_permits", deny)

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        return "unexpected"

    with pytest.raises(tp.PipelinePolicyError, match="policy denied"):
        await _runner(pipeline_files).run(
            "classify_then_generate",
            "hello",
            dispatch=dispatch,
            override_confirmed=True,
            override_reason="operator approved this request",
        )
    assert calls == [
        (
            5,
            {
                "task_type": "reasoning",
                "privacy_critical": False,
                "override_confirmed": True,
                "override_reason": "operator approved this request",
            },
        )
    ]


@pytest.mark.asyncio
async def test_offline_policy_blocks_before_dispatch(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    monkeypatch.setenv("ORAMASYS_OFFLINE", "1")
    called = False

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        nonlocal called
        called = True
        return "no"

    with pytest.raises(tp.PipelinePolicyError, match="ORAMASYS_OFFLINE"):
        await _runner(pipeline_files).run("classify_then_generate", "hello", dispatch=dispatch)
    assert called is False


@pytest.mark.asyncio
async def test_privacy_critical_uses_existing_override_contract(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    monkeypatch.delenv("ORAMASYS_OFFLINE", raising=False)

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        return stage

    runner = _runner(pipeline_files)
    with pytest.raises(tp.PipelinePolicyError, match="override_confirmed"):
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
    assert result.output == "generate"


def test_model_alias_must_resolve_to_current_tier_five(
    pipeline_files: tuple[Path, Path, Path]
) -> None:
    pipelines, models, trace = pipeline_files
    pipelines.write_text(
        pipelines.read_text(encoding="utf-8").replace("fast: paid-fast", "fast: local-model"),
        encoding="utf-8",
    )
    with pytest.raises(tp.PipelineConfigError, match="must be frugality tier 5"):
        tp.TieredPipelineRunner(
            config_path=pipelines,
            models_path=models,
            trace_path=trace,
        )


def test_recipe_validation_fails_closed_for_token_and_dependency_errors(
    pipeline_files: tuple[Path, Path, Path]
) -> None:
    pipelines, models, trace = pipeline_files
    pipelines.write_text(
        pipelines.read_text(encoding="utf-8").replace("max_total_tokens: 30", "max_total_tokens: 29"),
        encoding="utf-8",
    )
    with pytest.raises(tp.PipelineConfigError, match="requests 30 tokens but cap is 29"):
        tp.TieredPipelineRunner(
            config_path=pipelines,
            models_path=models,
            trace_path=trace,
        )

    pipelines.write_text(
        pipelines.read_text(encoding="utf-8")
        .replace("max_total_tokens: 29", "max_total_tokens: 30")
        .replace("input_from: classify", "input_from: future"),
        encoding="utf-8",
    )
    with pytest.raises(tp.PipelineConfigError, match="earlier stage"):
        tp.TieredPipelineRunner(
            config_path=pipelines,
            models_path=models,
            trace_path=trace,
        )


def test_invalid_token_limits_fail_as_configuration_errors(
    pipeline_files: tuple[Path, Path, Path]
) -> None:
    pipelines, models, trace = pipeline_files
    pipelines.write_text(
        pipelines.read_text(encoding="utf-8").replace("max_total_tokens: 30", "max_total_tokens: invalid"),
        encoding="utf-8",
    )
    with pytest.raises(tp.PipelineConfigError, match="max_total_tokens must be an integer"):
        tp.TieredPipelineRunner(
            config_path=pipelines,
            models_path=models,
            trace_path=trace,
        )


@pytest.mark.asyncio
async def test_input_budget_blocks_before_paid_dispatch(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    pipelines, models, trace = pipeline_files
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    monkeypatch.setattr(tp, "gate_permits", lambda *args, **kwargs: (True, None))
    pipelines.write_text(
        pipelines.read_text(encoding="utf-8").replace("max_input_tokens: 512", "max_input_tokens: 4"),
        encoding="utf-8",
    )
    called = False

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        nonlocal called
        called = True
        return "unexpected"

    with pytest.raises(tp.PipelinePolicyError, match="max_input_tokens"):
        await tp.TieredPipelineRunner(
            config_path=pipelines,
            models_path=models,
            trace_path=trace,
        ).run("classify_then_generate", "six!!", dispatch=dispatch)
    assert called is False


@pytest.mark.asyncio
async def test_prior_stage_output_cannot_expand_the_next_input(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    pipelines, models, trace = pipeline_files
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    monkeypatch.setattr(tp, "gate_permits", lambda *args, **kwargs: (True, None))
    pipelines.write_text(
        pipelines.read_text(encoding="utf-8").replace("max_input_tokens: 512", "max_input_tokens: 64"),
        encoding="utf-8",
    )
    calls = []

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        calls.append(stage)
        return "x" * 80

    with pytest.raises(tp.PipelinePolicyError, match="max_input_tokens"):
        await tp.TieredPipelineRunner(
            config_path=pipelines,
            models_path=models,
            trace_path=trace,
        ).run("classify_then_generate", "ok", dispatch=dispatch)
    assert calls == ["classify"]


@pytest.mark.asyncio
async def test_empty_dispatch_output_is_rejected(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    monkeypatch.setattr(tp, "gate_permits", lambda *args, **kwargs: (True, None))

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        return ""

    with pytest.raises(tp.PipelineExecutionError, match="empty/non-text"):
        await _runner(pipeline_files).run("classify_then_generate", "hello", dispatch=dispatch)
