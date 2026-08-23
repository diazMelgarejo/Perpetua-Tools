"""TDD test suite for Tier-5 execution service and settlement semantics."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import pytest

from orchestrator.tiered_pipeline import (
    PIPELINE_TIER,
    DispatchResult,
    PipelineApproval,
    PipelineError,
    PipelinePolicyError,
    PipelineRecipe,
    PipelineStage,
    TieredPipelineRunner,
)
from orchestrator.tier5_budget import (
    BudgetConflictError,
    BudgetInsufficientError,
    MICROUSD_PER_USD,
    Tier5BudgetLedger,
)
from orchestrator.tier5_execution import (
    HMAC_KEY_ENV,
    Tier5ConfigurationError,
    Tier5ExecutionService,
    compute_request_fingerprint,
)


def _make_approval(
    *,
    trace_id: str = "valid-trace-12345",
    recipe: str = "deep_reasoning",
    max_tokens: int = 4096,
    max_cost_usd: float = 0.10,
    expires_in_minutes: int = 15,
) -> PipelineApproval:
    return PipelineApproval(
        trace_id=trace_id,
        approved_by="cole",
        purpose="Tier-5 execution service tests",
        recipe=recipe,
        route_tier=PIPELINE_TIER,
        max_tokens=max_tokens,
        max_cost_usd=max_cost_usd,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
        scope=("tier5",),
    )


def _make_runner(
    tmp_path: Path,
    *,
    cost_reservation_usd: float = 0.05,
    max_total_tokens: int = 2048,
    max_input_tokens: int = 2048,
) -> TieredPipelineRunner:
    models_file = tmp_path / "models.yml"
    models_file.write_text(
        """models:
  - name: paid-fast
    frugality_tier: 5
  - name: paid-strong
    frugality_tier: 5
""",
        encoding="utf-8",
    )
    config_file = tmp_path / "pipelines.yml"
    config_file.write_text(
        f"""
version: 1
models:
  fast: paid-fast
  strong: paid-strong
recipes:
  deep_reasoning:
    stages:
      - name: draft
        model: fast
        max_tokens: 1024
      - name: review
        model: strong
        max_tokens: 1024
        input_from: draft
    max_total_tokens: {max_total_tokens}
    max_input_tokens: {max_input_tokens}
    cost_reservation_usd: {cost_reservation_usd}
""",
        encoding="utf-8",
    )
    return TieredPipelineRunner(
        config_path=config_file,
        models_path=models_file,
        trace_path=tmp_path / "trace.jsonl",
    )


@pytest.fixture
def hmac_key(monkeypatch: pytest.MonkeyPatch) -> str:
    key = "test-secret-hmac-key-2026"
    monkeypatch.setenv(HMAC_KEY_ENV, key)
    monkeypatch.setenv("PIPELINE_TIERED_ENABLED", "1")
    return key


@pytest.fixture
def ledger(tmp_path: Path) -> Tier5BudgetLedger:
    return Tier5BudgetLedger(
        tmp_path / "budget.db",
        daily_limit_microusd=10 * MICROUSD_PER_USD,
    )


def test_hmac_key_missing_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(HMAC_KEY_ENV, raising=False)
    approval = _make_approval()
    with pytest.raises(Tier5ConfigurationError, match="PT_TIER5_LEDGER_HMAC_KEY is required"):
        compute_request_fingerprint("deep_reasoning", "test prompt", approval)


def test_request_fingerprint_deterministic_and_sensitive(hmac_key: str) -> None:
    approval = _make_approval()
    fp1 = compute_request_fingerprint("deep_reasoning", "test prompt", approval)
    fp2 = compute_request_fingerprint("deep_reasoning", "test prompt", approval)
    assert fp1 == fp2
    assert len(fp1) == 64

    fp_diff_prompt = compute_request_fingerprint("deep_reasoning", "other prompt", approval)
    assert fp1 != fp_diff_prompt

    diff_approval = _make_approval(trace_id="other-trace-67890")
    fp_diff_trace = compute_request_fingerprint("deep_reasoning", "test prompt", diff_approval)
    assert fp1 != fp_diff_trace


@pytest.mark.asyncio
async def test_pre_dispatch_failure_releases_hold(
    tmp_path: Path, ledger: Tier5BudgetLedger, hmac_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A gate refusal or validation error before any provider dispatch must release the hold."""
    runner = _make_runner(tmp_path)
    service = Tier5ExecutionService(ledger=ledger, runner=runner)
    approval = _make_approval()

    # Simulate gate denial by forcing gate_permits to deny
    monkeypatch.setattr(
        "orchestrator.tiered_pipeline.gate_permits",
        lambda *args, **kwargs: (False, "policy denied"),
    )

    async def mock_dispatch(model: str, prompt: str, max_tokens: int, stage_name: str) -> DispatchResult:
        raise AssertionError("dispatch must not be called when gate denies")

    with pytest.raises(PipelinePolicyError, match="policy denied"):
        await service.execute(
            run_id="run-gate-fail-001",
            idempotency_key="550e8400-e29b-41d4-a716-446655440001",
            recipe_name="deep_reasoning",
            prompt="Hello world",
            approval=approval,
            dispatch=mock_dispatch,
        )

    # Verify reservation is RELEASED and held is 0
    row = ledger.get_reservation("run-gate-fail-001")
    assert row is not None
    assert row.state == "RELEASED"
    assert row.held_microusd == 0
    assert row.settled_microusd == 0


