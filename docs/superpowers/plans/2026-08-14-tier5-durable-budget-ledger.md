# Tier-5 Durable Budget Ledger Plan

**Goal:** Prevent any Tier-5 paid provider request unless an atomic, durable reservation
already exists, then settle only from normalized, verified usage.

**Architecture:** Keep the frugality gate and legacy `CostGuard` unchanged for their
existing callers. Add a Tier-5-only SQLite ledger and execution service. The service
reserves before the runner can dispatch, records a committed dispatch marker immediately
before each provider request, and applies conservative settlement after the run.

**Scope:** This plan replaces the current best-effort `cost_reservation_usd` check in
`orchestrator/fastapi_app.py` for Tier-5 only. `PIPELINE_TIERED_ENABLED=1` remains an
explicit opt-in throughout.

## Locked Decisions

| Concern | Decision |
| --- | --- |
| Money representation | SQLite `INTEGER` micro-USD only. `MICROUSD_PER_USD` is a unit conversion, not a budget ceiling. |
| Daily budget | `PT_TIER5_DAILY_LIMIT_MICROUSD` is a required positive external value, measured in UTC calendar days. |
| Missing or null cap | Hold `remaining_microusd - MICROUSD_PER_USD`. Fail closed if that is non-positive or below the calculated worst case. |
| Explicit cap | Positive integer only; reject boolean, float, zero, negative, and values below worst-case cost. |
| Idempotency key | Canonical UUIDv4 in `Idempotency-Key`; persist SHA-256 digest only. |
| Request identity | HMAC a canonical JSON fingerprint of recipe, prompt bytes, and policy-affecting request fields. Persist the digest only. |
| Same key and fingerprint | Return the stored non-sensitive run state and never dispatch again. |
| Same key, different fingerprint | Return HTTP 409 and never alter the original reservation. |
| Dispatches | A provider request has exactly one attempt. Persist `DISPATCH_STARTED` immediately before its HTTP call. |
| Settlement | Release only a confirmed pre-dispatch failure or a verified unused difference. Any ambiguity after a marker consumes the held amount. |
| Recovery | Expired `RESERVED` rows may release only when no stage marker exists. Expired marked rows become `CONSUMED_UNKNOWN`. |

## Current Gap

`TieredPipelineRunner` uses floating `cost_reservation_usd`; the API checks and records
it in separate `CostGuard` calls. `ProviderTransportRegistry._post()` may retry. Neither
the request nor partial stage usage has a durable, atomic lifecycle. These are the only
behaviors this implementation must replace for Tier-5.

## Task 1: Establish Contracts And Integer Pricing

**Files:** create `orchestrator/tier5_contracts.py`; modify
`orchestrator/model_registry.py`, `orchestrator/tiered_pipeline.py`,
`config/models.yml`, `config/pipelines.yml`; update
`tests/test_tiered_pipeline.py`, `tests/test_tiered_pipeline_config.py`.

1. Write failing tests for null caps, invalid explicit caps, and integer worst-case
   calculation across every configured stage.
2. Add frozen `ModelPricing`, `ProviderUsage`, `PreparedProviderCall`, and
   `ProviderDispatchResult` contracts. Pricing requires positive integer input/output
   rates per million tokens, an official HTTPS source URL, and ISO verification date.
3. Replace `cost_reservation_usd` with `max_cost_microusd: int | None` and compute:

```python
def ceil_per_million(tokens: int, rate_microusd: int) -> int:
    return (tokens * rate_microusd + 999_999) // 1_000_000
```

1. Calculate worst case from recipe input bound plus each stage output bound. Keep a null
   config value null until reservation resolves `remaining - one USD`.
2. Verify with:

```bash
python3 -m pytest -q tests/test_tiered_pipeline.py tests/test_tiered_pipeline_config.py
```

## Task 2: Add The Atomic Reservation Ledger

**Files:** create `orchestrator/tier5_budget.py` and `tests/test_tier5_budget.py`.

1. Start RED with concurrent reservations, missing-cap fallback, duplicate key,
   conflicting fingerprint, pre-dispatch release, and stale marked-run recovery tests.
2. Create `tier5_budget_runs` and `tier5_budget_stages` with integer monetary/token
   columns, a unique idempotency-key digest, UTC day, state, held/settled amounts, and
   timestamps. Never store prompt, completion, headers, provider body, raw key, or HMAC
   secret.
3. In one `BEGIN IMMEDIATE` transaction: find existing key, compare fingerprint, compute
   remaining from held plus consumed spend, resolve cap, verify worst case, and insert the
   `RESERVED` row. Set WAL, foreign keys, and a bounded busy timeout on every connection.
4. Retry lock acquisition with bounded delay; return a typed unavailable error when it
   exhausts rather than running without a hold.
5. Verify one competing reservation fails and only unmarked stale rows release:

