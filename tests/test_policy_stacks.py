"""Offline tests for the local-first and free-first stacks."""

from orchestrator.policy_stacks import (
    authorize_paid_candidate,
    automatic_free_candidates,
    classify_provider_result,
    load_policy,
    load_stacks,
    select_next_candidate,
)


def test_stacks_do_not_copy_the_candidate_list():
    stacks = load_stacks()
    assert [row["id"] for row in stacks["stacks"]] == [
        "local-llm-first",
        "free-first",
        "paid-hitl",
    ]
    assert "ordered_candidates" not in stacks
    assert stacks["stacks"][2]["automatic"] is False


def test_free_chain_ends_at_openrouter_and_excludes_paid():
    policy = load_policy()
    free = [row["model_id"] for row in automatic_free_candidates(policy)]
    assert free[-1] == "openrouter/free"
    assert "glm-5.3-flash" not in free
    assert policy["paid_candidates"][0]["automatic"] is False
    assert policy["paid_candidates"][0]["human_gate"] == "hitl"


def test_select_next_skips_settled_and_stops_before_paid():
    policy = load_policy()
    first = select_next_candidate(policy, {}, [])
    assert first["model_id"] == "glm-4.7-flash"
    ledger = [
        {"model_id": "glm-4.7-flash", "outcome": "model_unavailable"},
        {"model_id": "glm-4.5-flash", "outcome": "capability_ineligible"},
        {"model_id": "glm-4-flash-250414", "outcome": "rejected"},
    ]
    nxt = select_next_candidate(policy, {"modality": "text"}, ledger)
    assert nxt["model_id"] == "openrouter/free"
    assert select_next_candidate(policy, {"modality": "vision"}, []) is None


def test_1113_is_not_a_throttle_and_paid_needs_a_human_budget():
    assert classify_provider_result(429, "1113") == "billing_or_entitlement_blocked"
    assert classify_provider_result(429, None) == "throttled"
    assert classify_provider_result(200, None, "partial") == "recovery_required"
    paid = {"model_id": "glm-5.3-flash"}
    assert authorize_paid_candidate(None, {"budget_cny": 1}, paid) is False
    assert authorize_paid_candidate(
        {"human_approved": True, "per_run": True, "model_id": "glm-5.3-flash"},
        {"budget_cny": 1},
        paid,
    ) is True
    assert authorize_paid_candidate(
        {"human_approved": True, "per_run": True, "model_id": "glm-5.3-flash"},
        {"budget_cny": float("inf")},
        paid,
    ) is False