@pytest.mark.asyncio
async def test_dispatch_marker_committed_before_provider_io(
    tmp_path: Path, ledger: Tier5BudgetLedger, hmac_key: str
) -> None:
    """A spy proves the stage marker is committed in SQLite BEFORE provider I/O begins."""
    runner = _make_runner(tmp_path)
    service = Tier5ExecutionService(ledger=ledger, runner=runner)
    approval = _make_approval()
    run_id = "run-marker-spy-001"
    io_order: list[str] = []

    async def spy_dispatch(model: str, prompt: str, max_tokens: int, stage_name: str) -> DispatchResult:
        # Check SQLite during dispatch to verify marker was ALREADY committed
        row = ledger.get_reservation(run_id)
        assert row is not None
        assert row.state == "DISPATCHED"
        assert ledger.is_stage_marked(run_id, stage_name)
        io_order.append(f"io:{stage_name}")
        return DispatchResult(text=f"output of {stage_name}", total_tokens=100, cost_usd=0.01)

    result, reservation = await service.execute(
        run_id=run_id,
        idempotency_key="550e8400-e29b-41d4-a716-446655440002",
        recipe_name="deep_reasoning",
        prompt="Spy test prompt",
        approval=approval,
        dispatch=spy_dispatch,
    )

    assert io_order == ["io:draft", "io:review"]
    assert reservation.state == "SETTLED"


