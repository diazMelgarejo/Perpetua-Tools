"""Durable, shared and atomic budget guard.

Settled spend and live reservations live in one private SQLite store beside the budget file, so every
CostGuard instance and every process that uses the same state directory and budget file shares one
ledger. reserve() checks settled spend plus every live reservation and records the new hold inside one
``BEGIN IMMEDIATE`` transaction, so two callers cannot both pass the check against the same last dollars.
An existing budget JSON is imported into the store once and renamed to ``<name>.migrated`` after
the import commits; it is never read or written again, and a missing store beside a ``.migrated`` file fails closed.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator

from .private_sqlite import open_private_sqlite


_LOG = logging.getLogger(__name__)

_DEFAULT_BUDGET = {
    "daily_budget": 25.0,
    "daily_spend": 0.0,
    "last_reset": 0.0,
}


class BudgetExceededError(Exception):
    """Raised by reserve() when settled spend + in-flight reservations would exceed budget."""


class SpendReconciliationRequiredError(RuntimeError):
    """An expired possibly sent request must be reconciled before further admissions."""


class UnknownReservationError(Exception):
    """Raised by commit()/rollback() for a reservation_id that was never reserve()'d, or
    was already committed/rolled back (each id is single-use)."""


class TokenCliffExceededError(Exception):
    """Raised by check_token_cliff() when input_tokens reaches or exceeds TOKEN_CLIFF_HARD_TOKENS."""


class CostGuard:
    """
    Shared, durable daily or monthly budget guard.
    Auto-resets every 24h (daily) or at the UTC calendar month (monthly). Blocks orchestration when
    spend reaches the budget. Alert triggers at 80% of the budget (matching monitoring_config in the
    strategy JSON).

    reserve()/commit()/rollback() are the atomic path: reserve() holds estimated_cost against the budget
    (counting every other live reservation, from any instance or process, not just settled spend) in one
    transaction, so concurrent callers cannot jointly overspend. can_spend()/record_spend() remain for
    callers that don't need atomicity across an await (e.g. a single synchronous accounting step).

    The store fails closed: an unsafe or unwritable state directory raises instead of degrading to a
    per-process in-memory budget, which would silently break the shared ceiling.
    """

    ALERT_RATIO = 0.80

    # A reservation this old is treated as abandoned and self-heals on the
    # next reserve() call -- defense-in-depth for a caller that never
    # reaches commit()/rollback() at all (e.g. the process is killed, not
    # just cancelled; a try/finally can't run if there's no interpreter left
    # to run it in). Generous relative to any real request duration.
    RESERVATION_TTL_SECONDS = 300.0

    # A caller may declare a longer hold for a request that is allowed to run longer than the default,
    # but not an unbounded one: a leaked multi-day hold would block the budget as surely as no hold at all.
    MAX_HOLD_SECONDS = 86_400.0

    # A swept reservation is remembered this long, so a commit that arrives after the sweep is still
    # recognized and its spend recorded rather than dropped.
    SWEPT_MEMORY_SECONDS = 30 * 86_400.0

    # 05-ORAMASYS-UNIFIED-ACTION-PLAN-2026-08-18.md Phase 4: warn approaching the 200k 2x-billing cliff
    TOKEN_CLIFF_WARN_TOKENS = 180_000
    # 05-ORAMASYS-UNIFIED-ACTION-PLAN-2026-08-18.md Phase 4: refuse single calls at/above 199k to prevent 2x billing
    TOKEN_CLIFF_HARD_TOKENS = 199_000

    PERIODS = ("daily", "monthly")

    def __init__(
        self, state_dir: str = ".state", budget_file: str = "budget.json", period: str = "daily"
    ) -> None:
        """Bind a guard to ``state_dir``/``budget_file``; guards with the same pair share one ledger."""
        if period not in self.PERIODS:
            raise ValueError(f"period must be one of {self.PERIODS}, got {period!r}")
        self.period = period
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.budget_path = self.state_dir / budget_file
        self.store_path = self.budget_path.with_suffix(".sqlite3")
        # Serializes this instance's coroutines; cross-instance and cross-process atomicity comes from
        # the store's BEGIN IMMEDIATE transactions, not from this lock.
        self._lock = asyncio.Lock()

    # -- store ---------------------------------------------------------------------------------

    @contextmanager
    def _txn(self) -> Iterator[sqlite3.Connection]:
        """Commit schema initialization first, then run the operation in its own transaction.

        Initialization is independently durable so a refused operation cannot undo a legacy import.
        """
        connection = open_private_sqlite(
            self.state_dir, self.store_path.name,
            dir_label="spend state", file_label="spend ledger", timeout=5,
        )
        try:
            connection.isolation_level = None  # explicit transaction control below
            connection.execute("BEGIN IMMEDIATE")
            try:
                self._ensure_schema(connection)
                connection.execute("COMMIT")
            except BaseException:
                connection.execute("ROLLBACK")
                raise
            self._finish_legacy_migration(connection)
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except BaseException:
                connection.execute("ROLLBACK")
                raise
            connection.execute("COMMIT")
        finally:
            connection.close()

    def _ensure_schema(self, db: sqlite3.Connection) -> None:
        """Create the tables, and import a legacy budget JSON the first time the store is empty."""
        db.execute(
            "CREATE TABLE IF NOT EXISTS budget (id INTEGER PRIMARY KEY CHECK (id = 1), daily_budget REAL NOT NULL,"
            " daily_spend REAL NOT NULL, last_reset REAL NOT NULL, period TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS reservations (id TEXT PRIMARY KEY, amount REAL NOT NULL,"
            " reserved_at REAL NOT NULL, expires_at REAL NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS swept (id TEXT PRIMARY KEY, amount REAL NOT NULL, swept_at REAL NOT NULL)"
        )
        db.execute("CREATE TABLE IF NOT EXISTS migration (id INTEGER PRIMARY KEY CHECK(id = 1))")
        columns = {row[1] for row in db.execute("PRAGMA table_info(reservations)")}
        if "uncertain" not in columns:
            db.execute("ALTER TABLE reservations ADD COLUMN uncertain INTEGER NOT NULL DEFAULT 0")
            # Older ledgers do not distinguish sent from unsent work. Preserve all remaining
            # holds and swept late-commit memories until someone reconciles their outcomes.
            db.execute("UPDATE reservations SET uncertain = 1")
            db.execute("INSERT INTO reservations (id, amount, reserved_at, expires_at, uncertain) "
                       "SELECT id, amount, swept_at, 0, 1 FROM swept")
            db.execute("DELETE FROM swept")
        if db.execute("SELECT 1 FROM budget WHERE id = 1").fetchone() is None:
            migrated = self.budget_path.with_name(self.budget_path.name + ".migrated")
            if migrated.exists():
                # The legacy spend was imported into a store that is now gone or empty. Starting from
                # zero (or importing a stale copy again) would forget or double real spend.
                raise RuntimeError(
                    f"spend store {self.store_path.name} is missing or empty but {migrated.name} shows the "
                    f"legacy budget was already migrated; restore the store, or review {migrated.name} and "
                    "move it back deliberately to import it again"
                )
            legacy = self._legacy_payload()
            seed = legacy or {**_DEFAULT_BUDGET, "last_reset": time.time(), "period": self.period}
            db.execute(
                "INSERT INTO budget VALUES (1, ?, ?, ?, ?)",
                (float(seed["daily_budget"]), float(seed["daily_spend"]), float(seed["last_reset"]),
                 str(seed.get("period") or "daily")),
            )
            if legacy:
                db.execute("INSERT INTO migration VALUES (1)")

    def _finish_legacy_migration(self, db: sqlite3.Connection) -> None:
        """Retry the post-commit rename without ever undoing the imported accounting."""
        if db.execute("SELECT 1 FROM migration WHERE id = 1").fetchone() is None:
            return
        migrated = self.budget_path.with_name(self.budget_path.name + ".migrated")
        if not migrated.exists():
            try:
                os.link(self.budget_path, migrated)
            except FileExistsError:
                pass
            except FileNotFoundError:
                if not migrated.exists():
                    raise RuntimeError("legacy migration source disappeared")
        try:
            if os.path.samefile(self.budget_path, migrated):
                self.budget_path.unlink(missing_ok=True)
        except FileNotFoundError:
            pass  # Another initializer completed the same rename.

    def _legacy_payload(self) -> Dict[str, Any] | None:
        """The pre-store budget JSON, validated, or None when there is none. A malformed file raises: starting
        from zero would silently forget real spend."""
        try:
            raw = self.budget_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        try:
            payload = json.loads(raw)
            for key in ("daily_budget", "daily_spend", "last_reset"):
                value = payload[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError(key)
            if payload.get("period", "daily") not in self.PERIODS:
                raise ValueError("period")
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(f"legacy budget file {self.budget_path.name} is not a valid budget; fix or move it") from exc
        return payload

    @staticmethod
    def _row(db: sqlite3.Connection) -> Dict[str, Any]:
        """The single budget row as the dict shape callers have always seen."""
        budget, spend, last_reset, period = db.execute(
            "SELECT daily_budget, daily_spend, last_reset, period FROM budget WHERE id = 1"
        ).fetchone()
        return {"daily_budget": budget, "daily_spend": spend, "last_reset": last_reset, "period": period}

    def _write(self, db: sqlite3.Connection, payload: Dict[str, Any]) -> None:
        """Persist the budget row inside the open transaction."""
        db.execute(
            "UPDATE budget SET daily_budget = ?, daily_spend = ?, last_reset = ?, period = ? WHERE id = 1",
            (payload["daily_budget"], payload["daily_spend"], payload["last_reset"], payload["period"]),
        )

    @staticmethod
    def _month_of(ts: float) -> tuple[int, int]:
        """The UTC (year, month) of a timestamp."""
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.year, dt.month

    def _period_elapsed(self, payload: Dict[str, Any]) -> bool:
        """True when the budget window has rolled over: 24 hours, or a UTC calendar month."""
        now = time.time()
        if self.period == "monthly":
            return self._month_of(now) != self._month_of(payload["last_reset"])
        return now - payload["last_reset"] >= 86400

    def _current(self, db: sqlite3.Connection) -> Dict[str, Any]:
        """The budget row for this guard's period, rolled over and persisted when the window has elapsed.
        Raises ValueError when the store was created for a different period."""
        payload = self._row(db)
        if payload["period"] != self.period:
            raise ValueError(f"budget file is {payload['period']!r} but this guard is {self.period!r}")
        if self._period_elapsed(payload):
            payload["daily_spend"] = 0.0
            payload["last_reset"] = time.time()
            self._write(db, payload)
        return payload

    def _sweep(self, db: sqlite3.Connection) -> None:
        """Release expired ordinary reservations. Caller holds the write transaction.

        A swept reservation stops counting against the budget (an abandoned caller must not block it
        forever) but is remembered, so a commit that still arrives is recorded as a late commit. Old
        memories are forgotten after SWEPT_MEMORY_SECONDS.
        """
        now = time.time()
        db.execute(
            "INSERT OR REPLACE INTO swept SELECT id, amount, ? FROM reservations WHERE expires_at < ? AND uncertain = 0", (now, now)
        )
        db.execute("DELETE FROM reservations WHERE expires_at < ? AND uncertain = 0", (now,))
        db.execute("DELETE FROM swept WHERE swept_at < ?", (now - self.SWEPT_MEMORY_SECONDS,))

    def _in_flight(self, db: sqlite3.Connection) -> float:
        """Dollars held by live reservations and all uncertain reservations."""
        return float(db.execute(
            "SELECT COALESCE(SUM(amount), 0.0) FROM reservations WHERE expires_at >= ? OR uncertain = 1", (time.time(),)
        ).fetchone()[0])

    # -- synchronous accounting ---------------------------------------------------------------

    def can_spend(self, estimated_cost: float) -> bool:
        """True when settled spend plus ``estimated_cost`` stays within the budget."""
        with self._txn() as db:
            p = self._current(db)
        return (p["daily_spend"] + estimated_cost) <= p["daily_budget"]

    def alert_approaching(self) -> bool:
        """True when settled spend has reached ALERT_RATIO of the budget."""
        with self._txn() as db:
            p = self._current(db)
        return p["daily_spend"] >= (p["daily_budget"] * self.ALERT_RATIO)

    def record_spend(self, amount: float) -> Dict[str, Any]:
        """Add ``amount`` to settled spend atomically and return the new budget state."""
        with self._txn() as db:
            p = self._current(db)
            p["daily_spend"] = round(p["daily_spend"] + amount, 6)
            self._write(db, p)
        return p

    def snapshot(self) -> Dict[str, Any]:
        """Budget, settled spend, window start, period, alert flag and remaining dollars."""
        with self._txn() as db:
            p = self._current(db)
        out: Dict[str, Any] = dict(p)
        out["alert"] = p["daily_spend"] >= (p["daily_budget"] * self.ALERT_RATIO)
        out["period"] = self.period
        out["remaining"] = round(p["daily_budget"] - p["daily_spend"], 6)
        return out

    def set_budget(self, daily_budget: float) -> None:
        """Set the ceiling only when the stored accounting period matches this guard.

        Changing a ceiling does not reset spend, even if the current period has elapsed.
        """
        if not math.isfinite(daily_budget) or daily_budget < 0:
            raise ValueError(f"daily_budget must be a non-negative finite number, got {daily_budget!r}")
        with self._txn() as db:
            p = self._row(db)
            if p["period"] != self.period:
                raise ValueError(f"budget file is {p['period']!r} but this guard is {self.period!r}")
            p["daily_budget"] = float(daily_budget)
            self._write(db, p)

    def in_flight(self) -> float:
        """Dollars currently held by live reservations across every instance and process."""
        with self._txn() as db:
            return self._in_flight(db)

    def check_token_cliff(self, input_tokens: int) -> str | None:
        """Check if input_tokens approaches or exceeds the 199k billing cliff.

        Rejects negative or non-finite values before checking thresholds.
        Returns a warning string when >= TOKEN_CLIFF_WARN_TOKENS.
        Raises TokenCliffExceededError when >= TOKEN_CLIFF_HARD_TOKENS.
        Returns None when below the warning threshold.
        """
        if not math.isfinite(input_tokens) or input_tokens < 0:
            raise ValueError(f"input_tokens must be a non-negative finite number, got {input_tokens!r}")
        if input_tokens >= self.TOKEN_CLIFF_HARD_TOKENS:
            raise TokenCliffExceededError(
                f"Token count {input_tokens} reaches or exceeds the 199k billing cliff "
                f"(hard threshold: {self.TOKEN_CLIFF_HARD_TOKENS}); request must be split or refused"
            )
        elif input_tokens >= self.TOKEN_CLIFF_WARN_TOKENS:
            return f"Token count {input_tokens} is approaching the 199k billing cliff (warn threshold: {self.TOKEN_CLIFF_WARN_TOKENS})"
        return None

    # -- atomic reserve / commit / rollback -------------------------------------------------------

    def reserve_sync(self, estimated_cost: float, hold_seconds: float | None = None, *, uncertain: bool = False) -> str:
        """Atomically hold ``estimated_cost`` against the budget; the blocking core of reserve().

        Checks settled spend PLUS every live reservation (from any instance or process) and records the
        hold in the same transaction. Raises BudgetExceededError when it does not fit, ValueError for a
        negative or non-finite cost. Zero is valid: ``OrchestrateRequest.estimated_cost`` defaults to
        ``0.0`` for calls with no known cost estimate. A negative cost would LOWER the in-flight total
        and let others reserve past the budget; NaN makes every comparison False so the reservation
        would always "succeed" and poison settled spend on commit.

        ``uncertain`` retains a potentially sent request until settlement or explicit release; an expired
        uncertain hold blocks new admissions until reconciled. ``hold_seconds`` is how long this
        reservation is held before another reservation may sweep it
        (default RESERVATION_TTL_SECONDS; at most MAX_HOLD_SECONDS). A caller whose request may run
        longer than the default must declare that lifetime. Ordinary reservations can be swept after
        expiry; uncertain reservations instead block further admissions until reconciled.
        """
        if not math.isfinite(estimated_cost) or estimated_cost < 0:
            raise ValueError(f"estimated_cost must be a non-negative finite number, got {estimated_cost!r}")
        if hold_seconds is None:
            hold_seconds = self.RESERVATION_TTL_SECONDS
        elif (
            isinstance(hold_seconds, bool) or not isinstance(hold_seconds, (int, float))
            or not math.isfinite(hold_seconds) or not 0 < hold_seconds <= self.MAX_HOLD_SECONDS
        ):
            raise ValueError(f"hold_seconds must be a finite number in (0, {self.MAX_HOLD_SECONDS:g}], got {hold_seconds!r}")
        with self._txn() as db:
            self._sweep(db)
            if db.execute("SELECT 1 FROM reservations WHERE uncertain = 1 AND expires_at < ? LIMIT 1", (time.time(),)).fetchone():
                raise SpendReconciliationRequiredError("expired uncertain spend requires reconciliation")
            p = self._current(db)
            in_flight = self._in_flight(db)
            if p["daily_spend"] + in_flight + estimated_cost > p["daily_budget"]:
                raise BudgetExceededError(
                    f"reserving ${estimated_cost:.4f} would exceed daily budget "
                    f"(settled=${p['daily_spend']:.4f}, in_flight=${in_flight:.4f}, "
                    f"budget=${p['daily_budget']:.4f})"
                )
            reservation_id = uuid.uuid4().hex
            now = time.time()
            db.execute(
                "INSERT INTO reservations (id, amount, reserved_at, expires_at, uncertain) VALUES (?, ?, ?, ?, ?)",
                (reservation_id, estimated_cost, now, now + hold_seconds, int(uncertain)),
            )
            return reservation_id

    def commit_sync(self, reservation_id: str, actual_cost: float | None = None) -> Dict[str, Any]:
        """Settle a reservation into settled spend; the blocking core of commit().

        ``actual_cost`` overrides the reserved estimate when the real cost is known. It is validated
        before the reservation is touched, so an invalid value leaves the reservation intact for retry.
        A reservation the sweep already released still records its spend (the caller's request really
        ran): the result then carries ``late_commit: True`` and a warning is logged. Accounting is never
        dropped. The result always carries ``committed_usd``. Raises UnknownReservationError only for an
        id that was never reserved, was already settled or released, or was forgotten long ago.
        """
        if actual_cost is not None and (not math.isfinite(actual_cost) or actual_cost < 0):
            raise ValueError(f"actual_cost must be a non-negative finite number, got {actual_cost!r}")
        with self._txn() as db:
            self._sweep(db)
            late = False
            row = db.execute("SELECT amount, expires_at FROM reservations WHERE id = ?", (reservation_id,)).fetchone()
            if row is not None:
                late = row[1] < time.time()
            if row is None:
                row = db.execute("SELECT amount FROM swept WHERE id = ?", (reservation_id,)).fetchone()
                late = row is not None
            if row is None:
                raise UnknownReservationError(reservation_id)
            amount = row[0] if actual_cost is None else actual_cost
            db.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
            db.execute("DELETE FROM swept WHERE id = ?", (reservation_id,))
            p = self._current(db)
            p["daily_spend"] = round(p["daily_spend"] + amount, 6)
            self._write(db, p)
        if late:
            _LOG.warning("late commit: reservation outlived its hold; $%.6f recorded", amount)
        return {**p, "committed_usd": amount, "late_commit": late}

    def rollback_sync(self, reservation_id: str) -> None:
        """Release a reservation without charging the budget; the blocking core of rollback()."""
        with self._txn() as db:
            if db.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,)).rowcount != 1:
                raise UnknownReservationError(reservation_id)

    async def reserve(self, estimated_cost: float, hold_seconds: float | None = None) -> str:
        """Atomically hold ``estimated_cost`` against the shared budget. See reserve_sync()."""
        async with self._lock:
            return self.reserve_sync(estimated_cost, hold_seconds)

    async def commit(self, reservation_id: str, actual_cost: float | None = None) -> Dict[str, Any]:
        """Settle a reservation into settled spend. See commit_sync()."""
        async with self._lock:
            return self.commit_sync(reservation_id, actual_cost)

    async def rollback(self, reservation_id: str) -> None:
        """Release a reservation without charging the budget. See rollback_sync()."""
        async with self._lock:
            self.rollback_sync(reservation_id)
