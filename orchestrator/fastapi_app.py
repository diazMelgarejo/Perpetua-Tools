from __future__ import annotations

import asyncio
import collections
import json
import logging
import re as _re
import os
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from orchestrator.control_plane_auth import (
    ensure_control_plane_token,
    redact_runtime_payload,
)
from orchestrator.control_plane_asgi import ControlPlaneAuthMiddleware

from orchestrator import autoresearch_bridge
from orchestrator import __version__ as _ORCHESTRATOR_VERSION
from orchestrator.agent_tracker import AgentTracker
from orchestrator.connectivity import backend_health_map
from utils.endpoint_policy_core import build_transport_url
from utils.model_endpoint_url import ModelEndpointPolicyError, validate_model_endpoint_url
from orchestrator.control_plane import (
    bootstrap_runtime,
    load_runtime_payload,
    resolve_routing_state,
)
from orchestrator.cost_guard import CostGuard
from orchestrator.ecc_tools_sync import get_sync_status, sync_ecc_tools
from orchestrator.model_registry import ModelRegistry
from orchestrator.model_transport import (
    ProviderConfigError,
    ProviderTransportError,
    ProviderTransportRegistry,
)
from orchestrator.orama_bridge import (
    call_oramasys_mcp_or_bridge,
    parse_oramasys_timeout,
)
from orchestrator.tiered_pipeline import (
    PipelineApproval,
    PipelineApprovalError,
    PipelineConfigError,
    PipelineDisabledError,
    PipelineExecutionError,
    PipelinePolicyError,
    TieredPipelineRunner,
    load_pipeline_approval,
    register_pipeline_approval,
    tiered_pipeline_enabled,
    TRACE_ID_PATTERN,
)
from orchestrator.gossip_bus import GossipBus
from orchestrator.lan_gossip_bridge import _load_peers as _load_gossip_peers

_startup_log = logging.getLogger("orchestrator.fastapi_app")
# trace_id becomes a filename component (see tiered_pipeline.py's
# register_pipeline_approval/load_pipeline_approval). Restricting it to
# alphanumeric plus hyphen/underscore rejects path separators and "." (so
# "..") outright, before it ever reaches the filesystem layer -- the second,
# independent containment check there is defense-in-depth, not the only gate.
_TRACE_ID_PATTERN = r"^%s$" % TRACE_ID_PATTERN
_GLM_ORCHESTRATOR_MODEL = "glm-5.1:cloud"
_AUTORESEARCH_TASK_TYPES = {"autoresearch", "autoresearch-coder", "ml-experiment"}
_LOCAL_RUNTIME_BACKENDS = {"ollama", "lm-studio", "mlx"}

# GC guard for fire-and-forget startup tasks (D_GCG-1 from RAG backport 2026-05-22).
# asyncio.create_task() only holds a *weak* reference; without a strong reference
# in this set the task can be collected before it completes.  Each task discards
# itself via done-callback so the set stays bounded.
_bg_startup_tasks: set[asyncio.Task] = set()

# Shared gossip bus singleton — initialized once in lifespan, reused by endpoints.
_gossip_bus: GossipBus | None = None


def _init_gossip_db() -> None:
    """Initialize the shared gossip bus SQLite schema (idempotent).

    This function runs inside an executor worker thread during FastAPI
    lifespan startup. Worker threads do not have a default event loop on
    modern Python, so asyncio.get_event_loop().run_until_complete() would
    raise RuntimeError. asyncio.run() creates and closes the loop in this
    worker thread deterministically.
    """
    global _gossip_bus
    try:
        _gossip_bus = GossipBus()
        asyncio.run(_gossip_bus.init_db())
        _startup_log.info("GossipBus initialized: %s", _gossip_bus.db_path)
    except Exception as exc:  # noqa: BLE001
        _startup_log.warning("GossipBus init failed (non-fatal): %s", exc)


from orchestrator.mesh_auth import require_gossip_auth as _require_gossip_auth

def _run_ecc_sync_bg() -> None:
    """Blocking ECC sync run in a worker thread so startup stays responsive."""
    try:
        ecc_result = sync_ecc_tools(force=False)
        _startup_log.info(
            "ECC Tools sync: %s - %s",
            ecc_result.get("status"),
            ecc_result.get("message", ""),
        )
    except Exception as exc:  # noqa: BLE001
        _startup_log.warning("ECC Tools sync failed (non-fatal): %s", exc)


