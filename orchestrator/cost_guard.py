from __future__ import annotations

import asyncio
import json
import math
import time
import uuid
from pathlib import Path
from typing import Any, Dict


_DEFAULT_BUDGET = {
    "daily_budget": 25.0,
    "daily_spend": 0.0,
    "last_reset": 0.0,
}


class BudgetExceededError(Exception):
    """Raised by reserve() when settled spend + in-flight reservations would exceed budget."""


class UnknownReservationError(Exception):
    """Raised by commit()/rollback() for a reservation_id that was never reserve()'d, or
    was already committed/rolled back (each id is single-use)."""


class CostGuard:
    """
    File-persisted daily budget guard.
    Auto-resets every 24h. Blocks orchestration when daily_spend ≥ daily_budget.
    Alert triggers at 80% of daily_budget (matching monitoring_config in strategy JSON).

    reserve()/commit()/rollback() are the atomic path: reserve() holds
    estimated_cost against the budget (counting other in-flight reservations,
    not just settled daily_spend) before any await point, so two concurrent
    callers cannot both pass a check-then-act gap and jointly overspend.
    can_spend()/record_spend() remain for callers that don't need atomicity
    across an await (e.g. a single synchronous accounting step).
    """

    ALERT_RATIO = 0.80

    # A reservation this old is treated as abandoned and self-heals on the
    # next reserve() call -- defense-in-depth for a caller that never
    # reaches commit()/rollback() at all (e.g. the process is killed, not
    # just cancelled; a try/finally can't run if there's no interpreter left
    # to run it in). Generous relative to any real request duration.
    RESERVATION_TTL_SECONDS = 300.0

    def __init__(
        self, state_dir: str = ".state", budget_file: str = "budget.json"
    ) -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.budget_path = self.state_dir / budget_file
        self._memory_state: Dict[str, float] = {**_DEFAULT_BUDGET, "last_reset": time.time()}
        self._persist_enabled = True
        self._lock = asyncio.Lock()
        # reservation_id -> (amount, monotonic reserve() timestamp)
        self._reserved: Dict[str, tuple[float, float]] = {}

    def _load(self) -> Dict[str, float]:
        if not self._persist_enabled:
            return dict(self._memory_state)

        try:
            if not self.budget_path.exists():
                payload = {**_DEFAULT_BUDGET, "last_reset": time.time()}
                self._save(payload)
                return payload
            payload = json.loads(self.budget_path.read_text(encoding="utf-8"))
            self._memory_state = dict(payload)
            return payload
        except OSError:
            self._persist_enabled = False
            return dict(self._memory_state)

    def _save(self, payload: Dict[str, float]) -> None:
        self._memory_state = dict(payload)
        if not self._persist_enabled:
            return
        try:
            self.budget_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError:
            self._persist_enabled = False

    def _maybe_reset(self, payload: Dict[str, float]) -> Dict[str, float]:
        if time.time() - payload["last_reset"] >= 86400:
            payload["daily_spend"] = 0.0
            payload["last_reset"] = time.time()
            self._save(payload)
        return payload

    def can_spend(self, estimated_cost: float) -> bool:
        p = self._maybe_reset(self._load())
        return (p["daily_spend"] + estimated_cost) <= p["daily_budget"]

    def alert_approaching(self) -> bool:
        p = self._maybe_reset(self._load())
        return p["daily_spend"] >= (p["daily_budget"] * self.ALERT_RATIO)

    def record_spend(self, amount: float) -> Dict[str, float]:
        p = self._maybe_reset(self._load())
        p["daily_spend"] = round(p["daily_spend"] + amount, 6)
        self._save(p)
        return p

    def snapshot(self) -> Dict[str, Any]:
        p = self._maybe_reset(self._load())
        out: Dict[str, Any] = dict(p)
        out["alert"] = self.alert_approaching()
        out["remaining"] = round(p["daily_budget"] - p["daily_spend"], 6)
        return out

    def set_budget(self, daily_budget: float) -> None:
        p = self._load()
        p["daily_budget"] = daily_budget
        self._save(p)

    async def reserve(self, estimated_cost: float) -> str:
        """Atomically hold ``estimated_cost`` against the budget.

        Checks settled ``daily_spend`` PLUS every other currently-outstanding
        reservation, so concurrent callers each see the others' in-flight
        holds -- not just what's already been committed to disk. Raises
        BudgetExceededError instead of returning bool, since the caller must
        distinguish "no reservation was made" from "one was made and must be
        rolled back."

        Rejects negative or non-finite ``estimated_cost`` before touching any
        state: a negative value would LOWER ``in_flight``, letting other
        concurrent callers reserve past the real budget; NaN makes the
        Line-125-style comparison always False (Python: any comparison with
        NaN is False), so the reservation would always "succeed" and poison
        ``daily_spend`` with NaN on commit. Zero IS valid and common --
        ``OrchestrateRequest.estimated_cost`` defaults to ``0.0`` for calls
        with no known cost estimate.
        """
        if not math.isfinite(estimated_cost) or estimated_cost < 0:
            raise ValueError(f"estimated_cost must be a non-negative finite number, got {estimated_cost!r}")
        async with self._lock:
            self._sweep_expired_reservations_locked()
            p = self._maybe_reset(self._load())
            in_flight = sum(amount for amount, _ in self._reserved.values())
            if p["daily_spend"] + in_flight + estimated_cost > p["daily_budget"]:
                raise BudgetExceededError(
                    f"reserving ${estimated_cost:.4f} would exceed daily budget "
                    f"(settled=${p['daily_spend']:.4f}, in_flight=${in_flight:.4f}, "
                    f"budget=${p['daily_budget']:.4f})"
                )
            reservation_id = uuid.uuid4().hex
            self._reserved[reservation_id] = (estimated_cost, time.monotonic())
            return reservation_id

    def _sweep_expired_reservations_locked(self) -> None:
        """Drop reservations older than RESERVATION_TTL_SECONDS. Caller must
        already hold self._lock.

        This is the self-healing half of the leak fix: a caller that never
        reaches commit()/rollback() at all (process killed outright, not
        just the task cancelled -- a try/finally can't run without an
        interpreter left to run it in) would otherwise hold a phantom
        budget block forever. An expired reservation is dropped, not
        charged -- conservative in the operator's favor: if the original
        request really did complete, its real cost was either never
        significant (the common estimated_cost=0.0 case) or the caller's
        own commit()/rollback() already ran well within the TTL window.
        """
        now = time.monotonic()
        expired = [
            rid for rid, (_, reserved_at) in self._reserved.items()
            if now - reserved_at > self.RESERVATION_TTL_SECONDS
        ]
        for rid in expired:
            del self._reserved[rid]

    async def commit(self, reservation_id: str, actual_cost: float | None = None) -> Dict[str, float]:
        """Settle a reservation into ``daily_spend``.

        ``actual_cost`` overrides the original estimate when the real
        provider cost is known (e.g. from usage metadata) -- defaults to the
        reserved estimate when the caller has no better number. Raises
        UnknownReservationError both for a never-reserved id and for one the
        TTL sweep already reclaimed (rare -- see RESERVATION_TTL_SECONDS);
        callers that may race the sweep should catch it and treat it as a
        no-op, not a hard failure.
        """
        async with self._lock:
            if reservation_id not in self._reserved:
                raise UnknownReservationError(reservation_id)
            estimated, _ = self._reserved.pop(reservation_id)
            amount = estimated if actual_cost is None else actual_cost
            p = self._maybe_reset(self._load())
            p["daily_spend"] = round(p["daily_spend"] + amount, 6)
            self._save(p)
            return p

    async def rollback(self, reservation_id: str) -> None:
        """Release a reservation without charging the budget."""
        async with self._lock:
            if reservation_id not in self._reserved:
                raise UnknownReservationError(reservation_id)
            del self._reserved[reservation_id]
