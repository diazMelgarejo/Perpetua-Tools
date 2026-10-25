"""Backend connectivity probes and the concurrent /health fan-out.

Holds the deny-by-default probe for remote vendor APIs, the allowlist probe for
trusted local model servers, live model-online derivation, and the six-way
concurrent ``backend_health_map`` with its cloud-result cache.
"""

from __future__ import annotations

import concurrent.futures as _futures
import re as _re
from typing import Any, Callable, Dict, Optional, Tuple
from urllib.parse import urlsplit as _urlsplit

import httpx

# Whole-fan-out deadline for /health. The Portal calls /health with a 3 s
# timeout, so every stage of the request must fit well inside that.
_HEALTH_DEADLINE_S = 1.5
_LOCAL_PROBE_TIMEOUT_S = 1.0


def _probe(url: str, timeout: float = 2.5) -> Dict[str, Any]:
    """Deny-by-default probe for arbitrary/remote URLs (cloud vendor APIs).

    Routes through the Layer-2 pinned transport. Do not use this for local
    model servers (Ollama/LM Studio/MLX) -- loopback/RFC1918 targets are
    denied by design here; use ``_probe_local`` for those instead.
    """
    from utils.ssrf_pinned_adapter import ssrf_request
    try:
        r = ssrf_request("GET", url, timeout=timeout)
        return {"ok": r.status_code < 400, "status_code": r.status_code, "url": url}
    except Exception as exc:
        return {"ok": False, "status_code": None, "url": url, "error": str(exc)}


def _is_localhost_url(url: str) -> bool:
    """Return True when the URL's hostname is exactly ``localhost`` (case-insensitive); False on unparsable URLs."""
    try:
        return (_urlsplit(url).hostname or "").lower() == "localhost"
    except ValueError:
        return False


def _local_get(url: str, timeout: float) -> "httpx.Response":
    """GET a validated local URL.

    The URL is never rewritten, so proxy bypass (``NO_PROXY=localhost``), SNI
    and certificate hostname checks all keep seeing ``localhost``. For
    ``localhost`` the connection is forced onto IPv4 at the transport level by
    binding the IPv4 wildcard as the source address: the IPv6 candidate then
    fails immediately instead of costing ~2 s on Windows before the fallback.
    """
    if not _is_localhost_url(url):
        return httpx.get(url, timeout=timeout)
    transport = httpx.HTTPTransport(local_address="0.0.0.0")  # noqa: S104 -- source bind, not a listener
    with httpx.Client(transport=transport, timeout=timeout) as client:
        return client.get(url)


def _probe_local(url: str, timeout: float = _LOCAL_PROBE_TIMEOUT_S) -> Dict[str, Any]:
    """Allowlist probe for trusted local/LAN model servers (Ollama, LM Studio, MLX).

    Opposite polarity from ``_probe``: these health checks legitimately
    target loopback/RFC1918 hosts, which the deny-by-default SSRF transport
    would reject. Validates the URL is loopback/RFC1918 via
    ``model_endpoint_url`` (never weakens ``ssrf_request``'s own policy) then
    issues a plain request -- no DNS-rebinding exposure since these are
    fixed, code-reviewed local endpoints, not caller-supplied remote URLs.

    ``localhost`` URLs are forced onto IPv4 at the transport level (see
    ``_local_get``); the URL itself is passed through unchanged.
    """
    from utils.model_endpoint_url import ModelEndpointPolicyError, validate_model_endpoint_url
    try:
        validate_model_endpoint_url(url)
    except ModelEndpointPolicyError as exc:
        return {"ok": False, "status_code": None, "url": url, "error": str(exc)}
    try:
        r = _local_get(url, timeout)
        return {"ok": r.status_code < 400, "status_code": r.status_code, "url": url}
    except Exception as exc:
        return {"ok": False, "status_code": None, "url": url, "error": str(exc)}


# ── live model-online derivation (replaces static models.yml `online:` flag) ──
# A model is "online" when its endpoint is reachable AND, for listable local
# backends, the model id is actually served. Cached per-endpoint with a short TTL
# so list_models() stays cheap (one probe per unique endpoint per TTL window).
import threading as _threading
import time as _time

