"""Offline tests for the local-first and free-first stacks."""

import re
from pathlib import Path

import yaml

from orchestrator.gate import load_frugality_tier_by_name
from orchestrator.model_registry import ModelRegistry, ModelTarget
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


_LOCAL_MACHINE = re.compile(r"qwen|gemma|diffusion|3080|5080", re.IGNORECASE)


def test_hardware_policy_local_names_are_tier_1():
    """5080, 3080, qwen, gemma, and diffusion ids are on-machine LLMs."""
    root = Path(__file__).resolve().parents[1]
    policy = yaml.safe_load((root / "config" / "model_hardware_policy.yml").read_text())
    tiers = load_frugality_tier_by_name(str(root / "config"))
    names = []
    for key in (
        "mac_only",
        "windows_only",
        "shared",
        "shared_aliases",
        "windows_only_aliases",
    ):
        names.extend(policy.get(key) or [])
    for name in (
        "qwen3-30b-a3b-mlx",
        "qwen3.5-35b-a3b-q4",
        "qwen3-coder:14b",
        "qwen3-30b-critic",
        "gemma-4-26b-a4b-it-nvfp4",
    ):
        names.append(name)
    missing = [name for name in names if _LOCAL_MACHINE.search(name) and tiers.get(name) != 1]
    assert missing == []


def test_sorted_model_list_puts_qwen_first_and_openrouter_free_last():
    """Sorted means classified. It does not mean the model is available."""
    raw = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "config" / "models.yml").read_text()
    )
    names = [item["name"] for item in raw["models"]]
    assert names[0] == "oramasys"
    assert raw["models"][0]["frugality_tier"] == 0
    assert raw["models"][0]["online"] is False
    qwen_span = [name for name in names[1:] if "qwen" in name.lower()]
    assert names[1: 1 + len(qwen_span)] == qwen_span
    assert names[-1] == "openrouter/free"
    tiers = {item["name"]: item["frugality_tier"] for item in raw["models"]}
    assert tiers["bge-m3"] == 1
    for name in ("glm-4.7-flash", "glm-4.5-flash", "glm-4-flash-250414", "openrouter/free"):
        assert tiers[name] == 3


def test_every_configured_model_has_a_frugality_tier():
    raw = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "config" / "models.yml").read_text()
    )
    for item in raw["models"]:
        tier = item.get("frugality_tier")
        assert isinstance(tier, int) and not isinstance(tier, bool)
        assert 0 <= tier <= 6, item["name"]


def test_route_task_drops_an_unclassified_model(monkeypatch):
    registry = ModelRegistry(config_dir=str(Path(__file__).resolve().parents[1] / "config"))
    monkeypatch.delenv("ORAMASYS_OFFLINE", raising=False)
    original = registry.list_models

    def _with_blank(**kwargs):
        models = original(**kwargs)
        models.append(
            ModelTarget(
                name="unclassified-probe",
                backend="ollama",
                device="mac-studio",
                host="http://127.0.0.1",
                port=11434,
                context_window=None,
                roles=["general"],
                priority=0,
                online=False,
                reasoning="local",
                frugality_tier=None,
            )
        )
        return models

    monkeypatch.setattr(registry, "list_models", _with_blank)
    names = [item.name for item in registry.route_task("default")]
    assert "unclassified-probe" not in names


def test_offline_chain_cannot_reach_paid_or_free_remote_transport(monkeypatch):
    monkeypatch.setenv("ORAMASYS_OFFLINE", "1")
    registry = ModelRegistry(config_dir=str(Path(__file__).resolve().parents[1] / "config"))
    chain = registry.route_task("default")
    assert chain
    for item in chain:
        assert item.frugality_tier is not None and item.frugality_tier <= 2
        assert "openrouter.ai" not in item.host
        assert "bigmodel.cn" not in item.host
        assert item.name not in {"glm-5.3-flash", "openrouter/free"}


def test_exhausted_free_chain_does_not_select_paid():
    policy = load_policy()
    ledger = [
        {"model_id": row["model_id"], "outcome": "rejected"}
        for row in automatic_free_candidates(policy)
    ]
    assert select_next_candidate(policy, {"modality": "text"}, ledger) is None
