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
    Path("docs/standards/model-governance.md"),
    Path("SKILL.md"),
    Path("config/SKILL.md"),
    Path("hardware/SKILL.md"),
    Path(".cursor/commands/model-route.md"),
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
    pointer = Path("docs/standards/model-governance.md").read_text(encoding="utf-8")
    assert "grok-4.6" in pointer
    assert "claude-sonnet-5-5" in pointer
    skill = Path("SKILL.md").read_text(encoding="utf-8")
    assert "claude-sonnet-5-5" in skill
    assert '"model": "claude-sonnet-5"' not in skill
    hardware = Path("hardware/SKILL.md").read_text(encoding="utf-8")
    assert "grok-4.6" in hardware
    assert "| cloud | grok-4.5 |" not in hardware
    config_skill = Path("config/SKILL.md").read_text(encoding="utf-8")
    assert "grok-4.6" in config_skill
    assert "**grok-4.5**" not in config_skill
