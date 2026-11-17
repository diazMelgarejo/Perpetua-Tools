# PT spend gate

PT owns spend admission and accounting for paid provider requests. One module,
`orchestrator/spend_gate.py`, composes the provider policy (`orchestrator/provider_limits.py`:
operator attestation, upper-bound projection, size-only audit) with the shared budget
(`orchestrator/cost_guard.py`). Callers in other repositories forward to it; they keep no ledger.

## Lifecycle

`SpendGate(provider="wandb-inference", state_dir=None, now=None)`

- `preflight(prompt_chars, hold_seconds)` refuses with `attestation-required` or
  `budget-exhausted` before anything is reserved, or reserves the projected cost for
  `hold_seconds`. Declare a hold that covers the request's whole allowed lifetime, timeout
  included.
- Then exactly one of: `settle(...)` (answer received, estimated cost), `settle_unknown(...)`
  (the request may have been sent but has no usable answer: the full reservation is charged and
  the audit row records output as unknown) or `release(...)` (nothing was sent; idempotent).
- The estimate is not billing; the provider's Billing page is.

## The shared ledger

`CostGuard` keeps settled spend and live reservations in one private SQLite store beside the
budget file (`<budget file stem>.sqlite3`). Every instance and process that uses the same state
directory and budget file shares it. `reserve()` checks and records its hold inside one
`BEGIN IMMEDIATE` transaction, so two callers cannot both reserve the last dollars. The store is
opened through `orchestrator/private_sqlite.py` (the same checks the dispatch claim ledger uses)
and fails closed: an unsafe or unwritable directory raises instead of falling back to a
per-process budget.

- A reservation is swept only after its own declared hold (`reserve(cost, hold_seconds=None)`,
  default 300 s, at most 24 h).
- A commit for a swept reservation still records its spend and returns `late_commit: True`;
  accounting is never dropped.
- Rollback of an unknown or swept id still raises `UnknownReservationError`; `release()` hides it.

## Contract migration record

- Persistence: new `<budget file stem>.sqlite3`. An existing budget JSON is imported once, when
  the store is first created, and is never written again; a malformed one fails closed.
- Contract: `reserve(..., hold_seconds=None)`, `commit()` results gain `committed_usd` and
  `late_commit`, `in_flight()` and the `*_sync` methods are added. `snapshot()` is unchanged.
- Callers: `orchestrator/fastapi_app.py` (unchanged API), `.agent/harness/llm.py` W&B path (now
  through `SpendGate`), orama's `bin/agents/spend_guard.py` (to become a thin forwarder).
- Transport: same-user processes sharing a state directory. Not a network service.
- Lifecycle: holds default to 300 s; the harness declares its client timeout plus 300 s.
- Rollback: revert the commits. The legacy JSON is untouched, but spend recorded after the
  migration lives only in the SQLite store and must be copied back by hand.
