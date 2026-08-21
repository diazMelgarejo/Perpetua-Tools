"""Durable, conservative accounting for Tier-5 provider runs.

This module is intentionally independent of the legacy ``CostGuard``. SQLite
is the write authority: every reservation and lifecycle transition is committed
before a caller may perform paid provider I/O.
"""
from __future__ import annotations

import hashlib
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

MICROUSD_PER_USD = 1_000_000


class BudgetError(RuntimeError):
    """Base class for fail-closed ledger errors."""


class BudgetConflictError(BudgetError):
    """The idempotency key was reused for a different request."""


class BudgetInsufficientError(BudgetError):
    """The requested worst-case amount cannot be reserved."""


class BudgetUnavailableError(BudgetError):
    """The ledger could not obtain its bounded SQLite writer lock."""


@dataclass(frozen=True)
class Reservation:
    run_id: str
    key_digest: str
    fingerprint: str
    state: str
    policy_cap_microusd: int
    held_microusd: int
    settled_microusd: int


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def utc_day(now: datetime | None = None) -> str:
    value = now or datetime.now(timezone.utc)
    return value.astimezone(timezone.utc).date().isoformat()


class Tier5BudgetLedger:
    """SQLite-backed reservation ledger with one-winner writer semantics."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        daily_limit_microusd: int,
        busy_timeout_ms: int = 2_000,
    ) -> None:
        if isinstance(daily_limit_microusd, bool) or daily_limit_microusd <= 0:
            raise ValueError("daily_limit_microusd must be a positive integer")
        if (
            isinstance(busy_timeout_ms, bool)
            or not isinstance(busy_timeout_ms, int)
            or busy_timeout_ms <= 0
        ):
            raise ValueError("busy_timeout_ms must be a positive integer")
        self.db_path = Path(db_path)
        self.daily_limit_microusd = daily_limit_microusd
        self.busy_timeout_ms = busy_timeout_ms
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=self.busy_timeout_ms / 1000)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout = %d" % self.busy_timeout_ms)
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA journal_mode = WAL")
        return db

    @contextmanager
    def _transaction(self):
        """Open a connection, take an IMMEDIATE write lock, and always close it.

        ``with sqlite3.Connection:`` only commits/rolls back on exit -- it
        never closes the underlying connection, so every prior call site
        that did ``with self._connect() as db:`` leaked a connection per
        call. This combines both: transaction semantics via the inner
        ``with db:``, guaranteed close via ``finally``.

        ``BEGIN IMMEDIATE`` here (not deferred, Python's default) is load
        -bearing: it takes the write lock before the first statement, not
        before the first write, so every read this transaction does (e.g.
        reserve()'s existing-key and used-sum checks) is already under the
        same lock the eventual write commits under -- no window for a
        second writer to interleave between a check and the write it gates.
        """
        db = self._connect()
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                yield db
        finally:
            db.close()

    @staticmethod
    def _translate_operational_error(
        exc: sqlite3.OperationalError,
    ) -> "BudgetUnavailableError | None":
        message = str(exc).lower()
        if "locked" in message or "busy" in message:
            return BudgetUnavailableError("budget ledger is temporarily unavailable")
        return None

    @contextmanager
    def _guarded_transaction(self):
        """``_transaction()``, but every lock-contention OperationalError
        (not just reserve()'s and mark_dispatch()'s) surfaces as the ledger's
        own BudgetUnavailableError instead of a raw sqlite3 exception --
        settle() in particular can hit this after the provider spend already
        happened, so its caller must see a ledger error, not an sqlite3 one.
        """
        try:
            with self._transaction() as db:
                yield db
        except BudgetError:
            raise
        except sqlite3.OperationalError as exc:
            translated = self._translate_operational_error(exc)
            if translated is not None:
                raise translated from exc
            raise

    def _initialize(self) -> None:
        with self._transaction() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS tier5_budget_runs (
                    run_id TEXT PRIMARY KEY,
                    key_digest TEXT NOT NULL UNIQUE,
                    fingerprint TEXT NOT NULL,
                    utc_day TEXT NOT NULL,
                    state TEXT NOT NULL,
                    policy_cap_microusd INTEGER NOT NULL,
                    held_microusd INTEGER NOT NULL,
                    settled_microusd INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tier5_budget_stages (
                    run_id TEXT NOT NULL REFERENCES tier5_budget_runs(run_id),
                    stage_name TEXT NOT NULL,
                    marker_at REAL NOT NULL,
                    PRIMARY KEY (run_id, stage_name)
                );
                CREATE INDEX IF NOT EXISTS tier5_budget_runs_day
                    ON tier5_budget_runs (utc_day, state);
                """
            )

    @staticmethod
    def _row(row: sqlite3.Row) -> Reservation:
        return Reservation(
            run_id=row["run_id"],
            key_digest=row["key_digest"],
            fingerprint=row["fingerprint"],
            state=row["state"],
            policy_cap_microusd=row["policy_cap_microusd"],
            held_microusd=row["held_microusd"],
            settled_microusd=row["settled_microusd"],
        )

    def reserve(
        self,
        *,
        run_id: str,
        idempotency_key: str,
        fingerprint: str,
        worst_case_microusd: int,
        explicit_cap_microusd: Optional[int] = None,
        now: datetime | None = None,
    ) -> Reservation:
        """Reserve funds atomically, or return the existing identical run.

        Reserves exactly ``worst_case_microusd`` -- the deterministic
        worst-case exposure for this run -- never the full policy ceiling.
        The ceiling (``explicit_cap_microusd``, or the default "remaining
        minus one unit" rule) is the maximum this run is *allowed* to cost,
        validated against ``worst_case_microusd`` and stored separately as
        ``policy_cap_microusd`` for audit; it is never itself reserved.
        This lets multiple small runs proceed concurrently the same day
        instead of the first uncapped reservation locking out the rest of
        the day's budget. If the caller cannot provide a real
        ``worst_case_microusd``, this fails closed (ValueError) rather than
        silently reserving the remaining balance as a stand-in.
        """
        if not run_id.strip() or not idempotency_key.strip() or not fingerprint.strip():
            raise ValueError("run_id, idempotency_key, and fingerprint are required")
        if isinstance(worst_case_microusd, bool) or worst_case_microusd <= 0:
            raise ValueError("worst_case_microusd must be a positive integer")
        if explicit_cap_microusd is not None and (
            isinstance(explicit_cap_microusd, bool) or explicit_cap_microusd <= 0
        ):
            raise ValueError("explicit_cap_microusd must be a positive integer")
        key_digest = _digest(idempotency_key)
        day = utc_day(now)
        timestamp = time.time()
        with self._guarded_transaction() as db:
            existing = db.execute(
                "SELECT * FROM tier5_budget_runs WHERE key_digest = ?", (key_digest,)
            ).fetchone()
            if existing:
                if existing["fingerprint"] != fingerprint:
                    raise BudgetConflictError("idempotency key conflicts with an existing run")
                return self._row(existing)

            used = db.execute(
                "SELECT COALESCE(SUM(held_microusd + settled_microusd), 0) AS used "
                "FROM tier5_budget_runs WHERE utc_day = ? AND state IN "
                "('RESERVED', 'DISPATCHED', 'SETTLED', 'CONSUMED_UNKNOWN')",
                (day,),
            ).fetchone()["used"]
            remaining = self.daily_limit_microusd - int(used)
            # Required default policy ceiling: remaining minus a one-unit
            # safety buffer. This is the MAXIMUM this run may cost, not
            # the amount reserved -- see the docstring above.
            default_ceiling = remaining - MICROUSD_PER_USD
            policy_cap = (
                explicit_cap_microusd if explicit_cap_microusd is not None else default_ceiling
            )
            # An explicit cap is a caller-declared ceiling, not a grant --
            # it must never exceed what's actually left in the daily
            # budget, or a caller could reserve more than `remaining` by
            # simply passing a large explicit_cap_microusd.
            if policy_cap > remaining:
                policy_cap = remaining
            if policy_cap <= 0 or worst_case_microusd > policy_cap:
                raise BudgetInsufficientError("daily budget cannot cover the worst-case run")
            hold = worst_case_microusd
            db.execute(
                "INSERT INTO tier5_budget_runs "
                "(run_id, key_digest, fingerprint, utc_day, state, policy_cap_microusd, "
                "held_microusd, settled_microusd, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'RESERVED', ?, ?, 0, ?, ?)",
                (run_id, key_digest, fingerprint, day, policy_cap, hold, timestamp, timestamp),
            )
            row = db.execute(
                "SELECT * FROM tier5_budget_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            return self._row(row)

    def mark_dispatch(self, run_id: str, stage_name: str) -> None:
        """Commit the provider-dispatch marker before network I/O.

        Idempotent: a retried call with the same (run_id, stage_name) is a
        no-op on the marker (INSERT OR IGNORE), not an IntegrityError. The
        state transition only fires from RESERVED, so a run already
        SETTLED/RELEASED/CONSUMED_UNKNOWN can never be pulled back to
        DISPATCHED by a late or duplicate dispatch call. An unknown run_id
        (no matching row in tier5_budget_runs) fails the stage marker's
        foreign-key check -- OR IGNORE only suppresses uniqueness conflicts,
        not FK violations -- so that's translated to a BudgetError too.
        """
        with self._guarded_transaction() as db:
            try:
                db.execute(
                    "INSERT OR IGNORE INTO tier5_budget_stages "
                    "(run_id, stage_name, marker_at) VALUES (?, ?, ?)",
                    (run_id, stage_name, time.time()),
                )
            except sqlite3.IntegrityError as exc:
                raise BudgetError("cannot mark dispatch for an unknown budget run") from exc
            db.execute(
                "UPDATE tier5_budget_runs SET state = 'DISPATCHED', updated_at = ? "
                "WHERE run_id = ? AND state = 'RESERVED'",
                (time.time(), run_id),
            )

    def settle(
        self, run_id: str, *, verified_unused_microusd: int | None = None
    ) -> Reservation:
        """Settle conservatively; ambiguity consumes the complete hold."""
        with self._guarded_transaction() as db:
            row = db.execute(
                "SELECT * FROM tier5_budget_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if not row:
                raise BudgetError("budget run not found")
            if row["state"] in {"SETTLED", "RELEASED", "CONSUMED_UNKNOWN"}:
                return self._row(row)
            unused = verified_unused_microusd
            if unused is None or unused < 0 or unused > row["held_microusd"]:
                settled = row["held_microusd"]
            else:
                settled = row["held_microusd"] - unused
            db.execute(
                "UPDATE tier5_budget_runs SET state = 'SETTLED', held_microusd = 0, "
                "settled_microusd = ?, updated_at = ? WHERE run_id = ?",
                (settled, time.time(), run_id),
            )
            updated = db.execute(
                "SELECT * FROM tier5_budget_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            return self._row(updated)

    def release_pre_dispatch(self, run_id: str) -> Reservation:
        """Release only when no committed stage marker exists and the run
        is still RESERVED -- never a terminal state (SETTLED/CONSUMED_UNKNOWN)
        or already-RELEASED, which the state predicate on the UPDATE below
        enforces even under a race with settle()/mark_dispatch()."""
        with self._guarded_transaction() as db:
            existing = db.execute(
                "SELECT * FROM tier5_budget_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if not existing:
                raise BudgetError("budget run not found")
            if db.execute(
                "SELECT 1 FROM tier5_budget_stages WHERE run_id = ? LIMIT 1", (run_id,)
            ).fetchone():
                # Raising here, inside the `with db:` block and before any
                # commit, relies on sqlite3's connection context manager: it
                # rolls back the open transaction automatically on
                # exception (commits only on clean exit). No explicit
                # rollback call is needed or correct to add here.
                raise BudgetError("cannot release a run after dispatch was marked")
            cursor = db.execute(
                "UPDATE tier5_budget_runs SET state = 'RELEASED', held_microusd = 0, "
                "updated_at = ? WHERE run_id = ? AND state = 'RESERVED'",
                (time.time(), run_id),
            )
            if cursor.rowcount == 0:
                raise BudgetError(
                    f"cannot release {run_id!r}: not in RESERVED state "
                    f"(currently {existing['state']!r})"
                )
            row = db.execute(
                "SELECT * FROM tier5_budget_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            return self._row(row)

    def recover_expired(self, *, before: float) -> tuple[int, int]:
        """Release unmarked stale holds; consume marked stale runs."""
        with self._guarded_transaction() as db:
            unmarked = db.execute(
                "SELECT run_id FROM tier5_budget_runs WHERE state = 'RESERVED' AND updated_at < ? "
                "AND NOT EXISTS (SELECT 1 FROM tier5_budget_stages s WHERE s.run_id = tier5_budget_runs.run_id)",
                (before,),
            ).fetchall()
            marked = db.execute(
                "SELECT run_id FROM tier5_budget_runs WHERE state IN ('RESERVED', 'DISPATCHED') "
                "AND updated_at < ? AND EXISTS (SELECT 1 FROM tier5_budget_stages s WHERE s.run_id = tier5_budget_runs.run_id)",
                (before,),
            ).fetchall()
            for row in unmarked:
                db.execute(
                    "UPDATE tier5_budget_runs SET state = 'RELEASED', held_microusd = 0, updated_at = ? WHERE run_id = ?",
                    (time.time(), row["run_id"]),
                )
            for row in marked:
                db.execute(
                    "UPDATE tier5_budget_runs SET state = 'CONSUMED_UNKNOWN', settled_microusd = held_microusd, held_microusd = 0, updated_at = ? WHERE run_id = ?",
                    (time.time(), row["run_id"]),
                )
            return len(unmarked), len(marked)
