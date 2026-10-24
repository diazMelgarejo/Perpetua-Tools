"""Harness-path model governance pins for Perpetua-Tools.

The proposed Alexandria rules inform the local pin file; adopting that source
as authoritative requires a separate decision. This helper evaluates metadata
against those pins, not signatures, bearer credentials, or task ownership.
Config flags, env vars, agent-writable files and cached approvals are refused.

This is methodology-side policy, not a second runtime router. It does not
reorder the local-first frugality ladder. Cost-gate evaluation failures and
cloud escalation without a real token fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml

ALLOWED_PROOF_KINDS = frozenset(
    {"github_verified_signoff", "offline_gpg", "control_plane_online_signer"}
)
FORBIDDEN_PROOF_KINDS = frozenset(
    {"config_flag", "env_var", "agent_writable_file", "cached_approval"}
)
MAX_TOKEN_TTL = timedelta(hours=24)
_CONFIG_REL = Path("config") / "model-governance.yml"


class ModelGovernanceError(RuntimeError):
    """Raised when a launch violates model governance or config cannot be evaluated."""


class _StrictSafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate keys instead of overwriting them."""

    def construct_mapping(
        self, node: yaml.MappingNode, deep: bool = False
    ) -> dict[Any, Any]:
        self.flatten_mapping(node)
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in mapping
            except TypeError as exc:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found an unhashable key",
                    key_node.start_mark,
                ) from exc
            if duplicate:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"found duplicate key {key!r}",
                    key_node.start_mark,
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


@dataclass(frozen=True)
class LaunchSpec:
    path: str
    launch_id: str
    effort: str | None = None
    fast: bool | None = None
    reasoning_effort: str | None = None
    agent: bool = True


@dataclass(frozen=True)
class EscalationProof:
    """Approval metadata; authenticity and task scope require external verification."""

    kind: str
    reference: str
    model_id: str
    expires_at: datetime
    effort: str | None = None
    fast: bool | None = None
    budget_cap: str | None = None
    # Optional claims emitted by the trusted verifier.  This policy compares
    # them when present; it does not establish their authenticity.
    path: str | None = None
    scope: str | None = None


@dataclass(frozen=True)
class LaunchPlan:
    """Pure selection facts; neither this value nor its approval flag authorizes dispatch."""

    requested: LaunchSpec
    effective: LaunchSpec
    requires_human_approval: bool
    reason: str
    requested_mode: str = "standard"
    effective_mode: str = "standard"
    approval_candidate: LaunchSpec | None = None


def _assert_effort_aliases_consistent(spec: LaunchSpec) -> None:
    """Refuse different values supplied through the equivalent effort aliases."""
    if (
        spec.effort is not None
        and spec.reasoning_effort is not None
        and spec.effort != spec.reasoning_effort
    ):
        raise ModelGovernanceError("conflicting effort fields")


def plan_launch(
    spec: LaunchSpec,
    *,
    task_kind: str | None = None,
    mode: str = "standard",
    config: Mapping[str, Any] | None = None,
) -> LaunchPlan:
    """Select immediate policy fallback; task_kind must come from the trusted harness.

    Human authorization, budgets and execution leases belong to the dispatch
    boundary. This function accepts no agent-supplied approval boolean or proof.
    """
    if task_kind not in (None, "planning", "execution"):
        raise ModelGovernanceError("unsupported harness task kind")
    if mode not in ("standard", "ultracode"):
        raise ModelGovernanceError("unsupported orchestration mode")
    if any(value in ("xhigh", "max") for value in (spec.effort, spec.reasoning_effort)):
        raise ModelGovernanceError("effort is forbidden")
    _assert_effort_aliases_consistent(spec)
    cfg = dict(config) if config is not None else load_model_governance()
    if spec.launch_id in cfg.get("banned_launch_ids", ()):
        raise ModelGovernanceError(f"banned launch id: {spec.launch_id}")
    provider = "anthropic" if spec.path == "cursor_grok_bot" and spec.launch_id.startswith("claude-") else spec.path
    if provider not in ("anthropic", "openai", "google", "cursor_grok_bot", "direct_xai"):
        raise ModelGovernanceError("unknown harness path")
    policy = cfg[provider]
    planning = policy.get("planning") or {}
    controller = policy.get("controller") or {}
    is_planning_model = spec.launch_id == planning.get("launch_id")
    gated = (policy.get("gated") or {}).get(spec.launch_id)
    if is_planning_model or spec.launch_id == controller.get("launch_id"):
        row = planning if is_planning_model else controller
        allowed_efforts = row.get("allowed_efforts", [row.get("effort")])
        if _named_effort(spec) not in allowed_efforts:
            raise ModelGovernanceError("role requires an explicitly permitted effort")
        _assert_gated_params(spec, {**row, "effort": _named_effort(spec)})
    elif gated is not None:
        _assert_gated_params(spec, gated)
    elif provider in ("openai", "google"):
        if spec.launch_id != policy["default"]["launch_id"]:
            raise ModelGovernanceError("unlisted role model")
        _assert_gated_params(spec, policy["default"])
    else:
        assert_launch_allowed(spec, config=cfg)
    needs_approval = mode == "ultracode" or (
        is_planning_model and task_kind != "planning"
    ) or (gated is not None and not is_planning_model)
    if not needs_approval:
        return LaunchPlan(spec, spec, False, "planning" if is_planning_model else "allowed")
    fallback = replace(default_launch(provider, config=cfg), path=spec.path)
    candidate = spec
    if is_planning_model and task_kind != "planning":
        candidate = replace(spec, effort="medium", reasoning_effort=None)
    return LaunchPlan(
        spec, fallback, True, "human_approval_required", mode, "standard", candidate
    )


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / _CONFIG_REL
        if candidate.is_file():
            return parent
    raise ModelGovernanceError("config unavailable")


