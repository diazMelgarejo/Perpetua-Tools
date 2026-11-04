"""Unit tests for orchestrator/gate.py -- the canonical pre-dispatch policy
gate wrapper around orchestrator/frugality_router.py.

Covers: consult_gate()/gate_permits() fall-through ("no opinion") contract,
the override_confirmed + override_reason contract that prevents silent
privacy_critical escalation, filter_chain_by_gate() used by
ModelRegistry.route_task(), and load_frugality_tier_by_name() used by
src/perpetua_tools/orchestrator.py's privacy_critical branch.
Runs offline -- no Ollama or external API calls required.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from orchestrator.gate import (
    consult_gate,
    filter_chain_by_gate,
    gate_permits,
    load_frugality_tier_by_name,
)


@dataclass(frozen=True)
class _FakeCandidate:
    """Minimal stand-in for a model-chain entry carrying a name and optional frugality tier."""
    name: str
    frugality_tier: Optional[int] = None


class TestNoOpinionFallThrough:
    """Gate has no opinion (permits everything) when nothing is classified or no registry."""
    def test_unclassified_tier_is_always_permitted(self):
        """A candidate with no frugality tier is permitted even under privacy_critical."""
        allowed, reason = gate_permits(None, privacy_critical=True)
        assert allowed is True
        assert reason is None

    def test_consult_gate_returns_no_route_and_no_denial_when_unclassified(self):
        """An unclassified tier yields a decision with no route and no denial reason."""
        decision = consult_gate("reasoning", privacy_critical=True, frugality_tier=None)
        assert decision.has_route is False
        assert decision.route is None
        assert decision.denied_reason is None

    def test_consult_gate_returns_no_route_and_no_denial_without_registry(self):
        """Without a registry the gate returns a decision with no route and no denial reason."""
        decision = consult_gate("reasoning", privacy_critical=False)
        assert decision.has_route is False
        assert decision.denied_reason is None

    def test_filter_chain_keeps_unclassified_candidates_unchanged(self):
        """Filtering a chain of unclassified candidates returns it unchanged."""
        chain = [_FakeCandidate("a"), _FakeCandidate("b"), _FakeCandidate("c")]
        assert filter_chain_by_gate(chain) == chain

    def test_filter_chain_is_pure_superset_when_nothing_classified(self, monkeypatch):
        """With ORAMASYS_OFFLINE set, unclassified candidates all survive filtering (no drops)."""
        monkeypatch.setenv("ORAMASYS_OFFLINE", "1")
        chain = [_FakeCandidate("a"), _FakeCandidate("b")]
        assert filter_chain_by_gate(chain, privacy_critical=True) == chain


class TestOfflineModeFiltering:
    """ORAMASYS_OFFLINE mode drops classified paid tiers and cannot be overridden."""
    def test_offline_drops_classified_tier_above_2(self, monkeypatch):
        """Offline mode denies a classified tier above 2 and cites ORAMASYS_OFFLINE."""
        monkeypatch.setenv("ORAMASYS_OFFLINE", "1")
        allowed, reason = gate_permits(5, privacy_critical=False)
        assert allowed is False
        assert "ORAMASYS_OFFLINE" in reason

    def test_offline_keeps_classified_tier_at_or_below_2(self, monkeypatch):
        """Offline mode still permits a classified tier of 2 or lower with no reason."""
        monkeypatch.setenv("ORAMASYS_OFFLINE", "1")
        allowed, reason = gate_permits(1, privacy_critical=False)
        assert allowed is True
        assert reason is None

    def test_offline_filters_paid_remote_out_of_chain(self, monkeypatch):
        """Offline filtering removes the tier-5 candidate but keeps tier-1 and unclassified ones."""
        monkeypatch.setenv("ORAMASYS_OFFLINE", "1")
        chain = [
            _FakeCandidate("local-1", frugality_tier=1),
            _FakeCandidate("cloud-paid", frugality_tier=5),
            _FakeCandidate("unclassified"),
        ]
        result = filter_chain_by_gate(chain)
        names = [c.name for c in result]
        assert "cloud-paid" not in names
        assert "local-1" in names
        assert "unclassified" in names

    def test_offline_cannot_be_overridden(self, monkeypatch):
        """Offline mode denies a tier-5 model even with a confirmed override and reason (airgap)."""
        monkeypatch.setenv("ORAMASYS_OFFLINE", "1")
        allowed, reason = gate_permits(
            5,
            privacy_critical=False,
            override_confirmed=True,
            override_reason="I really need it",
        )
        assert allowed is False
        assert "airgap" in reason


class TestPrivacyCriticalOverrideContract:
    """privacy_critical escalation above the ceiling requires a confirmed, non-blank override."""
    def test_privacy_critical_denies_tier_above_3_without_override(self):
        """privacy_critical denies tier 5 with no override and names override_confirmed."""
        allowed, reason = gate_permits(5, privacy_critical=True)
        assert allowed is False
        assert "override_confirmed" in reason

    def test_privacy_critical_denies_with_override_confirmed_but_empty_reason(self):
        """A confirmed override with an empty reason is still denied for tier 5."""
        allowed, _ = gate_permits(
            5, privacy_critical=True, override_confirmed=True, override_reason=""
        )
        assert allowed is False

    def test_privacy_critical_denies_with_override_confirmed_whitespace_reason(self):
        """A confirmed override with a whitespace-only reason is still denied for tier 5."""
        allowed, _ = gate_permits(
            5, privacy_critical=True, override_confirmed=True, override_reason="   "
        )
        assert allowed is False

    def test_privacy_critical_denies_with_reason_but_override_not_confirmed(self):
        """A reason without override_confirmed is still denied for tier 5."""
        allowed, _ = gate_permits(
            5,
            privacy_critical=True,
            override_confirmed=False,
            override_reason="human confirmed this is fine",
        )
        assert allowed is False

    def test_privacy_critical_permits_escalation_with_confirmed_and_reasoned_override(self):
        """A confirmed override with a real reason permits tier 5 and returns no denial reason."""
        allowed, reason = gate_permits(
            5,
            privacy_critical=True,
            override_confirmed=True,
            override_reason="human confirmed via AskUserQuestion",
        )
        assert allowed is True
        assert reason is None

    def test_privacy_critical_permits_tier_at_or_below_default_ceiling_without_override(self):
        """Tier 3 is permitted under privacy_critical without any override."""
        allowed, _ = gate_permits(3, privacy_critical=True)
        assert allowed is True

    def test_filter_chain_never_escalates_privacy_critical_without_override(self):
        """privacy_critical chain filtering drops the tier-5 candidate and keeps the local one."""
        chain = [
            _FakeCandidate("local", frugality_tier=1),
            _FakeCandidate("paid-remote", frugality_tier=5),
        ]
        result = filter_chain_by_gate(chain, privacy_critical=True)
        names = [c.name for c in result]
        assert "paid-remote" not in names
        assert "local" in names

    def test_filter_chain_allows_escalation_only_with_confirmed_reasoned_override(self):
        """Chain filtering keeps a tier-5 candidate only with a confirmed, reasoned override."""
        chain = [_FakeCandidate("paid-remote", frugality_tier=5)]
        denied = filter_chain_by_gate(chain, privacy_critical=True)
        assert denied == []
        allowed = filter_chain_by_gate(
            chain,
            privacy_critical=True,
            override_confirmed=True,
            override_reason="human confirmed",
        )
        assert allowed == chain


class TestLoadFrugalityTierByName:
    """load_frugality_tier_by_name maps model names to tiers from the config."""
    def test_returns_dict_keyed_by_model_name(self):
        """The loader returns a dict with at least 11 model entries."""
        tiers = load_frugality_tier_by_name()
        assert isinstance(tiers, dict)
        assert len(tiers) >= 11

    def test_local_lmstudio_models_are_low_tier(self):
        """Local LM Studio models are classified at tier 1 or 2."""
        tiers = load_frugality_tier_by_name()
        assert tiers["qwen3.5-27b-claude-4.6-opus-reasoning-distilled-v2"] in (1, 2)
        assert tiers["Qwen3.5-9B-MLX-4bit"] in (1, 2)

    def test_local_ollama_models_are_low_tier(self):
        """Local Ollama models are classified at tier 1 or 2."""
        tiers = load_frugality_tier_by_name()
        assert tiers["qwen3.5:35b-a3b-q4_K_M"] in (1, 2)
        assert tiers["qwen3-30b-autoresearch-critic"] in (1, 2)

    def test_paid_cloud_models_are_classified_tier_3_or_above(self):
        """Paid cloud models (glm, sonar, claude, grok) are classified tier 3 or above."""
        tiers = load_frugality_tier_by_name()
        assert tiers["glm-5.3-flash"] >= 3
        assert tiers["sonar-reasoning-pro"] >= 3
        assert tiers["claude-sonnet-5"] >= 3
        assert tiers["claude-sonnet-5-5"] >= 3
        assert tiers["grok-4.7"] >= 3

    def test_unknown_model_name_is_absent_not_erroring(self):
        """An unknown model name is simply absent from the mapping rather than raising."""
        tiers = load_frugality_tier_by_name()
        assert tiers.get("some-model-not-in-config") is None
