"""Unit tests for orchestrator/frugality_router.py (v1.1 P1 spike).

Covers ORAMASYS_OFFLINE tier caps, privacy_critical tier caps, local-first
probing, tier-1 backend_resolver delegation, and trace emission.
Runs offline — no Ollama or external API calls required.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from orchestrator.frugality_router import (
    FrugalityPolicyError,
    ResolvedRoute,
    TIERS,
    ToolCallSpec,
    is_offline_mode,
    max_allowed_tier,
    resolve_route,
)
from perpetua.discovery.backend import Backend, BackendHealth, BackendKind
from perpetua.discovery.registry import BackendRegistry


@pytest.fixture
def registry():
    reg = BackendRegistry()
    reg._backends["lmstudio-win"] = Backend(
        "lmstudio-win",
        "http://127.0.1.1:1234/v1",
        BackendKind.LMSTUDIO,
        ("qwen3-coder-30b",),
        BackendHealth.ONLINE,
        datetime.now(timezone.utc),
    )
    return reg


class TestTiersConstant:
    def test_tiers_cover_0_through_6(self):
        assert set(TIERS.keys()) == set(range(7))
        assert TIERS[0] == "in_context"
        assert TIERS[5] == "paid"


class TestOfflineMode:
    def test_is_offline_mode_env(self, monkeypatch):
        monkeypatch.delenv("ORAMASYS_OFFLINE", raising=False)
        assert is_offline_mode() is False
        monkeypatch.setenv("ORAMASYS_OFFLINE", "1")
        assert is_offline_mode() is True

    def test_offline_caps_max_tier_at_2(self, monkeypatch):
        monkeypatch.setenv("ORAMASYS_OFFLINE", "1")
        spec = ToolCallSpec(task_type="reasoning")
        assert max_allowed_tier(spec) == 2

    def test_offline_rejects_escalation_to_tier_3(self, monkeypatch):
        monkeypatch.setenv("ORAMASYS_OFFLINE", "1")
        spec = ToolCallSpec(
            task_type="reasoning",
            escalation_reason="needs remote OSS",
        )
        with pytest.raises(FrugalityPolicyError, match="ORAMASYS_OFFLINE=1 rejects tier >= 3"):
            resolve_route(spec)

    def test_offline_allows_tier_0(self, monkeypatch):
        monkeypatch.setenv("ORAMASYS_OFFLINE", "1")
        route = resolve_route(ToolCallSpec(in_context=True))
        assert route.tier == 0
        assert route.backend == "in_context"

    def test_offline_allows_tier_1_via_backend_resolver(self, monkeypatch, registry):
        monkeypatch.setenv("ORAMASYS_OFFLINE", "1")
        route = resolve_route(
            ToolCallSpec(task_type="coding", model_hint="qwen3-coder-30b"),
            registry=registry,
        )
        assert route.tier == 1
        assert route.backend == "lmstudio-win"

    def test_offline_allows_tier_2_local_index(self, monkeypatch):
        monkeypatch.setenv("ORAMASYS_OFFLINE", "1")
        route = resolve_route(ToolCallSpec(task_type="gbrain"))
        assert route.tier == 2
        assert route.backend == "gbrain"

    def test_offline_rejects_remote_tier1_override(self, monkeypatch, registry):
        monkeypatch.setenv("ORAMASYS_OFFLINE", "1")
        spec = ToolCallSpec(
            task_type="coding",
            base_url_override="https://api.openai.com/v1",
        )
        with pytest.raises(FrugalityPolicyError, match="ORAMASYS_OFFLINE=1 rejects non-local tier-1"):
            resolve_route(spec, registry=registry)


class TestPrivacyCritical:
    def test_privacy_critical_caps_max_tier_at_3(self):
        spec = ToolCallSpec(privacy_critical=True)
        assert max_allowed_tier(spec) == 3

    def test_privacy_critical_forbids_tier_4_escalation(self):
        spec = ToolCallSpec(
            task_type="reasoning",
            privacy_critical=True,
            escalation_reason="needs brave search",
        )
        with pytest.raises(
            FrugalityPolicyError,
            match="privacy_critical=True forbids tier >= 4",
        ):
            resolve_route(spec, escalation_tier=4)

    def test_privacy_critical_allows_tier_3_escalation(self):
        spec = ToolCallSpec(
            task_type="reasoning",
            privacy_critical=True,
            escalation_reason="hf free inference required",
        )
        route = resolve_route(spec, escalation_tier=3)
        assert route.tier == 3
        assert route.backend == "huggingface_free"

    def test_privacy_critical_prefers_local_tier_1(self, registry):
        route = resolve_route(
            ToolCallSpec(task_type="coding", privacy_critical=True),
            registry=registry,
        )
        assert route.tier == 1
        assert route.est_cost_usd == 0.0

    def test_privacy_critical_rejects_remote_tier1_override(self, registry):
        spec = ToolCallSpec(
            task_type="coding",
            privacy_critical=True,
            base_url_override="https://api.openai.com/v1",
        )
        with pytest.raises(
            FrugalityPolicyError,
            match="privacy_critical=True rejects non-local tier-1",
        ):
            resolve_route(spec, registry=registry)


class TestLocalFirstProbing:
    def test_tier_0_in_context(self):
        route = resolve_route(ToolCallSpec(in_context=True))
        assert route == ResolvedRoute(tier=0, backend="in_context")

    def test_tier_2_before_escalation(self):
        route = resolve_route(ToolCallSpec(task_type="crg"))
        assert route.tier == 2
        assert route.backend == "crg"

    def test_escalation_requires_reason(self):
        with pytest.raises(FrugalityPolicyError, match="escalation_reason is required"):
            resolve_route(ToolCallSpec(task_type="reasoning"), escalation_tier=3)

    def test_escalation_rejects_tier_at_or_below_2(self):
        with pytest.raises(
            FrugalityPolicyError,
            match="cannot escalate to tier 2; tiers 0-2 require probe match",
        ):
            resolve_route(ToolCallSpec(task_type="reasoning"), escalation_tier=2)


class TestTraceEmission:
    def test_trace_writes_ot_tool_tier(self, tmp_path):
        trace_file = tmp_path / "traces" / "session.jsonl"
        route = resolve_route(
            ToolCallSpec(in_context=True, parent_id="req-abc"),
            trace_path=trace_file,
        )
        assert route.tier == 0
        lines = trace_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        span = json.loads(lines[0])
        assert span["attributes"]["ot.tool.tier"] == 0
        assert span["attributes"]["parent_id"] == "req-abc"
        assert span["attributes"]["ot.tool.tier_name"] == "in_context"
