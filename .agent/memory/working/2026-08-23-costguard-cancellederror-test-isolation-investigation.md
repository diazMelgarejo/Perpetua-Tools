# CostGuard CancelledError regression test: cross-file leak investigation (2026-08-23)

**Status:** Production fix landed and verified. Permanent regression test NOT landed — do not re-attempt the same approach.

## What happened

CodeRabbit review on PT PR #362 flagged: `except Exception` in
`orchestrator/fastapi_app.py`'s `/orchestrate` handler does not catch
`asyncio.CancelledError` (derives from `BaseException`), so a client
disconnect during `await _resolve_candidates(...)` leaks the CostGuard
reservation permanently.

**Fix** (commit `ce1e885f`): replaced `except Exception: rollback(); raise`
with `try/finally` + a `committed` flag — `finally` runs for any unwind,
including `CancelledError`. Also added `RESERVATION_TTL_SECONDS` self-healing
as defense-in-depth. This fix is solid: RED-GREEN verified interactively via
`git stash push --keep-index` against pre-fix code — the leak reproduced
exactly as described pre-fix, and was gone post-fix.

**The problem**: a permanent automated regression test for this exact path
(`TestOrchestrateEndpointCancellation`, added alongside the fix) corrupted
`tests/test_orama_integration.py`'s routing assertions whenever both files ran
in the same pytest session — `test_orama_integration.py` started selecting
`bigmodel` instead of `ultrathink` after the new test ran first.

## What was tried (all failed to isolate it)

1. Bare `await fastapi_app.orchestrate(req)` call, no `TestClient`, no
   lifespan touched at all. **Still leaked.** This rules out
   lifespan-triggered background tasks as the *sole* cause.
2. `TestClient(fastapi_app.app)` with zero extra mocks. **Still leaked.**
3. Attempt 2 + mocking `resolve_routing_state` to match
   `test_orama_integration.py`'s own `client` fixture exactly (same fake
   routing payload). **Still leaked.**
4. Attempt 3 + also mocking `sync_ecc_tools` (a real git pull was observed
   running unmocked in one repro — `"[ECC Sync] Pulling latest ECC
   Tools..."` in captured stderr). **Still leaked.**

Also tried an ad-hoc bisection script (import `fastapi_app` + monkeypatch +
undo, then invoke `pytest.main()` from inside a `python3 -c` one-liner) to
narrow the cause faster — this produced a real ECC-sync side effect too, but
the script's own non-standard import order makes it unreliable as evidence
(it doesn't mirror how pytest actually collects/imports test modules).

**The actual mechanism was never conclusively identified.** ~40 minutes spent
before cutting losses.

## What shipped instead

- Removed `TestOrchestrateEndpointCancellation` entirely (commit `1dea3885`).
- Left a code comment in `tests/test_cost_guard.py` documenting the gap
  (not a silent drop).
- Kept all other CostGuard coverage: `TestReservationTTLSelfHeal` and
  `TestAtomicReserveCommitRollback` (input validation, TTL sweep) are
  unaffected and remain in place — 46/46 `test_cost_guard.py` +
  `test_orama_integration.py` green together after removal.

## For next time — do NOT repeat "mock one more thing"

That approach was tried 4 times with escalating mock coverage and never
worked. A genuinely different strategy is needed:

- **(a) Don't touch the real singleton at all.** Build a minimal, isolated
  Starlette/FastAPI app in the test itself that only mounts the one route
  under test, wired to a throwaway `CostGuard`/registry/tracker — never
  import or touch `fastapi_app.app`/`fastapi_app.registry`/
  `fastapi_app.tracker` module-level objects.
- **(b) Process isolation.** Run this one test in its own subprocess (or via
  `pytest-xdist` with `--dist=loadscope` pinning it to its own worker) so
  whatever it dirties never coexists in-process with
  `test_orama_integration.py`.
- **(c) Actually instrument the diff**, don't guess. Snapshot
  `sys.modules`, `fastapi_app.registry.__dict__`,
  `fastapi_app.tracker.__dict__`, `os.environ`, and any `.state/*.json`
  file mtimes/contents immediately before and after the suspect test, diff
  them, and find the ACTUAL delta instead of hypothesizing which known
  side-effect function might be responsible.

## Cross-reference

Generalized lesson: [[lesson_d58f0f64b208]] (episodic + semantic, PT
`.agent/memory`). Production fix commits: `ce1e885f` (fix + first test
attempt), `1dea3885` (test removal + this doc). PT PR #362.
