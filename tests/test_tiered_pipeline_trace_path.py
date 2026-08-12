from orchestrator.tiered_pipeline import DEFAULT_TRACE, TieredPipelineRunner


def test_empty_trace_path_env_uses_default(monkeypatch) -> None:
    monkeypatch.setenv("PT_PIPELINE_TRACE_PATH", "   ")
    runner = TieredPipelineRunner()
    assert runner.trace_path == DEFAULT_TRACE