_ENDPOINT_TTL = 20.0  # seconds
_endpoint_cache: Dict[tuple, tuple] = {}  # (base,backend) -> (monotonic_ts, ok, frozenset[str])
_endpoint_lock = _threading.Lock()
_CLOUD_BACKENDS = {"perplexity", "openrouter", "anthropic", "online", "xai", "cloud"}


def _is_ollama_backend(backend: str) -> bool:
    """True for Ollama and Ollama-family backends (e.g. mac-ollama, ollama-win)."""
    b = backend.lower()
    return b == "ollama" or "ollama" in b


def _served_model_ids(base: str, backend: str, timeout: float = 1.5) -> tuple:
    """(reachable, {served model ids, lowercased}) for a local inference endpoint."""
    base = base.rstrip("/")
    try:
        if _is_ollama_backend(backend):
            r = httpx.get(f"{base}/api/tags", timeout=timeout)
            if r.status_code >= 400:
                return (False, frozenset())
            ms = r.json().get("models", []) or []
            ids = {str(m.get("name", "")).lower() for m in ms} | {str(m.get("model", "")).lower() for m in ms}
        else:  # lm-studio / mlx / OpenAI-compatible
            r = httpx.get(f"{base}/v1/models", timeout=timeout)
            if r.status_code >= 400:
                return (False, frozenset())
            ids = {str(m.get("id", "")).lower() for m in (r.json().get("data", []) or [])}
        return (True, frozenset(i for i in ids if i))
    except Exception:
        return (False, frozenset())


def endpoint_online(base: str, backend: str, model_id: str = "", ttl: float = _ENDPOINT_TTL) -> bool:
    """Live-derived online status (cached). Endpoint reachable AND — for listable
    local backends — the model id is served. Cloud backends: base reachability only.
    Never raises; a failed probe simply reports offline.
    """
    cloud = backend in _CLOUD_BACKENDS
    key = (base, backend)
    now = _time.monotonic()
    with _endpoint_lock:
        cached = _endpoint_cache.get(key)
    if not cached or (now - cached[0]) > ttl:
        if cloud:
            ok, served = _probe(base, timeout=1.5).get("ok", False), frozenset()
        else:
            ok, served = _served_model_ids(base, backend)
        cached = (now, ok, served)
        with _endpoint_lock:
            _endpoint_cache[key] = cached
    ok, served = cached[1], cached[2]
    if not ok:
        return False
    if cloud:
        return ok
    if not model_id:
        return ok
    if not served:
        return False

    def _norm(x: str) -> str:
        """Strip trailing quant/format suffixes (repeatedly) so differently-tagged ids of one model compare equal."""
        # strip trailing quant/format tags (LM Studio lists the base id; the
        # registry name often carries -Q4_K_M / -4bit / -gguf / -mlx etc.)
        prev = None
        while prev != x:
            prev = x
            x = _re.sub(r"[-_:](q\d[\w]*|\d+bit|f16|bf16|fp\d+|gguf|mlx)$", "", x)
        return x

    mid = model_id.lower()
    nmid = _norm(mid)
    for s in served:
        if mid == s or s.startswith(mid + ":") or mid.startswith(s + ":"):
            return True
        if _norm(s) == nmid:
            return True
    return False


def check_ollama(host: str = "http://localhost:11434") -> Dict[str, Any]:
    """Works for shared Ollama on Mac or Windows."""
    return _probe_local(f"{host.rstrip('/')}/api/tags")


def check_lm_studio(host: str = "http://localhost:1234") -> Dict[str, Any]:
    """LM Studio OpenAI-compatible endpoint on Mac or Windows."""
    return _probe_local(f"{host.rstrip('/')}/v1/models")


def check_mlx(host: str = "http://localhost:8081") -> Dict[str, Any]:
    """MLX server on Mac (mlx-lm serve)."""
    return _probe_local(f"{host.rstrip('/')}/v1/models")


