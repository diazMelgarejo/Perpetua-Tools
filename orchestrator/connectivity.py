from __future__ import annotations

import re as _re
from typing import Any, Dict

import httpx


def _probe(url: str, timeout: float = 2.5) -> Dict[str, Any]:
    from utils.ssrf_pinned_adapter import ssrf_request
    try:
        r = ssrf_request("GET", url, timeout=timeout)
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
    return _probe(f"{host.rstrip('/')}/api/tags")


def check_lm_studio(host: str = "http://localhost:1234") -> Dict[str, Any]:
    """LM Studio OpenAI-compatible endpoint on Mac or Windows."""
    return _probe(f"{host.rstrip('/')}/v1/models")


def check_mlx(host: str = "http://localhost:8081") -> Dict[str, Any]:
    """MLX server on Mac (mlx-lm serve)."""
    return _probe(f"{host.rstrip('/')}/v1/models")


def check_perplexity() -> Dict[str, Any]:
    return _probe("https://api.perplexity.ai")


def check_openrouter() -> Dict[str, Any]:
    return _probe("https://openrouter.ai/api/v1/models")


def check_anthropic() -> Dict[str, Any]:
    return _probe("https://api.anthropic.com")


def backend_health_map(
    ollama_host: str = "http://localhost:11434",
    lm_studio_host: str = "http://localhost:1234",
    mlx_host: str = "http://localhost:8081",
) -> Dict[str, Dict[str, Any]]:
    """One-shot health snapshot for all configured backends."""
    return {
        "ollama": check_ollama(ollama_host),
        "lm_studio": check_lm_studio(lm_studio_host),
        "mlx": check_mlx(mlx_host),
        "perplexity": check_perplexity(),
        "openrouter": check_openrouter(),
        "anthropic": check_anthropic(),
    }
