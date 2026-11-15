"""Two stacked dispatch policies: local runtime first, then free financial fallback.

Paid models are never selected automatically. A paid candidate requires an
explicit per-run human approval and a positive finite budget. This module does
not open a network connection and does not parse endpoint URLs.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

POLICY_FILENAME = "bigmodel-free-first-policy.json"
STACKS_FILENAME = "routing-policy-stacks.json"
PAID_TIER = 5
LOCAL_TIER_MAX = 2
FREE_TIER_MAX = 4
_CONTINUABLE_OUTCOMES = frozenset(
    {"model_unavailable", "capability_ineligible", "rejected"}
)


def _config_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "config"


def load_policy(path: Path | None = None) -> dict[str, Any]:
    """Return the canonical free-first policy document."""
    policy_path = path or (_config_dir() / POLICY_FILENAME)
    with policy_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("free-first policy must be a JSON object")
    return payload


def load_stacks(path: Path | None = None) -> dict[str, Any]:
    """Return the stack order. It does not repeat the candidate list."""
    stacks_path = path or (_config_dir() / STACKS_FILENAME)
    with stacks_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("routing policy stacks must be a JSON object")
    return payload


def automatic_free_candidates(policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Free candidates in policy order. Paid entries are not in this list."""
    rows = policy.get("ordered_candidates") or []
    free: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict) and row.get("pricing_status") == "free":
            free.append(dict(row))
    return free


def classify_provider_result(
    http_status: int | None,
    structured_code: Any = None,
    execution_state: str | None = None,
) -> str:
    """Map one provider result to a policy error class. No retry is implied."""
    state = (execution_state or "").lower()
    if state in {"recovery", "partial", "tool_effects", "cancelled"}:
        return "recovery_required"
    if state in {"safety", "policy_rejection"}:
        return "safety_blocked"
    if state in {"timeout", "network", "interrupted"}:
        return "outcome_unknown"
    code = str(structured_code) if structured_code is not None else ""
    if http_status == 429 and code == "1113":
        return "billing_or_entitlement_blocked"
    if http_status in {401, 403}:
        return "credentials_blocked"
    if http_status == 429:
        return "throttled"
    if http_status == 400:
        return "request_invalid_or_unknown"
    if http_status == 404:
        return "model_unavailable"
    if http_status == 422:
        return "rejected"
    if http_status is not None and http_status >= 500:
        return "outcome_unknown"
    if http_status == 200 and state in {"", "stop"}:
        return "success"
    return "outcome_unknown"


def authorize_paid_candidate(
    authorization: Mapping[str, Any] | None,
    budget_state: Mapping[str, Any] | None,
    candidate: Mapping[str, Any],
) -> bool:
    """True only for an explicit per-run human approval of this exact model.

    An environment variable is not an authorization. An absent or non-finite
    budget is not an authorization.
    """
    if not isinstance(authorization, Mapping):
        return False
    if authorization.get("human_approved") is not True:
        return False
    if authorization.get("per_run") is not True:
        return False
    model_id = candidate.get("model_id") or candidate.get("name")
    if not model_id or authorization.get("model_id") != model_id:
        return False
    if not isinstance(budget_state, Mapping):
        return False
    budget = budget_state.get("budget_cny")
    if isinstance(budget, bool) or not isinstance(budget, (int, float)):
        return False
    if not math.isfinite(budget) or budget <= 0:
        return False
    return True


def chain_stage(tier: Any) -> int | None:
    """Map a frugality tier onto local, free, or paid. None stays unclassified."""
    if isinstance(tier, bool) or not isinstance(tier, int):
        return None
    if tier <= LOCAL_TIER_MAX:
        return 0
    if tier <= FREE_TIER_MAX:
        return 1
    return 2


def requires_paid_gate(tier: Any) -> bool:
    """Paid and last-resort tiers need a human gate. Tier 4 stays free."""
    return isinstance(tier, int) and not isinstance(tier, bool) and tier >= PAID_TIER


def ledger_outcome(row: Mapping[str, Any]) -> str:
    """Read a ledger class. A terminal signal beats a continuable label.

    Partial execution, billing code 1113, credentials, and unknown execution
    stop even when the row also says ``rejected``. An explicit outcome is
    used only when no terminal signal is present. A bare model id, 404, or
    422 is not evidence the task may continue.
    """
    structural = ""
    if any(key in row for key in ("http_status", "code", "execution_state")):
        structural = classify_provider_result(
            row.get("http_status"),
            row.get("code"),
            row.get("execution_state"),
        )
    if structural and structural not in _CONTINUABLE_OUTCOMES:
        return structural
    named = row.get("outcome")
    if isinstance(named, str) and named:
        return named
    return structural


def candidate_dispatch_allowed(
    policy: Mapping[str, Any],
    candidate: Mapping[str, Any],
    task_requirements: Mapping[str, Any] | None,
) -> bool:
    """Catalog membership is not permission to call the model.

    Ordinary dispatch requires an open lane and a qualified free candidate.
    ``dispatch_mode=qualification_probe`` may walk unqualified free ids, and
    route assembly does not use that mode.
    """
    if candidate.get("pricing_status") != "free":
        return False
    requirements = task_requirements or {}
    if requirements.get("dispatch_mode") == "qualification_probe":
        return True
    lane = policy.get("lane_qualification") or {}
    if not isinstance(lane, Mapping) or lane.get("status") == "blocked":
        return False
    if candidate.get("qualification_status") != "qualified":
        return False
    needed = requirements.get("min_context_tokens")
    if needed is not None:
        window = candidate.get("context_window")
        if isinstance(window, bool) or not isinstance(window, int) or window < needed:
            return False
    return True


def select_next_candidate(
    policy: Mapping[str, Any],
    task_requirements: Mapping[str, Any] | None,
    evidence_ledger: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any] | None:
    """Return the next free candidate the task may call, or None to stop.

    Success, billing, credentials, safety, throttle, and unknown or partial
    execution stop the chain. Only a proven model-specific miss moves on.
    Vision tasks and retired ids are not members of this chain. Paid models
    are never returned. While the lane is blocked, only an explicit
    qualification probe may see an unqualified candidate.
    """
    requirements = task_requirements or {}
    if requirements.get("modality") == "vision":
        return None
    settled: set[Any] = set()
    for row in evidence_ledger or []:
        if not isinstance(row, Mapping) or not row.get("model_id"):
            continue
        explicit = row.get("outcome")
        proven_miss = (
            isinstance(explicit, str)
            and explicit in _CONTINUABLE_OUTCOMES
            and ledger_outcome(row) in _CONTINUABLE_OUTCOMES
        )
        if not proven_miss:
            return None
        settled.add(row.get("model_id"))
    retired = set((policy.get("retired_models") or {}).get("models") or [])
    for candidate in automatic_free_candidates(policy):
        model_id = candidate.get("model_id")
        if not model_id or model_id in retired or model_id in settled:
            continue
        if not candidate_dispatch_allowed(policy, candidate, requirements):
            continue
        return candidate
    return None


def drop_ungated_paid(
    chain: Sequence[Any],
    authorization: Mapping[str, Any] | None,
    budget_state: Mapping[str, Any] | None,
) -> list[Any]:
    """Drop paid and last-resort tiers unless this run's human gate names that model."""
    kept: list[Any] = []
    for item in chain:
        tier = getattr(item, "frugality_tier", None)
        if requires_paid_gate(tier):
            candidate = {"model_id": getattr(item, "name", None)}
            if authorize_paid_candidate(authorization, budget_state, candidate):
                kept.append(item)
            continue
        kept.append(item)
    return kept
