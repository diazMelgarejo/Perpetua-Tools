"""Concurrency, deadline and cache behaviour of the /health backend probes (F20).

All hosts are TEST-NET (192.0.2.x) or ``localhost``; probes are fakes, so no
network traffic happens here.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from orchestrator import connectivity, fastapi_app

_BACKENDS = ["ollama", "lm_studio", "mlx", "perplexity", "openrouter", "anthropic"]
_OLLAMA = "http://192.0.2.10:11434"
_LMS = "http://192.0.2.11:1234"
_MLX = "http://192.0.2.12:8081"


def _ok(name: str) -> Dict[str, Any]:
    return {"ok": True, "status_code": 200, "url": f"test://{name}"}


@pytest.fixture(autouse=True)
def _clean_cache():
    connectivity._reset_cloud_probe_cache_for_tests()
    yield
    connectivity._reset_cloud_probe_cache_for_tests()


def _patch_all(monkeypatch: pytest.MonkeyPatch, fn) -> None:
    for attr in ("check_ollama", "check_lm_studio", "check_mlx"):
        monkeypatch.setattr(connectivity, attr, lambda host, _a=attr: fn(_a, host))
    for attr in ("check_perplexity", "check_openrouter", "check_anthropic"):
        monkeypatch.setattr(connectivity, attr, lambda _a=attr: fn(_a, None))


@pytest.mark.unit
def test_six_probes_run_concurrently(monkeypatch: pytest.MonkeyPatch) -> None:
    barrier = threading.Barrier(6, timeout=5)

    def slow(name: str, host: Any) -> Dict[str, Any]:
        barrier.wait()  # only passes if all six are in flight at once
        time.sleep(0.3)
        return _ok(name)

    _patch_all(monkeypatch, slow)
    start = time.monotonic()
    out = connectivity.backend_health_map(_OLLAMA, _LMS, _MLX)
    elapsed = time.monotonic() - start
    assert list(out) == _BACKENDS
    assert all(v["ok"] for v in out.values())
    assert elapsed < 1.2  # ~max (0.3 s), nowhere near the 1.8 s sum


@pytest.mark.unit
def test_late_probe_reported_as_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(connectivity, "_HEALTH_DEADLINE_S", 0.2)
    release = threading.Event()

    def fn(name: str, host: Any) -> Dict[str, Any]:
        if name == "check_mlx":
            release.wait(5)
        return _ok(name)

    _patch_all(monkeypatch, fn)
    try:
        start = time.monotonic()
        out = connectivity.backend_health_map(_OLLAMA, _LMS, _MLX)
        assert time.monotonic() - start < 1.0
    finally:
        release.set()
    assert out["mlx"]["ok"] is False
    assert out["mlx"]["status_code"] is None
    assert out["mlx"]["url"] == f"{_MLX}/v1/models"
    assert "timeout" in out["mlx"]["error"]
    assert out["ollama"]["ok"] is True


@pytest.mark.unit
def test_cloud_cache_hit_and_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [1000.0]
    monkeypatch.setattr(connectivity._time, "monotonic", lambda: now[0])
    calls = []

    def fn() -> Dict[str, Any]:
        calls.append(1)
        return _ok("cloud")

    first = connectivity._cached_cloud_probe("perplexity", fn)
    now[0] += 59
    second = connectivity._cached_cloud_probe("perplexity", fn)
    assert len(calls) == 1
    assert first == second
    second["ok"] = False  # returned object is a copy
    assert connectivity._cached_cloud_probe("perplexity", fn)["ok"] is True
    now[0] += 2  # 61 s after the refresh
    connectivity._cached_cloud_probe("perplexity", fn)
    assert len(calls) == 2


@pytest.mark.unit
def test_cloud_cache_failure_ttl_is_shorter(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [1000.0]
    monkeypatch.setattr(connectivity._time, "monotonic", lambda: now[0])
    calls = []

    def fn() -> Dict[str, Any]:
        calls.append(1)
        return {"ok": False, "status_code": None, "url": "test://x", "error": "boom"}

    connectivity._cached_cloud_probe("anthropic", fn)
    now[0] += 14
    connectivity._cached_cloud_probe("anthropic", fn)
    assert len(calls) == 1
    now[0] += 2  # 16 s > 15 s failure TTL
    connectivity._cached_cloud_probe("anthropic", fn)
    assert len(calls) == 2


@pytest.mark.unit
def test_cloud_cache_keyed_by_backend_name_only() -> None:
    connectivity._cached_cloud_probe("openrouter", lambda: _ok("a"))
    other = connectivity._cached_cloud_probe("anthropic", lambda: _ok("b"))
    assert other["url"] == "test://b"


@pytest.mark.unit
def test_cloud_cache_single_flight() -> None:
    calls = []
    gate = threading.Event()

    def fn() -> Dict[str, Any]:
        calls.append(1)
        gate.wait(5)
        return _ok("cloud")

    results = []
    threads = [
        threading.Thread(target=lambda: results.append(connectivity._cached_cloud_probe("openrouter", fn)))
        for _ in range(5)
    ]
    for t in threads:
        t.start()
    time.sleep(0.2)
    gate.set()
    for t in threads:
        t.join(5)
    assert len(calls) == 1
    assert len(results) == 5 and all(r["ok"] for r in results)


@pytest.mark.unit
def test_cloud_probe_exception_is_contained_and_cached_as_failure() -> None:
    def boom() -> Dict[str, Any]:
        raise RuntimeError("dns exploded")

    out = connectivity._cached_cloud_probe("perplexity", boom)
    assert out["ok"] is False and "dns exploded" in out["error"]


@pytest.mark.unit
def test_probe_local_connects_ipv4_but_reports_original_url(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: Dict[str, Any] = {}

    class _Resp:
        status_code = 200

    def fake_get(url, timeout=None, headers=None):
        seen.update(url=url, timeout=timeout, headers=headers)
        return _Resp()

    monkeypatch.setattr(connectivity.httpx, "get", fake_get)
    monkeypatch.setattr(
        connectivity._socket,
        "getaddrinfo",
        lambda host, port, family, type_: [(family, type_, 6, "", ("192.0.2.77", port))],
    )
    orig = "http://localhost:11434/api/tags"
    res = connectivity._probe_local(orig)
    assert res == {"ok": True, "status_code": 200, "url": orig}
    assert "192.0.2.77" in seen["url"] and "localhost" not in seen["url"]
    assert seen["headers"] == {"Host": "localhost:11434"}
    assert seen["timeout"] <= 1.0


@pytest.mark.unit
def test_probe_local_non_localhost_url_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: Dict[str, Any] = {}

    class _Resp:
        status_code = 503

    monkeypatch.setattr(
        connectivity.httpx, "get", lambda url, timeout=None, headers=None: seen.update(url=url, h=headers) or _Resp()
    )
    url = _OLLAMA + "/api/tags"
    res = connectivity._probe_local(url)
    assert seen == {"url": url, "h": None}
    assert res["ok"] is False and res["status_code"] == 503 and res["url"] == url


# ── /health endpoint ─────────────────────────────────────────────────────────


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(fastapi_app, "HEALTH_OLLAMA_HOST", _OLLAMA)
    monkeypatch.setattr(fastapi_app, "HEALTH_MLX_HOST", _MLX)
    return TestClient(fastapi_app.app)


@pytest.mark.unit
def test_lm_studio_candidates_probed_concurrently_first_healthy_in_order(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    cands = [f"http://192.0.2.{n}:1234" for n in (21, 22, 23)]
    monkeypatch.setattr(fastapi_app, "health_lm_studio_candidates", lambda: cands)
    barrier = threading.Barrier(3, timeout=5)
    seen = []

    def fake_lms(host: str) -> Dict[str, Any]:
        barrier.wait()  # all three must be in flight together
        seen.append(host)
        # 2nd answers first (fast), 3rd also healthy, 1st unhealthy
        if host == cands[0]:
            time.sleep(0.2)
            return {"ok": False, "url": host}
        return {"ok": True, "url": host}

    captured: Dict[str, Any] = {}

    def fake_map(**kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(fastapi_app, "check_lm_studio", fake_lms)
    monkeypatch.setattr(fastapi_app, "backend_health_map", fake_map)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert sorted(seen) == sorted(cands)
    assert captured["lm_studio_host"] == cands[1]  # first healthy IN ORDER, not fastest


@pytest.mark.unit
def test_lm_studio_none_healthy_falls_back_to_last(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    cands = ["http://192.0.2.31:1234", "http://192.0.2.32:1234"]
    monkeypatch.setattr(fastapi_app, "health_lm_studio_candidates", lambda: cands)
    captured: Dict[str, Any] = {}
    monkeypatch.setattr(fastapi_app, "check_lm_studio", lambda host: {"ok": False, "url": host})
    monkeypatch.setattr(fastapi_app, "backend_health_map", lambda **kw: captured.update(kw) or {})
    assert client.get("/health").status_code == 200
    assert captured == {"ollama_host": _OLLAMA, "lm_studio_host": cands[-1], "mlx_host": _MLX}


@pytest.mark.unit
def test_health_response_shape_unchanged(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setattr(fastapi_app, "health_lm_studio_candidates", lambda: [_LMS])
    monkeypatch.setattr(fastapi_app, "check_lm_studio", lambda host: _ok("lms"))
    _patch_all(monkeypatch, lambda name, host: _ok(name))
    body = client.get("/health").json()
    assert set(body) == {"status", "version", "runtime", "backends"}
    assert body["status"] == "ok"
    assert list(body["backends"]) == _BACKENDS
    for entry in body["backends"].values():
        assert {"ok", "status_code", "url"} <= set(entry)


@pytest.mark.unit
def test_health_stays_fast_with_unreachable_backend(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setattr(fastapi_app, "health_lm_studio_candidates", lambda: [_LMS])
    monkeypatch.setattr(fastapi_app, "check_lm_studio", lambda host: _ok("lms"))
    monkeypatch.setattr(connectivity, "_HEALTH_DEADLINE_S", 0.3)
    release = threading.Event()

    def fn(name: str, host: Any) -> Dict[str, Any]:
        if name in ("check_ollama", "check_openrouter"):
            release.wait(5)
        return _ok(name)

    _patch_all(monkeypatch, fn)
    try:
        start = time.monotonic()
        body = client.get("/health").json()
        assert time.monotonic() - start < 1.5
    finally:
        release.set()
    assert body["backends"]["ollama"]["ok"] is False
    assert "timeout" in body["backends"]["ollama"]["error"]
    assert body["backends"]["openrouter"]["ok"] is False
    assert body["backends"]["anthropic"]["ok"] is True
