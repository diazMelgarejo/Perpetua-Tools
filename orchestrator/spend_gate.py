"""The one spend gate in front of every paid provider request.

Perpetua-Tools is the runtime and state authority for spend. This module composes the provider policy
(operator attestation, upper-bound projection, size-only audit; ``provider_limits``) with the shared
atomic budget (``CostGuard``) into the single lifecycle every caller uses: preflight (refuse or reserve),
then exactly one of settle, settle_unknown or release. Callers that live elsewhere (the agent harness,
orama-system's adapter) forward to this class and keep no ledger of their own.

    gate = SpendGate()
    pre = gate.preflight(prompt_chars, hold_seconds)       # refused here: nothing is sent
    if not pre["ok"]: ...                                   # reason: attestation-required | budget-exhausted
    ... send the request ...
    gate.settle(pre["reservation"], in_chars, out_chars, "ok", seat, mode)         # answer received
    gate.settle_unknown(pre["reservation"], in_chars, "request-failed", seat, mode)  # may have been sent
    gate.release(pre["reservation"])                                                # nothing was sent

The estimate is not billing; the provider's Billing page is. The module also loads when it is imported
by file path (without the ``orchestrator`` package), which is how a consumer checkout uses it.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from . import cost_guard as _cg
    from . import provider_limits as _pl
except ImportError:  # loaded by file path: bring the sibling modules in under a private package name
    _PRIVATE_PACKAGE = "pt_orchestrator_spend_gate"
    if _PRIVATE_PACKAGE not in sys.modules:
        _here = Path(__file__).resolve().parent
        _spec = importlib.util.spec_from_file_location(
            _PRIVATE_PACKAGE, _here / "__init__.py", submodule_search_locations=[str(_here)]
        )
        if _spec is None or _spec.loader is None:  # pragma: no cover - the checkout is broken
            raise
        _package = importlib.util.module_from_spec(_spec)
        sys.modules[_PRIVATE_PACKAGE] = _package
        _spec.loader.exec_module(_package)
    _cg = importlib.import_module(f"{_PRIVATE_PACKAGE}.cost_guard")
    _pl = importlib.import_module(f"{_PRIVATE_PACKAGE}.provider_limits")

# Public names for the exceptions a consumer must handle, so no caller reaches into the private imports.
# ProviderPolicyError: no valid policy (SpendGate() refuses). BudgetExceededError and
# UnknownReservationError are what the underlying guard raises; PermissionError (an unsafe spend store)
# is the builtin.
ProviderPolicyError = _pl.ProviderPolicyError
BudgetExceededError = _cg.BudgetExceededError
UnknownReservationError = _cg.UnknownReservationError

__all__ = [
    "DEFAULT_PROVIDER", "SpendGate", "ProviderPolicyError", "BudgetExceededError", "UnknownReservationError",
]

DEFAULT_PROVIDER = "wandb-inference"


class SpendGate:
    """Preflight, settle and release one provider's spend through the shared CostGuard."""

    def __init__(
        self,
        provider: str = DEFAULT_PROVIDER,
        state_dir: str | Path | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        """Load ``provider``'s policy and bind the shared budget store in ``state_dir``.

        ``state_dir`` defaults to the operator spend directory (``provider_limits.spend_dir()``); every
        gate and process that uses the same directory shares one budget. ``now`` is an injectable clock
        returning an aware datetime. Raises ``provider_limits.ProviderPolicyError`` when there is no
        valid policy, and PermissionError when the spend store is unsafe: callers must treat both as a
        refusal.
        """
        self.pl = _pl
        self.cg = _cg
        self.policy = _pl.load_policy(provider)
        self.provider = provider
        self._now = now or (lambda: datetime.now(timezone.utc))
        spend = Path(state_dir) if state_dir else _pl.spend_dir()
        self.guard = _cg.CostGuard(
            state_dir=str(spend), budget_file=f"{provider}-budget.json", period=self.policy["budget"]["period"]
        )
        ceiling = float(self.policy["budget"]["operator_estimate_ceiling_usd"])
        if self.guard.snapshot()["daily_budget"] != ceiling:
            self.guard.set_budget(ceiling)  # the policy file is the source of truth for the ceiling
        self.audit_path = spend / f"{provider}-spend-audit.jsonl"

    def _attestation(self) -> Any:
        """The operator's attestation record: None when absent, ``{}`` when unreadable (both refuse)."""
        path = _pl.attestation_path(self.provider)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            return {}

    def preflight(self, prompt_chars: int, hold_seconds: float) -> dict:
        """Check the operator attestation, then reserve the projected cost for ``hold_seconds``.

        ``hold_seconds`` must cover the request's whole allowed lifetime (including its timeout), or the
        reservation can be swept while the request is still running. Returns ``{"ok": True, "reservation",
        "projected_usd"}``, or ``{"ok": False, "stop": True, "reason": "attestation-required" |
        "budget-exhausted", ...}``; in the refusal case nothing is reserved and the caller must not send.
        Raises ValueError for a negative or non-finite size or an invalid hold.
        """
        projected = _pl.projected_usd(self.policy, prompt_chars)
        status = _pl.attestation_status(self.policy, self._attestation(), self._now())
        if not status["ok"]:
            return {"ok": False, "reason": "attestation-required", "stop": True, "reasons": status["reasons"]}
        try:
            reservation = self.guard.reserve_sync(projected, hold_seconds)
        except self.cg.BudgetExceededError as exc:
            return {"ok": False, "reason": "budget-exhausted", "stop": True, "error": str(exc),
                    "projected_usd": projected}
        return {"ok": True, "reservation": reservation, "projected_usd": projected}

    def _audit(self, row: dict) -> None:
        """Append one size-only audit row (sizes and identifiers only; never prompts or answers)."""
        _pl.append_audit(self.audit_path, {
            "ts": self._now().isoformat(), "estimated": True, "provider": self.provider,
            "policy_id": self.policy["policy_id"], **row,
        })

    def settle(self, reservation: str, input_chars: int, output_chars: int, outcome: str, seat: str, mode: str) -> float:
        """Commit the estimated actual cost of an answered request and audit it. Returns the estimate.

        Sizes are validated before anything is committed. A reservation whose hold lapsed still records
        the spend, and its audit row says ``basis: late-commit``.
        """
        usd = _pl.estimate_usd(self.policy, input_chars, output_chars)
        late = self.guard.commit_sync(reservation, usd)["late_commit"]
        self._audit({"seat": seat, "mode": mode, "input_chars": input_chars, "output_chars": output_chars,
                     "estimated_usd": usd, "outcome": outcome, **({"basis": "late-commit"} if late else {})})
        return usd

    def settle_unknown(self, reservation: str, input_chars: int, outcome: str, seat: str, mode: str) -> float:
        """Commit the FULL reserved amount for a request that may have been sent but has no usable answer.

        Unavailable output is not evidence of zero billed output (a timeout or a dropped stream can still
        bill the reasoning stream), so the whole reservation is charged and the audit row records the
        output as unknown (no ``output_chars``; ``basis: output-unknown``). Returns the amount committed.
        """
        _pl.estimate_usd(self.policy, input_chars, 0)  # validates the size before anything is committed
        result = self.guard.commit_sync(reservation)
        usd = result["committed_usd"]
        self._audit({"seat": seat, "mode": mode, "input_chars": input_chars, "estimated_usd": usd,
                     "outcome": outcome, "basis": "late-commit" if result["late_commit"] else "output-unknown"})
        return usd

    def release(self, reservation: str) -> None:
        """Release a reservation that was never sent, charging nothing. Idempotent: a reservation that is
        already settled, released or swept is not an error, so cleanup never masks the original failure."""
        try:
            self.guard.rollback_sync(reservation)
        except self.cg.UnknownReservationError:
            pass

    def classify(self, text: Any) -> str | None:
        """``provider-payment-required``, ``provider-rate-limited`` or None for a failure message."""
        return _pl.classify_failure(self.policy, text)

    def snapshot(self) -> dict:
        """The shared budget snapshot (budget, settled spend, window, alert, remaining)."""
        return self.guard.snapshot()