@lru_cache(maxsize=8)
def load_model_governance(config_path: str | None = None) -> dict[str, Any]:
    """Load the pin YAML. Refuse a pin that drops fail-closed / default-deny."""
    path = Path(config_path) if config_path else _repo_root() / _CONFIG_REL
    try:
        raw = yaml.load(
            path.read_text(encoding="utf-8"), Loader=_StrictSafeLoader
        ) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ModelGovernanceError("config unavailable") from exc
    if not isinstance(raw, dict):
        raise ModelGovernanceError("config unavailable")
    if raw.get("invariants", {}).get("cost_gate") != "fail_closed":
        raise ModelGovernanceError("cost gate must stay fail-closed")
    if raw.get("invariants", {}).get("cloud_escalation") != "default_deny":
        raise ModelGovernanceError("cloud escalation must stay default-deny")
    return raw


def default_launch(path: str, *, config: Mapping[str, Any] | None = None) -> LaunchSpec:
    """Return the ungated default LaunchSpec for a harness path."""
    cfg = dict(config) if config is not None else load_model_governance()
    if path == "cursor_grok_bot":
        row = cfg["cursor_grok_bot"]["default"]
        return LaunchSpec(
            path=path,
            launch_id=str(row["launch_id"]),
            effort=str(row["effort"]),
            fast=bool(row["fast"]),
        )
    if path in ("anthropic", "openai", "google"):
        row = cfg[path]["default"]
        return LaunchSpec(
            path=path,
            launch_id=str(row["launch_id"]),
            effort=str(row["effort"]),
            fast=bool(row["fast"]) if "fast" in row else None,
        )
    if path == "direct_xai":
        row = cfg["direct_xai"]["default"]
        return LaunchSpec(
            path=path,
            launch_id=str(row["launch_id"]),
            reasoning_effort=str(row["reasoning_effort"]),
            fast=bool(row.get("fast", False)),
        )
    raise ModelGovernanceError("unknown harness path")


def _ungated_cursor_ids(cfg: Mapping[str, Any]) -> set[str]:
    ids = {str(cfg["cursor_grok_bot"]["default"]["launch_id"])}
    for row in cfg["cursor_grok_bot"].get("allowed_ungated") or []:
        ids.add(str(row["launch_id"]))
    return ids


def _anthropic_ungated_ids(cfg: Mapping[str, Any]) -> set[str]:
    row = cfg["anthropic"]["default"]
    ids = {str(row["launch_id"])}
    legacy = row.get("legacy_pin")
    if legacy:
        ids.add(str(legacy))
    return ids


def _named_effort(spec: LaunchSpec) -> str | None:
    return spec.effort or spec.reasoning_effort


def proof_is_token(proof: EscalationProof | None, *, now: datetime | None = None) -> bool:
    """Check metadata freshness and shape only, not signatures or authorization."""
    if proof is None:
        return False
    if proof.kind in FORBIDDEN_PROOF_KINDS:
        return False
    if proof.kind not in ALLOWED_PROOF_KINDS:
        return False
    if not str(proof.reference).strip():
        return False
    clock = now or datetime.now(timezone.utc)
    expiry = proof.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry > clock + MAX_TOKEN_TTL:
        return False
    if expiry <= clock:
        return False
    return True


