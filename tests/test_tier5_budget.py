from __future__ import annotations

from datetime import datetime, timezone

import pytest

from orchestrator.tier5_budget import (
    BudgetConflictError,
    BudgetError,
    BudgetInsufficientError,
    Tier5BudgetLedger,
)


def _ledger(tmp_path):
    return Tier5BudgetLedger(tmp_path / "ledger.db", daily_limit_microusd=10_000_000)


@pytest.mark.unit
def test_reservation_is_atomic_and_same_key_is_idempotent(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    first = ledger.reserve(
        run_id="run-1",
        idempotency_key="key-1",
        fingerprint="fingerprint-1",
        worst_case_microusd=2_000_000,
        now=datetime(2026, 8, 20, tzinfo=timezone.utc),
    )
    replay = ledger.reserve(
        run_id="different-run",
        idempotency_key="key-1",
        fingerprint="fingerprint-1",
        worst_case_microusd=2_000_000,
    )
    assert replay == first
    with pytest.raises(BudgetConflictError):
        ledger.reserve(
            run_id="run-2",
            idempotency_key="key-1",
            fingerprint="different",
            worst_case_microusd=2_000_000,
        )


@pytest.mark.unit
def test_missing_cap_uses_remaining_minus_one_usd(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    reservation = ledger.reserve(
        run_id="run-1",
        idempotency_key="key-1",
        fingerprint="fingerprint-1",
        worst_case_microusd=8_000_000,
    )
    assert reservation.held_microusd == 9_000_000


@pytest.mark.unit
def test_pre_dispatch_release_and_marked_settlement_are_conservative(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    released = ledger.reserve(
        run_id="run-1",
        idempotency_key="key-1",
        fingerprint="fingerprint-1",
        worst_case_microusd=1_000_000,
        explicit_cap_microusd=1_000_000,
    )
    assert ledger.release_pre_dispatch(released.run_id).state == "RELEASED"

    marked = ledger.reserve(
        run_id="run-2",
        idempotency_key="key-2",
        fingerprint="fingerprint-2",
        worst_case_microusd=1_000_000,
        explicit_cap_microusd=1_000_000,
    )
    ledger.mark_dispatch(marked.run_id, "stage-1")
    with pytest.raises(BudgetError):
        ledger.release_pre_dispatch(marked.run_id)
    settled = ledger.settle(marked.run_id)
    assert settled.state == "SETTLED"
    assert settled.settled_microusd == marked.held_microusd


@pytest.mark.unit
def test_stale_recovery_releases_only_unmarked_runs(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    unmarked = ledger.reserve(
        run_id="run-1",
        idempotency_key="key-1",
        fingerprint="fingerprint-1",
        worst_case_microusd=1_000_000,
        explicit_cap_microusd=1_000_000,
    )
    marked = ledger.reserve(
        run_id="run-2",
        idempotency_key="key-2",
        fingerprint="fingerprint-2",
        worst_case_microusd=1_000_000,
        explicit_cap_microusd=1_000_000,
    )
    ledger.mark_dispatch(marked.run_id, "stage-1")
    released, consumed = ledger.recover_expired(before=10**10)
    assert (released, consumed) == (1, 1)
    assert ledger.reserve(
        run_id="run-3",
        idempotency_key="key-3",
        fingerprint="fingerprint-3",
        worst_case_microusd=1_000_000,
    ).state == "RESERVED"


@pytest.mark.unit
def test_reservation_rejects_worst_case_above_available_budget(tmp_path) -> None:
    ledger = Tier5BudgetLedger(tmp_path / "ledger.db", daily_limit_microusd=2_000_000)
    with pytest.raises(BudgetInsufficientError):
        ledger.reserve(
            run_id="run-1",
            idempotency_key="key-1",
            fingerprint="fingerprint-1",
            worst_case_microusd=2_000_000,
        )
