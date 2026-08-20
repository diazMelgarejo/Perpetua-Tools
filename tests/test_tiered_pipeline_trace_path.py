import pytest

from orchestrator.tiered_pipeline import (
    DEFAULT_TRACE,
    PipelineApprovalError,
    TieredPipelineRunner,
    _approval_artifact_path,
)


def test_empty_trace_path_env_uses_default(monkeypatch) -> None:
    monkeypatch.delenv("PIPELINE_FAST_MODEL", raising=False)
    monkeypatch.delenv("PIPELINE_STRONG_MODEL", raising=False)
    monkeypatch.setenv("PT_PIPELINE_TRACE_PATH", "   ")
    runner = TieredPipelineRunner()
    assert runner.trace_path == DEFAULT_TRACE


@pytest.mark.unit
@pytest.mark.parametrize("trace_id", ["../../escape", "with.dot", "a" * 129])
def test_direct_approval_path_rejects_invalid_trace_id(tmp_path, trace_id: str) -> None:
    with pytest.raises(PipelineApprovalError):
        _approval_artifact_path(tmp_path, trace_id)