async def _resolve_routing_bg() -> None:
    """Resolve routing state in background — non-blocking startup."""
    try:
        routing = await resolve_routing_state()
        _startup_log.info(
            "Routing: manager=%s coder=%s (%s) distributed=%s",
            routing["manager_endpoint"],
            routing["coder_endpoint"],
            routing.get("coder_backend", "?"),
            routing["distributed"],
        )
    except Exception as exc:  # noqa: BLE001
        _startup_log.warning("Backend detection failed (non-fatal): %s", exc)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    token = ensure_control_plane_token()
    if token:
        _startup_log.info(
            "Control-plane bearer auth active; token persisted to .state/control_plane_token"
        )
    # GossipBus init runs in executor so it never blocks port binding.
    asyncio.get_event_loop().run_in_executor(None, _init_gossip_db)
    # Both background tasks fire at t=0; neither blocks port binding.
    asyncio.get_event_loop().run_in_executor(None, _run_ecc_sync_bg)
    # Hold a strong reference so GC cannot collect the task before it runs (D_GCG-1).
    _routing_task = asyncio.create_task(_resolve_routing_bg(), name="routing-bg")
    _bg_startup_tasks.add(_routing_task)
    _routing_task.add_done_callback(_bg_startup_tasks.discard)
    yield


app = FastAPI(
    title="Perpetua-Tools Orchestrator",
    version=_ORCHESTRATOR_VERSION,
    description=(
        "Top-level idempotent multi-agent orchestrator. "
        "Repo #1 complements orama-system with routing, runtime "
        "reconciliation, and control-plane state."
    ),
    lifespan=_lifespan,
)

