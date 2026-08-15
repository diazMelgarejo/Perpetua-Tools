from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from orchestrator import tiered_pipeline as tp


@pytest.fixture
def pipeline_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    models = tmp_path / "models.yml"
    models.write_text(
        """models:
  - name: paid-fast
    frugality_tier: 5
  - name: paid-strong
    frugality_tier: 5
  - name: local-model
    frugality_tier: 1
""",
        encoding="utf-8",
    )
    pipelines = tmp_path / "pipelines.yml"
    pipelines.write_text(
        """version: 1
models:
  fast: paid-fast
  strong: paid-strong
recipes:
  classify_then_generate:
    max_total_tokens: 30
    cost_reservation_usd: 0.25
    max_input_tokens: 512
    stages:
      - name: classify
        model: fast
        max_tokens: 10
        instruction: classify
      - name: generate
        model: strong
        max_tokens: 20
        input_from: classify
        instruction: generate
""",
        encoding="utf-8",
    )
    return pipelines, models, tmp_path / "trace.jsonl"


def _runner(files: tuple[Path, Path, Path]) -> tp.TieredPipelineRunner:
    pipelines, models, trace = files
    return tp.TieredPipelineRunner(
        config_path=pipelines,
        models_path=models,
        trace_path=trace,
    )


def _approval(**overrides: object) -> tp.PipelineApproval:
    """A valid approval for the ``classify_then_generate`` fixture recipe.

    Defaults satisfy every check in ``_validate_approval``; individual tests
    override exactly the field(s) they want to violate.
    """
    fields: dict[str, object] = {
        "trace_id": "trace-abc123",
        "approved_by": "operator@example.com",
        "purpose": "test run",
        "recipe": "classify_then_generate",
        "route_tier": tp.PIPELINE_TIER,
        "max_tokens": 30,
        "max_cost_usd": 0.25,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "scope": ("openrouter",),
    }
    fields.update(overrides)
    return tp.PipelineApproval(**fields)


@pytest.mark.asyncio
async def test_flag_defaults_off_and_never_dispatches(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(tp.PIPELINE_FLAG, raising=False)
    calls: list[str] = []

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        calls.append(stage)
        return "unexpected"

    with pytest.raises(tp.PipelineDisabledError):
        await _runner(pipeline_files).run(
            "classify_then_generate", "hello", approval=_approval(), dispatch=dispatch
        )
    assert calls == []


def test_flag_requires_literal_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "true")
    assert tp.tiered_pipeline_enabled() is False
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    assert tp.tiered_pipeline_enabled() is True


