"""orchestrator/gate.py — canonical pre-dispatch frugality policy gate.

Design decision (2026-07-22): `orchestrator/frugality_router.py`'s
`resolve_route()` becomes the single canonical policy gate for both
`ModelRegistry.route_task()` (orchestrator/model_registry.py) and
`src/perpetua_tools/orchestrator.py`'s `/orchestrate` `privacy_critical`
branch. Before this module those three paths were independent and unaware
of each other; this is the thin wrapper both callers consult BEFORE
dispatch so they converge on frugality_router's tier policy.

Two ways to consult the gate
-----------------------------
1. `frugality_tier` known up front (the common case here): both callers
   already have a candidate model and a `frugality_tier` value — either
   from a `ModelTarget.frugality_tier` (route_task's ModelRegistry) or a
   `config/models.yml` lookup by model name (`load_frugality_tier_by_name`,
   used by the standalone orchestrator, which dispatches by hardcoded model
   name and has no `ModelTarget`/`BackendRegistry` at all). In this mode
   the gate answers directly from `frugality_router.max_allowed_tier()` —
   `resolve_route()` itself has no notion of `frugality_tier` and cannot
   answer this question; see `_consult_by_known_tier()`.
2. `frugality_tier` unknown, `registry` (a
   `perpetua.discovery.registry.BackendRegistry`) supplied: falls through
   to `frugality_router.resolve_route()`'s own tier 0-2 probing plus
   tier>=3 escalation, exactly as frugality_router already does for its
   existing callers. See `_consult_by_resolve_route()`.

Fall-through ("no opinion") contract — READ BEFORE CHANGING
-------------------------------------------------------------
`consult_gate()` / `gate_permits()` never invent a policy where none
exists. When `frugality_tier` is `None` (not yet classified in
`config/models.yml`) AND no `registry` was supplied, the gate returns
`has_route=False, denied_reason=None` — "no opinion". Callers MUST treat
that specific combination (no route, no denial) as "fall through to your
pre-existing, pre-gate dispatch logic unchanged" — this is what makes the
wiring in `route_task()` and the `/orchestrate` `privacy_critical` branch a
pure superset of prior behavior for every model that has no
`frugality_tier` set. A non-`None` `denied_reason` is a REAL policy
decision (offline egress refused, privacy_critical ceiling hit) and must
never be treated as "no opinion" / silently ignored.

Override contract — CRITICAL, read before touching override_confirmed
------------------------------------------------------------------------
The gate must never silently escalate a `privacy_critical` dispatch past
its default tier ceiling (tier 3, see `frugality_router.max_allowed_tier`).
`override_confirmed=True` is accepted ONLY together with a non-empty,
non-whitespace `override_reason` string; either one alone is refused.
Setting `override_confirmed=True` is the CALLER'S responsibility, and only
after a human has explicitly confirmed the escalation — an
`AskUserQuestion` round-trip in an interactive agent context, or a
CLI/dashboard confirmation modal in an operator context. Building that
confirmation UI is explicitly OUT OF SCOPE for this module; this module
only guarantees the backend contract that makes a *silent* bypass
impossible. `ORAMASYS_OFFLINE=1` is a hard local-only airgap, not a
privacy nicety, and is NEVER relaxed by `override_confirmed` — see
`_ceiling_for()`.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import yaml

from orchestrator.frugality_router import (
    FrugalityPolicyError,
    ResolvedRoute,
    ToolCallSpec,
    is_offline_mode,
    max_allowed_tier,
    resolve_route,
)

__all__ = [
    "GateDecision",
    "consult_gate",
    "gate_permits",
    "filter_chain_by_gate",
    "load_frugality_tier_by_name",
]


@dataclass(frozen=True)
class GateDecision:
    """Outcome of consulting the canonical frugality gate for one dispatch.

    has_route=True                          -> `.route` is concrete; dispatch it.
    has_route=False, denied_reason=None     -> gate has NO OPINION; caller
                                                falls through to its
                                                pre-existing dispatch logic
                                                unchanged.
    has_route=False, denied_reason=<str>    -> gate actively refused the
                                                request; caller MUST NOT
                                                dispatch and should surface
                                                `denied_reason` rather than
                                                silently falling through to
                                                a chain that violates the
                                                same policy.
    """

    has_route: bool
    route: Optional[ResolvedRoute] = None
    denied_reason: Optional[str] = None


def _ceiling_for(
    spec: ToolCallSpec, *, override_confirmed: bool, override_reason: Optional[str]
) -> int:
    """Effective tier ceiling for *spec*, honoring a confirmed+reasoned
    override of the privacy_critical cap. ORAMASYS_OFFLINE is never
    relaxed by override_confirmed — it is a hard local-only airgap.
    """
    ceiling = max_allowed_tier(spec)
    has_override = bool(override_confirmed and override_reason and override_reason.strip())
    if spec.privacy_critical and has_override and not is_offline_mode():
        return 6
    return ceiling


def _override_required_reason(tier: int, ceiling: int, *, offline: bool) -> str:
    if offline:
        return (
            f"tier {tier} exceeds the ORAMASYS_OFFLINE=1 ceiling (tier {ceiling}); "
            "ORAMASYS_OFFLINE is a hard local-only airgap and is never "
            "overridable by override_confirmed"
        )
    return (
        f"tier {tier} exceeds the default policy ceiling (tier {ceiling}); "
        "override_confirmed=True and a non-empty override_reason are "
        "required to escalate past it -- obtain human confirmation first "
        "(AskUserQuestion in an agent context, or a CLI/dashboard "
        "confirmation modal in an operator context) before setting them"
    )


def _consult_by_known_tier(
    frugality_tier: int,
    *,
    spec: ToolCallSpec,
    model_hint: Optional[str],
    override_confirmed: bool,
    override_reason: Optional[str],
) -> GateDecision:
    ceiling = _ceiling_for(
        spec, override_confirmed=override_confirmed, override_reason=override_reason
    )
    if frugality_tier > ceiling:
        return GateDecision(
            has_route=False,
            denied_reason=_override_required_reason(
                frugality_tier, ceiling, offline=is_offline_mode()
            ),
        )
    return GateDecision(
        has_route=True,
        route=ResolvedRoute(tier=frugality_tier, backend=None, model=model_hint),
    )


def _consult_by_resolve_route(
    spec: ToolCallSpec,
    *,
    registry: Any,
    escalation_tier: Optional[int],
    override_confirmed: bool,
    override_reason: Optional[str],
    trace_path: Optional[str],
) -> GateDecision:
    default_ceiling = max_allowed_tier(spec)
    wants_escalation_past_ceiling = (
        escalation_tier is not None and escalation_tier > default_ceiling
    )

    effective_spec = spec
    if wants_escalation_past_ceiling:
        has_reason = bool(override_reason and override_reason.strip())
        if not (override_confirmed and has_reason):
            return GateDecision(
                has_route=False,
                denied_reason=_override_required_reason(
                    escalation_tier, default_ceiling, offline=False
                ),
            )
        if is_offline_mode():
            return GateDecision(
                has_route=False,
                denied_reason=_override_required_reason(
                    escalation_tier, default_ceiling, offline=True
                ),
            )
        # Confirmed, reasoned override: relax only the privacy_critical tier
        # ceiling for this one resolution. Every other frugality_router
        # invariant (offline cap above, tier-1 local-backend validation,
        # escalation_reason requirement, trace emission) still applies.
        effective_spec = ToolCallSpec(
            task_type=spec.task_type,
            model_hint=spec.model_hint,
            est_tokens=spec.est_tokens,
            privacy_critical=False,
            parent_id=spec.parent_id,
            escalation_reason=spec.escalation_reason or override_reason,
            in_context=spec.in_context,
            base_url_override=spec.base_url_override,
            target_tier=spec.target_tier,
            windows_only=spec.windows_only,
        )

    try:
        route = resolve_route(
            effective_spec,
            registry=registry,
            trace_path=trace_path,
            escalation_tier=escalation_tier,
        )
    except FrugalityPolicyError as exc:
        return GateDecision(has_route=False, denied_reason=str(exc))

    return GateDecision(has_route=True, route=route)


def consult_gate(
    task_type: str,
    *,
    preferred_device: Optional[str] = None,
    privacy_critical: bool = False,
    model_hint: Optional[str] = None,
    frugality_tier: Optional[int] = None,
    est_tokens: int = 0,
    registry: Any = None,
    escalation_reason: Optional[str] = None,
    escalation_tier: Optional[int] = None,
    override_confirmed: bool = False,
    override_reason: Optional[str] = None,
    trace_path: Optional[str] = None,
) -> GateDecision:
    """Consult frugality_router as the single canonical pre-dispatch policy
    gate for *task_type*. See module docstring for the fall-through and
    override contracts.

    `preferred_device` is best-effort only: `ToolCallSpec` has no general
    device-affinity field, so this maps a Windows-named device to
    `windows_only=True` and otherwise ignores it. Callers that need real
    device affinity keep using their existing device-aware selection logic
    (e.g. `ModelRegistry.select_for_role`) — the gate only ever narrows or
    denies a dispatch, it never picks a device.
    """
    windows_only = bool(preferred_device) and "win" in preferred_device.lower()
    spec = ToolCallSpec(
        task_type=task_type,
        model_hint=model_hint,
        est_tokens=est_tokens,
        privacy_critical=privacy_critical,
        escalation_reason=escalation_reason,
        windows_only=windows_only,
    )

    if frugality_tier is not None:
        return _consult_by_known_tier(
            frugality_tier,
            spec=spec,
            model_hint=model_hint,
            override_confirmed=override_confirmed,
            override_reason=override_reason,
        )

    if registry is None:
        # No BackendRegistry to probe tier 1, and no pre-classified tier to
        # check directly -- the gate genuinely has no opinion. Callers MUST
        # fall through to their pre-existing (pre-gate) dispatch logic.
        return GateDecision(has_route=False, route=None, denied_reason=None)

    return _consult_by_resolve_route(
        spec,
        registry=registry,
        escalation_tier=escalation_tier,
        override_confirmed=override_confirmed,
        override_reason=override_reason,
        trace_path=trace_path,
    )


def gate_permits(
    frugality_tier: Optional[int],
    *,
    task_type: str = "reasoning",
    privacy_critical: bool = False,
    override_confirmed: bool = False,
    override_reason: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    """Convenience over `consult_gate()` for a single already-known
    `frugality_tier` value (e.g. a model name looked up in
    `config/models.yml`) rather than a full `resolve_route()` resolution.

    Returns `(True, None)` when the gate has no opinion (`frugality_tier`
    is `None`) or actively approves. Returns `(False, <reason>)` when the
    gate actively denies -- callers must not dispatch in that case.
    """
    if frugality_tier is None:
        return True, None
    decision = consult_gate(
        task_type,
        privacy_critical=privacy_critical,
        frugality_tier=frugality_tier,
        override_confirmed=override_confirmed,
        override_reason=override_reason,
    )
    return decision.has_route, decision.denied_reason


def filter_chain_by_gate(
    chain: Sequence[Any],
    *,
    task_type: str = "reasoning",
    privacy_critical: bool = False,
    override_confirmed: bool = False,
    override_reason: Optional[str] = None,
) -> list[Any]:
    """Filter an already-ordered fallback chain (e.g. `ModelRegistry.
    route_task()`'s `List[ModelTarget]`) through the canonical frugality
    gate, using each candidate's `frugality_tier` attribute.

    Pure superset contract: a candidate with `frugality_tier is None` (not
    yet classified in `config/models.yml`) is ALWAYS kept -- the gate has
    no opinion about it. A chain built entirely from unclassified
    candidates comes back byte-identical to the input. A classified
    candidate is dropped only when its tier exceeds the current ceiling
    (see `gate_permits()` / the override contract in the module
    docstring); this function only ever narrows a chain, never reorders or
    invents entries the caller didn't already have.
    """
    kept: list[Any] = []
    for candidate in chain:
        tier = getattr(candidate, "frugality_tier", None)
        allowed, _ = gate_permits(
            tier,
            task_type=task_type,
            privacy_critical=privacy_critical,
            override_confirmed=override_confirmed,
            override_reason=override_reason,
        )
        if allowed:
            kept.append(candidate)
    return kept


def load_frugality_tier_by_name(config_dir: Optional[str] = None) -> Dict[str, Optional[int]]:
    """Read `config/models.yml` directly and return `{model_name:
    frugality_tier}`.

    Deliberately does NOT go through `ModelRegistry.list_models()` (which
    performs live endpoint reachability probes) -- callers outside
    `ModelRegistry`, such as `src/perpetua_tools/orchestrator.py`'s
    `/orchestrate` handler (which dispatches by hardcoded model name, not
    `ModelTarget` objects), need the same `frugality_tier` classification
    without triggering network I/O or importing `ModelRegistry` at all.

    `config_dir` defaults to the `config/` directory next to this
    repository's `orchestrator/` package, resolved from this file's own
    path so the lookup is independent of the caller's working directory.
    """
    base = Path(config_dir) if config_dir else Path(__file__).resolve().parent.parent / "config"
    path = base / "models.yml"
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        item["name"]: item.get("frugality_tier")
        for item in raw.get("models", [])
        if "name" in item
    }