def assert_launch_allowed(
    spec: LaunchSpec,
    *,
    proof: EscalationProof | None = None,
    config: Mapping[str, Any] | None = None,
    now: datetime | None = None,
    approval_scope: str | None = None,
    task_kind: str | None = None,
) -> None:
    """Refuse banned, auto-for-agent, ungated-mismatch, and unproven gated launches."""
    if task_kind not in (None, "planning", "execution"):
        raise ModelGovernanceError("unsupported harness task kind")
    for effort in (spec.effort, spec.reasoning_effort):
        if effort in ("xhigh", "max"):
            raise ModelGovernanceError(f"effort is forbidden: {effort}")
    _assert_effort_aliases_consistent(spec)
    cfg = dict(config) if config is not None else load_model_governance()
    banned = {str(x) for x in cfg.get("banned_launch_ids") or []}
    if spec.launch_id in banned:
        raise ModelGovernanceError(f"banned launch id: {spec.launch_id}")

    if spec.launch_id in {"auto", "default"} and spec.agent:
        raise ModelGovernanceError("auto is editor-only; never for agents")

    # R1: a presented proof must cover the exact requested launch tuple before
    # any early return below; it is never silently ignored.
    if proof is not None and not _token_covers(
        spec, proof, now=now, approval_scope=approval_scope
    ):
        raise ModelGovernanceError(
            "cloud escalation default-deny: proof expired or "
            "model/effort/fast/path/scope mismatch"
        )

    if spec.path in ("openai", "google"):
        plan = plan_launch(spec, task_kind=task_kind, config=cfg)
        if plan.requires_human_approval and not _token_covers(
            spec, proof, now=now, approval_scope=approval_scope
        ):
            raise ModelGovernanceError("cloud escalation default-deny: escalation token required")
        return
    if spec.path in ("anthropic", "cursor_grok_bot"):
        policy = cfg["anthropic"]
        planning_id = (policy.get("planning") or {}).get("launch_id")
        controller_id = (policy.get("controller") or {}).get("launch_id")
        if spec.launch_id == controller_id or (
            spec.launch_id == planning_id and task_kind == "planning"
        ):
            plan_launch(spec, task_kind=task_kind, config=cfg)
            return
    if spec.path == "cursor_grok_bot":
        _assert_cursor_launch(
            spec, proof=proof, cfg=cfg, now=now, approval_scope=approval_scope
        )
        return
    if spec.path == "anthropic":
        _assert_anthropic_launch(
            spec, proof=proof, cfg=cfg, now=now, approval_scope=approval_scope
        )
        return
    if spec.path == "direct_xai":
        _assert_direct_xai_launch(spec, cfg=cfg)
        return
    raise ModelGovernanceError("unknown harness path")


def _token_covers(
    spec: LaunchSpec,
    proof: EscalationProof | None,
    *,
    now: datetime | None,
    approval_scope: str | None = None,
) -> bool:
    """True only if a fresh proof covers the whole normalized launch tuple.

    Compared: model_id, normalized effort (effort or reasoning_effort), the
    fast flag (anything but True is non-fast), ``path`` when the proof sets it,
    and ``scope``. Scope is strict equality against ``approval_scope`` (None
    matches None): a proof without a scope is refused when the caller passes a
    scope, and a scoped proof is refused when the caller passes none.
    """
    if not proof_is_token(proof, now=now):
        return False
    assert proof is not None
    return (
        proof.model_id == spec.launch_id
        and proof.effort == _named_effort(spec)
        and (proof.fast is True) == (spec.fast is True)
        and (proof.path is None or proof.path == spec.path)
        and proof.scope == approval_scope
    )


def _assert_gated_params(spec: LaunchSpec, row: Mapping[str, Any]) -> None:
    wanted_effort = row.get("effort")
    if wanted_effort is not None and _named_effort(spec) not in row.get(
        "allowed_efforts", [str(wanted_effort)]
    ):
        raise ModelGovernanceError(
            f"{spec.launch_id} requires effort {wanted_effort} (set explicitly)"
        )
    if "fast" in row and spec.fast is not bool(row["fast"]):
        raise ModelGovernanceError(
            f"{spec.launch_id} requires fast={row['fast']}"
        )