def check_perplexity() -> Dict[str, Any]:
    """Probe the Perplexity API root through the deny-by-default remote transport."""
    return _probe("https://api.perplexity.ai")


def check_openrouter() -> Dict[str, Any]:
    """Probe the OpenRouter models endpoint through the deny-by-default remote transport."""
    return _probe("https://openrouter.ai/api/v1/models")


def check_anthropic() -> Dict[str, Any]:
    """Probe the Anthropic API root through the deny-by-default remote transport."""
    return _probe("https://api.anthropic.com")


# ── concurrent /health fan-out ────────────────────────────────────────────────
# Module-level pools, deliberately NOT ``with ThreadPoolExecutor`` blocks: their
# exit waits for every thread, and DNS inside resolve_all has no timeout, so one
# stuck probe would hold /health hostage. Late probes are abandoned and reported
# as timeouts; their threads finish in the background.
#
# Local and cloud probes use SEPARATE pools so stalled cloud probes (internet
# down, LAN up) can never starve the local ones. The cloud pool only ever runs
# single-flight leaders (at most one per cloud backend), so 3 workers suffice;
# callers that merely wait on an in-flight refresh wait in the request thread
# and never occupy a pool worker.
_LOCAL_POOL = _futures.ThreadPoolExecutor(max_workers=6, thread_name_prefix="health-local")
_CLOUD_POOL = _futures.ThreadPoolExecutor(max_workers=3, thread_name_prefix="health-cloud")

_CLOUD_OK_TTL_S = 60.0
_CLOUD_FAIL_TTL_S = 15.0
_cloud_lock = _threading.Lock()
_cloud_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}  # name -> (expires_monotonic, result)
_cloud_inflight: Dict[str, "_futures.Future[Dict[str, Any]]"] = {}


def _reset_cloud_probe_cache_for_tests() -> None:
    """Test hook: drop cached cloud probe results and in-flight markers."""
    with _cloud_lock:
        _cloud_cache.clear()
        _cloud_inflight.clear()


def _failure_result(error: str) -> Dict[str, Any]:
    """Build the standard failed-probe result dict carrying ``error`` and an empty URL."""
    return {"ok": False, "status_code": None, "url": "", "error": error}


def _cloud_acquire(
    name: str,
) -> Tuple[Optional[Dict[str, Any]], Optional["_futures.Future[Dict[str, Any]]"], bool]:
    """Non-blocking cache lookup: ``(cached_result, future, is_leader)``.

    Either a fresh cached copy, or the in-flight future (``is_leader`` True when
    the caller must run the refresh and resolve that future).
    """
    with _cloud_lock:
        cached = _cloud_cache.get(name)
        if cached is not None and cached[0] > _time.monotonic():
            return dict(cached[1]), None, False
        fut = _cloud_inflight.get(name)
        if fut is not None:
            return None, fut, False
        fut = _futures.Future()
        _cloud_inflight[name] = fut
        return None, fut, True


def _cloud_refresh(
    name: str, fn: Callable[[], Dict[str, Any]], fut: "_futures.Future[Dict[str, Any]]"
) -> Dict[str, Any]:
    """Run the leader's probe and ALWAYS publish the outcome.

    The cache write, in-flight removal and future resolution sit in ``finally``
    so even a non-``Exception`` raise cannot leave waiters blocked forever.
    """
    result: Dict[str, Any] = _failure_result("probe did not complete")
    try:
        result = fn()
    except Exception as exc:  # noqa: BLE001 -- a probe must never raise
        result = _failure_result(str(exc))
    except BaseException as exc:
        result = _failure_result(f"probe aborted: {type(exc).__name__}")
        raise
    finally:
        ttl = _CLOUD_OK_TTL_S if result.get("ok") else _CLOUD_FAIL_TTL_S
        with _cloud_lock:
            _cloud_cache[name] = (_time.monotonic() + ttl, result)
            if _cloud_inflight.get(name) is fut:
                _cloud_inflight.pop(name, None)
        try:
            fut.set_result(result)
        except _futures.InvalidStateError:
            pass
    return result


