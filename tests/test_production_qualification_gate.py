"""Production candidate resolution must honor the free-first qualification gate.

Regression for the PT #510 review P1: ``candidate_dispatch_allowed()`` correctly
refuses an unqualified candidate, but ``fastapi_app._candidate_availability()``
treated non-local backends as ready without consulting that gate, so catalog
entries marked offline/unqualified still became executable fallbacks through
``_resolve_candidates()``.
"""
import asyncio
import contextlib
from typing import Any
from types import SimpleNamespace

import pytest

import orchestrator.fastapi_app as fa


def _candidate(name: str, backend: str = "openrouter") -> SimpleNamespace:
    """A non-local registry candidate: never probed, historically always ready."""
    return SimpleNamespace(
        name=name,
        backend=backend,
        device="cloud" if backend not in fa._LOCAL_RUNTIME_BACKENDS else "local",
        host="https://example.invalid",
        port=443,
        online=True,
        reasoning=False,
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


# --- Round 2: the review's P1 (fail-open policy load) and P2 (denied-candidate probe) ---


@contextlib.contextmanager
def _client():
    """TestClient with routing-state resolution and ECC sync mocked out."""
    from unittest.mock import patch

    from fastapi.testclient import TestClient

    async def fake_resolve_routing_state():
        return {
            "manager_endpoint": "http://127.0.2.2:11434",
            "manager_model": "glm-5.3-flash:cloud",
            "manager_backend": "mac-ollama",
            "coder_endpoint": "http://127.0.2.1:1234",
            "coder_model": "Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-v2",
            "coder_backend": "windows-lmstudio",
            "distributed": True,
        }

    with (
        patch("orchestrator.fastapi_app.resolve_routing_state", new=fake_resolve_routing_state),
        patch("orchestrator.fastapi_app.sync_ecc_tools", return_value={"status": "ok", "message": "mocked"}),
    ):
        yield TestClient(fa.app)


def test_policy_load_failure_refuses_dispatch(monkeypatch):
    """P1: an unavailable policy must refuse dispatch, never disable the gate.

    Fail-secure: the handler loads ONE validated snapshot before route
    assembly; if it cannot, the request answers 503 instead of dispatching
    already-assembled unqualified candidates.
    """
    def broken_loader():
        raise FileNotFoundError("bigmodel-free-first-policy.json missing")

    monkeypatch.setattr(fa, "load_free_first_policy", broken_loader)
    with _client() as client:
        resp = client.post("/orchestrate", json={"task": "ping", "task_type": "default"})
    assert resp.status_code == 503
    assert "policy unavailable" in resp.json()["detail"]


def test_policy_load_failure_refuses_dispatch_on_value_error(monkeypatch):
    """P1: a malformed policy document is the same fail-secure refusal."""
    def malformed_loader():
        raise ValueError("free-first policy must be a JSON object")

    monkeypatch.setattr(fa, "load_free_first_policy", malformed_loader)
    with _client() as client:
        resp = client.post("/orchestrate", json={"task": "ping", "task_type": "default"})
    assert resp.status_code == 503
    assert "policy unavailable" in resp.json()["detail"]


def test_denied_candidate_is_not_probed(monkeypatch):
    """P2: a gate-denied candidate must not reach the availability probe.

    A denied Ollama-backed GLM cloud candidate would otherwise hit the one-shot
    cloud probe even though it can never be dispatched.
"""
    rows = [
        {"model_id": "glm-4.7-flash", "pricing_status": "free",
         "qualification_status": "unqualified"},
    ]
    policy = _policy(rows)
    monkeypatch.setattr(fa, "load_free_first_policy", lambda: policy)

    probed = []

    async def spy_availability(model):
        probed.append(getattr(model, "name", "?"))
        return True, "spy-ready"

    monkeypatch.setattr(fa, "_candidate_availability", spy_availability)
    candidate = _candidate("glm-4.7-flash")

    resolved, availability = asyncio.run(
        fa._resolve_candidates([candidate], "default", policy=policy)
    )

    assert resolved == []
    assert probed == [], "denied candidate must be skipped, not probed"
    entry = availability["glm-4.7-flash@cloud"]
    assert entry["dispatch_allowed"] is False
    assert entry["detail"] == "qualification-gate-blocked"


def test_single_policy_snapshot_shared_with_route_assembly(monkeypatch):
    """P1: route construction and qualification share ONE validated snapshot.

    Reading the policy twice leaves a failure window between assembly and the
    gate. The handler must load once, hand the same snapshot to route_task,
    and the registry must not re-read the file.
"""
    import orchestrator.model_registry as mr

    policy = _unqualified_catalog()
    calls = {"loader": 0, "registry_loader": 0}

    def counting_loader():
        calls["loader"] += 1
        return policy

    def counting_registry_loader():
        calls["registry_loader"] += 1
        return policy

    monkeypatch.setattr(fa, "load_free_first_policy", counting_loader)
    monkeypatch.setattr(mr, "load_policy", counting_registry_loader)

    captured = {}

    def fake_route_task(task_type, preferred_device=None, **kwargs):
        captured.update(kwargs)
        return [_candidate("glm-4.7-flash")]

    monkeypatch.setattr(fa.registry, "route_task", fake_route_task)

    with _client() as client:
        resp = client.post("/orchestrate", json={"task": "ping", "task_type": "default"})
    # Empty chain resolves to the 503 no-qualified-candidate response; the
    # snapshot assertions below are independent of that outcome.
    assert resp.status_code in (200, 503)
    assert calls["loader"] == 1, "the handler must load the policy exactly once"
    assert calls["registry_loader"] == 0, "route assembly must reuse the snapshot, not re-read"
    assert captured.get("policy") is policy


def test_orchestrate_fallback_chain_excludes_gate_denied(monkeypatch):
    """Response fallback_chain must not advertise qualification-blocked models.

    CodeRabbit outside-diff nit: /orchestrate built fallback_chain from the
    ungated route_candidates list, so a catalog-denied sibling could appear in
    the response even though the executable resolver already excluded it.
    """
    rows = [
        {"model_id": "glm-4.7-flash", "pricing_status": "free",
         "qualification_status": "qualified"},
        {"model_id": "openrouter/free", "pricing_status": "free",
         "qualification_status": "unqualified"},
    ]
    policy = _policy(rows)
    monkeypatch.setattr(fa, "load_free_first_policy", lambda: policy)

    qualified = _candidate("glm-4.7-flash")
    denied = _candidate("openrouter/free")

    monkeypatch.setattr(
        fa.registry,
        "route_task",
        lambda task_type, preferred_device=None, **kwargs: [qualified, denied],
    )

    async def always_ready(_model):
        return True, "mock-ready"

    monkeypatch.setattr(fa, "_candidate_availability", always_ready)

    with _client() as client:
        resp = client.post(
            "/orchestrate",
            json={"task": "fallback-chain gate check", "task_type": "default", "force": True},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["selected_model"]["name"] == "glm-4.7-flash"
    fallback_names = [entry["name"] for entry in body["fallback_chain"]]
    assert "openrouter/free" not in fallback_names
    assert body["availability"]["openrouter/free@cloud"]["dispatch_allowed"] is False
