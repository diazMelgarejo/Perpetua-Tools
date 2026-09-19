from orchestrator.tiered_pipeline import TieredPipelineRunner, tiered_pipeline_enabled


def test_repository_pipeline_config_resolves_ordered_tier_five_candidates(monkeypatch) -> None:
    monkeypatch.delenv("PIPELINE_TIERED_ENABLED", raising=False)
    monkeypatch.delenv("PIPELINE_FAST_MODEL", raising=False)
    monkeypatch.delenv("PIPELINE_STRONG_MODEL", raising=False)
    runner = TieredPipelineRunner()
    recipe = runner.recipe("classify_then_generate")

    assert tiered_pipeline_enabled() is True
    assert recipe.stages[0].models == (
        "openrouter-gpt-4o-mini",
        "glm-5.2",
        "claude-sonnet-5",
    )
    assert recipe.stages[1].models == (
        "openrouter-claude-sonnet-4.6",
        "claude-sonnet-5",
        "glm-5.2",
    )
    assert sum(stage.max_tokens for stage in recipe.stages) <= recipe.max_total_tokens
    assert recipe.max_input_tokens > 0
    assert recipe.cost_reservation_usd > 0
