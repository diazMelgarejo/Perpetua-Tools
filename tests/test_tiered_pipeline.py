from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from orchestrator.tiered_pipeline import (
    PipelineApproval,
    PipelineConfigError,
    PipelinePolicyError,
    execute_tier5_pipeline,
    load_pipeline_config,
    pipelines_enabled,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "pipelines.yml"


def approval(**overrides):
    values = {
        "trace_id": "trace-human-001",
        "human_ref": "operator-confirmation-001",
        "purpose": "Generate an approved final answer after cheap classification",
        "recipe_id": "classify_then_generate",
        "allowed_route_tier": 5,
        "max_tokens": 4256,
        "max_cost_usd": 0.05,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
        "provider_scope": ("openrouter",),
    }
    values.update(overrides)
    return PipelineApproval(**values)


def test_feature_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("PIPELINE_TIERED_ENABLED", raising=False)
    assert pipelines_enabled() is False


@pytest.mark.asyncio
async def test_disabled_pipeline_makes_no_provider_call(monkeypatch):
    monkeypatch.delenv("PIPELINE_TIERED_ENABLED", raising=False)
    calls = []

    async def fake(*args):
        calls.append(args)
        return "never", 1, 0.0

    with pytest.raises(PipelinePolicyError, match="disabled"):
        await execute_tier5_pipeline(
            "hello",
            recipe_id="classify_then_generate",
            approval=approval(),
            stage_executor=fake,
        )
    assert calls == []


@pytest.mark.asyncio
async def test_offline_gate_blocks_before_provider(monkeypatch):
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "1")
    monkeypatch.setenv("ORAMASYS_OFFLINE", "1")
    calls = []

    async def fake(*args):
        calls.append(args)
        return "never", 1, 0.0

    with pytest.raises(PipelinePolicyError, match="ORAMASYS_OFFLINE"):
        await execute_tier5_pipeline(
            "hello",
            recipe_id="classify_then_generate",
            approval=approval(),
            stage_executor=fake,
        )
    assert calls == []


@pytest.mark.asyncio
async def test_privacy_critical_gate_blocks_before_provider(monkeypatch):
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "1")
    monkeypatch.delenv("ORAMASYS_OFFLINE", raising=False)
    calls = []

    async def fake(*args):
        calls.append(args)
        return "never", 1, 0.0

    with pytest.raises(PipelinePolicyError, match="ceiling"):
        await execute_tier5_pipeline(
            "sensitive",
            recipe_id="classify_then_generate",
            approval=approval(),
            privacy_critical=True,
            stage_executor=fake,
        )
    assert calls == []


@pytest.mark.asyncio
async def test_expired_or_wrong_scope_approval_is_rejected(monkeypatch):
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "1")
    monkeypatch.delenv("ORAMASYS_OFFLINE", raising=False)

    async def fake(*args):
        raise AssertionError("provider must not run")

    expired = approval(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    with pytest.raises(PipelinePolicyError, match="expired"):
        await execute_tier5_pipeline(
            "hello",
            recipe_id="classify_then_generate",
            approval=expired,
            stage_executor=fake,
        )

    wrong = approval(provider_scope=("other",))
    with pytest.raises(PipelinePolicyError, match="openrouter"):
        await execute_tier5_pipeline(
            "hello",
            recipe_id="classify_then_generate",
            approval=wrong,
            stage_executor=fake,
        )


@pytest.mark.asyncio
async def test_stage_order_and_inputs_are_deterministic(monkeypatch):
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "1")
    monkeypatch.delenv("ORAMASYS_OFFLINE", raising=False)
    seen = []

    async def fake(model, prompt, max_tokens, timeout):
        seen.append((model, prompt, max_tokens, timeout))
        if len(seen) == 1:
            return "classification: standard", 20, 0.001
        return "final answer", 40, 0.002

    result = await execute_tier5_pipeline(
        "original request",
        recipe_id="classify_then_generate",
        approval=approval(),
        stage_executor=fake,
    )

    assert [stage.name for stage in result.stages] == ["classify", "generate"]
    assert seen[0][0] == "openai/gpt-5.4-mini"
    assert "[original]\noriginal request" in seen[0][1]
    assert seen[1][0] == "anthropic/claude-sonnet-4.6"
    assert "[original]\noriginal request" in seen[1][1]
    assert "[classify]\nclassification: standard" in seen[1][1]
    assert result.output == "final answer"
    assert result.total_tokens == 60
    assert result.cost_usd == pytest.approx(0.003)


@pytest.mark.asyncio
async def test_cost_cap_stops_successor_stage(monkeypatch):
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "1")
    monkeypatch.delenv("ORAMASYS_OFFLINE", raising=False)
    calls = 0

    async def fake(*args):
        nonlocal calls
        calls += 1
        return "too expensive", 10, 0.051

    with pytest.raises(PipelinePolicyError, match="cost budget"):
        await execute_tier5_pipeline(
            "hello",
            recipe_id="classify_then_generate",
            approval=approval(),
            stage_executor=fake,
        )
    assert calls == 1


@pytest.mark.asyncio
async def test_trace_contains_metadata_not_prompt_output_or_secret(monkeypatch, tmp_path):
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "1")
    monkeypatch.delenv("ORAMASYS_OFFLINE", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "should-never-be-persisted")
    trace = tmp_path / "tier5.jsonl"

    async def fake(model, prompt, max_tokens, timeout):
        return "PRIVATE GENERATED OUTPUT", 5, 0.001

    await execute_tier5_pipeline(
        "PRIVATE ORIGINAL PROMPT",
        recipe_id="classify_then_generate",
        approval=approval(),
        trace_path=trace,
        stage_executor=fake,
    )
    text = trace.read_text(encoding="utf-8")
    assert "PRIVATE ORIGINAL PROMPT" not in text
    assert "PRIVATE GENERATED OUTPUT" not in text
    assert "should-never-be-persisted" not in text
    events = [json.loads(line) for line in text.splitlines()]
    assert all(event["tier"] == 5 for event in events)
    assert events[0]["event"] == "pipeline_start"
    assert events[-1]["event"] == "pipeline_complete"


def test_config_is_strict_and_current_recipe_fits_caps(tmp_path):
    config = load_pipeline_config(CONFIG)
    assert config["schema_version"] == 1
    assert config["limits"]["max_pipeline_stages"] == 3
    assert sum(
        stage["max_tokens"]
        for stage in config["recipes"]["classify_then_generate"]["stages"]
    ) <= config["limits"]["max_total_tokens"]

    bad = tmp_path / "bad.yml"
    bad.write_text(
        "schema_version: 1\nlimits: {}\nmodels: {}\nrecipes: {}\nextra: true\n",
        encoding="utf-8",
    )
    with pytest.raises(PipelineConfigError, match="unknown keys"):
        load_pipeline_config(bad)