# ``add_middleware`` inserts at the outside of the current stack.  Register
# auth first so CORS remains outermost and rejected browser requests retain
# the policy headers needed by a legitimate frontend.
app.add_middleware(ControlPlaneAuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://localhost:3000",
        "http://localhost:8002", "http://localhost:8002",  # portal
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


tracker = AgentTracker()
registry = ModelRegistry()
cost_guard = CostGuard()
_ORAMASYS_TASK_TYPES = {"deep_reasoning", "code_analysis"}

# ── User-input queue ──────────────────────────────────────────────────────────
# Shared in-process queue; agents poll GET /user-input/next to consume tasks.
# Portal or CLI can push via POST /user-input.
_USER_INPUT_QUEUE: collections.deque[Dict[str, Any]] = collections.deque(maxlen=50)


class OrchestrateRequest(BaseModel):
    task: str
    task_type: str = "default"
    preferred_device: Optional[str] = None
    estimated_cost: float = 0.0
    parent_agent_id: Optional[str] = None
    force: bool = False


class TieredPipelineRequest(BaseModel):
    """Explicit request body for an authenticated, paid pipeline execution.

    Carries only a reference (``trace_id``) to a previously-registered
    approval artifact, never inline approval fields. A single endpoint that
    accepted either an artifact reference OR inline approval data would let a
    caller pick whichever is easier to satisfy, silently downgrading the
    approval boundary to its weakest supported form -- so this is the only
    shape accepted.
    """

    prompt: str = Field(min_length=1, max_length=32768)
    trace_id: str = Field(min_length=8, max_length=128, pattern=_TRACE_ID_PATTERN)
    privacy_critical: bool = False
    override_confirmed: bool = False
    override_reason: Optional[str] = None

    @field_validator("prompt")
    @classmethod
    def _validate_prompt(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("prompt cannot be empty or whitespace only")
        return v


class PipelineApprovalRequest(BaseModel):
    """Registers one approval artifact -- a distinct, prior step from execution.

    Deliberately the only place inline approval fields are accepted. Once
    registered, execution (POST /pipelines/{recipe_name}/run) can only
    reference the artifact by trace_id -- never re-supply or override its
    fields inline.
    """

    trace_id: str = Field(min_length=8, max_length=128, pattern=_TRACE_ID_PATTERN)
    approved_by: str = Field(min_length=1, max_length=256)
    purpose: str = Field(min_length=1, max_length=1024)
    recipe: str = Field(min_length=1, max_length=128)
    route_tier: int
    max_tokens: int = Field(gt=0)
    max_cost_usd: float = Field(gt=0)
    expires_at: str
    scope: List[str] = Field(min_length=1)


class ConflictResponse(BaseModel):
    conflict: bool
    message: str
    existing_agents: List[Dict[str, Any]]


def get_tiered_pipeline_runner() -> TieredPipelineRunner:
    """Construct the policy-only runner; no provider credentials are read here."""
    return TieredPipelineRunner()


def get_provider_transport() -> ProviderTransportRegistry:
    """Construct the PT-owned native transport at the execution boundary."""
    return ProviderTransportRegistry()


def _runtime_summary() -> dict[str, Any]:
    runtime_state = load_runtime_payload()
    if runtime_state is None:
        return {"available": False, "gateway_ready": False, "distributed": False}
    return {
        "available": True,
        "gateway_ready": bool(runtime_state.get("gateway", {}).get("gateway_ready")),
        "distributed": bool(runtime_state.get("routing", {}).get("distributed")),
    }


def _candidate_base_url(host: str, port: int) -> str:
    # Route through the shared endpoint_policy_core boundary so a malformed
    # host string (bad port syntax/range) can never raise a bare ValueError
    # here — parse_transport_identity/build_transport_url swallow ValueError
    # internally and fall back to the plain host:port reconstruction below.
    built = build_transport_url(host, port)
    if built is not None:
        return built
    return f"{host.rstrip('/')}:{port}"


def _normalize_model_name(value: str) -> str:
    return value.strip().lower().replace("_", "-")


def _model_matches(available: str, expected: str) -> bool:
    lhs = _normalize_model_name(available)
    rhs = _normalize_model_name(expected)
    return lhs == rhs or lhs.startswith(rhs) or rhs.startswith(lhs) or rhs in lhs or lhs in rhs


def _is_local_candidate(model: Any) -> bool:
    return getattr(model, "backend", "") in _LOCAL_RUNTIME_BACKENDS and getattr(model, "device", "") != "cloud"


async def _probe_openai_compatible(
    base_url: str,
    expected_model: str,
    *,
    timeout: float,
    token: str = "",
) -> tuple[bool, str]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(f"{base_url}/v1/models", headers=headers)
        if resp.status_code >= 400:
            return False, f"HTTP {resp.status_code}"
        payload = resp.json()
        models = payload.get("data", []) if isinstance(payload, dict) else []
        ids = [
            item.get("id") or item.get("name") or ""
            for item in models
            if isinstance(item, dict)
        ]
        if ids and any(_model_matches(model_id, expected_model) for model_id in ids):
            return True, "model-available"
        if ids:
            return False, f"model-not-loaded:{expected_model}"
        return True, "reachable"


async def _probe_ollama_model(
    base_url: str,
    expected_model: str,
    *,
    timeout: float,
) -> tuple[bool, str]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(f"{base_url}/api/tags")
        if resp.status_code >= 400:
            return False, f"HTTP {resp.status_code}"
        payload = resp.json()
        models = payload.get("models", []) if isinstance(payload, dict) else []
        names = [
            item.get("name") or item.get("model") or ""
            for item in models
            if isinstance(item, dict)
        ]
        if names and any(_model_matches(name, expected_model) for name in names):
            return True, "model-available"
        if names:
            return False, f"model-not-loaded:{expected_model}"
        return True, "reachable"


async def _probe_glm_cloud_candidate(model: Any) -> tuple[bool, str]:
    timeout = float(os.getenv("GLM_PROBE_TIMEOUT", "8"))
    base_url = _candidate_base_url(model.host, model.port)
    payload = {
        "model": model.name,
        "prompt": "ping",
        "stream": False,
        "options": {"num_predict": 1},
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{base_url}/api/generate", json=payload)
        if resp.status_code == 429:
            return False, "rate-limited"
        if resp.status_code >= 400:
            return False, f"HTTP {resp.status_code}"
        data = resp.json()
        if isinstance(data, dict) and data.get("error"):
            return False, str(data["error"])
        if isinstance(data, dict) and (data.get("response") is not None or data.get("done") is not None):
            return True, "glm-ready"
        return False, "empty-response"


async def _candidate_availability(model: Any) -> tuple[bool, str]:
    backend = getattr(model, "backend", "")
    name = getattr(model, "name", "")
    if backend not in _LOCAL_RUNTIME_BACKENDS:
        return True, "not-probed"

    try:
        base_url = _candidate_base_url(model.host, model.port)
        timeout = float(os.getenv("MODEL_PROBE_TIMEOUT", "3"))
        if name == _GLM_ORCHESTRATOR_MODEL:
            return await _probe_glm_cloud_candidate(model)
        if backend == "ollama":
            return await _probe_ollama_model(base_url, name, timeout=timeout)
        if backend in {"lm-studio", "mlx"}:
            return await _probe_openai_compatible(
                base_url,
                name,
                timeout=timeout,
                token=os.getenv("LM_STUDIO_API_TOKEN", ""),
            )
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    return True, "unhandled-backend"


async def _resolve_candidates(
    candidates: List[Any],
    task_type: str,
) -> tuple[list[Any], dict[str, dict[str, Any]]]:
    resolved: list[Any] = []
    availability: dict[str, dict[str, Any]] = {}

    for candidate in candidates:
        ready, detail = await _candidate_availability(candidate)
        key = f"{getattr(candidate, 'name', 'unknown')}@{getattr(candidate, 'device', 'unknown')}"
        availability[key] = {
            "ready": ready,
            "detail": detail,
            "backend": getattr(candidate, "backend", ""),
            "device": getattr(candidate, "device", ""),
        }
        if ready:
            resolved.append(candidate)

    if task_type in _AUTORESEARCH_TASK_TYPES:
        local_ready = [candidate for candidate in resolved if _is_local_candidate(candidate)]
        if not local_ready:
            return [], availability
        return local_ready, availability

    return resolved or candidates, availability


@app.get("/ecc/status", tags=["ecc"])
def ecc_status() -> Dict[str, Any]:
    return get_sync_status()


@app.post("/ecc/sync", tags=["ecc"])
def ecc_sync(force: bool = Query(False)) -> Dict[str, Any]:
    try:
        return sync_ecc_tools(force=force)
    except Exception as exc:  # noqa: BLE001
        _startup_log.exception("ECC sync endpoint error")
        return {"status": "error", "message": str(exc)}


class UserInputRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    source: str = "portal"  # "portal" | "cli"


@app.post("/user-input", tags=["user-input"])
def post_user_input(req: UserInputRequest) -> Dict[str, Any]:
    """Queue a task message from the portal or CLI for researchers to pick up."""
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="message is required")
    entry = {"message": message, "source": req.source, "ts": time.time()}
    _USER_INPUT_QUEUE.appendleft(entry)
    return {"status": "queued", "queue_depth": len(_USER_INPUT_QUEUE), "entry": entry}


@app.get("/user-input/next", tags=["user-input"])
def get_user_input_next() -> Dict[str, Any]:
    """Return and remove the next queued user message.

    Empty queue: ``{"message": null}`` only (no ``source`` / ``ts`` keys).
    When a message is available, returns the enqueued ``message`` and, when
    present on the queued entry, ``source`` and ``ts`` (via ``dict.get``).

    Implementation uses two complementary guards (additive, not either/or):
    - ``if not _USER_INPUT_QUEUE`` — fast path for idle queue; preserves the
      historical empty response shape used by portal researchers and CLI pollers.
    - ``try`` / ``except IndexError`` on ``pop()`` — covers concurrent
      ``GET /user-input/next`` callers that race between the emptiness check
      and the pop; treated as empty, not a server error.

    Returns:
        dict: ``{"message": None}`` if no entry is available (empty queue or
        concurrent race); otherwise
        ``{"message": str, "source": str | None, "ts": int | float | None}``.
    """
    if not _USER_INPUT_QUEUE:
        return {"message": None}
    try:
        entry = _USER_INPUT_QUEUE.pop()
    except IndexError:
        # Another poller drained the queue after our check — same contract as empty.
        return {"message": None}
    return {
        "message": entry["message"],
        "source": entry.get("source"),
        "ts": entry.get("ts"),
    }


@app.get("/user-input/status", tags=["user-input"])
def get_user_input_status() -> Dict[str, Any]:
    """Return queue depth and all pending messages (without consuming them)."""
    return {
        "queue_depth": len(_USER_INPUT_QUEUE),
        "pending": list(_USER_INPUT_QUEUE),
    }


@app.get("/health", tags=["system"])
def health(
    ollama_host: str = os.getenv("OLLAMA_MAC_ENDPOINT", "http://localhost:11434"),
    lm_studio_host: str = os.getenv("LM_STUDIO_MAC_ENDPOINT", "http://localhost:1234"),
    mlx_host: str = "http://localhost:8081",
) -> Dict[str, Any]:
    def _validated(raw: str, default: str) -> str:
        candidate = (raw or default).strip()
        try:
            return validate_model_endpoint_url(candidate)
        except ModelEndpointPolicyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    safe_ollama = _validated(ollama_host, "http://localhost:11434")
    safe_lm = _validated(lm_studio_host, "http://localhost:1234")
    safe_mlx = _validated(mlx_host, "http://localhost:8081")
    return {
        "status": "ok",
        "version": _ORCHESTRATOR_VERSION,
        "runtime": _runtime_summary(),
        "backends": backend_health_map(
            ollama_host=safe_ollama,
            lm_studio_host=safe_lm,
            mlx_host=safe_mlx,
        ),
    }


class _GossipEmitRequest(BaseModel):
    event_type: str
    payload: Dict[str, Any]
    uuid: Optional[str] = None


@app.post("/gossip/emit", tags=["gossip"])
async def gossip_emit(req: _GossipEmitRequest, request: Request):
    """Accept a gossip event from a LAN peer and persist it locally."""
    _require_gossip_auth(request)
    bus = _gossip_bus if _gossip_bus is not None else GossipBus()
    event_uuid = await bus.emit(req.event_type, req.payload, event_uuid=req.uuid)
    return {"ok": True, "uuid": event_uuid}


@app.get("/gossip/tail", tags=["gossip"])
async def gossip_tail(
    request: Request,
    limit: int = Query(20, ge=1, le=1000),
    event_type: Optional[str] = Query(None),
):
    """Return newest local gossip events for LAN peer replication."""
    _require_gossip_auth(request)
    bus = _gossip_bus if _gossip_bus is not None else GossipBus()
    events = await bus.tail(limit=limit, event_type=event_type)
    return {"events": events, "peers": _load_gossip_peers()}


@app.get("/budget", tags=["cost"])
def budget() -> Dict[str, Any]:
    return cost_guard.snapshot()


@app.get("/runtime", tags=["runtime"])
def runtime_state() -> Dict[str, Any]:
    payload = load_runtime_payload()
    if payload is None:
        return {"available": False, "runtime": None}
    return {"available": True, "runtime": redact_runtime_payload(payload)}


@app.post("/runtime/bootstrap", tags=["runtime"])
async def runtime_bootstrap(
    force_gateway: bool = Query(False),
    autoresearch: bool = Query(True),
    run_tag: Optional[str] = Query(None),
) -> Dict[str, Any]:
    payload = await bootstrap_runtime(
        interactive=False,
        force_gateway=force_gateway,
        run_autoresearch_preflight=autoresearch,
        run_tag=run_tag,
        print_progress=False,
    )
    return {
        "schema_version": payload.get("schema_version"),
        "generated_at": payload.get("generated_at"),
        "stages": payload.get("stages"),
        "autoresearch": payload.get("autoresearch"),
        "runtime": redact_runtime_payload(payload),
    }


@app.get("/agents", tags=["agents"])
def list_agents(status: Optional[str] = None) -> Dict[str, Any]:
    agents = tracker.list_agents(status=status)
    return {"agents": [asdict(a) for a in agents]}


@app.get("/agents/conflicts", tags=["agents"])
def detect_conflicts() -> ConflictResponse:
    conflicts = tracker.detect_conflicts()
    if conflicts:
        return ConflictResponse(
            conflict=True,
            message=(
                f"{len(conflicts)} duplicate-role agent(s) detected. "
                "Resolve or pass force=true on /orchestrate to override."
            ),
            existing_agents=[asdict(a) for a in conflicts],
        )
    return ConflictResponse(conflict=False, message="No conflicts", existing_agents=[])


@app.delete("/agents/{agent_id}", tags=["agents"])
def destroy_agent(agent_id: str) -> Dict[str, Any]:
    ok = tracker.destroy(agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"destroyed": agent_id}


@app.delete("/agents/gc/stopped", tags=["agents"])
def gc_stopped() -> Dict[str, Any]:
    removed = tracker.destroy_stopped()
    return {"removed": removed}


@app.get("/activity", tags=["agents"])
def get_activity(limit: int = Query(50, ge=1, le=200)) -> Dict[str, Any]:
    from json import JSONDecodeError

    path = Path(".state/researcher_activity.jsonl")
    if not path.exists():
        return {"events": [], "count": 0}

    raw_lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    events: List[Dict[str, Any]] = []
    for line in raw_lines[-limit:]:
        try:
            events.append(json.loads(line))
        except JSONDecodeError:
            pass
    events.sort(key=lambda event: event.get("ts", 0), reverse=True)
    return {"events": events, "count": len(events)}


@app.get("/models", tags=["models"])
def list_models() -> Dict[str, Any]:
    return {"models": [model.__dict__ for model in registry.list_models()]}


@app.get("/models/route", tags=["models"])
def route(
    task_type: str = Query("default"),
    preferred_device: Optional[str] = Query(None),
) -> Dict[str, Any]:
    chain = registry.route_task(task_type, preferred_device=preferred_device)
    return {"fallback_chain": [model.__dict__ for model in chain]}


@app.post("/orchestrate", tags=["orchestrate"])
async def orchestrate(req: OrchestrateRequest) -> Dict[str, Any]:
    task_hash = sha256(f"{req.task_type}:{req.task}".encode()).hexdigest()

    existing = tracker.find_existing(role=req.task_type, task_hash=task_hash)
    if existing and not req.force:
        return {
            "status": "conflict",
            "message": (
                "A running agent already exists for this role and task. "
                "Pass force=true to override, or use the existing agent below."
            ),
            "existing_agent": asdict(existing),
        }

    snapshot = cost_guard.snapshot()
    if not cost_guard.can_spend(req.estimated_cost):
        raise HTTPException(
            status_code=402,
            detail=f"Daily budget exceeded. Remaining: ${snapshot.get('remaining', 0):.4f}",
        )

    budget_warning = None
    if cost_guard.alert_approaching():
        budget_state = cost_guard.snapshot()
        budget_warning = (
            f"Budget at {budget_state['daily_spend']:.2f} / "
            f"{budget_state['daily_budget']:.2f} (>=80%)"
        )

    route_candidates = registry.route_task(req.task_type, preferred_device=req.preferred_device)
    if not route_candidates:
        raise HTTPException(
            status_code=404,
            detail=f"No model candidates found for task_type='{req.task_type}'",
        )

    candidates, availability = await _resolve_candidates(route_candidates, req.task_type)
    if req.task_type in _AUTORESEARCH_TASK_TYPES and not candidates:
        return {
            "status": "needs_user_action",
            "message": (
                "No viable local coder backend is reachable for autoresearch. "
                "Start Windows LM Studio (Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-v2) "
                "or a reachable local LM Studio fallback, then retry."
            ),
            "runtime": _runtime_summary(),
            "availability": availability,
        }

    selected = candidates[0]
    route_cfg = registry.routing_cfg.get("routes", {}).get(req.task_type, {})

    agent = tracker.register(
        role=req.task_type,
        model=selected.name,
        backend=selected.backend,
        host=selected.host,
        port=selected.port,
        task_hash=task_hash,
        parent_agent_id=req.parent_agent_id,
        metadata={
            "reasoning": selected.reasoning,
            "device": selected.device,
            "online": selected.online,
        },
        status="idle",
    )
    cost_guard.record_spend(req.estimated_cost)

    response: Dict[str, Any] = {
        "status": "created",
        "agent": asdict(agent),
        "selected_model": {
            "name": selected.name,
            "backend": selected.backend,
            "device": selected.device,
            "host": _candidate_base_url(selected.host, selected.port),
            "online": selected.online,
            "reasoning": selected.reasoning,
        },
        "fallback_chain": [
            {
                "priority": index + 2,
                "name": model.name,
                "backend": model.backend,
                "device": model.device,
                "online": model.online,
            }
            for index, model in enumerate(
                [model for model in route_candidates if model is not selected][:5]
            )
        ],
        "runtime": _runtime_summary(),
        "availability": availability,
    }
    if budget_warning:
        response["budget_warning"] = budget_warning

    if req.task_type in _ORAMASYS_TASK_TYPES and route_cfg.get("endpoint"):
        timeout = parse_oramasys_timeout(route_cfg.get("timeout"))
        try:
            bridge_result = {
                "enabled": True,
                **await call_oramasys_mcp_or_bridge(
                    endpoint=str(route_cfg["endpoint"]),
                    timeout=timeout,
                    task=req.task,
                    task_type=req.task_type,
                ),
            }
            response["oramasys_bridge"] = bridge_result
            response["ultrathink_bridge"] = bridge_result
        except Exception as exc:  # noqa: BLE001
            _startup_log.warning("oramasys bridge call failed: %s", exc)
            bridge_error = {
                "enabled": True,
                "error": str(exc),
                "endpoint": os.path.expandvars(str(route_cfg["endpoint"])),
            }
            response["oramasys_bridge"] = bridge_error
            response["ultrathink_bridge"] = bridge_error
    return response


@app.post("/pipelines/approvals", tags=["pipelines"])
async def register_tiered_pipeline_approval(
    request: PipelineApprovalRequest,
) -> Dict[str, Any]:
    """Register one Tier-5 approval artifact, distinct from execution.

    This endpoint is the ONLY code path that constructs a ``PipelineApproval``
    from inline fields. It never executes a pipeline; execution
    (``POST /pipelines/{recipe_name}/run``) can only reference the resulting
    artifact by ``trace_id``, keeping "who approved this" a separate action
    from "run it now" rather than a parameter of the same request.
    """
    try:
        expires_at = datetime.fromisoformat(request.expires_at)
        if expires_at.tzinfo is None:
            raise ValueError("expires_at must include a UTC offset")
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="expires_at must be a timezone-aware ISO-8601 timestamp"
        ) from exc

    approval = PipelineApproval(
        trace_id=request.trace_id,
        approved_by=request.approved_by,
        purpose=request.purpose,
        recipe=request.recipe,
        route_tier=request.route_tier,
        max_tokens=request.max_tokens,
        max_cost_usd=request.max_cost_usd,
        expires_at=expires_at,
        scope=tuple(request.scope),
    )
    try:
        register_pipeline_approval(approval)
    except PipelineApprovalError as exc:
        raise HTTPException(status_code=422, detail="Unable to register approval") from exc
    # Deliberately not returning the artifact's filesystem path -- an API
    # response is not the place to expose internal server directory layout.
    return {"status": "registered", "trace_id": approval.trace_id}


@app.post("/pipelines/{recipe_name}/run", tags=["pipelines"])
async def run_tiered_pipeline(
    recipe_name: str,
    request: TieredPipelineRequest,
    runner: TieredPipelineRunner = Depends(get_tiered_pipeline_runner),
    transport: ProviderTransportRegistry = Depends(get_provider_transport),
) -> Dict[str, Any]:
    """Run one configured Tier-5 recipe through guarded native transport.

    Authentication is applied by ``ControlPlaneAuthMiddleware`` before this
    handler.  The body never selects a provider, model, price, or endpoint;
    those are immutable configuration and the canonical frugality gate owns
    cloud eligibility.
    """
    try:
        recipe = runner.recipe(recipe_name)
    except PipelineConfigError as exc:
        raise HTTPException(status_code=404, detail="Unknown pipeline recipe") from exc

    if not tiered_pipeline_enabled():
        raise HTTPException(status_code=409, detail="Tier-5 pipelines are disabled")

    # KNOWN, DELIBERATELY DEFERRED GAP: can_spend() here and record_spend()
    # after the run (below) are not an atomic reservation -- concurrent
    # requests can each observe remaining budget, each pass this check, and
    # collectively overspend. A same-process asyncio.Lock or a two-method
    # CostGuard.reserve()/rollback() sketch was considered and explicitly
    # rejected as the fix: neither provides idempotency, crash recovery, or
    # conservative settlement after an uncertain provider response, and
    # would conflict with the durable SQLite ledger already planned to
    # replace this whole check/record pattern (see
    # docs/superpowers/plans/2026-08-14-tier5-durable-budget-ledger.md,
    # steelmanned separately from this diff). Not patched here to avoid
    # building throwaway code against a design that's already been
    # superseded by a more rigorous one.
    if not cost_guard.can_spend(recipe.cost_reservation_usd):
        raise HTTPException(status_code=402, detail="Daily budget cannot reserve this pipeline run")

    # A missing, unreadable, or malformed approval artifact and a genuinely
    # absent approval are intentionally indistinguishable here -- both
    # surface as the same PipelineApprovalError below.
    try:
        approval = load_pipeline_approval(request.trace_id)
    except PipelineApprovalError as exc:
        raise HTTPException(
            status_code=403, detail="Pipeline approval invalid, expired, or revoked"
        ) from exc

    try:
        result = await runner.run(
            recipe_name,
            request.prompt,
            approval=approval,
            dispatch=transport.dispatch,
            privacy_critical=request.privacy_critical,
            override_confirmed=request.override_confirmed,
            override_reason=request.override_reason,
        )
    except PipelineDisabledError as exc:
        raise HTTPException(status_code=409, detail="Tier-5 pipelines are disabled") from exc
    except PipelineApprovalError as exc:
        raise HTTPException(
            status_code=403, detail="Pipeline approval invalid, expired, or revoked"
        ) from exc
    except PipelinePolicyError as exc:
        raise HTTPException(status_code=403, detail="Pipeline execution denied by policy") from exc
    except ProviderTransportError as exc:
        status = 503 if exc.retryable else 502
        raise HTTPException(status_code=status, detail="Configured provider could not complete the pipeline") from exc
    except (ProviderConfigError, PipelineExecutionError, PipelineConfigError) as exc:
        raise HTTPException(status_code=503, detail="Pipeline transport is not ready") from exc

    cost_guard.record_spend(recipe.cost_reservation_usd)
    return {
        "status": "completed",
        "recipe": result.recipe,
        "output": result.output,
        "requested_tokens": result.requested_tokens,
        "cost_reservation_usd": recipe.cost_reservation_usd,
    }


@app.post("/autoresearch/sync", tags=["autoresearch"])
def autoresearch_sync(run_tag: Optional[str] = Query(None)) -> Dict[str, Any]:
    result = autoresearch_bridge.preflight(run_tag=run_tag)
    if not result["sync_ok"]:
        raise HTTPException(
            status_code=500,
            detail=f"Autoresearch sync failed: {result['error']}",
        )
    return result


@app.get("/autoresearch/gpu_status", tags=["autoresearch"])
def autoresearch_gpu_status() -> Dict[str, Any]:
    state = autoresearch_bridge.read_swarm_state()
    return {
        "gpu_idle": state.gpu_status.upper() == "IDLE",
        "swarm_state": {
            "gpu_status": state.gpu_status,
            "baseline_val_bpb": state.baseline_val_bpb,
            "baseline_sha": state.baseline_sha,
            "orchestrator_directive": state.orchestrator_directive,
            "evaluator_findings": state.evaluator_findings,
        },
    }


# ── V1 Supervisor endpoints ───────────────────────────────────────────────────
# Thin HTTP surface over OrchestrationSupervisor — handlers ≤ 10 lines each.
# Brainstorm ref: orama-system/docs/2026-05-08-v1-supervisor-brainstorm.md §5
# Legacy /orchestrate route (orchestrator.py) stays intact — backwards compatible.

from orchestrator.supervisor import JobSpec, JobStatus, OrchestrationSupervisor, _new_id  # noqa: E402

# Security: job_id flows into filesystem paths (.state/jobs/<id>/result.json)
# via OrchestrationSupervisor. Validate the format at the HTTP boundary so a
# path-traversal payload (e.g. ".." or absolute paths) never reaches disk I/O.
# _new_id() generates uuid.uuid4() — accept only that exact shape.
_UUID4_RE = _re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    _re.IGNORECASE,
)


