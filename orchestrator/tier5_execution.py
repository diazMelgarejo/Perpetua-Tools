"""Governed Tier-5 execution service with durable budget settlement.

This service coordinates the Tier5BudgetLedger lifecycle around TieredPipelineRunner:
1. Calculates request fingerprint using HMAC-SHA256 with required local secret.
2. Obtains an atomic SQLite reservation before execution.
3. Commits a durable dispatch marker immediately before each provider call.
4. Conservatively settles after execution: releases holds on pre-dispatch errors,
   releases verified unused difference on success, and consumes full holds on
   ambiguous or post-marker failures.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from typing import Optional

from orchestrator.tiered_pipeline import (
    Dispatcher,
    PipelineApproval,
    PipelineError,
    PipelineRecipe,
    PipelineResult,
    TieredPipelineRunner,
)
from orchestrator.tier5_budget import (
    MICROUSD_PER_USD,
    Reservation,
    Tier5BudgetLedger,
)

_log = logging.getLogger(__name__)

HMAC_KEY_ENV = "PT_TIER5_LEDGER_HMAC_KEY"


class Tier5ExecutionError(PipelineError):
    """Base error for Tier-5 execution service operations."""


class Tier5ConfigurationError(Tier5ExecutionError):
    """Raised when required Tier-5 configuration or secrets are missing."""


class Tier5SecurityError(Tier5ExecutionError):
    """Raised when security or integrity checks fail."""


def compute_request_fingerprint(
    recipe_name: str,
    prompt: str,
    approval: PipelineApproval,
    task_type: str = "reasoning",
    privacy_critical: bool = False,
    hmac_key: str | None = None,
) -> str:
    """Compute HMAC-SHA256 fingerprint for request identity.

    Fails closed if the HMAC secret is missing or empty.
    """
    secret = hmac_key or os.environ.get(HMAC_KEY_ENV, "")
    if not secret or not secret.strip():
        raise Tier5ConfigurationError(
            f"{HMAC_KEY_ENV} is required and must be non-empty for Tier-5 execution"
        )

    canonical_data = {
        "recipe": str(recipe_name).strip(),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "trace_id": str(approval.trace_id).strip(),
        "approved_by": str(approval.approved_by).strip(),
        "purpose": str(approval.purpose).strip(),
        "task_type": str(task_type).strip(),
        "privacy_critical": bool(privacy_critical),
    }
    canonical_json = json.dumps(canonical_data, sort_keys=True, separators=(",", ":"))
    return hmac.new(
        secret.encode("utf-8"),
        canonical_json.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class Tier5ExecutionService:
    """Orchestrates durable budget reservation and execution for Tier-5 pipelines."""

    def __init__(
        self,
        ledger: Tier5BudgetLedger,
        runner: TieredPipelineRunner,
        *,
        hmac_key: str | None = None,
    ) -> None:
        self.ledger = ledger
        self.runner = runner
        self.hmac_key = hmac_key

    async def execute(
        self,
        run_id: str,
        idempotency_key: str,
        recipe_name: str,
        prompt: str,
        *,
        approval: PipelineApproval,
        dispatch: Dispatcher,
        task_type: str = "reasoning",
        privacy_critical: bool = False,
        override_confirmed: bool = False,
        override_reason: str | None = None,
        explicit_cap_microusd: Optional[int] = None,
    ) -> tuple[PipelineResult, Reservation]:
        """Execute a governed Tier-5 pipeline run with atomic budget settlement.

        1. Fingerprints request with HMAC-SHA256.
        2. Reserves worst-case exposure atomically in SQLite.
        3. If already processed/replayed with same fingerprint, returns stored state.
        4. Commits stage dispatch markers before provider I/O.
        5. Conservatively settles spend upon completion or failure.
        """
        fingerprint = compute_request_fingerprint(
            recipe_name=recipe_name,
            prompt=prompt,
            approval=approval,
            task_type=task_type,
            privacy_critical=privacy_critical,
            hmac_key=self.hmac_key,
        )

        recipe = self.runner.recipe(recipe_name)
        worst_case_microusd = int(round(recipe.cost_reservation_usd * MICROUSD_PER_USD))

        reservation = self.ledger.reserve(
            run_id=run_id,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
            worst_case_microusd=worst_case_microusd,
            explicit_cap_microusd=explicit_cap_microusd,
        )

        if reservation.state != "RESERVED":
            # Idempotent replay: return stored reservation without executing again
            _log.info(
                "Tier-5 idempotent replay for run_id=%s in state=%s",
                reservation.run_id,
                reservation.state,
            )
            empty_result = PipelineResult(
                recipe=recipe.name,
                output="",
                stage_outputs={},
                requested_tokens=0,
                total_tokens_used=None,
                total_cost_usd=None,
            )
            return empty_result, reservation

        async def marked_dispatch(
            model: str, stage_prompt: str, max_tokens: int, stage_name: str
        ) -> DispatchResult:
            # Commit the stage marker BEFORE performing provider I/O
            self.ledger.mark_dispatch(run_id, stage_name)
            return await dispatch(model, stage_prompt, max_tokens, stage_name)

        try:
            result = await self.runner.run(
                recipe_name,
                prompt,
                approval=approval,
                dispatch=marked_dispatch,
                task_type=task_type,
                privacy_critical=privacy_critical,
                override_confirmed=override_confirmed,
                override_reason=override_reason,
            )
        except Exception:
            if self.ledger.has_stage_markers(run_id):
                # Ambiguous / post-marker failure consumes the complete held amount
                self.ledger.settle(run_id, verified_unused_microusd=0)
            else:
                # Pre-dispatch failure: release held funds back to daily budget
                try:
                    self.ledger.release_pre_dispatch(run_id)
                except Exception as release_exc:
                    _log.warning(
                        "Failed to release pre-dispatch hold for %s: %s",
                        run_id,
                        release_exc,
                    )
            raise

        # Successful run: calculate verified unused difference
        if result.total_cost_usd is not None and result.total_cost_usd >= 0:
            actual_microusd = int(round(result.total_cost_usd * MICROUSD_PER_USD))
            verified_unused = max(0, reservation.held_microusd - actual_microusd)
        else:
            # Absent or invalid usage cannot be proven unused -> consumes full hold
            verified_unused = 0

        settled_reservation = self.ledger.settle(
            run_id, verified_unused_microusd=verified_unused
        )
        return result, settled_reservation
