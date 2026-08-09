from __future__ import annotations

import time
from pathlib import Path

import pytest

from orchestrator.frugality_router import ResolvedRoute, ToolCallSpec
from orchestrator.tiered_pipeline import ApprovalRecord, PipelinePolicyError, TieredPipelineRunner

CONFIG = Path(__file__).parents[1] / "config/pipelines.yml"
ROUTE = ResolvedRoute(tier=5, backend="openrouter", escalation_reason="human-approved paid pipeline")
SPEC = ToolCallSpec(task_type="reasoning", escalation_reason="human-approved paid pipeline")


def approval(**overrides):
    data = dict(trace_id="trace-1", human_ref="operator", purpose="bounded synthesis",
                recipe_id="classify_then_generate", allowed_route_tier=5,
                max_tokens=4256, max_cost_usd=0.05, expires_at=time.time()+300,
                provider_scope=("openrouter",))
    data.update(overrides)
    return ApprovalRecord(**data)


def test_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("PIPELINE_TIERED_ENABLED", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    calls=[]
    with pytest.raises(PipelinePolicyError, match="disabled"):
        TieredPipelineRunner(CONFIG, lambda *a: calls.append(a)).run(route=ROUTE,spec=SPEC,recipe_id="classify_then_generate",task_input="x",approval=approval())
    assert calls == []


def test_offline_and_privacy_deny_before_egress(monkeypatch):
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "1"); monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    calls=[]; runner=TieredPipelineRunner(CONFIG, lambda *a: calls.append(a))
    monkeypatch.setenv("ORAMASYS_OFFLINE", "1")
    with pytest.raises(PipelinePolicyError, match="offline/privacy"):
        runner.run(route=ROUTE,spec=SPEC,recipe_id="classify_then_generate",task_input="x",approval=approval())
    monkeypatch.delenv("ORAMASYS_OFFLINE", raising=False)
    with pytest.raises(PipelinePolicyError, match="offline/privacy"):
        runner.run(route=ROUTE,spec=ToolCallSpec(privacy_critical=True),recipe_id="classify_then_generate",task_input="x",approval=approval())
    assert calls == []


def test_approval_required_and_must_match(monkeypatch):
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "1"); monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    runner=TieredPipelineRunner(CONFIG, lambda *a: {"text":"x","tokens":1,"cost_usd":0.001})
    with pytest.raises(PipelinePolicyError, match="expired"):
        runner.run(route=ROUTE,spec=SPEC,recipe_id="classify_then_generate",task_input="x",approval=approval(expires_at=time.time()-1))
    with pytest.raises(PipelinePolicyError, match="does not match"):
        runner.run(route=ROUTE,spec=SPEC,recipe_id="classify_then_generate",task_input="x",approval=approval(allowed_route_tier=4))


def test_stage_order_and_input_from(monkeypatch):
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "1"); monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    calls=[]
    def invoke(model_class,prompt,max_tokens):
        calls.append((model_class,prompt,max_tokens))
        return {"text": f"out-{len(calls)}", "tokens": 10, "cost_usd": 0.001}
    result=TieredPipelineRunner(CONFIG,invoke).run(route=ROUTE,spec=SPEC,recipe_id="classify_then_generate",task_input="original",approval=approval())
    assert calls == [("fast","original",256),("strong","out-1",4000)]
    assert result.output == "out-2" and result.tokens_used == 20
    assert [s["stage_id"] for s in result.stages] == ["classify","generate"]


def test_budget_blocks_before_stage_that_would_exceed(monkeypatch):
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "1"); monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    calls=[]
    def invoke(*args): calls.append(args); return {"text":"ok","tokens":1,"cost_usd":0.001}
    with pytest.raises(PipelinePolicyError, match="token budget"):
        TieredPipelineRunner(CONFIG,invoke).run(route=ROUTE,spec=SPEC,recipe_id="classify_then_generate",task_input="x",approval=approval(max_tokens=300))
    assert len(calls) == 1
