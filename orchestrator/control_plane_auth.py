"""Control-plane authentication for Perpetua-Tools operator APIs."""
from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any, Literal, Mapping

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

ENV_TOKEN = "ORAMA_CONTROL_PLANE_TOKEN"
ENV_TOKEN_LOCAL = "ORAMA_CONTROL_PLANE_TOKEN_LOCAL"
ENV_TOKEN_PEER = "ORAMA_CONTROL_PLANE_TOKEN_PEER"
ENV_PT_TOKEN = "PT_CONTROL_PLANE_TOKEN"
ENV_INSECURE = "ORAMA_INSECURE_DEV"
_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TOKEN_PATH = _REPO_ROOT / ".state" / "control_plane_token"

_SAFE_ROUTING_KEYS = (
    "distributed",
    "manager_endpoint",
    "manager_model",
    "manager_backend",
    "coder_endpoint",
    "coder_model",
    "coder_backend",
    "mac_reachable",
    "lmstudio_detected",
    "synced_at",
    "manager_affinity_alert",
)

_PUBLIC_PATHS = frozenset({"/health", "/docs", "/openapi.json", "/redoc"})

_PROTECTED_GET_PREFIXES = (
    "/runtime",
    "/agents",
    "/activity",
    "/models",
    "/v1/jobs",
    "/user-input/status",
    "/user-input/next",
    "/budget",
    "/ecc/status",
    "/autoresearch/",
)

_PROTECTED_POST_PREFIXES = (
    "/user-input",
    "/runtime/bootstrap",
    "/orchestrate",
    "/v1/jobs",
    "/ecc/sync",
    "/autoresearch/",
)


def control_plane_token() -> str:
    return os.getenv(ENV_TOKEN, "").strip()


def _strip_env(name: str) -> str:
    return os.getenv(name, "").strip()


def _read_persisted_token(path: Path | None = None) -> str:
    token_path = path or DEFAULT_TOKEN_PATH
    if token_path.is_file():
        return token_path.read_text(encoding="utf-8").strip()
    return ""


def pt_lane_token_candidates() -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw in (_strip_env(ENV_PT_TOKEN), _read_persisted_token()):
        if raw and raw not in seen:
            seen.add(raw)
            ordered.append(raw)
    return ordered


def orama_lane_token_candidates() -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw in (_strip_env(ENV_TOKEN), _strip_env(ENV_TOKEN_LOCAL)):
        if raw and raw not in seen:
            seen.add(raw)
            ordered.append(raw)
    return ordered


def control_plane_auth_mode() -> Literal["unset", "pt_only", "orama_only", "joint"]:
    pt = pt_lane_token_candidates()
    orama = orama_lane_token_candidates()
    if pt and orama:
        return "joint"
    if pt:
        return "pt_only"
    if orama:
        return "orama_only"
    return "unset"


