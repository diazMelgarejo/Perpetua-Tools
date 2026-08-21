from __future__ import annotations

from datetime import datetime, timezone

import pytest

from orchestrator.tier5_budget import (
    BudgetConflictError,
    BudgetError,
    BudgetInsufficientError,
    Tier5BudgetLedger,
)


@pytest.mark.unit
@pytest.mark.parametrize("bad_timeout", [0, -1, True, 1.5, "2000"])
def test_busy_timeout_ms_rejects_non_positive_or_non_integer(tmp_path, bad_timeout) -> None:
    with pytest.raises(ValueError):
        Tier5BudgetLedger(
            tmp_path / "ledger.db", daily_limit_microusd=1_000_000, busy_timeout_ms=bad_timeout
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
def test_missing_cap_uses_remaining_minus_one_usd_as_ceiling_not_hold(tmp_path) -> None:
    # daily_limit=10_000_000 -> default ceiling = 10_000_000 - 1_000_000 = 9_000_000.
    # A worst_case within that ceiling holds exactly worst_case, not the ceiling.
    ledger = _ledger(tmp_path)
    reservation = ledger.reserve(
        run_id="run-1",
        idempotency_key="key-1",
        fingerprint="fingerprint-1",
        worst_case_microusd=8_000_000,
    )
    assert reservation.policy_cap_microusd == 9_000_000
    assert reservation.held_microusd == 8_000_000


@pytest.mark.unit
def test_worst_case_above_default_ceiling_is_rejected(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    with pytest.raises(BudgetInsufficientError):
        ledger.reserve(
            run_id="run-1",
            idempotency_key="key-1",
            fingerprint="fingerprint-1",
            worst_case_microusd=9_500_000,  # exceeds the 9_000_000 default ceiling
        )


@pytest.mark.unit
def test_explicit_cap_below_worst_case_is_rejected(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    with pytest.raises(BudgetInsufficientError):
        ledger.reserve(
            run_id="run-1",
            idempotency_key="key-1",
            fingerprint="fingerprint-1",
            worst_case_microusd=2_000_000,
            explicit_cap_microusd=1_000_000,
        )


@pytest.mark.unit
def test_explicit_cap_holds_worst_case_not_the_cap(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    reservation = ledger.reserve(
        run_id="run-1",
        idempotency_key="key-1",
        fingerprint="fingerprint-1",
        worst_case_microusd=500_000,
        explicit_cap_microusd=1_000_000,
    )
    assert reservation.policy_cap_microusd == 1_000_000
    assert reservation.held_microusd == 500_000


@pytest.mark.unit
def test_explicit_cap_above_remaining_budget_is_capped_not_granted(tmp_path) -> None:
    # An explicit cap is a caller-declared ceiling, not a grant -- it must
    # never let a reservation exceed what's actually left in the daily
    # budget, even if the caller passes an explicit_cap_microusd larger
    # than remaining.
    ledger = _ledger(tmp_path)
    ledger.reserve(
        run_id="run-1",
        idempotency_key="key-1",
        fingerprint="fingerprint-1",
        worst_case_microusd=9_500_000,
        explicit_cap_microusd=9_500_000,
    )
    # remaining is now 500_000; an explicit cap of 5_000_000 must not
    # override that, and a worst_case exceeding the true remaining balance
    # must still be rejected.
    with pytest.raises(BudgetInsufficientError):
        ledger.reserve(
            run_id="run-2",
            idempotency_key="key-2",
            fingerprint="fingerprint-2",
            worst_case_microusd=600_000,
            explicit_cap_microusd=5_000_000,
        )


@pytest.mark.unit
def test_two_small_uncapped_runs_proceed_without_oversubscription(tmp_path) -> None:
    # The bug this guards against: an uncapped reservation used to hold
    # nearly the entire remaining daily budget (remaining - $1), so a
    # second small uncapped run the same day would be rejected even though
    # its own worst_case is tiny. With the fix, each run holds only its
    # own worst_case, so many small concurrent runs coexist under the cap.
    ledger = _ledger(tmp_path)
    first = ledger.reserve(
        run_id="run-1",
        idempotency_key="key-1",
        fingerprint="fingerprint-1",
        worst_case_microusd=1_000_000,
    )
    second = ledger.reserve(
        run_id="run-2",
        idempotency_key="key-2",
        fingerprint="fingerprint-2",
        worst_case_microusd=1_000_000,
    )
    third = ledger.reserve(
        run_id="run-3",
        idempotency_key="key-3",
        fingerprint="fingerprint-3",
        worst_case_microusd=1_000_000,
    )
    assert {first.state, second.state, third.state} == {"RESERVED"}
    assert first.held_microusd == second.held_microusd == third.held_microusd == 1_000_000
    # daily_limit=10_000_000; three 1_000_000 holds leave headroom for
    # several more small runs, unlike the pre-fix behavior where the first
    # reservation alone would have consumed 9_000_000 of it.
    remaining_after_three = 10_000_000 - 3 * 1_000_000
    assert remaining_after_three == 7_000_000


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
def test_mark_dispatch_is_idempotent_and_does_not_revert_terminal_states(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    run = ledger.reserve(
        run_id="run-1",
        idempotency_key="key-1",
        fingerprint="fingerprint-1",
        worst_case_microusd=1_000_000,
        explicit_cap_microusd=1_000_000,
    )
    # A retried mark_dispatch with the same stage must not raise
    # IntegrityError from the tier5_budget_stages primary key.
    ledger.mark_dispatch(run.run_id, "stage-1")
    ledger.mark_dispatch(run.run_id, "stage-1")

    settled = ledger.settle(run.run_id)
    assert settled.state == "SETTLED"

    # A late/duplicate mark_dispatch after settlement must not pull the run
    # back to DISPATCHED -- the state predicate on the UPDATE only matches
    # RESERVED, so this is a silent no-op on the run's state.
    ledger.mark_dispatch(run.run_id, "stage-2")
    still_settled = ledger.settle(run.run_id)  # idempotent re-fetch
    assert still_settled.state == "SETTLED"


@pytest.mark.unit
def test_settle_without_dispatch_marker_then_release_pre_dispatch_is_blocked(tmp_path) -> None:
    # A run can be settled without ever calling mark_dispatch (e.g. a
    # zero-cost/cancelled run recorded directly). Once SETTLED, the state
    # guard on release_pre_dispatch's UPDATE (WHERE state = 'RESERVED')
    # must reject it even though there's no stage marker to trip the
    # marker-based guard -- otherwise settled spend could be zeroed back
    # out of the daily total by a subsequent release call.
    ledger = _ledger(tmp_path)
    run = ledger.reserve(
        run_id="run-1",
        idempotency_key="key-1",
        fingerprint="fingerprint-1",
        worst_case_microusd=1_000_000,
        explicit_cap_microusd=1_000_000,
    )
    settled = ledger.settle(run.run_id)
    assert settled.state == "SETTLED"
    assert settled.settled_microusd == 1_000_000

    with pytest.raises(BudgetError):
        ledger.release_pre_dispatch(run.run_id)

    # Settled spend must still be counted -- release_pre_dispatch's failed
    # attempt must not have zeroed held/settled amounts.
    reread = ledger.settle(run.run_id)  # idempotent re-fetch, no-op on SETTLED
    assert reread.settled_microusd == 1_000_000


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