def _validate_job_id(job_id: str) -> str:
    """
    Validate that job_id is a server-issued UUIDv4.
    
    Raises:
        HTTPException: 400 with a fixed detail message if `job_id` does not match the strict UUIDv4 pattern.
    
    Returns:
        str: The validated `job_id` unchanged.
    """
    if not _UUID4_RE.match(job_id):
        raise HTTPException(
            status_code=400,
            detail="job_id must be a uuid4-formatted server-issued identifier",
        )
    return job_id


_supervisor: OrchestrationSupervisor | None = None


def _get_supervisor() -> OrchestrationSupervisor:
    global _supervisor
    if _supervisor is None:
        _supervisor = OrchestrationSupervisor()
    return _supervisor


class _JobSubmitRequest(BaseModel):
    intent:       str = "freeform"
    prompt:       str
    backend_hint: Optional[str] = None
    constraints:  Dict[str, Any] = {}
    metadata:     Dict[str, Any] = {}
    # Skill routing: maps to openclaw-skills SKILL_MAP when non-empty.
    # Without this field the skill gate in _dispatch() is never triggered
    # for API-submitted jobs.
    task_type:    str = ""


@app.post("/v1/jobs", tags=["supervisor"])
async def supervisor_submit_job(req: _JobSubmitRequest):
    """Submit a job to the V1 OrchestrationSupervisor (file-based persistence)."""
    spec = JobSpec(
        job_id=_new_id(),
        intent=req.intent,
        prompt=req.prompt,
        backend_hint=req.backend_hint,
        constraints=req.constraints,
        metadata=req.metadata,
        task_type=req.task_type,
    )
    try:
        job_id = await _get_supervisor().submit_job(spec)
        return {"job_id": job_id, "state": JobStatus.QUEUED.value}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/v1/jobs", tags=["supervisor"])