def _merge_unique(*groups: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for raw in group:
            if raw and raw not in seen:
                seen.add(raw)
                ordered.append(raw)
    return ordered


def collect_control_plane_token_candidates() -> list[str]:
    peer = _strip_env(ENV_TOKEN_PEER)
    extra = [peer] if peer else []
    mode = control_plane_auth_mode()
    if mode == "joint":
        return _merge_unique(pt_lane_token_candidates(), orama_lane_token_candidates(), extra)
    if mode == "pt_only":
        return _merge_unique(pt_lane_token_candidates(), extra)
    if mode == "orama_only":
        return _merge_unique(orama_lane_token_candidates(), extra)
    return _merge_unique(extra)


def accepted_control_plane_tokens(
    scope: Literal["pt", "orama"] = "pt",
) -> frozenset[str]:
    mode = control_plane_auth_mode()
    pt = pt_lane_token_candidates()
    orama = orama_lane_token_candidates()
    if mode == "joint":
        return frozenset(_merge_unique(pt, orama))
    if mode == "pt_only":
        return frozenset(pt)
    if mode == "orama_only":
        return frozenset(orama)
    if scope == "pt":
        return frozenset(pt or orama)
    return frozenset(orama or pt)


def outbound_control_plane_tokens() -> list[str]:
    peer = _strip_env(ENV_TOKEN_PEER)
    ordered: list[str] = []
    seen: set[str] = set()
    if peer:
        ordered.append(peer)
        seen.add(peer)
    for raw in _merge_unique(orama_lane_token_candidates(), pt_lane_token_candidates()):
        if raw not in seen:
            seen.add(raw)
            ordered.append(raw)
    return ordered


def token_matches_control_plane(
    provided: str,
    scope: Literal["pt", "orama"] = "pt",
) -> bool:
    if not provided:
        return False
    for expected in accepted_control_plane_tokens(scope):
        if secrets.compare_digest(provided, expected):
            return True
    return False


def _env_control_plane_token_candidates() -> list[str]:
    return orama_lane_token_candidates()


def _resolved_control_plane_token() -> str:
    tokens = outbound_control_plane_tokens()
    return tokens[0] if tokens else ""


def auth_headers() -> dict[str, str]:
    """Bearer headers for outbound PT HTTP clients (researchers, scripts)."""
    tokens = outbound_control_plane_tokens()
    if tokens:
        return {"Authorization": f"Bearer {tokens[0]}"}
    return {}


def auth_enforced() -> bool:
    """Return True when control-plane bearer auth must be checked."""
    insecure = os.getenv(ENV_INSECURE, "").strip().lower()
    if insecure in ("1", "true", "yes"):
        return False
    if _env_control_plane_token_candidates() or pt_lane_token_candidates():
        return True
    if insecure in ("0", "false", "no"):
        return True
    return True


def verify_control_plane_auth(request: Request) -> None:
    if not auth_enforced():
        return
    if not accepted_control_plane_tokens("pt"):
        raise HTTPException(status_code=503, detail="Control plane token not configured")
    auth_header = request.headers.get("authorization", "")
    provided = auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""
    if not token_matches_control_plane(provided, scope="pt"):
        raise HTTPException(status_code=401, detail="Unauthorized")


def control_plane_auth_failure(request: Request) -> JSONResponse | None:
    if not auth_enforced():
        return None
    try:
        verify_control_plane_auth(request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return None


def pt_path_requires_auth(path: str, method: str) -> bool:
    if path in _PUBLIC_PATHS:
        return False
    if method.upper() == "OPTIONS":
        return False
    upper = method.upper()
    if upper in ("POST", "PUT", "PATCH", "DELETE"):
        return True
    if upper in ("GET", "HEAD"):
        return any(path.startswith(prefix) for prefix in _PROTECTED_GET_PREFIXES)
    return False


def persist_control_plane_token(token: str, path: Path | None = None) -> Path:
    token_path = path or DEFAULT_TOKEN_PATH
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(token, encoding="utf-8")
    token_path.chmod(0o600)
    return token_path


def ensure_control_plane_token() -> str:
    existing = control_plane_token()
    if existing:
        return existing
    persisted = _read_persisted_token()
    if persisted:
        os.environ[ENV_TOKEN] = persisted
        return persisted
    if not auth_enforced():
        return ""
    generated = secrets.token_urlsafe(32)
    os.environ[ENV_TOKEN] = generated
    persist_control_plane_token(generated)
    return generated


def redact_runtime_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {"available": False, "gateway_ready": False, "distributed": False}
    gateway = payload.get("gateway") if isinstance(payload.get("gateway"), dict) else {}
    routing = payload.get("routing") if isinstance(payload.get("routing"), dict) else {}
    redacted: dict[str, Any] = {
        "available": True,
        "gateway_ready": bool(gateway.get("gateway_ready") or gateway.get("ready")),
        "distributed": bool(routing.get("distributed")),
        "gateway": {
            "gateway_ready": bool(gateway.get("gateway_ready") or gateway.get("ready")),
            "running": bool(gateway.get("running")),
            "port": int(gateway.get("port") or 0),
        },
        "routing": {key: routing[key] for key in _SAFE_ROUTING_KEYS if key in routing},
    }
    for key in _SAFE_ROUTING_KEYS:
        if key in routing:
            redacted[key] = routing[key]
    return redacted
