from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from orchestrator import tiered_pipeline as tp


def _write_config(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def _valid_config(path: Path) -> Path:
    return _write_config(
        path,
        """version: 1
provider: openrouter
models:
  fast:
    env: PIPELINE_FAST_MODEL
  strong:
    env: PIPELINE_STRONG_MODEL
limits:
  max_total_tokens: 1024
recipes:
  classify_then_generate:
    - name: classify
      model: fast
      max_tokens: 128
    - name: generate
      model: strong
      max_tokens: 512
      input_from: classify
""",
    )


def _ready_env(monkeypatch) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    monkeypatch.setenv("PIPELINE_FAST_MODEL", "fast-model")
    monkeypatch.setenv("PIPELINE_STRONG_MODEL", "strong-model")
    monkeypatch.delenv("ORAMASYS_OFFLINE", raising=False)


def test_pipeline_flag_is_explicit_and_key_presence_does_not_enable(monkeypatch) -> None:
    monkeypatch.delenv(tp.PIPELINE_FLAG, raising=False)
    monkeypatch.setenv(tp.OPENROUTER_KEY_ENV, "present-but-not-enabling")
    assert tp.tiered_pipeline_enabled() is False
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    assert tp.tiered_pipeline_enabled() is True


def test_disabled_pipeline_never_dispatches(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "0")
    called = False

    async def dispatch(model: str, prompt: str, max_tokens: int) -> str:
        nonlocal called
        called = True
        return "unexpected"

    runner = tp.TieredPipelineRunner(_valid_config(tmp_path / "pipelines.yml"), dispatch)
    with pytest.raises(tp.PipelineDisabledError):
        asyncio.run(runner.run("classify_then_generate", "hello"))
    assert called is False


def test_pipeline_consults_canonical_tier5_gate(tmp_path, monkeypatch) -> None:
    _ready_env(monkeypatch)
    calls = []

    def deny(tier, **kwargs):
        calls.append((tier, kwargs))
        return False, "policy denied"

    monkeypatch.setattr(tp, "gate_permits", deny)

    async def dispatch(model: str, prompt: str, max_tokens: int) -> str:
        return "unexpected"

    runner = tp.TieredPipelineRunner(_valid_config(tmp_path / "pipelines.yml"), dispatch)
    with pytest.raises(tp.PipelinePolicyError, match="policy denied"):
        asyncio.run(
            runner.run(
                "classify_then_generate",
                "hello",
                task_type="reasoning",
                privacy_critical=True,
            )
        )
    assert calls == [(5, {"task_type": "reasoning", "privacy_critical": True})]


def test_real_offline_gate_blocks_tier5(tmp_path, monkeypatch) -> None:
    _ready_env(monkeypatch)
    monkeypatch.setenv("ORAMASYS_OFFLINE", "1")

    async def dispatch(model: str, prompt: str, max_tokens: int) -> str:
        return "unexpected"

    runner = tp.TieredPipelineRunner(_valid_config(tmp_path / "pipelines.yml"), dispatch)
    with pytest.raises(tp.PipelinePolicyError, match="ORAMASYS_OFFLINE"):
        asyncio.run(runner.run("classify_then_generate", "hello"))


def test_real_privacy_gate_blocks_tier5(tmp_path, monkeypatch) -> None:
    _ready_env(monkeypatch)

    async def dispatch(model: str, prompt: str, max_tokens: int) -> str:
        return "unexpected"

    runner = tp.TieredPipelineRunner(_valid_config(tmp_path / "pipelines.yml"), dispatch)
    with pytest.raises(tp.PipelinePolicyError, match="tier 5 exceeds"):
        asyncio.run(
            runner.run(
                "classify_then_generate",
                "hello",
                privacy_critical=True,
            )
        )


def test_stage_order_and_input_from_are_deterministic(tmp_path, monkeypatch) -> None:
    _ready_env(monkeypatch)
    monkeypatch.setattr(tp, "gate_permits", lambda *args, **kwargs: (True, None))
    calls = []

    async def dispatch(model: str, prompt: str, max_tokens: int) -> str:
        calls.append((model, prompt, max_tokens))
        return "classified" if model == "fast-model" else "generated"

    runner = tp.TieredPipelineRunner(_valid_config(tmp_path / "pipelines.yml"), dispatch)
    result = asyncio.run(runner.run("classify_then_generate", "original"))

    assert calls == [
        ("fast-model", "original", 128),
        ("strong-model", "classified", 512),
    ]
    assert result.output == "generated"
    assert result.stage_outputs == {"classify": "classified", "generate": "generated"}


def test_forward_input_reference_fails_closed(tmp_path, monkeypatch) -> None:
    _ready_env(monkeypatch)
    monkeypatch.setattr(tp, "gate_permits", lambda *args, **kwargs: (True, None))
    config = _write_config(
        tmp_path / "pipelines.yml",
        """models:
  fast:
    id: fast-model
recipes:
  bad:
    - name: first
      model: fast
      max_tokens: 32
      input_from: later
    - name: later
      model: fast
      max_tokens: 32
""",
    )
    runner = tp.TieredPipelineRunner(config)
    with pytest.raises(tp.PipelineConfigError, match="earlier stage"):
        asyncio.run(runner.run("bad", "hello"))


def test_total_token_budget_fails_closed(tmp_path, monkeypatch) -> None:
    _ready_env(monkeypatch)
    monkeypatch.setattr(tp, "gate_permits", lambda *args, **kwargs: (True, None))
    config = _write_config(
        tmp_path / "pipelines.yml",
        """models:
  fast:
    id: fast-model
limits:
  max_total_tokens: 10
recipes:
  too_large:
    - name: first
      model: fast
      max_tokens: 11
""",
    )
    runner = tp.TieredPipelineRunner(config)
    with pytest.raises(tp.PipelineConfigError, match="token budget"):
        asyncio.run(runner.run("too_large", "hello"))


def test_trace_records_metadata_not_prompt_or_output(tmp_path, monkeypatch) -> None:
    _ready_env(monkeypatch)
    monkeypatch.setattr(tp, "gate_permits", lambda *args, **kwargs: (True, None))
    trace = tmp_path / "trace.jsonl"

    async def dispatch(model: str, prompt: str, max_tokens: int) -> str:
        return "sensitive-output"

    runner = tp.TieredPipelineRunner(
        _valid_config(tmp_path / "pipelines.yml"), dispatch, trace
    )
    asyncio.run(runner.run("classify_then_generate", "sensitive-input"))

    rows = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    assert {row["attributes"]["ot.tool.tier"] for row in rows} == {5}
    assert {row["attributes"]["pipeline.recipe"] for row in rows} == {
        "classify_then_generate"
    }
    serialized = trace.read_text(encoding="utf-8")
    assert "sensitive-input" not in serialized
    assert "sensitive-output" not in serialized


def test_default_dispatcher_requires_runtime_secret(monkeypatch) -> None:
    monkeypatch.delenv(tp.OPENROUTER_KEY_ENV, raising=False)
    with pytest.raises(tp.PipelineExecutionError, match="OPENROUTER_API_KEY"):
        asyncio.run(tp._dispatch_openrouter("model", "prompt", 16))
