"""Role selection returns policy facts without manufacturing launch authority."""

from datetime import datetime, timedelta, timezone

import pytest

from perpetua_tools.model_governance import (
    LaunchSpec,
    EscalationProof,
    ModelGovernanceError,
    assert_launch_allowed,
    plan_launch,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "path,model,effort,task_kind,effective,approval",
    [
        ("anthropic", "claude-opus-5-5", "high", "planning", "claude-opus-5-5", False),
        ("anthropic", "claude-opus-5-5", "medium", "planning", "claude-opus-5-5", False),
        ("anthropic", "claude-opus-5-5", "high", "execution", "claude-sonnet-5-5", True),
        ("anthropic", "claude-opus-5-5", "medium", None, "claude-sonnet-5-5", True),
        ("openai", "gpt-6.1-sol", "medium", "planning", "gpt-6.1-sol", False),
        ("openai", "gpt-6.1-sol", "medium", "execution", "gpt-5.6-terra", True),
        ("openai", "gpt-6-luna", "medium", "execution", "gpt-6-luna", False),
        ("google", "gemini-3.8-flash", "medium", "execution", "gemini-3.8-flash", False),
        ("anthropic", "claude-haiku-5-5", "medium", "execution", "claude-haiku-5-5", False),
    ],
)
def test_role_selection(
    path: str, model: str, effort: str, task_kind: str | None,
    effective: str, approval: bool,
) -> None:
    requested = LaunchSpec(path=path, launch_id=model, effort=effort, fast=False)
    plan = plan_launch(requested, task_kind=task_kind)
    assert plan.requested == requested
    assert plan.effective.launch_id == effective
    assert plan.requires_human_approval is approval
    assert plan.effective.effort == (effort if not approval else "medium")


def test_automation_cannot_start_ultracode_even_for_planning() -> None:
    requested = LaunchSpec(
        path="anthropic", launch_id="claude-opus-5-5", effort="high", fast=False
    )
    plan = plan_launch(requested, task_kind="planning", mode="ultracode")
    assert plan.requires_human_approval
    assert plan.effective.launch_id == "claude-sonnet-5-5"
    assert plan.effective.effort == "medium"
    assert plan.effective_mode == "standard"
    assert plan.requested_mode == "ultracode"


@pytest.mark.parametrize("effort", ["xhigh", "max"])
def test_role_fallback_does_not_mask_forbidden_effort(effort: str) -> None:
    with pytest.raises(ModelGovernanceError, match="forbidden"):
        plan_launch(LaunchSpec("anthropic", "claude-opus-5-5", effort, False))


def test_cursor_opus_falls_back_to_sonnet_on_the_same_harness() -> None:
    plan = plan_launch(LaunchSpec("cursor_grok_bot", "claude-opus-5-5", "high", False))
    assert plan.effective.path == "cursor_grok_bot"
    assert plan.effective.launch_id == "claude-sonnet-5-5"
    assert plan.requires_human_approval


def test_unknown_model_and_invalid_classification_are_not_rerouted() -> None:
    with pytest.raises(ModelGovernanceError):
        plan_launch(LaunchSpec("anthropic", "unknown-model", "medium", False))
    with pytest.raises(ModelGovernanceError, match="task kind"):
        plan_launch(LaunchSpec("anthropic", "claude-opus-5-5", "high", False), task_kind="agent_says_planning")


@pytest.mark.parametrize(
    "path,model,effort",
    [("anthropic", "claude-opus-5-5", "high"), ("openai", "gpt-6.1-sol", "medium")],
)
def test_strict_validator_uses_harness_planning_classification(
    path: str, model: str, effort: str
) -> None:
    spec = LaunchSpec(path, model, effort, False)
    assert_launch_allowed(spec, task_kind="planning")
    with pytest.raises(ModelGovernanceError, match="escalation token"):
        assert_launch_allowed(spec, task_kind="execution")


def test_approval_candidate_does_not_implicitly_raise_nonplanning_effort() -> None:
    plan = plan_launch(LaunchSpec("anthropic", "claude-opus-5-5", "high", False))
    assert plan.approval_candidate is not None
    assert plan.approval_candidate.effort == "medium"
    now = datetime.now(timezone.utc)
    proof = EscalationProof(
        kind="control_plane_online_signer", reference="verified-approval-reference",
        model_id="claude-opus-5-5", expires_at=now + timedelta(minutes=1),
        effort="medium", fast=False,
    )
    assert_launch_allowed(
        plan.approval_candidate, proof=proof, task_kind="execution", now=now
    )
