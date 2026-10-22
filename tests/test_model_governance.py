"""Pins for harness-path model governance (Alexandria standard, local pin file)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from perpetua_tools.model_governance import (
    EscalationProof,
    LaunchSpec,
    ModelGovernanceError,
    assert_launch_allowed,
    default_launch,
    evaluate_cost_gate,
    load_model_governance,
    proof_is_token,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_GUIDANCE = (
    REPO_ROOT / "docs/standards/model-governance.md",
    REPO_ROOT / "SKILL.md",
    REPO_ROOT / "config/SKILL.md",
    REPO_ROOT / "hardware/SKILL.md",
    REPO_ROOT / ".cursor/commands/model-route.md",
)


@pytest.fixture
def cfg() -> dict:
    return load_model_governance()


def test_cost_gate_and_cloud_escalation_invariants(cfg: dict) -> None:
    assert cfg["invariants"]["cost_gate"] == "fail_closed"
    assert cfg["invariants"]["cloud_escalation"] == "default_deny"


def test_cursor_default_is_grok_46_medium_fast_off() -> None:
    spec = default_launch("cursor_grok_bot")
    assert spec.launch_id == "grok-4.6"
    assert spec.effort == "medium"
    assert spec.fast is False
    assert_launch_allowed(spec)


def test_anthropic_default_is_sonnet_55_medium() -> None:
    spec = default_launch("anthropic")
    assert spec.launch_id == "claude-sonnet-5-5"
    assert spec.effort == "medium"
    assert_launch_allowed(spec)


def test_legacy_sonnet_5_pin_allowed(cfg: dict) -> None:
    spec = LaunchSpec(path="anthropic", launch_id="claude-sonnet-5", effort="medium")
    assert_launch_allowed(spec, config=cfg)


def test_cursor_sonnet_55_follows_anthropic_gate_without_token() -> None:
    spec = LaunchSpec(
        path="cursor_grok_bot",
        launch_id="claude-sonnet-5-5",
        effort="medium",
    )
    assert_launch_allowed(spec)


def test_grok_45_banned() -> None:
    spec = LaunchSpec(
        path="cursor_grok_bot",
        launch_id="grok-4.5",
        effort="medium",
        fast=False,
    )
    with pytest.raises(ModelGovernanceError, match="banned"):
        assert_launch_allowed(spec)


def test_auto_never_for_agents() -> None:
    spec = LaunchSpec(path="cursor_grok_bot", launch_id="auto", agent=True)
    with pytest.raises(ModelGovernanceError, match="editor-only"):
        assert_launch_allowed(spec)


def test_composer_requires_fast_off() -> None:
    ok = LaunchSpec(path="cursor_grok_bot", launch_id="composer-2.5", fast=False)
    assert_launch_allowed(ok)
    bad = LaunchSpec(path="cursor_grok_bot", launch_id="composer-2.5", fast=True)
    with pytest.raises(ModelGovernanceError, match="fast"):
        assert_launch_allowed(bad)


def test_cursor_non_medium_reasoning_effort_requires_token() -> None:
    spec = LaunchSpec(
        path="cursor_grok_bot",
        launch_id="composer-2.5",
        reasoning_effort="high",
        fast=False,
    )
    with pytest.raises(ModelGovernanceError, match="non-medium effort"):
        assert_launch_allowed(spec)


def test_cursor_non_medium_reasoning_effort_accepts_matching_token() -> None:
    spec = LaunchSpec(
        path="cursor_grok_bot",
        launch_id="composer-2.5",
        reasoning_effort="high",
        fast=False,
    )
    proof = EscalationProof(
        kind="offline_gpg",
        reference="fpr:operator",
        model_id="composer-2.5",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        effort="high",
        fast=False,
    )
    assert_launch_allowed(spec, proof=proof)


def test_env_and_config_flags_are_not_escalation_tokens() -> None:
    env_shaped = EscalationProof(
        kind="env_var",
        reference="HUMAN_APPROVED=true",
        model_id="grok-4.7",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    flag_shaped = EscalationProof(
        kind="config_flag",
        reference="human_approved: true",
        model_id="grok-4.7",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    cached = EscalationProof(
        kind="cached_approval",
        reference="yesterday.sig",
        model_id="grok-4.7",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    assert proof_is_token(env_shaped) is False
    assert proof_is_token(flag_shaped) is False
    assert proof_is_token(cached) is False
    spec = LaunchSpec(
        path="cursor_grok_bot",
        launch_id="grok-4.7",
        effort="medium",
        fast=False,
    )
    with pytest.raises(ModelGovernanceError, match="default-deny"):
        assert_launch_allowed(spec, proof=env_shaped)
    with pytest.raises(ModelGovernanceError, match="default-deny"):
        assert_launch_allowed(spec, proof=flag_shaped)


def test_grok_47_allowed_only_with_real_proof() -> None:
    spec = LaunchSpec(
        path="cursor_grok_bot",
        launch_id="grok-4.7",
        effort="medium",
        fast=False,
    )
    with pytest.raises(ModelGovernanceError, match="default-deny"):
        assert_launch_allowed(spec)
    proof = EscalationProof(
        kind="github_verified_signoff",
        reference="abc123verified",
        model_id="grok-4.7",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        effort="medium",
        fast=False,
    )
    assert_launch_allowed(spec, proof=proof)
    high = LaunchSpec(
        path="cursor_grok_bot",
        launch_id="grok-4.7",
        effort="high",
        fast=False,
    )
    with pytest.raises(ModelGovernanceError, match="effort"):
        assert_launch_allowed(high, proof=proof)


def test_opus_and_fable_require_token_fable_needs_cap() -> None:
    opus = LaunchSpec(
        path="anthropic", launch_id="claude-opus-5-5", effort="high", fast=False
    )
    with pytest.raises(ModelGovernanceError, match="default-deny"):
        assert_launch_allowed(opus)
    opus_proof = EscalationProof(
        kind="offline_gpg",
        reference="fpr:operator",
        model_id="claude-opus-5-5",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        effort="high",
        fast=False,
    )
    assert_launch_allowed(opus, proof=opus_proof)
    opus_medium = LaunchSpec(path="anthropic", launch_id="claude-opus-5-5", effort="medium")
    with pytest.raises(ModelGovernanceError, match="effort"):
        assert_launch_allowed(opus_medium, proof=opus_proof)

    fable = LaunchSpec(path="anthropic", launch_id="claude-fable-5-1", effort="medium")
    no_cap = EscalationProof(
        kind="offline_gpg",
        reference="fpr:operator",
        model_id="claude-fable-5-1",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        effort="medium",
    )
    with pytest.raises(ModelGovernanceError, match="budget cap"):
        assert_launch_allowed(fable, proof=no_cap)
    with_cap = EscalationProof(
        kind="offline_gpg",
        reference="fpr:operator",
        model_id="claude-fable-5-1",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        effort="medium",
        budget_cap="max_tokens=8192",
    )
    assert_launch_allowed(fable, proof=with_cap)
    cursor_fable = LaunchSpec(
        path="cursor_grok_bot", launch_id="claude-fable-5-1", effort="medium"
    )
    with pytest.raises(ModelGovernanceError, match="budget cap"):
        assert_launch_allowed(cursor_fable, proof=no_cap)
    assert_launch_allowed(cursor_fable, proof=with_cap)


def test_direct_xai_requires_medium_reasoning() -> None:
    ok = default_launch("direct_xai")
    assert ok.launch_id == "grok-4.6"
    assert ok.reasoning_effort == "medium"
    assert_launch_allowed(ok)
    high = LaunchSpec(
        path="direct_xai", launch_id="grok-4.6", reasoning_effort="high"
    )
    with pytest.raises(ModelGovernanceError, match="reasoning_effort"):
        assert_launch_allowed(high)


def test_cost_gate_fail_closed() -> None:
    with pytest.raises(ModelGovernanceError, match="cannot be evaluated"):
        evaluate_cost_gate(cap_evaluable=False, remaining=100)
    with pytest.raises(ModelGovernanceError, match="cannot be evaluated"):
        evaluate_cost_gate(cap_evaluable=True, remaining=None)
    with pytest.raises(ModelGovernanceError, match="cap hit"):
        evaluate_cost_gate(cap_evaluable=True, remaining=0)
    evaluate_cost_gate(cap_evaluable=True, remaining=10)


def test_pin_refuses_non_fail_closed_cost_gate(tmp_path: Path) -> None:
    src = yaml.safe_load(
        (REPO_ROOT / "config" / "model-governance.yml").read_text(encoding="utf-8")
    )
    src["invariants"]["cost_gate"] = "fail_open"
    broken = tmp_path / "model-governance.yml"
    broken.write_text(yaml.safe_dump(src), encoding="utf-8")
    with pytest.raises(ModelGovernanceError, match="fail-closed"):
        load_model_governance(str(broken))


def test_pin_refuses_duplicate_mapping_keys(tmp_path: Path) -> None:
    broken = tmp_path / "model-governance.yml"
    broken.write_text(
        """\
