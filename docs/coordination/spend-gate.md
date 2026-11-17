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
- The harness sets a 600 s openai client timeout. That timeout applies per HTTP phase (connect,
  write, read, pool), not as a total deadline, so a request can outlive the 900 s hold (600 s plus
  a 300 s margin). The hold is then swept, but the late `settle` or `settle_unknown` still
  records the spend (`late_commit`; audit `basis: late-commit`), so accounting is not dropped.
  Until it lands, the swept hold no longer counts against the budget.
- If `settle` itself fails after a paid answer, the harness still returns the answer, reports the
  accounting error on stderr and falls back to `settle_unknown`. That charges the full
  reservation when nothing was committed, and is a reported no-op when the commit already
  happened (for example a failed audit write).
- Then exactly one of: `settle(...)` (answer received, estimated cost), `settle_unknown(...)`
  (the request may have been sent but has no usable answer: the full reservation is charged and
  the audit row records output as unknown) or `release(...)` (nothing was sent; idempotent).
- The W&B harness maps outcomes as follows: an answer settles; an HTTP status below 500 is a
  definitive refusal before generation (402 allowance or cap, 429 rate limit, 400 invalid
  request), so it releases and records nothing; status 500 and above, transport errors,
  timeouts, interrupts and malformed responses may have been processed, so they call
  `settle_unknown`. 402 and 429 still raise `ProviderLimitStop`.
- Consumers catch `ProviderPolicyError`, `BudgetExceededError` and `UnknownReservationError`
  as public attributes of `spend_gate` (plus the builtin `PermissionError` for an unsafe store).
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

## Behaviour change: fail closed by default

The default `CostGuard()` in `orchestrator/fastapi_app.py` (state directory `./.state`) now
applies the private-store checks to `./.state` and every ancestor directory: real,
user-owned, not writable by others, symlinks only when trusted. Before, an unusable directory
degraded to a per-process in-memory budget, which silently broke the shared ceiling. Now the
first budget call (`/budget`, reserve, commit) raises and the endpoint returns an error. A
host whose working directory sits under a group- or world-writable ancestor must fix the
permissions or point the guard at a private state directory.

## Legacy budget import

The first open of a new store imports an existing budget JSON and, in the same transaction,
renames it to `<name>.migrated`. The import therefore cannot run twice. If the store is later
deleted while the `.migrated` file exists, opening fails closed with a `RuntimeError` naming
the file rather than starting from zero or importing again. To recover, restore the store; to
import the old figures on purpose, move the `.migrated` file back after reviewing it.

## Contract migration record

- Persistence: new `<budget file stem>.sqlite3`. An existing budget JSON is imported once, when
  the store is first created, then renamed to `<name>.migrated`; a malformed one fails closed.
- Contract: `reserve(..., hold_seconds=None)`, `commit()` results gain `committed_usd` and
  `late_commit`, `in_flight()` and the `*_sync` methods are added. `snapshot()` is unchanged.
- Callers: `orchestrator/fastapi_app.py` (unchanged API), `.agent/harness/llm.py` W&B path (now
  through `SpendGate`), orama's `bin/agents/spend_guard.py` (to become a thin forwarder).
- Transport: same-user processes sharing a state directory. Not a network service.
- Lifecycle: holds default to 300 s; the harness declares its client timeout plus 300 s.
- Rollback: revert the commits. The legacy JSON now sits at `<name>.migrated` (rename it back),
  and spend recorded after the migration lives only in the SQLite store and must be copied back
  by hand. The previous in-memory fallback returns with the revert, so the fail-closed checks
  above stop applying.
