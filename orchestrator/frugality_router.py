"""Orchestrator-side frugality router (v1.1 P1 spike).

Single chokepoint for tool/model tier selection. Probes tiers 0–2 local-first
before escalation. Enforces ORAMASYS_OFFLINE and privacy_critical policies.

See orama-system/docs/plans/2026-05-29-03-v1.1-definitive.md §4.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

TIERS: dict[int, str] = {
    0: "in_context",
    1: "local_oss",
    2: "local_index",
    3: "free_remote",
    4: "free_proprietary",
    5: "paid",
    6: "last_resort",
}

_LOCAL_INDEX_TASK_TYPES = frozenset(
    {"search", "index", "gbrain", "crg", "code_search", "semantic_search"}
)

__all__ = [
    "TIERS",
    "FrugalityPolicyError",
    "ResolvedRoute",
    "ToolCallSpec",
    "is_offline_mode",
    "max_allowed_tier",
    "resolve_route",
]

try:
    from orchestrator.backend_resolver import PolicyUnavailable, resolve_backend_for_spec
except ImportError:  # pragma: no cover - optional during partial installs
    PolicyUnavailable = RuntimeError  # type: ignore[misc, assignment]
    resolve_backend_for_spec = None  # type: ignore[assignment]


class FrugalityPolicyError(RuntimeError):
    """Raised when route selection violates frugality policy."""


@dataclass(frozen=True)
class ToolCallSpec:
    """Inputs for a single tool/model dispatch decision."""

    task_type: str = "reasoning"
    model_hint: str | None = None
    est_tokens: int = 0
    privacy_critical: bool = False
    parent_id: str | None = None
    escalation_reason: str | None = None
    in_context: bool = False
    base_url_override: str | None = None
    target_tier: str = "shared"
    windows_only: bool = False


@dataclass(frozen=True)
class ResolvedRoute:
    """Concrete tier selection for a tool/model call."""

    tier: int
    backend: str | None = None
    model: str | None = None
    est_cost_usd: float = 0.0
    fallback_chain: tuple[int, ...] = ()
    escalation_reason: str | None = None


def is_offline_mode() -> bool:
    """True when cloud egress is disabled (ORAMASYS_OFFLINE=1)."""
    return os.getenv("ORAMASYS_OFFLINE") == "1"


def max_allowed_tier(spec: ToolCallSpec) -> int:
    """Highest tier permitted for *spec* under current policy flags."""
    if is_offline_mode():
        return 2
    if spec.privacy_critical:
        return 3
    return 6


def _enforce_tier_policy(tier: int, spec: ToolCallSpec) -> None:
    if is_offline_mode() and tier >= 3:
        raise FrugalityPolicyError(
            f"ORAMASYS_OFFLINE=1 rejects tier >= 3 (requested tier {tier})"
        )
    if spec.privacy_critical and tier >= 4:
        raise FrugalityPolicyError(
            f"privacy_critical=True forbids tier >= 4 (requested tier {tier})"
        )


def _validate_tier1_local_backend(spec: ToolCallSpec, backend: Any) -> None:
    """Block tier-1 cloud endpoints when offline or privacy-critical."""
    if not (is_offline_mode() or spec.privacy_critical):
        return
    base_url = getattr(backend, "base_url", None)
    if not base_url:
        raise FrugalityPolicyError(
            "tier-1 backend missing base_url under restricted egress policy"
        )
    from utils.model_endpoint_url import ModelEndpointPolicyError, validate_model_endpoint_url

    try:
        validate_model_endpoint_url(str(base_url), allow_public=False)
    except ModelEndpointPolicyError as exc:
        mode = "ORAMASYS_OFFLINE=1" if is_offline_mode() else "privacy_critical=True"
        raise FrugalityPolicyError(f"{mode} rejects non-local tier-1 backend") from exc


def _probe_tier_0(spec: ToolCallSpec) -> Optional[ResolvedRoute]:
    if spec.in_context or spec.task_type == "in_context":
        return ResolvedRoute(tier=0, backend="in_context", model=None, est_cost_usd=0.0)
    return None


def _probe_tier_1(spec: ToolCallSpec, registry: Any) -> Optional[ResolvedRoute]:
    if registry is None or resolve_backend_for_spec is None:
        return None
    launch_spec = {
        "task_type": spec.task_type,
        "model_hint": spec.model_hint,
        "target_tier": spec.target_tier,
        "base_url_override": spec.base_url_override,
        "windows_only": spec.windows_only,
    }
    try:
        backend = resolve_backend_for_spec(registry, launch_spec)
    except PolicyUnavailable:
        return None
    _validate_tier1_local_backend(spec, backend)
    model = spec.model_hint
    if model is None and getattr(backend, "models", ()):
        model = backend.models[0]
    return ResolvedRoute(
        tier=1,
        backend=backend.name,
        model=model,
        est_cost_usd=0.0,
        fallback_chain=(0,),
    )


def _probe_tier_2(spec: ToolCallSpec) -> Optional[ResolvedRoute]:
    if spec.task_type not in _LOCAL_INDEX_TASK_TYPES:
        return None
    backend = "gbrain" if spec.task_type in {"gbrain", "semantic_search"} else "crg"
    return ResolvedRoute(
        tier=2,
        backend=backend,
        model=spec.model_hint,
        est_cost_usd=0.0,
        fallback_chain=(0, 1),
    )


def _escalation_route(spec: ToolCallSpec, tier: int) -> ResolvedRoute:
    if tier >= 3 and not spec.escalation_reason:
        raise FrugalityPolicyError(
            "escalation_reason is required when tier >= 3"
        )
    _enforce_tier_policy(tier, spec)
    est_cost = 0.0 if tier <= 2 else 0.001 * max(spec.est_tokens, 1)
    backend_by_tier = {
        3: "huggingface_free",
        4: "free_proprietary",
        5: "openrouter",
        6: "grok",
    }
    return ResolvedRoute(
        tier=tier,
        backend=backend_by_tier.get(tier),
        model=spec.model_hint,
        est_cost_usd=est_cost,
        fallback_chain=tuple(range(tier)),
        escalation_reason=spec.escalation_reason,
    )


def _emit_trace(route: ResolvedRoute, spec: ToolCallSpec, trace_path: Path | None) -> None:
    span: Dict[str, Any] = {
        "timestamp": time.time(),
        "name": "frugality_router.resolve_route",
        "attributes": {
            "ot.tool.tier": route.tier,
            "ot.tool.tier_name": TIERS.get(route.tier, "unknown"),
            "task_type": spec.task_type,
            "parent_id": spec.parent_id,
            "backend": route.backend,
            "model": route.model,
            "privacy_critical": spec.privacy_critical,
            "offline_mode": is_offline_mode(),
        },
    }
    if route.escalation_reason:
        span["attributes"]["escalation_reason"] = route.escalation_reason

    if trace_path is None:
        return

    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(span, separators=(",", ":")) + "\n")


def resolve_route(
    spec: ToolCallSpec,
    *,
    registry: Any = None,
    trace_path: str | Path | None = None,
    escalation_tier: int | None = None,
) -> ResolvedRoute:
    """Select the lowest eligible frugality tier for *spec*.

    Probes tiers 0–2 in order. When none match, escalates to *escalation_tier*
    (default 3) if policy permits and *spec.escalation_reason* is set.
    """
    path = Path(trace_path) if trace_path is not None else None
    allowed_max = max_allowed_tier(spec)

    for tier, probe in (
        (0, lambda: _probe_tier_0(spec)),
        (1, lambda: _probe_tier_1(spec, registry)),
        (2, lambda: _probe_tier_2(spec)),
    ):
        if tier > allowed_max:
            continue
        route = probe()
        if route is not None:
            _enforce_tier_policy(route.tier, spec)
            _emit_trace(route, spec, path)
            return route

    target = escalation_tier if escalation_tier is not None else 3
    if target <= 2:
        raise FrugalityPolicyError(
            f"cannot escalate to tier {target}; tiers 0-2 require probe match"
        )
    _enforce_tier_policy(target, spec)

    route = _escalation_route(spec, target)
    _emit_trace(route, spec, path)
    return route