@pytest.mark.asyncio
async def test_pipeline_runs_in_order_and_preserves_original_request(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    monkeypatch.delenv("ORAMASYS_OFFLINE", raising=False)
    calls: list[tuple[str, str, int, str]] = []

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        calls.append((model, prompt, max_tokens, stage))
        return "classification-result" if stage == "classify" else "final-result"

    approval = _approval()
    result = await _runner(pipeline_files).run(
        "classify_then_generate", "ORIGINAL-REQUEST", approval=approval, dispatch=dispatch
    )

    assert [row[3] for row in calls] == ["classify", "generate"]
    assert calls[0][0] == "paid-fast"
    assert calls[1][0] == "paid-strong"
    assert calls[1][2] == 20
    assert "ORIGINAL-REQUEST" in calls[1][1]
    assert "classification-result" in calls[1][1]
    assert result.output == "final-result"
    assert result.requested_tokens == 30

    trace_text = pipeline_files[2].read_text(encoding="utf-8")
    trace_lines = [json.loads(line) for line in trace_text.splitlines()]
    assert [line["attributes"]["pipeline.stage"] for line in trace_lines] == [
        "classify",
        "generate",
    ]
    assert {line["attributes"]["status"] for line in trace_lines} == {"completed"}
    assert {line["attributes"]["pipeline.trace_id"] for line in trace_lines} == {
        approval.trace_id
    }
    assert {line["attributes"]["pipeline.error_class"] for line in trace_lines} == {None}
    assert "ORIGINAL-REQUEST" not in trace_text
    assert "classification-result" not in trace_text
    assert approval.approved_by not in trace_text
    assert approval.purpose not in trace_text


@pytest.mark.asyncio
async def test_gate_receives_explicit_override_contract(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    calls = []

    def deny(tier: int, **kwargs: object) -> tuple[bool, str]:
        calls.append((tier, kwargs))
        return False, "policy denied"

    monkeypatch.setattr(tp, "gate_permits", deny)

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        return "unexpected"

    with pytest.raises(tp.PipelinePolicyError, match="policy denied"):
        await _runner(pipeline_files).run(
            "classify_then_generate",
            "hello",
            approval=_approval(),
            dispatch=dispatch,
            override_confirmed=True,
            override_reason="operator approved this request",
        )
    assert calls == [
        (
            5,
            {
                "task_type": "reasoning",
                "privacy_critical": False,
                "override_confirmed": True,
                "override_reason": "operator approved this request",
            },
        )
    ]


@pytest.mark.asyncio
async def test_offline_policy_blocks_before_dispatch(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    monkeypatch.setenv("ORAMASYS_OFFLINE", "1")
    called = False

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        nonlocal called
        called = True
        return "no"

    with pytest.raises(tp.PipelinePolicyError, match="ORAMASYS_OFFLINE"):
        await _runner(pipeline_files).run(
            "classify_then_generate", "hello", approval=_approval(), dispatch=dispatch
        )
    assert called is False


@pytest.mark.asyncio
async def test_privacy_critical_uses_existing_override_contract(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    monkeypatch.delenv("ORAMASYS_OFFLINE", raising=False)

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        return stage

    runner = _runner(pipeline_files)
    with pytest.raises(tp.PipelinePolicyError, match="override_confirmed"):
        await runner.run(
            "classify_then_generate",
            "hello",
            approval=_approval(),
            dispatch=dispatch,
            privacy_critical=True,
        )

    result = await runner.run(
        "classify_then_generate",
        "hello",
        approval=_approval(),
        dispatch=dispatch,
        privacy_critical=True,
        override_confirmed=True,
        override_reason="operator explicitly approved paid cloud execution",
    )
    assert result.output == "generate"


def test_model_alias_must_resolve_to_current_tier_five(
    pipeline_files: tuple[Path, Path, Path]
) -> None:
    pipelines, models, trace = pipeline_files
    pipelines.write_text(
        pipelines.read_text(encoding="utf-8").replace("fast: paid-fast", "fast: local-model"),
        encoding="utf-8",
    )
    with pytest.raises(tp.PipelineConfigError, match="must be frugality tier 5"):
        tp.TieredPipelineRunner(
            config_path=pipelines,
            models_path=models,
            trace_path=trace,
        )


def test_recipe_validation_fails_closed_for_token_and_dependency_errors(
    pipeline_files: tuple[Path, Path, Path]
) -> None:
    pipelines, models, trace = pipeline_files
    pipelines.write_text(
        pipelines.read_text(encoding="utf-8").replace("max_total_tokens: 30", "max_total_tokens: 29"),
        encoding="utf-8",
    )
    with pytest.raises(tp.PipelineConfigError, match="requests 30 tokens but cap is 29"):
        tp.TieredPipelineRunner(
            config_path=pipelines,
            models_path=models,
            trace_path=trace,
        )

    pipelines.write_text(
        pipelines.read_text(encoding="utf-8")
        .replace("max_total_tokens: 29", "max_total_tokens: 30")
        .replace("input_from: classify", "input_from: future"),
        encoding="utf-8",
    )
    with pytest.raises(tp.PipelineConfigError, match="earlier stage"):
        tp.TieredPipelineRunner(
            config_path=pipelines,
            models_path=models,
            trace_path=trace,
        )


def test_invalid_token_limits_fail_as_configuration_errors(
    pipeline_files: tuple[Path, Path, Path]
) -> None:
    pipelines, models, trace = pipeline_files
    pipelines.write_text(
        pipelines.read_text(encoding="utf-8").replace("max_total_tokens: 30", "max_total_tokens: invalid"),
        encoding="utf-8",
    )
    with pytest.raises(tp.PipelineConfigError, match="max_total_tokens must be an integer"):
        tp.TieredPipelineRunner(
            config_path=pipelines,
            models_path=models,
            trace_path=trace,
        )


@pytest.mark.asyncio
async def test_input_budget_blocks_before_paid_dispatch(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    pipelines, models, trace = pipeline_files
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    monkeypatch.setattr(tp, "gate_permits", lambda *args, **kwargs: (True, None))
    pipelines.write_text(
        pipelines.read_text(encoding="utf-8").replace("max_input_tokens: 512", "max_input_tokens: 4"),
        encoding="utf-8",
    )
    called = False

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        nonlocal called
        called = True
        return "unexpected"

    with pytest.raises(tp.PipelinePolicyError, match="max_input_tokens"):
        await tp.TieredPipelineRunner(
            config_path=pipelines,
            models_path=models,
            trace_path=trace,
        ).run("classify_then_generate", "six!!", approval=_approval(), dispatch=dispatch)
    assert called is False


@pytest.mark.asyncio
async def test_prior_stage_output_cannot_expand_the_next_input(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    pipelines, models, trace = pipeline_files
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    monkeypatch.setattr(tp, "gate_permits", lambda *args, **kwargs: (True, None))
    pipelines.write_text(
        pipelines.read_text(encoding="utf-8").replace("max_input_tokens: 512", "max_input_tokens: 64"),
        encoding="utf-8",
    )
    calls = []

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        calls.append(stage)
        return "x" * 80

    with pytest.raises(tp.PipelinePolicyError, match="max_input_tokens"):
        await tp.TieredPipelineRunner(
            config_path=pipelines,
            models_path=models,
            trace_path=trace,
        ).run("classify_then_generate", "ok", approval=_approval(), dispatch=dispatch)
    assert calls == ["classify"]


@pytest.mark.asyncio
async def test_empty_dispatch_output_is_rejected(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    monkeypatch.setattr(tp, "gate_permits", lambda *args, **kwargs: (True, None))

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        return ""

    with pytest.raises(tp.PipelineExecutionError, match="empty/non-text"):
        await _runner(pipeline_files).run(
            "classify_then_generate", "hello", approval=_approval(), dispatch=dispatch
        )


# ── Approval boundary ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_missing_approval_blocks_before_gate_and_dispatch(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    gate_calls = []
    monkeypatch.setattr(
        tp, "gate_permits", lambda *a, **k: (gate_calls.append((a, k)), (True, None))[1]
    )
    dispatch_calls = []

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        dispatch_calls.append(stage)
        return "unexpected"

    with pytest.raises(tp.PipelineApprovalError, match="approval is required"):
        await _runner(pipeline_files).run(
            "classify_then_generate", "hello", approval=None, dispatch=dispatch
        )
    assert gate_calls == []
    assert dispatch_calls == []


@pytest.mark.asyncio
async def test_expired_approval_blocks_before_dispatch(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    called = False

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        nonlocal called
        called = True
        return "unexpected"

    expired = _approval(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    with pytest.raises(tp.PipelineApprovalError, match="expired"):
        await _runner(pipeline_files).run(
            "classify_then_generate", "hello", approval=expired, dispatch=dispatch
        )
    assert called is False


@pytest.mark.asyncio
async def test_approval_recipe_mismatch_blocks_before_dispatch(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    called = False

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        nonlocal called
        called = True
        return "unexpected"

    mismatched = _approval(recipe="some_other_recipe")
    with pytest.raises(tp.PipelineApprovalError, match="does not match"):
        await _runner(pipeline_files).run(
            "classify_then_generate", "hello", approval=mismatched, dispatch=dispatch
        )
    assert called is False


@pytest.mark.asyncio
async def test_approval_route_tier_mismatch_blocks_before_dispatch(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        return "unexpected"

    mismatched = _approval(route_tier=3)
    with pytest.raises(tp.PipelineApprovalError, match="route tier"):
        await _runner(pipeline_files).run(
            "classify_then_generate", "hello", approval=mismatched, dispatch=dispatch
        )


@pytest.mark.asyncio
async def test_approval_max_tokens_below_recipe_cap_blocks(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        return "unexpected"

    underbudget = _approval(max_tokens=29)  # recipe ceiling is 30
    with pytest.raises(tp.PipelineApprovalError, match="token budget"):
        await _runner(pipeline_files).run(
            "classify_then_generate", "hello", approval=underbudget, dispatch=dispatch
        )


@pytest.mark.asyncio
async def test_approval_max_cost_below_recipe_reservation_blocks(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        return "unexpected"

    underbudget = _approval(max_cost_usd=0.10)  # recipe reservation is 0.25
    with pytest.raises(tp.PipelineApprovalError, match="cost budget"):
        await _runner(pipeline_files).run(
            "classify_then_generate", "hello", approval=underbudget, dispatch=dispatch
        )


@pytest.mark.asyncio
async def test_approval_scope_must_be_non_empty(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        return "unexpected"

    scopeless = _approval(scope=())
    with pytest.raises(tp.PipelineApprovalError, match="scope"):
        await _runner(pipeline_files).run(
            "classify_then_generate", "hello", approval=scopeless, dispatch=dispatch
        )


@pytest.mark.asyncio
async def test_approval_approved_by_and_purpose_must_be_non_blank(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        return "unexpected"

    for blank_field in ("approved_by", "purpose"):
        blank = _approval(**{blank_field: "   "})
        with pytest.raises(tp.PipelineApprovalError, match="required"):
            await _runner(pipeline_files).run(
                "classify_then_generate", "hello", approval=blank, dispatch=dispatch
            )


@pytest.mark.asyncio
async def test_revoked_trace_id_blocks_before_dispatch(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    approval = _approval(trace_id="revoke-me")
    revoked_file = tmp_path / "revoked.txt"
    revoked_file.write_text("revoke-me\n", encoding="utf-8")
    monkeypatch.setenv(tp.REVOKED_APPROVALS_ENV, str(revoked_file))
    called = False

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        nonlocal called
        called = True
        return "unexpected"

    with pytest.raises(tp.PipelineApprovalError, match="revoked"):
        await _runner(pipeline_files).run(
            "classify_then_generate", "hello", approval=approval, dispatch=dispatch
        )
    assert called is False


@pytest.mark.asyncio
async def test_revocation_appended_after_construction_is_observed_without_restart(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Regression test for the stale-cache finding: revoking a trace_id after
    the runner is constructed must still block it -- the revocation list is
    not allowed to be a frozen __init__-time snapshot."""
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    approval = _approval(trace_id="revoke-me-later")
    revoked_file = tmp_path / "revoked.txt"
    revoked_file.write_text("", encoding="utf-8")  # empty at construction time
    monkeypatch.setenv(tp.REVOKED_APPROVALS_ENV, str(revoked_file))

    runner = _runner(pipeline_files)  # constructed while the file is empty

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        return "unexpected"

    # Not yet revoked: should pass approval validation (fails later on the
    # frugality gate instead, which is fine -- this only tests revocation).
    monkeypatch.setattr(tp, "gate_permits", lambda *a, **k: (False, "stop here"))
    with pytest.raises(tp.PipelinePolicyError, match="stop here"):
        await runner.run(
            "classify_then_generate", "hello", approval=approval, dispatch=dispatch
        )

    # Revoke it now, on the same already-constructed runner instance.
    revoked_file.write_text("revoke-me-later\n", encoding="utf-8")
    with pytest.raises(tp.PipelineApprovalError, match="revoked"):
        await runner.run(
            "classify_then_generate", "hello", approval=approval, dispatch=dispatch
        )


def test_unreadable_revocation_file_fails_closed(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    revoked_dir = tmp_path / "revoked_is_a_directory"
    revoked_dir.mkdir()
    monkeypatch.setenv(tp.REVOKED_APPROVALS_ENV, str(revoked_dir))
    with pytest.raises(tp.PipelineApprovalError, match="unreadable"):
        tp.TieredPipelineRunner._load_revoked_trace_ids()


# ── Path traversal containment ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "malicious_trace_id",
    [
        "../../etc/cron.d/evil",
        "../escape",
        "/etc/passwd",
        "a/../../b",
        # "..%2Fescape" and "..\\escape" are deliberately not exercised here:
        # this function receives a raw Python string, not a URL-decoded path
        # segment, so "%2F" never becomes "/", and a literal backslash is an
        # inert filename character (not a separator) on POSIX. Both are
        # still rejected outright by the Pydantic pattern
        # ^[a-zA-Z0-9_-]+$ in fastapi_app.py before a request body ever
        # reaches this function -- see
        # test_register_approval_rejects_malicious_trace_id, which covers
        # exactly these two payloads at that layer.
    ],
)
def test_approval_artifact_path_rejects_traversal(
    tmp_path: Path, malicious_trace_id: str
) -> None:
    directory = tmp_path / "approvals"
    with pytest.raises(tp.PipelineApprovalError, match="escapes approval directory"):
        tp._approval_artifact_path(directory, malicious_trace_id)
    # Confirm nothing was written outside the intended directory either.
    assert not any(tmp_path.glob("**/evil*"))
    assert not any(tmp_path.glob("**/escape*"))


def test_approval_artifact_path_accepts_normal_trace_id(tmp_path: Path) -> None:
    directory = tmp_path / "approvals"
    path = tp._approval_artifact_path(directory, "normal-trace-id-123")
    assert path.is_relative_to(directory.resolve())
    assert path.name == "normal-trace-id-123.json"


def test_approval_expires_at_must_be_timezone_aware(
    pipeline_files: tuple[Path, Path, Path]
) -> None:
    naive = _approval(expires_at=datetime.now() + timedelta(hours=1))  # noqa: DTZ005
    runner = _runner(pipeline_files)
    recipe = runner.recipe("classify_then_generate")
    with pytest.raises(tp.PipelineApprovalError, match="timezone-aware"):
        runner._validate_approval(naive, recipe_name="classify_then_generate", recipe=recipe)


# ── Approval artifact round-trip ──────────────────────────────────────────────


def test_approval_register_and_load_round_trip(tmp_path: Path) -> None:
    approval_dir = tmp_path / "approvals"
    approval = _approval(trace_id="round-trip-1")
    path = tp.register_pipeline_approval(approval, approval_dir=approval_dir)
    assert path.is_file()

    loaded = tp.load_pipeline_approval("round-trip-1", approval_dir=approval_dir)
    assert loaded.trace_id == approval.trace_id
    assert loaded.approved_by == approval.approved_by
    assert loaded.purpose == approval.purpose
    assert loaded.recipe == approval.recipe
    assert loaded.route_tier == approval.route_tier
    assert loaded.max_tokens == approval.max_tokens
    assert loaded.max_cost_usd == approval.max_cost_usd
    assert loaded.expires_at == approval.expires_at
    assert loaded.scope == approval.scope


def test_load_missing_approval_raises(tmp_path: Path) -> None:
    with pytest.raises(tp.PipelineApprovalError, match="no approval record"):
        tp.load_pipeline_approval("never-registered", approval_dir=tmp_path / "approvals")


def test_load_malformed_approval_raises(tmp_path: Path) -> None:
    approval_dir = tmp_path / "approvals"
    approval_dir.mkdir(parents=True)
    (approval_dir / "bad.json").write_text("not json", encoding="utf-8")
    with pytest.raises(tp.PipelineApprovalError, match="unreadable"):
        tp.load_pipeline_approval("bad", approval_dir=approval_dir)


# ── Telemetry ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_error_class_recorded_on_dispatch_failure(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(tp.PIPELINE_FLAG, "1")
    monkeypatch.setattr(tp, "gate_permits", lambda *args, **kwargs: (True, None))

    async def dispatch(model: str, prompt: str, max_tokens: int, stage: str) -> str:
        raise RuntimeError("provider exploded")

    approval = _approval()
    with pytest.raises(RuntimeError):
        await _runner(pipeline_files).run(
            "classify_then_generate", "hello", approval=approval, dispatch=dispatch
        )

    trace_lines = [
        json.loads(line) for line in pipeline_files[2].read_text(encoding="utf-8").splitlines()
    ]
    assert len(trace_lines) == 1
    attrs = trace_lines[0]["attributes"]
    assert attrs["status"] == "failed"
    assert attrs["pipeline.error_class"] == "RuntimeError"
    assert attrs["pipeline.trace_id"] == approval.trace_id
    assert "provider exploded" not in pipeline_files[2].read_text(encoding="utf-8")


# ── Config validation: unknown keys + stage cap ────────────────────────────────


def test_unknown_top_level_key_rejected(pipeline_files: tuple[Path, Path, Path]) -> None:
    pipelines, models, trace = pipeline_files
    pipelines.write_text(
        pipelines.read_text(encoding="utf-8") + "\nunexpected_top_level_key: true\n",
        encoding="utf-8",
    )
    with pytest.raises(tp.PipelineConfigError, match="unknown keys.*unexpected_top_level_key"):
        tp.TieredPipelineRunner(config_path=pipelines, models_path=models, trace_path=trace)


def test_unknown_recipe_level_key_rejected(pipeline_files: tuple[Path, Path, Path]) -> None:
    pipelines, models, trace = pipeline_files
    pipelines.write_text(
        pipelines.read_text(encoding="utf-8").replace(
            "cost_reservation_usd: 0.25", "cost_reservation_usd: 0.25\n    bogus_recipe_key: 1"
        ),
        encoding="utf-8",
    )
    with pytest.raises(tp.PipelineConfigError, match="unknown keys.*bogus_recipe_key"):
        tp.TieredPipelineRunner(config_path=pipelines, models_path=models, trace_path=trace)


def test_unknown_stage_level_key_rejected(pipeline_files: tuple[Path, Path, Path]) -> None:
    pipelines, models, trace = pipeline_files
    pipelines.write_text(
        pipelines.read_text(encoding="utf-8").replace(
            "instruction: classify", "instruction: classify\n        bogus_stage_key: 1"
        ),
        encoding="utf-8",
    )
    with pytest.raises(tp.PipelineConfigError, match="unknown keys.*bogus_stage_key"):
        tp.TieredPipelineRunner(config_path=pipelines, models_path=models, trace_path=trace)


def test_more_than_three_stages_rejected(pipeline_files: tuple[Path, Path, Path]) -> None:
    pipelines, models, trace = pipeline_files
    extra_stages = "\n".join(
        "      - name: stage%d\n        model: fast\n        max_tokens: 1\n" % i
        for i in range(2)
    )
    pipelines.write_text(
        pipelines.read_text(encoding="utf-8").replace(
            "        instruction: generate\n",
            "        instruction: generate\n" + extra_stages,
        ),
        encoding="utf-8",
    )
    with pytest.raises(tp.PipelineConfigError, match="exceeding the 3-stage limit"):
        tp.TieredPipelineRunner(config_path=pipelines, models_path=models, trace_path=trace)


def test_exactly_three_stages_is_accepted(pipeline_files: tuple[Path, Path, Path]) -> None:
    pipelines, models, trace = pipeline_files
    pipelines.write_text(
        pipelines.read_text(encoding="utf-8")
        .replace("max_total_tokens: 30", "max_total_tokens: 31")
        .replace(
            "        instruction: generate\n",
            "        instruction: generate\n"
            "      - name: extra\n"
            "        model: fast\n"
            "        max_tokens: 1\n"
            "        input_from: generate\n",
        ),
        encoding="utf-8",
    )
    runner = tp.TieredPipelineRunner(config_path=pipelines, models_path=models, trace_path=trace)
    assert len(runner.recipe("classify_then_generate").stages) == 3


# ── Model resolution: env override, still registry-validated ──────────────────


def test_pipeline_model_env_override_still_requires_frugality_tier_five(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    pipelines, models, trace = pipeline_files
    monkeypatch.setenv("PIPELINE_FAST_MODEL", "local-model")  # frugality_tier 1, not 5
    with pytest.raises(tp.PipelineConfigError, match="must be frugality tier 5"):
        tp.TieredPipelineRunner(config_path=pipelines, models_path=models, trace_path=trace)


def test_pipeline_model_env_override_resolves_when_valid(
    pipeline_files: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    pipelines, models, trace = pipeline_files
    monkeypatch.setenv("PIPELINE_FAST_MODEL", "paid-strong")  # a different, still-valid tier-5 model
    runner = tp.TieredPipelineRunner(config_path=pipelines, models_path=models, trace_path=trace)
    assert runner._models["fast"] == "paid-strong"
