from __future__ import annotations

import asyncio
import logging
import os
import shlex
from typing import Any, Dict, List, Optional

log = logging.getLogger("orchestrator.orama_bridge")


OPTIMIZE_FOR_TO_REASONING_DEPTH = {
    "reliability": "ultra",
    "creativity": "deep",
    "speed": "standard",
}

TASK_TYPE_TO_OPTIMIZE_FOR = {
    "deep_reasoning": "reliability",
    "code_analysis": "reliability",
}

TASK_TYPE_TO_HTTP_TASK_TYPE = {
    "deep_reasoning": "analysis",
    "code_analysis": "code",
}


def normalize_oramasys_endpoint(endpoint: str) -> str:
    expanded = os.path.expandvars(str(endpoint or "")).rstrip("/")
    if not expanded:
        return ""
    if expanded.endswith("/oramasys"):
        return expanded
    if expanded.endswith("/ultrathink"):
        return f"{expanded[:-len('/ultrathink')]}/oramasys"
    return f"{expanded}/oramasys"


def parse_oramasys_timeout(timeout_value: Any, default: float = 120.0) -> float:
    expanded = os.path.expandvars(str(timeout_value or "")).strip()
    try:
        return float(expanded)
    except (TypeError, ValueError):
        return default


def build_oramasys_http_payload(task: str, task_type: str) -> Dict[str, Any]:
    optimize_for = TASK_TYPE_TO_OPTIMIZE_FOR.get(task_type, "reliability")
    reasoning_depth = OPTIMIZE_FOR_TO_REASONING_DEPTH[optimize_for]
    http_task_type = TASK_TYPE_TO_HTTP_TASK_TYPE.get(task_type, "analysis")
    return {
        "task_description": task,
        "task_type": http_task_type,
        "optimize_for": optimize_for,
        "reasoning_depth": reasoning_depth,
    }


def _is_local_oramasys_endpoint(url: str) -> bool:
    """True when ``url`` is loopback/RFC1918 (orama's typical deployment).

    ``allow_public=False`` is explicit here regardless of
    ``ALLOW_PUBLIC_MODEL_ENDPOINTS`` -- this call only classifies routing
    (local vs. remote transport), it never gates a request outright, so it
    must not be swayed by an env var meant for a different policy surface.
    """
    from utils.model_endpoint_url import ModelEndpointPolicyError, validate_model_endpoint_url

    try:
        validate_model_endpoint_url(url, allow_public=False)
    except ModelEndpointPolicyError:
        return False
    return True


def call_oramasys_bridge(
    *,
    endpoint: str,
    timeout: float,
    task: str,
    task_type: str,
) -> Dict[str, Any]:
    """Synchronous HTTP bridge kept for direct callers.

    orama runs on loopback/RFC1918 by default (``ORAMA_ENDPOINT`` typically
    ``http://localhost:8001``) -- ``ssrf_request``'s Layer-2 transport denies
    exactly those ranges by design, so routing every call through it would
    make the default local deployment permanently unreachable. Mirrors
    ``connectivity.py``'s ``_probe``/``_probe_local`` split: local endpoints
    (validated via ``validate_model_endpoint_url``, never weakened) use a
    direct request; only remote endpoints go through the deny-by-default
    pinned transport, where a private-range target would itself be the
    suspicious case worth denying.
    """
    url = normalize_oramasys_endpoint(endpoint)
    payload = build_oramasys_http_payload(task, task_type)

    if _is_local_oramasys_endpoint(url):
        import httpx

        response = httpx.post(url, json=payload, timeout=timeout)
    else:
        from utils.ssrf_pinned_adapter import ssrf_request

        response = ssrf_request("POST", url, json=payload, timeout=timeout)

    response.raise_for_status()
    return {
        "endpoint": url,
        "request": payload,
        "response": response.json(),
    }


def _mcp_server_cmd() -> Optional[List[str]]:
    """Return parsed server command from env, or None if unset."""
    raw = (
        os.getenv("ORAMASYS_MCP_SERVER_CMD", "").strip()
        or os.getenv("ULTRATHINK_MCP_SERVER_CMD", "").strip()
    )
    return shlex.split(raw) if raw else None


async def call_oramasys_mcp_or_bridge(
    *,
    endpoint: str,
    timeout: float,
    task: str,
    task_type: str,
) -> Dict[str, Any]:
    """Try MCP transport first; fall back to async HTTP on any failure.

    MCP is attempted only when ORAMASYS_MCP_SERVER_CMD or the legacy
    ULTRATHINK_MCP_SERVER_CMD is set as a deprecated alias. The HTTP fallback
    routes local endpoints (loopback/RFC1918 -- orama's typical deployment)
    through a direct ``httpx.AsyncClient`` call, and only remote endpoints
    through ``ssrf_request`` (the same Layer-2 pinned transport used by
    ``call_oramasys_bridge``, via a worker thread so it doesn't block the
    event loop). See ``call_oramasys_bridge``'s docstring for why: routing
    the default local deployment through the deny-by-default pinned
    transport would make it permanently unreachable.
    """
    from orchestrator.orama_mcp_client import OramasysMCPClient

    cmd = _mcp_server_cmd()
    if cmd:
        try:
            async with OramasysMCPClient(cmd, timeout=timeout) as client:
                result = await asyncio.wait_for(
                    client.call_solve(task, task_type),
                    timeout=timeout,
                )
            return {"transport": "mcp", "result": result}
        except Exception as exc:
            log.warning("MCP transport failed (%s), falling back to HTTP", exc)

    url = normalize_oramasys_endpoint(endpoint)
    payload = build_oramasys_http_payload(task, task_type)

    if _is_local_oramasys_endpoint(url):
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=timeout)
    else:
        from utils.ssrf_pinned_adapter import ssrf_request

        response = await asyncio.to_thread(
            ssrf_request, "POST", url, json=payload, timeout=timeout
        )
    response.raise_for_status()
    return {"transport": "http", "endpoint": url, "request": payload, "response": response.json()}


# Backward-compatible aliases for one v1.x release.
normalize_ultrathink_endpoint = normalize_oramasys_endpoint
parse_ultrathink_timeout = parse_oramasys_timeout
build_ultrathink_http_payload = build_oramasys_http_payload
call_ultrathink_bridge = call_oramasys_bridge
call_ultrathink_mcp_or_bridge = call_oramasys_mcp_or_bridge
