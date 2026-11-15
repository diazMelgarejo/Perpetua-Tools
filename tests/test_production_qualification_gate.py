"""Production candidate resolution must honor the free-first qualification gate.

Regression for the PT #510 review P1: ``candidate_dispatch_allowed()`` correctly
refuses an unqualified candidate, but ``fastapi_app._candidate_availability()``
treated non-local backends as ready without consulting that gate, so catalog
entries marked offline/unqualified still became executable fallbacks through
``_resolve_candidates()``.
"""
import asyncio
from types import SimpleNamespace

import pytest

import orchestrator.fastapi_app as fa


def _candidate(name: str, backend: str = "openrouter") -> SimpleNamespace:
    """A non-local registry candidate: never probed, historically always ready."""
    return SimpleNamespace(
        name=name,
        backend=backend,
        device="cloud" if backend not in fa._LOCAL_RUNTIME_BACKENDS else "local",
        host=None,
        port=None,
        online=True,
    )


def _policy(rows, lane_status="open") -> dict:
    return {
        "lane_qualification": {"status": lane_status},
        "ordered_candidates": rows,
    }


def _unqualified_catalog(policy_overrides: dict | None = None) -> dict:
    rows = [
        {"model_id": "glm-4.7-flash", "pricing_status": "free",
         "qualification_status": "unqualified"},
        {"model_id": "openrouter/free", "pricing_status": "free",
         "qualification_status": "unqualified"},
    ]
    policy = _policy(rows)
    if policy_overrides:
        policy.update(policy_overrides)
    return policy


def test_blocked_catalog_candidates_cannot_become_executable_fallbacks(monkeypatch):
    """The exact review reproduction: gate-denied candidates stay out of the chain.

    Both backends are non-local, so the availability probe would call them ready
    without probing. The qualification gate refuses them; the resolver must not
    return them as resolved candidates OR as the probe-failure fallback chain.
    """
    policy = _unqualified_catalog()
    monkeypatch.setattr(fa, "load_free_first_policy", lambda: policy)
    candidates = [_candidate("glm-4.7-flash"), _candidate("openrouter/free")]

    resolved, availability = asyncio.run(
        fa._resolve_candidates(candidates, "default", policy=policy)
    )

    assert resolved == [], "blocked candidates must not become executable fallbacks"
    for key, entry in availability.items():
        assert entry["dispatch_allowed"] is False
        assert entry["ready"] is False
        assert entry["detail"] == "qualification-gate-blocked"


def test_offline_catalog_flag_blocks_dispatch(monkeypatch):
    """Setting a catalog entry to online=False keeps it out of the resolved chain."""
    rows = [
        {"model_id": "glm-4.7-flash", "pricing_status": "free",
         "qualification_status": "qualified", "online": False},
    ]
    policy = _policy(rows)
    monkeypatch.setattr(fa, "load_free_first_policy", lambda: policy)
    candidate = _candidate("glm-4.7-flash")

    resolved, availability = asyncio.run(
        fa._resolve_candidates([candidate], "default", policy=policy)
    )

    assert resolved == []
    entry = availability["glm-4.7-flash@cloud"]
    assert entry["dispatch_allowed"] is False


def test_blocked_lane_refuses_qualified_candidate(monkeypatch):
    """A blocked lane refuses even a qualified catalog candidate."""
    rows = [
        {"model_id": "glm-4.7-flash", "pricing_status": "free",
         "qualification_status": "qualified"},
    ]
    policy = _policy(rows, lane_status="blocked")
    monkeypatch.setattr(fa, "load_free_first_policy", lambda: policy)

    resolved, _ = asyncio.run(
        fa._resolve_candidates([_candidate("glm-4.7-flash")], "default", policy=policy)
    )
    assert resolved == []


def test_qualified_candidate_still_resolves(monkeypatch):
    """Positive control: the gate admits a qualified, online catalog candidate."""
    rows = [
        {"model_id": "glm-4.7-flash", "pricing_status": "free",
         "qualification_status": "qualified"},
    ]
    policy = _policy(rows)
    monkeypatch.setattr(fa, "load_free_first_policy", lambda: policy)

    resolved, availability = asyncio.run(
        fa._resolve_candidates([_candidate("glm-4.7-flash")], "default", policy=policy)
    )
    assert [c.name for c in resolved] == ["glm-4.7-flash"]
    assert availability["glm-4.7-flash@cloud"]["dispatch_allowed"] is True


def test_uncataloged_local_candidate_is_not_gated(monkeypatch):
    """Candidates absent from the free-first catalog keep registry-trust behavior."""
    policy = _unqualified_catalog()
    monkeypatch.setattr(fa, "load_free_first_policy", lambda: policy)
    local = _candidate("local-coder-model", backend="lm-studio")
    local.device = "local"
    local.backend = "lm-studio"

    resolved, availability = asyncio.run(
        fa._resolve_candidates([local], "default", policy=policy)
    )
    assert [c.name for c in resolved] == ["local-coder-model"]
    assert availability["local-coder-model@local"]["dispatch_allowed"] is True
