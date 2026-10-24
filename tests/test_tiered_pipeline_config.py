from orchestrator.tiered_pipeline import TieredPipelineRunner, tiered_pipeline_enabled


def test_repository_pipeline_config_resolves_ordered_tier_five_candidates(monkeypatch) -> None:
    """Verify default pipeline candidate order and the recipe token budget."""
    monkeypatch.delenv("PIPELINE_TIERED_ENABLED", raising=False)
    monkeypatch.delenv("PIPELINE_FAST_MODEL", raising=False)
    monkeypatch.delenv("PIPELINE_STRONG_MODEL", raising=False)
    runner = TieredPipelineRunner()
    recipe = runner.recipe("classify_then_generate")

    assert tiered_pipeline_enabled() is True
    assert recipe.stages[0].models == (
        "glm-5.2",
        "glm-5.1:cloud",
        "Qwen3.5-9B-MLX-4bit",
        "claude-sonnet-5-5",
    )
    assert recipe.stages[1].models == (
        "glm-5.2",
        "glm-5.1:cloud",
        "claude-sonnet-5-5",
        "Qwen3.5-9B-MLX-4bit",
    )
    assert sum(stage.max_tokens for stage in recipe.stages) <= recipe.max_total_tokens
    assert recipe.max_input_tokens > 0
    assert recipe.cost_reservation_usd > 0
