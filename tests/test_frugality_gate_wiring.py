"""Integration tests for the v1.1 P4 frugality gate wiring:
ModelRegistry.route_task() and src/perpetua_tools/orchestrator.py's
/orchestrate privacy_critical branch both consulting orchestrator/gate.py
(backed by orchestrator/frugality_router.py) as the single canonical
pre-dispatch policy gate.

Runs offline -- no Ollama/LM Studio/network calls required
(PT_DISABLE_LIVE_MODEL_PROBES=1 avoids ModelRegistry's live endpoint probes).
"""
from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))


def _load_orchestrator_module():
    """Load src/perpetua_tools/orchestrator.py by path (mirrors
    tests/test_resilience.py's _load_orchestrator_module helper) so the
    standalone FastAPI entrypoint doesn't collide with the orchestrator/
    package that shadows it on sys.path."""
    py_file = REPO_ROOT / "src" / "perpetua_tools" / "orchestrator.py"
    spec = importlib.util.spec_from_file_location(
        "orchestrator_gate_wiring_module", py_file
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Pydantic (with `from __future__ import annotations`) resolves forward
    # refs via sys.modules[cls.__module__] -- the module must be registered
    # there before exec_module runs, mirroring
    # tests/test_resilience.py::_load_orchestrator_module.
    sys.modules.setdefault("orchestrator_gate_wiring_module", mod)
    spec.loader.exec_module(mod)
    return mod


class _FakeRedis:
    """Async no-op Redis stub whose methods return empty/None values."""
    async def get(self, *a):
        """Return None, as if the key were absent."""
        return None

    async def incr(self, *a):
        """Accept an increment and do nothing."""
        pass

    async def incrbyfloat(self, *a):
        """Accept a float increment and do nothing."""
        pass

    async def keys(self, *a):
        """Return an empty key list."""
        return []

    async def setex(self, *a):
        """Accept a set-with-expiry and do nothing."""
        pass


@pytest.fixture(autouse=True)
def _disable_live_probes(monkeypatch):
    """Autouse fixture that disables ModelRegistry live endpoint probes for every test."""
    monkeypatch.setenv("PT_DISABLE_LIVE_MODEL_PROBES", "1")


@pytest.fixture
def registry():
    """Provide a ModelRegistry built from the repository config directory."""
    from orchestrator.model_registry import ModelRegistry

    return ModelRegistry(config_dir=str(REPO_ROOT / "config"))


class TestRouteTaskOfflineNeverReturnsPaidRemote:
    """With ORAMASYS_OFFLINE=1, route_task chains contain no paid or remote cloud models."""
    def test_default_route_excludes_paid_and_remote_cloud_when_offline(
        self, registry, monkeypatch
    ):
        """The default route drops all paid and remote cloud models when offline."""
        monkeypatch.setenv("ORAMASYS_OFFLINE", "1")
        chain = registry.route_task("default")
        names = {m.name for m in chain}
        for paid_or_remote in (
            "glm-5.3-flash",
            "sonar-reasoning-pro",
            "claude-sonnet-5",
            "claude-sonnet-5-5",
            "grok-4.7",
        ):
            assert paid_or_remote not in names, (
                f"{paid_or_remote} must not survive ORAMASYS_OFFLINE=1"
            )

    def test_strategy_route_excludes_paid_and_remote_cloud_when_offline(
        self, registry, monkeypatch
    ):
        """The strategy route drops claude-sonnet and glm cloud models when offline."""
        monkeypatch.setenv("ORAMASYS_OFFLINE", "1")
        chain = registry.route_task("strategy")
        names = {m.name for m in chain}
        assert "claude-sonnet-5" not in names
        assert "claude-sonnet-5-5" not in names
        assert "glm-5.3-flash" not in names
        assert "glm-5.3-flash:cloud" not in names

    def test_default_route_unchanged_when_offline_flag_not_set(self, registry, monkeypatch):
        """Without ORAMASYS_OFFLINE the default route still includes glm and claude models."""
        monkeypatch.delenv("ORAMASYS_OFFLINE", raising=False)
        chain = registry.route_task("default")
        names = {m.name for m in chain}
        # Pure superset behavior: nothing dropped when no policy is active.
        assert "glm-5.3-flash" in names
        assert "claude-sonnet-5" in names
        assert "claude-sonnet-5-5" in names

    def test_route_task_signature_and_return_type_unchanged_for_existing_callers(
        self, registry
    ):
        # Existing 2-positional-arg call form must keep working unmodified.
        """route_task keeps its two-positional-argument call form and returns a list."""
        chain = registry.route_task("coding", "win-rtx3080")
        assert isinstance(chain, list)
        assert chain[0].name == "qwen3.5-27b-claude-4.6-opus-reasoning-distilled-v2"


class TestOrchestratorPrivacyCriticalGateWiring:
    """The /orchestrate privacy_critical path consults the frugality gate for each hop."""
    def test_privacy_critical_never_escalates_without_override(self, monkeypatch):
        """Even if a local model's classification were bumped above the
        privacy_critical ceiling, gate_permits() must deny dispatch rather
        than silently proceeding -- proves the override contract holds on
        the real /orchestrate code path, not just in gate.py isolation."""
        orch_mod = _load_orchestrator_module()

        monkeypatch.setitem(orch_mod._FRUGALITY_TIER_BY_MODEL, orch_mod.LMS_WIN_MODEL, 5)
        monkeypatch.setitem(orch_mod._FRUGALITY_TIER_BY_MODEL, orch_mod.LMS_MAC_MODEL, 5)

        calls = {"lmstudio": 0}

        async def _tracking_lmstudio(*a, **kw):
            """Stub LM Studio call that counts invocations and returns a sentinel result."""
            calls["lmstudio"] += 1
            return "should not be reached"

        async def _none(*a, **kw):
            """Async stub that returns None."""
            return None

        monkeypatch.setattr(orch_mod, "call_oramasys", _none)
        monkeypatch.setattr(orch_mod, "call_lmstudio", _tracking_lmstudio)
        monkeypatch.setattr(orch_mod, "call_ollama", _none)
        monkeypatch.setattr(orch_mod, "r", _FakeRedis())

        req = orch_mod.OrchestrationRequest(
            task_description="sensitive local-only task",
            privacy_critical=True,
            enable_critic=False,
        )
        handler = getattr(orch_mod.orchestrate, "__wrapped__", orch_mod.orchestrate)
        resp = asyncio.run(handler(req, None))

        assert calls["lmstudio"] == 0, (
            "gate must deny dispatch to a tier-5-classified model under privacy_critical"
        )
        assert any("Frugality gate denied" in line for line in resp.routing_log)

    def test_privacy_critical_dispatches_normally_for_unclassified_or_local_models(
        self, monkeypatch
    ):
        """Byte-identical fall-through behavior for today's actual
        config/models.yml classifications (all local-tier for these models)."""
        orch_mod = _load_orchestrator_module()

        calls = {"lmstudio": 0}

        async def _tracking_lmstudio(*a, **kw):
            """Stub LM Studio call that counts invocations and returns a local result."""
            calls["lmstudio"] += 1
            return "local result"

        async def _none(*a, **kw):
            """Async stub that returns None."""
            return None

        monkeypatch.setattr(orch_mod, "call_oramasys", _none)
        monkeypatch.setattr(orch_mod, "call_lmstudio", _tracking_lmstudio)
        monkeypatch.setattr(orch_mod, "call_ollama", _none)
        monkeypatch.setattr(orch_mod, "r", _FakeRedis())

        req = orch_mod.OrchestrationRequest(
            task_description="sensitive local-only task",
            privacy_critical=True,
            enable_critic=False,
        )
        handler = getattr(orch_mod.orchestrate, "__wrapped__", orch_mod.orchestrate)
        resp = asyncio.run(handler(req, None))

        assert calls["lmstudio"] == 1
        assert resp.result == "local result"
        assert not any("Frugality gate denied" in line for line in resp.routing_log)

    def test_privacy_critical_oramasys_step_always_permitted_no_tier_entry(self, monkeypatch):
        """oramasys has no config/models.yml entry -> tier=None -> gate has
        no opinion -> the primary local-orchestrator hop is always tried,
        matching pre-gate behavior exactly."""
        orch_mod = _load_orchestrator_module()

        assert orch_mod._FRUGALITY_TIER_BY_MODEL.get("oramasys") is None

        calls = {"oramasys": 0}

        async def _tracking_oramasys(*a, **kw):
            """Stub oramasys call that counts invocations and returns a sentinel result."""
            calls["oramasys"] += 1
            return "oramasys result"

        monkeypatch.setattr(orch_mod, "call_oramasys", _tracking_oramasys)
        monkeypatch.setattr(orch_mod, "r", _FakeRedis())

        req = orch_mod.OrchestrationRequest(
            task_description="sensitive local-only task",
            privacy_critical=True,
            enable_critic=False,
        )
        handler = getattr(orch_mod.orchestrate, "__wrapped__", orch_mod.orchestrate)
        resp = asyncio.run(handler(req, None))

        assert calls["oramasys"] == 1
        assert resp.result == "oramasys result"
