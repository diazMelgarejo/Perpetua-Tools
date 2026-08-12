from orchestrator.tiered_pipeline import TieredPipelineRunner


def test_repository_pipeline_config_resolves_current_tier_five_models() -> None:
    runner = TieredPipelineRunner()
    recipe = runner.recipe("classify_then_generate")

    assert [stage.model for stage in recipe.stages] == ["glm-5.2", "claude-sonnet-5"]
    assert sum(stage.max_tokens for stage in recipe.stages) <= recipe.max_total_tokens
    assert recipe.max_input_tokens > 0
    assert recipe.cost_reservation_usd > 0
