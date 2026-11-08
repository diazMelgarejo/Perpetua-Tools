"""Operator-approved Gemini roles never turn planning into human authorization."""
import pytest
from datetime import datetime, timedelta, timezone

from perpetua_tools.model_governance import (
    EscalationProof, LaunchSpec, ModelGovernanceError, assert_launch_allowed, plan_launch,
)


@pytest.mark.parametrize("task_kind", [None, "planning", "execution"])
def test_google_pro_always_requires_human_approval(task_kind: str | None) -> None:
    """A planning label must not bypass the explicit Pro HITL requirement."""
    spec = LaunchSpec("google", "gemini-pro-latest", "medium", False)
    plan = plan_launch(spec, task_kind=task_kind)
    assert plan.requires_human_approval
    assert plan.effective.launch_id == "gemini-3.8-flash"
    with pytest.raises(ModelGovernanceError, match="escalation token"):
        assert_launch_allowed(spec, task_kind=task_kind)


def test_google_dynamic_flash_fallback_is_a_usable_ungated_role() -> None:
    """The configured stable Flash fallback alias is usable without Pro escalation."""
    spec = LaunchSpec("google", "gemini-flash-latest", "medium", False)
    plan = plan_launch(spec, task_kind="execution")
    assert not plan.requires_human_approval
    assert plan.effective == spec
    assert_launch_allowed(spec, task_kind="execution")


@pytest.mark.parametrize("budget", [None, "", "   "])
def test_frontier_google_model_requires_a_nonempty_approved_budget(budget: str | None) -> None:
    """A covering approval must not silently discard Argon's required budget cap."""
    now = datetime.now(timezone.utc)
    proof = EscalationProof(
        "control_plane_online_signer", "verified-reference", "gemini-4-argon",
        now + timedelta(minutes=1), effort="medium", fast=False,
        budget_cap=budget, path="google",
    )
    with pytest.raises(ModelGovernanceError, match="budget cap"):
        assert_launch_allowed(LaunchSpec("google", "gemini-4-argon", "medium", False),
                              proof=proof, now=now, task_kind="planning")