def _assert_cursor_launch(
    spec: LaunchSpec,
    *,
    proof: EscalationProof | None,
    cfg: Mapping[str, Any],
    now: datetime | None,
    approval_scope: str | None = None,
) -> None:
    def covers() -> bool:
        return _token_covers(spec, proof, now=now, approval_scope=approval_scope)

    if spec.launch_id.startswith("claude-"):
        _assert_anthropic_launch(
            spec, proof=proof, cfg=cfg, now=now, approval_scope=approval_scope
        )
        return
    default = cfg["cursor_grok_bot"]["default"]
    if spec.launch_id == str(default["launch_id"]):
        _assert_gated_params(spec, default)
        return
    if spec.fast is True:
        if spec.launch_id == "composer-2.5" and covers():
            return
        raise ModelGovernanceError(
            "fast mode requires an operator request plus a real escalation token"
        )
    if _named_effort(spec) not in (None, "medium") and not covers():
        raise ModelGovernanceError("non-medium effort requires an escalation token")
    if spec.launch_id in _ungated_cursor_ids(cfg):
        if spec.launch_id == "composer-2.5" and spec.fast is not False:
            raise ModelGovernanceError("composer-2.5 must launch with fast off")
        return
    gated = cfg["cursor_grok_bot"].get("gated") or {}
    if spec.launch_id in gated:
        if not covers():
            raise ModelGovernanceError(
                "cloud escalation default-deny: escalation token required"
            )
        _assert_gated_params(spec, gated[spec.launch_id])
        return
    if covers():
        return
    raise ModelGovernanceError("cloud escalation default-deny: unlisted Cursor model")


def _assert_anthropic_launch(
    spec: LaunchSpec,
    *,
    proof: EscalationProof | None,
    cfg: Mapping[str, Any],
    now: datetime | None,
    approval_scope: str | None = None,
) -> None:
    # R2: fast mode is not a supported escalation for this policy; refuse it
    # before any ungated-model early return.
    if spec.fast is True:
        raise ModelGovernanceError("fast mode is unsupported for this Anthropic policy")
    if spec.launch_id in _anthropic_ungated_ids(cfg):
        if _named_effort(spec) != "medium":
            raise ModelGovernanceError("Sonnet default is medium effort, set explicitly")
        return
    gated = cfg["anthropic"].get("gated") or {}
    row = gated.get(spec.launch_id)
    if row is None:
        raise ModelGovernanceError(
            "cloud escalation default-deny: unlisted Anthropic model"
        )
    if not _token_covers(spec, proof, now=now, approval_scope=approval_scope):
        raise ModelGovernanceError(
            "cloud escalation default-deny: escalation token required"
        )
    _assert_gated_params(spec, row)
    requires = row.get("requires") or []
    if isinstance(requires, str):
        requires = [requires]
    if "budget_cap" in requires and not (proof and proof.budget_cap):
        raise ModelGovernanceError(
            "Fable requires a hard budget cap on the escalation approval"
        )


def _assert_direct_xai_launch(spec: LaunchSpec, cfg: Mapping[str, Any]) -> None:
    row = cfg["direct_xai"]["default"]
    if spec.launch_id != str(row["launch_id"]):
        raise ModelGovernanceError(
            "direct-xAI launch is default-deny without a listed default"
        )
    if spec.reasoning_effort != str(row["reasoning_effort"]):
        raise ModelGovernanceError(
            "direct-xAI default is grok-4.7 with reasoning_effort medium"
        )
    # This metadata policy is not the trusted P5 composition boundary. A
    # generic EscalationProof cannot establish a verified P5 receipt, so this
    # helper always refuses. The operator exception is a one-use P5 approval
    # that the trusted dispatcher verifies and consumes before provider
    # invocation (Phylax ``authorize_direct_xai_fast``).
    if spec.fast is True:
        raise ModelGovernanceError(
            "direct-xAI fast mode is refused here; it requires a one-use P5 operator "
            "approval enforced at the trusted dispatch boundary"
        )


def evaluate_cost_gate(*, cap_evaluable: bool, remaining: int | None) -> None:
    """Fail closed when the cap cannot be evaluated or is exhausted. No silent reroute."""
    if not cap_evaluable or remaining is None:
        raise ModelGovernanceError("cost gate fail-closed: cap cannot be evaluated")
    if remaining <= 0:
        raise ModelGovernanceError("cost gate fail-closed: cap hit")