```bash
python3 -m pytest -q tests/test_tier5_budget.py
```

## Task 3: Split Provider Preparation From One-Shot Dispatch

**Files:** modify `orchestrator/model_transport.py` and
`tests/test_model_transport.py`.

1. Write failing tests that `prepare()` performs no I/O, `execute()` makes one HTTP
   request, and BigModel/OpenAI-compatible plus Anthropic payloads normalize token usage
   and provider request IDs without retaining bodies.
2. Make provider configuration reject Tier-5 `max_attempts` other than exactly one.
   Existing retry behavior remains only for non-Tier-5 callers, if any.
3. Implement `prepare()` to resolve model, provenance, credential, allowed endpoint, and
   redacted payload. Implement `execute()` as one request and return:

```python
@dataclass(frozen=True)
class ProviderDispatchResult:
    text: str
    provider: str
    model: str
    usage: ProviderUsage | None
    provider_request_id: str | None
```

1. Preserve legacy `dispatch()` as a compatibility wrapper returning `.text`.
2. Verify normalized usage, malformed usage, HTTP failure, timeout, and no-retry paths:

```bash
python3 -m pytest -q tests/test_model_transport.py
```

## Task 4: Orchestrate Markers And Conservative Settlement

**Files:** create `orchestrator/tier5_execution.py` and
`tests/test_tier5_execution.py`; modify `orchestrator/tiered_pipeline.py` and its tests.

1. Write RED tests proving a missing credential releases a new hold, a timeout after a
   marker consumes the full hold, a partial pipeline consumes when any marked stage is
   unresolved, and verified success releases only the unused difference.
2. Add runner callbacks for prepare, `before_paid_dispatch`, execute, and stage result.
   The service reserves before `run()`, calls `prepare()`, commits the stage marker, then
   invokes `execute()` exactly once.
3. Convert verified token usage to exact integer micro-USD. A successful response with
   absent or invalid usage is not proven unused and therefore consumes the held amount.
4. HMAC the request fingerprint using required local
   `PT_TIER5_LEDGER_HMAC_KEY`; reject missing or empty secrets before any reservation.
5. Verify ordering with a spy that proves the committed marker precedes provider I/O:

```bash
python3 -m pytest -q tests/test_tier5_execution.py tests/test_tiered_pipeline.py
```

## Task 5: Replace The Authenticated API Boundary

**Files:** modify `orchestrator/fastapi_app.py` and
`tests/test_tiered_pipeline_endpoint.py`.

1. Write endpoint tests for missing/non-v4 key (422), same-key replay (non-dispatching
   status response), same-key conflict (409), insufficient funds (402), ledger lock
   exhaustion (503), and unchanged control-plane authentication.
2. Add ledger/service dependencies that parse only the two local environment values.
   Configuration errors are redacted and never returned as secrets.
3. Replace direct `CostGuard.can_spend()` and `record_spend()` calls. The run endpoint
   returns current run metadata; the status endpoint exposes only run ID, recipe, state,
   held amount, and settled amount, never output or sensitive digests.
4. Translate typed errors consistently and retain the opt-in feature flag.
5. Verify:

```bash
python3 -m pytest -q tests/test_tiered_pipeline_endpoint.py tests/test_tier5_execution.py
```

## Task 6: Enforce Evidence And Close The Gate

**Files:** modify `scripts/check_model_ids.py`, Tier-5 config tests, and
`docs/next/2026-08-14-operational-work-disposition.md` only after evidence exists.

1. Reject Tier-5 model entries that lack valid immutable pricing evidence.
2. Add a recovery command or startup check that changes stale marked rows to
   `CONSUMED_UNKNOWN` before accepting a new run.
3. Run final verification:

```bash
python3 -m pytest -q tests/test_tier5_budget.py tests/test_tier5_execution.py \
  tests/test_tiered_pipeline.py tests/test_tiered_pipeline_config.py \
  tests/test_tiered_pipeline_endpoint.py tests/test_model_transport.py
python3 scripts/check_model_ids.py
python3 scripts/review/repo_hygiene.py .
git diff --check origin/main...HEAD
```

1. Update the operational disposition with only verified results. Do not enable shared
   paid execution until all checks pass and a separate review approves the ledger.

## Commit Order

1. `feat(tier5): add atomic budget reservation ledger`
2. `feat(tier5): normalize one-shot provider usage`
3. `feat(tier5): settle reservations conservatively`
4. `feat(tier5): require idempotent durable budget holds`
5. `docs(tier5): record verified accounting evidence`

## Plan Review

The plan has one authority for money and lifecycle state, one explicit pre-dispatch
marker, no implicit paid retries, and no default total budget. It releases only when
non-dispatch or unused amount is proven. It also makes duplicate delivery safe without
pretending a different request is the same operation.