@pytest.mark.asyncio
async def test_post_marker_settle_failure_does_not_mask_original_exception(
    tmp_path: Path, ledger: Tier5BudgetLedger, hmac_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If ledger.settle() itself raises while handling a post-marker pipeline
    failure (e.g. BudgetUnavailableError on lock contention), the ORIGINAL
    pipeline exception must still propagate -- not the settlement error.
    Previously the marker branch had no try/except around settle(), so a
    settle failure replaced the real error, and orchestrator/fastapi_app.py's
    caller would return a misleading 503 'budget ledger unavailable' instead
    of surfacing the actual provider/policy failure."""
    runner = _make_runner(tmp_path, cost_reservation_usd=0.05)
    service = Tier5ExecutionService(ledger=ledger, runner=runner)
    approval = _make_approval()
    run_id = "run-settle-fails-001"

    async def timeout_dispatch(model: str, prompt: str, max_tokens: int, stage_name: str) -> DispatchResult:
        raise TimeoutError("provider timed out after dispatch marker")

    monkeypatch.setattr(
        ledger,
        "settle",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("ledger lock contention")),
    )

    with pytest.raises(TimeoutError, match="provider timed out"):
        await service.execute(
            run_id=run_id,
            idempotency_key="550e8400-e29b-41d4-a716-446655440009",
            recipe_name="deep_reasoning",
            prompt="Settle-fails test prompt",
            approval=approval,
            dispatch=timeout_dispatch,
        )


@pytest.mark.asyncio
async def test_post_marker_timeout_consumes_full_hold(
    tmp_path: Path, ledger: Tier5BudgetLedger, hmac_key: str
) -> None:
    """A timeout/failure occurring after a stage marker is committed consumes the complete hold."""
    runner = _make_runner(tmp_path, cost_reservation_usd=0.05)
    service = Tier5ExecutionService(ledger=ledger, runner=runner)
    approval = _make_approval()
    run_id = "run-timeout-001"

    async def timeout_dispatch(model: str, prompt: str, max_tokens: int, stage_name: str) -> DispatchResult:
        raise TimeoutError("provider timed out after dispatch marker")

    with pytest.raises(TimeoutError, match="provider timed out"):
        await service.execute(
            run_id=run_id,
            idempotency_key="550e8400-e29b-41d4-a716-446655440003",
            recipe_name="deep_reasoning",
            prompt="Timeout test prompt",
            approval=approval,
            dispatch=timeout_dispatch,
        )

    row = ledger.get_reservation(run_id)
    assert row is not None
    assert row.state == "SETTLED"
    assert row.held_microusd == 0
    # Consumed the full held amount (50,000 microUSD = $0.05)
    assert row.settled_microusd == int(0.05 * MICROUSD_PER_USD)


@pytest.mark.asyncio
async def test_partial_pipeline_failure_consumes_held_amount(
    tmp_path: Path, ledger: Tier5BudgetLedger, hmac_key: str
) -> None:
    """If stage 1 succeeds but stage 2 fails, the full hold is consumed (ambiguous expenditure)."""
    runner = _make_runner(tmp_path, cost_reservation_usd=0.05)
    service = Tier5ExecutionService(ledger=ledger, runner=runner)
    approval = _make_approval()
    run_id = "run-partial-001"

    async def partial_dispatch(model: str, prompt: str, max_tokens: int, stage_name: str) -> DispatchResult:
        if stage_name == "draft":
            return DispatchResult(text="draft result", total_tokens=50, cost_usd=0.005)
        raise RuntimeError("stage review crashed")

    with pytest.raises(RuntimeError, match="stage review crashed"):
        await service.execute(
            run_id=run_id,
            idempotency_key="550e8400-e29b-41d4-a716-446655440004",
            recipe_name="deep_reasoning",
            prompt="Partial failure test",
            approval=approval,
            dispatch=partial_dispatch,
        )

    row = ledger.get_reservation(run_id)
    assert row is not None
    assert row.state == "SETTLED"
    assert row.settled_microusd == int(0.05 * MICROUSD_PER_USD)


@pytest.mark.asyncio
async def test_successful_run_releases_verified_unused_difference(
    tmp_path: Path, ledger: Tier5BudgetLedger, hmac_key: str
) -> None:
    """A completed run with verified telemetry settles only the actual spend and releases the remainder."""
    runner = _make_runner(tmp_path, cost_reservation_usd=0.05)
    service = Tier5ExecutionService(ledger=ledger, runner=runner)
    approval = _make_approval()
    run_id = "run-success-001"

    # Held is $0.05 (50,000 microUSD). Actual spend is $0.01 + $0.01 = $0.02 (20,000 microUSD).
    async def success_dispatch(model: str, prompt: str, max_tokens: int, stage_name: str) -> DispatchResult:
        return DispatchResult(text=f"valid output from {stage_name}", total_tokens=100, cost_usd=0.01)

    result, reservation = await service.execute(
        run_id=run_id,
        idempotency_key="550e8400-e29b-41d4-a716-446655440005",
        recipe_name="deep_reasoning",
        prompt="Success prompt",
        approval=approval,
        dispatch=success_dispatch,
    )

    assert result.output == "valid output from review"
    assert reservation.state == "SETTLED"
    assert reservation.held_microusd == 0
    # Actual spend settled: $0.02 = 20,000 microUSD
    assert reservation.settled_microusd == int(0.02 * MICROUSD_PER_USD)


@pytest.mark.asyncio
async def test_successful_run_with_missing_cost_consumes_full_hold(
    tmp_path: Path, ledger: Tier5BudgetLedger, hmac_key: str
) -> None:
    """If provider returns text but no cost telemetry, unproven unused funds cannot be released."""
    runner = _make_runner(tmp_path, cost_reservation_usd=0.05)
    service = Tier5ExecutionService(ledger=ledger, runner=runner)
    approval = _make_approval()
    run_id = "run-no-telemetry-001"

    async def no_cost_dispatch(model: str, prompt: str, max_tokens: int, stage_name: str) -> DispatchResult:
        return DispatchResult(text=f"valid output from {stage_name}", total_tokens=None, cost_usd=None)

    result, reservation = await service.execute(
        run_id=run_id,
        idempotency_key="550e8400-e29b-41d4-a716-446655440006",
        recipe_name="deep_reasoning",
        prompt="No telemetry prompt",
        approval=approval,
        dispatch=no_cost_dispatch,
    )

    assert reservation.state == "SETTLED"
    assert reservation.settled_microusd == int(0.05 * MICROUSD_PER_USD)


@pytest.mark.asyncio
async def test_idempotency_replay_returns_existing_reservation(
    tmp_path: Path, ledger: Tier5BudgetLedger, hmac_key: str
) -> None:
    """Same idempotency key and same fingerprint returns the existing run without re-executing."""
    runner = _make_runner(tmp_path)
    service = Tier5ExecutionService(ledger=ledger, runner=runner)
    approval = _make_approval()
    run_id = "run-idemp-001"
    key = "550e8400-e29b-41d4-a716-446655440007"
    call_count = 0

    async def dispatch_count(model: str, prompt: str, max_tokens: int, stage_name: str) -> DispatchResult:
        nonlocal call_count
        call_count += 1
        return DispatchResult(text="output", total_tokens=100, cost_usd=0.01)

    result1, res1 = await service.execute(
        run_id=run_id,
        idempotency_key=key,
        recipe_name="deep_reasoning",
        prompt="Idempotent prompt",
        approval=approval,
        dispatch=dispatch_count,
    )
    assert call_count == 2  # 2 stages
    assert result1.replay is False, "the real, first execution must not be flagged as a replay"

    # Second call with identical parameters
    result2, res2 = await service.execute(
        run_id=run_id,
        idempotency_key=key,
        recipe_name="deep_reasoning",
        prompt="Idempotent prompt",
        approval=approval,
        dispatch=dispatch_count,
    )
    # Must NOT call dispatch again
    assert call_count == 2
    assert res2.state == "SETTLED"
    assert res2.run_id == run_id
    # A client polling this endpoint must be able to tell "this response is
    # a replay of an already-settled run, its empty output is not a bug"
    # from "the run genuinely produced no output" -- see
    # orchestrator/fastapi_app.py's "replay" field in the /orchestrate
    # response.
    assert result2.replay is True
    assert result2.output == ""


@pytest.mark.asyncio
async def test_idempotency_conflict_raises_error(
    tmp_path: Path, ledger: Tier5BudgetLedger, hmac_key: str
) -> None:
    """Same idempotency key with different fingerprint raises BudgetConflictError."""
    runner = _make_runner(tmp_path)
    service = Tier5ExecutionService(ledger=ledger, runner=runner)
    approval1 = _make_approval()
    key = "550e8400-e29b-41d4-a716-446655440008"

    async def simple_dispatch(model: str, prompt: str, max_tokens: int, stage_name: str) -> DispatchResult:
        return DispatchResult(text="output", total_tokens=100, cost_usd=0.01)

    await service.execute(
        run_id="run-conflict-001",
        idempotency_key=key,
        recipe_name="deep_reasoning",
        prompt="First prompt",
        approval=approval1,
        dispatch=simple_dispatch,
    )

    # Different prompt with same key
    with pytest.raises(BudgetConflictError, match="conflicts with an existing run"):
        await service.execute(
            run_id="run-conflict-002",
            idempotency_key=key,
            recipe_name="deep_reasoning",
            prompt="Different conflicting prompt",
            approval=approval1,
            dispatch=simple_dispatch,
        )
