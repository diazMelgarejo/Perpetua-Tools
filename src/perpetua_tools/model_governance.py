"""Harness-path model governance pins for Perpetua-Tools.

Canonical rules live in Alexandria. This module loads the local pin file and
refuses launches that violate it. It does not treat config flags, env vars,
agent-writable files, or cached approvals as an escalation token.

This is methodology-side policy, not a second runtime router. It does not
reorder the local-first frugality ladder. Cost-gate evaluation failures and
cloud escalation without a real token fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    """Pointer to a real HITL proof. Never constructed from env/config flags."""

    kind: str
    reference: str
    model_id: str
    expires_at: datetime
    effort: str | None = None
    fast: bool | None = None
    budget_cap: str | None = None


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
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
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
    if path == "anthropic":
        row = cfg["anthropic"]["default"]
        return LaunchSpec(
            path=path,
            launch_id=str(row["launch_id"]),
            effort=str(row["effort"]),
            fast=None,
        )
    if path == "direct_xai":
        row = cfg["direct_xai"]["default"]
        return LaunchSpec(
            path=path,
            launch_id=str(row["launch_id"]),
            reasoning_effort=str(row["reasoning_effort"]),
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
    """Return True only for a fresh allowed-kind proof with a non-blank reference."""
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
) -> None:
    """Refuse banned, auto-for-agent, ungated-mismatch, and unproven gated launches."""
    cfg = dict(config) if config is not None else load_model_governance()
    banned = {str(x) for x in cfg.get("banned_launch_ids") or []}
    if spec.launch_id in banned:
        raise ModelGovernanceError(f"banned launch id: {spec.launch_id}")

    if spec.launch_id in {"auto", "default"} and spec.agent:
        raise ModelGovernanceError("auto is editor-only; never for agents")

    if spec.path == "cursor_grok_bot":
        _assert_cursor_launch(spec, proof=proof, cfg=cfg, now=now)
        return
    if spec.path == "anthropic":
        _assert_anthropic_launch(spec, proof=proof, cfg=cfg, now=now)
        return
    if spec.path == "direct_xai":
        _assert_direct_xai_launch(spec, cfg=cfg)
        return
    raise ModelGovernanceError("unknown harness path")


def _token_covers(
    spec: LaunchSpec, proof: EscalationProof | None, *, now: datetime | None
) -> bool:
    if not proof_is_token(proof, now=now):
        return False
    assert proof is not None
    return proof.model_id == spec.launch_id


def _assert_gated_params(spec: LaunchSpec, row: Mapping[str, Any]) -> None:
    wanted_effort = row.get("effort")
    if wanted_effort is not None and _named_effort(spec) != str(wanted_effort):
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
) -> None:
    if spec.launch_id.startswith("claude-"):
        _assert_anthropic_launch(spec, proof=proof, cfg=cfg, now=now)
        return
    if spec.fast is True:
        if spec.launch_id == "composer-2.5" and _token_covers(spec, proof, now=now):
            return
        raise ModelGovernanceError(
            "fast mode requires an operator request plus a real escalation token"
        )
    if spec.effort not in (None, "medium") and not _token_covers(spec, proof, now=now):
        raise ModelGovernanceError("non-medium effort requires an escalation token")
    if spec.launch_id in _ungated_cursor_ids(cfg):
        if spec.launch_id == "composer-2.5" and spec.fast is not False:
            raise ModelGovernanceError("composer-2.5 must launch with fast off")
        if spec.launch_id == "grok-4.6" and (
            spec.effort != "medium" or spec.fast is not False
        ):
            raise ModelGovernanceError("grok-4.6 default is medium effort with fast off")
        return
    gated = cfg["cursor_grok_bot"].get("gated") or {}
    if spec.launch_id in gated:
        if not _token_covers(spec, proof, now=now):
            raise ModelGovernanceError(
                "cloud escalation default-deny: escalation token required"
            )
        _assert_gated_params(spec, gated[spec.launch_id])
        return
    if _token_covers(spec, proof, now=now):
        return
    raise ModelGovernanceError("cloud escalation default-deny: unlisted Cursor model")


def _assert_anthropic_launch(
    spec: LaunchSpec,
    *,
    proof: EscalationProof | None,
    cfg: Mapping[str, Any],
    now: datetime | None,
) -> None:
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
    if not _token_covers(spec, proof, now=now):
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
            "direct-xAI default is grok-4.6 with reasoning_effort medium"
        )


def evaluate_cost_gate(*, cap_evaluable: bool, remaining: int | None) -> None:
    """Fail closed when the cap cannot be evaluated or is exhausted. No silent reroute."""
    if not cap_evaluable or remaining is None:
        raise ModelGovernanceError("cost gate fail-closed: cap cannot be evaluated")
    if remaining <= 0:
        raise ModelGovernanceError("cost gate fail-closed: cap hit")