def _cached_cloud_probe(name: str, fn: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    """Cache one cloud probe, keyed by backend name only (never request input).

    60 s on success, 15 s on failure. Single-flight: concurrent callers share
    one in-flight refresh. Always returns a fresh copy of the stored dict.
    """
    cached, fut, leader = _cloud_acquire(name)
    if cached is not None:
        return cached
    assert fut is not None
    if not leader:
        return dict(fut.result())
    return dict(_cloud_refresh(name, fn, fut))


def _timeout_result(url: str) -> Dict[str, Any]:
    """Build the failed-probe result for a probe that missed the health deadline, keeping the URL it was probing."""
    return {
        "ok": False,
        "status_code": None,
        "url": url,
        "error": f"timeout: probe exceeded {_HEALTH_DEADLINE_S:g}s health deadline",
    }


def backend_health_map(
    ollama_host: str = "http://localhost:11434",
    lm_studio_host: str = "http://localhost:1234",
    mlx_host: str = "http://localhost:8081",
) -> Dict[str, Dict[str, Any]]:
    """One-shot health snapshot for all configured backends.

    The six probes run concurrently and the call returns within
    ``_HEALTH_DEADLINE_S``; a probe still running then is reported ``ok: False``
    with a timeout error. The three cloud probes are cached (see
    ``_cloud_acquire``); local probes are always live and run on their own pool.
    """
    # check_* are resolved at call time so tests can monkeypatch them.
    local_specs: Dict[str, Tuple[Callable[[], Dict[str, Any]], str]] = {
        "ollama": (lambda: check_ollama(ollama_host), f"{ollama_host.rstrip('/')}/api/tags"),
        "lm_studio": (lambda: check_lm_studio(lm_studio_host), f"{lm_studio_host.rstrip('/')}/v1/models"),
        "mlx": (lambda: check_mlx(mlx_host), f"{mlx_host.rstrip('/')}/v1/models"),
    }
    cloud_specs: Dict[str, Tuple[Callable[[], Dict[str, Any]], str]] = {
        "perplexity": (lambda: check_perplexity(), "https://api.perplexity.ai"),
        "openrouter": (lambda: check_openrouter(), "https://openrouter.ai/api/v1/models"),
        "anthropic": (lambda: check_anthropic(), "https://api.anthropic.com"),
    }
    urls = {n: u for n, (_f, u) in {**local_specs, **cloud_specs}.items()}
    local_futs = {name: _LOCAL_POOL.submit(fn) for name, (fn, _u) in local_specs.items()}

    ready: Dict[str, Dict[str, Any]] = {}
    cloud_futs: Dict[str, "_futures.Future[Dict[str, Any]]"] = {}
    for name, (fn, _u) in cloud_specs.items():
        cached, fut, leader = _cloud_acquire(name)
        if cached is not None:
            ready[name] = cached
            continue
        assert fut is not None
        cloud_futs[name] = fut
        if leader:
            try:
                _CLOUD_POOL.submit(_cloud_refresh, name, fn, fut)
            except BaseException as exc:  # noqa: BLE001 -- never leave the marker dangling
                with _cloud_lock:
                    if _cloud_inflight.get(name) is fut:
                        _cloud_inflight.pop(name, None)
                try:
                    fut.set_result(_failure_result(f"probe not scheduled: {exc}"))
                except _futures.InvalidStateError:
                    pass

    _futures.wait([*local_futs.values(), *cloud_futs.values()], timeout=_HEALTH_DEADLINE_S)
    out: Dict[str, Dict[str, Any]] = {}
    for name in ("ollama", "lm_studio", "mlx", "perplexity", "openrouter", "anthropic"):
        url = urls[name]
        if name in ready:
            out[name] = ready[name]
            continue
        fut = local_futs.get(name) or cloud_futs[name]
        if not fut.done():
            if name in local_futs:
                fut.cancel()  # never cancel a shared single-flight future
            out[name] = _timeout_result(url)
            continue
        try:
            out[name] = dict(fut.result())
        except Exception as exc:  # noqa: BLE001 -- a probe must never fail /health
            out[name] = {"ok": False, "status_code": None, "url": url, "error": str(exc)}
    return out