invariants:
  cost_gate: fail_closed
  cost_gate: fail_closed
  cloud_escalation: default_deny
""",
        encoding="utf-8",
    )
    with pytest.raises(ModelGovernanceError, match="config unavailable") as exc_info:
        load_model_governance(str(broken))
    assert isinstance(exc_info.value.__cause__, yaml.constructor.ConstructorError)


def test_models_yml_drops_banned_grok_45() -> None:
    text = (REPO_ROOT / "config" / "models.yml").read_text(encoding="utf-8")
    raw = yaml.safe_load(text)
    names = {row.get("name") for row in raw.get("models") or [] if isinstance(row, dict)}
    apis = {
        row.get("api_model") for row in raw.get("models") or [] if isinstance(row, dict)
    }
    assert "grok-4.5" not in names
    assert "grok-4.5" not in apis
    assert "grok-4.6" in names
    assert "claude-sonnet-5-5" in names
    assert "claude-sonnet-5" in names


def test_live_guidance_has_no_stale_defaults() -> None:
    for path in LIVE_GUIDANCE:
        text = path.read_text(encoding="utf-8")
        assert "Haiku 4.5" not in text
        assert "Sonnet 4.6" not in text
        assert "Opus 4.6" not in text
        assert "claude-opus-4-8" not in text
        assert "claude-4.6-sonnet" not in text
    pointer = (REPO_ROOT / "docs/standards/model-governance.md").read_text(
        encoding="utf-8"
    )
    assert "grok-4.6" in pointer
    assert "claude-sonnet-5-5" in pointer
    skill = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "claude-sonnet-5-5" in skill
    assert '"model": "claude-sonnet-5"' not in skill
    hardware = (REPO_ROOT / "hardware/SKILL.md").read_text(encoding="utf-8")
    assert "grok-4.6" in hardware
    assert "| cloud | grok-4.5 |" not in hardware
    config_skill = (REPO_ROOT / "config/SKILL.md").read_text(encoding="utf-8")
    assert "grok-4.6" in config_skill
    assert "**grok-4.5**" not in config_skill


# ---------------------------------------------------------------------------
# R1-R4 shared behavioral vectors. Identical block in orama-system and
# Perpetua-Tools tests; no shared runtime import. Proof fixtures are synthetic
# and unauthenticated: they exercise policy metadata only, not signatures.
# Provider model availability is unverified here.
# ---------------------------------------------------------------------------
_VEC_NOW = datetime(2026, 10, 21, tzinfo=timezone.utc)


def _vec_proof(model, effort, fast, budget=None, hours=1, **extra):
    return EscalationProof(
        kind="offline_gpg",
        reference="synthetic-policy-fixture",
        model_id=model,
        effort=effort,
        fast=fast,
        budget_cap=budget,
        expires_at=_VEC_NOW + timedelta(hours=hours),
        **extra,
    )


@pytest.mark.parametrize("path", ["anthropic", "cursor_grok_bot"])
@pytest.mark.parametrize(
    "model",
    ["claude-sonnet-5-5", "claude-sonnet-5", "claude-opus-5-5", "claude-fable-5-1"],
)
@pytest.mark.parametrize("effort", [None, "medium", "high"])
@pytest.mark.parametrize("fast", [None, False, True])
@pytest.mark.parametrize("approval", ["absent", "fresh", "expired"])
@pytest.mark.parametrize("budget", [None, "max_tokens=8192"])
def test_vector_family_matrix(path, model, effort, fast, approval, budget) -> None:
    spec = LaunchSpec(path=path, launch_id=model, effort=effort, fast=fast)
    proof = None
    if approval != "absent":
        proof = _vec_proof(
            model, effort, fast, budget, hours=1 if approval == "fresh" else -1
        )
    allowed = fast is not True
    if model.startswith("claude-sonnet"):
        allowed = allowed and effort == "medium"
    elif model == "claude-opus-5-5":
        allowed = allowed and effort == "high" and fast is False
        allowed = allowed and approval == "fresh"
    else:
        allowed = allowed and effort == "medium"
        allowed = allowed and approval == "fresh" and budget is not None
    if approval == "expired":
        allowed = False
    if allowed:
        assert_launch_allowed(spec, proof=proof, now=_VEC_NOW)
    else:
        with pytest.raises(ModelGovernanceError):
            assert_launch_allowed(spec, proof=proof, now=_VEC_NOW)


@pytest.mark.parametrize(
    "approved_model,approved_effort,approved_fast,hours,allowed",
    [
        ("composer-2.5", "high", True, 1, True),
        ("other-model", "high", True, 1, False),
        ("composer-2.5", "medium", True, 1, False),
        ("composer-2.5", "high", False, 1, False),
        ("composer-2.5", "high", None, 1, False),
        ("composer-2.5", "high", True, -1, False),
    ],
)
def test_vector_approval_binds_launch_tuple(
    approved_model, approved_effort, approved_fast, hours, allowed
) -> None:
    spec = LaunchSpec(
        path="cursor_grok_bot", launch_id="composer-2.5", effort="high", fast=True
    )
    proof = _vec_proof(approved_model, approved_effort, approved_fast, hours=hours)
    if allowed:
        assert_launch_allowed(spec, proof=proof, now=_VEC_NOW)
    else:
        with pytest.raises(ModelGovernanceError):
            assert_launch_allowed(spec, proof=proof, now=_VEC_NOW)


def test_vector_stray_mismatched_proof_refused_on_ungated_launch() -> None:
    spec = LaunchSpec(path="anthropic", launch_id="claude-sonnet-5-5", effort="medium")
    stale = _vec_proof("claude-sonnet-5-5", "medium", None, hours=-1)
    with pytest.raises(ModelGovernanceError):
        assert_launch_allowed(spec, proof=stale, now=_VEC_NOW)
    wrong_effort = _vec_proof("claude-sonnet-5-5", "high", None)
    with pytest.raises(ModelGovernanceError):
        assert_launch_allowed(spec, proof=wrong_effort, now=_VEC_NOW)


@pytest.mark.parametrize("fast,approved_fast", [(None, False), (False, None)])
@pytest.mark.parametrize("reasoning_field", [False, True])
def test_vector_nonfast_and_effort_fields_normalize(
    fast, approved_fast, reasoning_field
) -> None:
    spec = LaunchSpec(
        path="anthropic",
        launch_id="claude-fable-5-1",
        fast=fast,
        effort=None if reasoning_field else "medium",
        reasoning_effort="medium" if reasoning_field else None,
    )
    proof = _vec_proof(spec.launch_id, "medium", approved_fast, "max_tokens=8192")
    assert_launch_allowed(spec, proof=proof, now=_VEC_NOW)


def test_vector_scope_and_path_binding() -> None:
    spec = LaunchSpec(
        path="cursor_grok_bot", launch_id="grok-4.7", effort="medium", fast=False
    )
    scoped = _vec_proof("grok-4.7", "medium", False, scope="task-a")
    assert_launch_allowed(spec, proof=scoped, approval_scope="task-a", now=_VEC_NOW)
    with pytest.raises(ModelGovernanceError):
        assert_launch_allowed(spec, proof=scoped, approval_scope="task-b", now=_VEC_NOW)
    with pytest.raises(ModelGovernanceError):
        assert_launch_allowed(spec, proof=scoped, now=_VEC_NOW)
    unscoped = _vec_proof("grok-4.7", "medium", False)
    with pytest.raises(ModelGovernanceError):
        assert_launch_allowed(spec, proof=unscoped, approval_scope="task-a", now=_VEC_NOW)
    other_path = _vec_proof("grok-4.7", "medium", False, path="anthropic")
    with pytest.raises(ModelGovernanceError):
        assert_launch_allowed(spec, proof=other_path, now=_VEC_NOW)


def test_vector_sonnet_fast_refused_without_proof() -> None:
    bad = LaunchSpec(
        path="anthropic", launch_id="claude-sonnet-5-5", effort="medium", fast=True
    )
    with pytest.raises(ModelGovernanceError, match="fast"):
        assert_launch_allowed(bad)
    for fast in (None, False):
        ok = LaunchSpec(
            path="anthropic", launch_id="claude-sonnet-5-5", effort="medium", fast=fast
        )
        assert_launch_allowed(ok)


def test_vector_cursor_family_controls() -> None:
    fable = LaunchSpec(
        path="cursor_grok_bot", launch_id="claude-fable-5-1", effort="medium"
    )
    with pytest.raises(ModelGovernanceError, match="budget cap"):
        assert_launch_allowed(
            fable, proof=_vec_proof("claude-fable-5-1", "medium", None), now=_VEC_NOW
        )
    assert_launch_allowed(
        fable,
        proof=_vec_proof("claude-fable-5-1", "medium", None, "max_tokens=8192"),
        now=_VEC_NOW,
    )
    opus_medium = LaunchSpec(
        path="cursor_grok_bot", launch_id="claude-opus-5-5", effort="medium", fast=False
    )
    with pytest.raises(ModelGovernanceError, match="effort"):
        assert_launch_allowed(
            opus_medium,
            proof=_vec_proof("claude-opus-5-5", "medium", False),
            now=_VEC_NOW,
        )
    opus_fast = LaunchSpec(
        path="cursor_grok_bot", launch_id="claude-opus-5-5", effort="high", fast=True
    )
    with pytest.raises(ModelGovernanceError):
        assert_launch_allowed(
            opus_fast, proof=_vec_proof("claude-opus-5-5", "high", True), now=_VEC_NOW
        )
    sonnet = LaunchSpec(
        path="cursor_grok_bot", launch_id="claude-sonnet-5-5", effort="medium"
    )
    assert_launch_allowed(sonnet)
    grok_high = LaunchSpec(
        path="cursor_grok_bot", launch_id="grok-4.7", effort="high", fast=False
    )
    with pytest.raises(ModelGovernanceError, match="effort"):
        assert_launch_allowed(
            grok_high, proof=_vec_proof("grok-4.7", "high", False), now=_VEC_NOW
        )


@pytest.mark.parametrize("effort", [None, "high", "low", "medium"])
def test_vector_direct_xai_requires_medium_effort(effort) -> None:
    spec = LaunchSpec(path="direct_xai", launch_id="grok-4.6", reasoning_effort=effort)
    if effort == "medium":
        assert_launch_allowed(spec)
    else:
        with pytest.raises(ModelGovernanceError, match="reasoning_effort"):
            assert_launch_allowed(spec)


def test_vector_approval_optionally_binds_path_and_scope() -> None:
    spec = LaunchSpec(
        path="cursor_grok_bot", launch_id="grok-4.7", effort="medium", fast=False
    )
    bound = _vec_proof(
        "grok-4.7", "medium", False, path="cursor_grok_bot", scope="task-a"
    )
    assert_launch_allowed(spec, proof=bound, approval_scope="task-a", now=_VEC_NOW)
    with pytest.raises(ModelGovernanceError):
        assert_launch_allowed(spec, proof=bound, approval_scope="task-b", now=_VEC_NOW)
    with pytest.raises(ModelGovernanceError):
        assert_launch_allowed(spec, proof=bound, now=_VEC_NOW)
    wrong_path = _vec_proof("grok-4.7", "medium", False, path="anthropic")
    with pytest.raises(ModelGovernanceError):
        assert_launch_allowed(spec, proof=wrong_path, now=_VEC_NOW)


def test_vector_expiry_equal_to_now_is_refused() -> None:
    spec = LaunchSpec(
        path="cursor_grok_bot", launch_id="grok-4.7", effort="medium", fast=False
    )
    at_now = _vec_proof("grok-4.7", "medium", False, hours=0)
    with pytest.raises(ModelGovernanceError):
        assert_launch_allowed(spec, proof=at_now, now=_VEC_NOW)
    one_second_left = EscalationProof(
        kind="offline_gpg",
        reference="synthetic-policy-fixture",
        model_id="grok-4.7",
        effort="medium",
        fast=False,
        expires_at=_VEC_NOW + timedelta(seconds=1),
    )
    assert_launch_allowed(spec, proof=one_second_left, now=_VEC_NOW)


def test_vector_empty_string_scope_is_strict_equality() -> None:
    spec = LaunchSpec(
        path="cursor_grok_bot", launch_id="grok-4.7", effort="medium", fast=False
    )
    empty = _vec_proof("grok-4.7", "medium", False, scope="")
    assert_launch_allowed(spec, proof=empty, approval_scope="", now=_VEC_NOW)
    with pytest.raises(ModelGovernanceError):
        assert_launch_allowed(spec, proof=empty, now=_VEC_NOW)
    with pytest.raises(ModelGovernanceError):
        assert_launch_allowed(spec, proof=empty, approval_scope="task-a", now=_VEC_NOW)
    unscoped = _vec_proof("grok-4.7", "medium", False)
    with pytest.raises(ModelGovernanceError):
        assert_launch_allowed(spec, proof=unscoped, approval_scope="", now=_VEC_NOW)


def test_vector_unknown_proof_kind_is_not_a_token() -> None:
    gated = LaunchSpec(
        path="cursor_grok_bot", launch_id="grok-4.7", effort="medium", fast=False
    )
    unknown = EscalationProof(
        kind="vibes_based_approval",
        reference="synthetic-policy-fixture",
        model_id="grok-4.7",
        effort="medium",
        fast=False,
        expires_at=_VEC_NOW + timedelta(hours=1),
    )
    assert not proof_is_token(unknown, now=_VEC_NOW)
    with pytest.raises(ModelGovernanceError):
        assert_launch_allowed(gated, proof=unknown, now=_VEC_NOW)
    ungated = LaunchSpec(
        path="anthropic", launch_id="claude-sonnet-5-5", effort="medium"
    )
    stray = EscalationProof(
        kind="vibes_based_approval",
        reference="synthetic-policy-fixture",
        model_id="claude-sonnet-5-5",
        effort="medium",
        fast=None,
        expires_at=_VEC_NOW + timedelta(hours=1),
    )
    with pytest.raises(ModelGovernanceError):
        assert_launch_allowed(ungated, proof=stray, now=_VEC_NOW)


@pytest.mark.parametrize("path", ["anthropic", "cursor_grok_bot"])
def test_vector_banned_launch_id_refused_even_with_matching_proof(path) -> None:
    spec = LaunchSpec(path=path, launch_id="grok-4.5", effort="medium", fast=False)
    with pytest.raises(ModelGovernanceError, match="banned"):
        assert_launch_allowed(spec)
    with pytest.raises(ModelGovernanceError, match="banned"):
        assert_launch_allowed(
            spec, proof=_vec_proof("grok-4.5", "medium", False), now=_VEC_NOW
        )


@pytest.mark.parametrize("path", ["anthropic", "cursor_grok_bot"])
def test_vector_fable_requires_budget_cap_on_every_path(path) -> None:
    spec = LaunchSpec(path=path, launch_id="claude-fable-5-1", effort="medium")
    with pytest.raises(ModelGovernanceError, match="budget cap"):
        assert_launch_allowed(
            spec, proof=_vec_proof("claude-fable-5-1", "medium", None), now=_VEC_NOW
        )
    with pytest.raises(ModelGovernanceError):
        assert_launch_allowed(spec)
    assert_launch_allowed(
        spec,
        proof=_vec_proof("claude-fable-5-1", "medium", None, "max_tokens=8192"),
        now=_VEC_NOW,
    )
