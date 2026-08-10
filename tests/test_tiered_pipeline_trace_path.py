from pathlib import Path

from orchestrator.tiered_pipeline import TieredPipelineRunner


def test_empty_trace_path_env_uses_default(monkeypatch) -> None:
    monkeypatch.setenv("PT_PIPELINE_TRACE_PATH", "   ")
    runner = TieredPipelineRunner()
    expected = Path(__file__).resolve().parents[1] / ".state/frugality_pipeline.jsonl"
    assert runner.trace_path == expected