async def supervisor_list_jobs(status: Optional[str] = None):
    """List all known jobs, optionally filtered by status string."""
    try:
        filter_status = JobStatus(status) if status else None
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown status: {status}") from None
    return {"jobs": _get_supervisor().list_jobs(status=filter_status)}


@app.get("/v1/jobs/{job_id}", tags=["supervisor"])
async def supervisor_get_job(job_id: str):
    """
    Retrieve the last-known state for the specified supervisor job.
    
    Parameters:
        job_id (str): Job identifier (must be a UUIDv4).
    
    Returns:
        dict: The job's last-known status as returned by the supervisor.
    
    Raises:
        HTTPException: 400 if `job_id` fails UUIDv4 validation.
        HTTPException: 404 if no job with `job_id` exists.
    """
    _validate_job_id(job_id)
    result = await _get_supervisor().get_status(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return result


@app.post("/v1/jobs/{job_id}/cancel", tags=["supervisor"])
async def supervisor_cancel_job(job_id: str):
    """
    Request cancellation of a running job identified by its job ID.
    
    Parameters:
        job_id (str): UUIDv4 job identifier. Must match the server's UUIDv4 format; otherwise an HTTPException(400) is raised.
    
    Returns:
        dict: {
            "job_id": job_id,
            "cancel_requested": bool
        } where `cancel_requested` is `True` if a cancellation was requested, `False` otherwise.
    """
    _validate_job_id(job_id)
    cancelled = await _get_supervisor().cancel(job_id)
    return {"job_id": job_id, "cancel_requested": cancelled}


@app.post("/v1/jobs/{job_id}/replay", tags=["supervisor"])
async def supervisor_replay_job(job_id: str):
    """
    Replay a completed, failed, or cancelled job by creating a new job with a fresh job_id.
    
    Validates that `job_id` is a UUIDv4; on success requests the supervisor to replay the job and returns the new job's id and queued state.
    
    Parameters:
        job_id (str): The UUIDv4 identifier of the existing job to replay.
    
    Returns:
        dict: {
            "original_job_id": <original id>,
            "new_job_id": <newly issued job id>,
            "state": JobStatus.QUEUED.value
        }
    
    Raises:
        HTTPException: 400 if `job_id` is not a valid UUIDv4.
        HTTPException: 404 if the original job cannot be found or replay is not possible.
    """
    _validate_job_id(job_id)
    try:
        new_id = await _get_supervisor().replay(job_id)
        return {"original_job_id": job_id, "new_job_id": new_id, "state": JobStatus.QUEUED.value}
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found") from None


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("orchestrator.fastapi_app:app", host="localhost", port=8000, reload=True)
