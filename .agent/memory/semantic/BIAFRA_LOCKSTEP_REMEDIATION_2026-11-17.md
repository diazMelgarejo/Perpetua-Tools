# Biafra lockstep remediation: decisions, changes and later TODOs (2026-11-17)

Author/actor: Claude Code, self-reported. Scope is Perpetua-Tools (PT, producer and runtime/state
authority) pull request [516](https://github.com/diazMelgarejo/Perpetua-Tools/pull/516) and
orama-system (consumer, stateless) pull request
[519](https://github.com/diazMelgarejo/orama-system/pull/519), both on branch
`2026-11-17-001-biafra-seat-canonical`. Both pull requests are OPEN and were NOT merged. The
operator believed them merged, but their heads were still the reviewed `c90feebb` (PT) and
`bd5931a2` (orama). No merge was made. Items 11 to 15 below are decided and in progress, not
verified.

## Inputs

- Lockstep review "2026-11-17 Restack Review" of PT #516 at `c90feebb` and orama #519 at
  `bd5931a2`: verdict request changes, seven findings (P1: 1 and 2; P2: 3 to 7), with G3 and G9
  called out as open design gaps.
- Saved method: `REMEDIATION_FLOW_AND_AGY_PARALLEL_2026-11-02.md` (working) and
  `REVIEW_REMEDIATION_CONVERGENCE_2026-08-27_TO_2026-08-29.md` (semantic): collect once, fix the
  owning abstraction once, failing-first tests, docstrings 100%, push once per pull request, reply
  with the fixing SHA, never merge without an explicit instruction.
- Execution: isolated lane worktrees, one subagent per lane, integrator verification of every
  report, and an independent read-only reviewer per repository.

## Decisions and rationale

1. **G3, evaluator pin and receipt binding** (orama `bin/agents/seat_contracts.py`). The digest
   covers exactly the verifier files given to `evaluator_digest`, by file name and bytes.
   `pin_evaluator` writes a one-time pin file at run start (atomic exclusive create via a temp
   file and `os.link`); re-pinning succeeds only for the same digest and covers, otherwise
   "evaluator changed". `read_pin` validates the shape.
   `validate_mechanism_card(card, pinned_digest=None)`: a reviewed or graduated card needs a
   dry-run receipt `trace` that validates and carries the card's digest; a graduated card needs
   `pinned_digest` equal to the card's digest. This closes the three accepted cases in doc 76 G3
   (no trace, receipt digest differs, never pinned).
2. **G9, "no card, no promotion".** A mandatory input card on every cycle would break the real
   flow, because the outer dry run produces the receipt the card is built from. Cycles stay usable
   without a card. A cycle that validated a card adds `card_id = "<mechanism_id>@<revision>"`. A
   reviewed or graduated card needs a receipt with `card_checked: true` and its own `card_id`.
   Decided by the operator's request to resolve G9 in this change; reversible.
3. **One spend gate owned by PT** (findings 1 to 3). New `orchestrator/spend_gate.py` (SpendGate:
   `preflight(prompt_chars, hold_seconds)`, `settle`, `settle_unknown`, `release`, `classify`,
   `snapshot`; public `ProviderPolicyError`, `BudgetExceededError`, `UnknownReservationError`).
   `CostGuard` is now shared and atomic across instances and processes: one private SQLite store
   per budget file, every operation in `BEGIN IMMEDIATE`, with the private-file checks extracted
   from `dispatch_guard` into `orchestrator/private_sqlite.py`. Declared holds
   `reserve(cost, hold_seconds)`: a late commit for a swept reservation still records the spend
   (`late_commit`). A legacy budget JSON is imported once and renamed `<name>.migrated`; a missing
   store beside a `.migrated` file fails closed. Orama's `bin/agents/spend_guard.py` is now a thin
   forwarder with no ledger.
4. **Outcome mapping on the PT W&B path** (`.agent/harness/llm.py`). Refuse before dispatch on a
   missing or stale attestation or an exhausted budget (`create()` is never called). Success
   settles. An HTTP status below 500 is a definitive provider refusal and releases (an integrator
   amendment to the first design, which charged every HTTP error). A 5xx, transport error,
   timeout, interrupt or malformed response settles the full reservation (`settle_unknown`). If
   settling fails after a paid answer, the answer is kept and the charge falls back to
   `settle_unknown`.
5. **Orama live cycle** (`bin/agents/biafra_cycle.py`). Hold is `timeout_s + SETTLE_MARGIN_S`
   (120 s, chosen by the lane and recorded as a constant). The launcher starts with `Popen` and is
   awaited with `communicate`. Only a failed `Popen` releases. Any failure after start (timeout,
   pipe `OSError`, interrupt) kills and reaps the child and settles unknown. Output is decoded
   after the wait with `errors="replace"`.
6. **Sandbox cleanup** (`bin/agents/sandbox_run.py`). Never reap the leader before signalling the
   group. Cleanup is armed immediately after `Popen`. Exit probe order: `waitid`, then kqueue
   (`KQ_FILTER_PROC`, `KQ_NOTE_EXIT`, one kqueue per run, `ESRCH` means exited), then `/proc`,
   else fail closed (`SandboxUnavailable`). A per-poll `ps` probe was rejected for cost. CPython
   exposes `os.waitid` on macOS only from 3.13, so older macOS Pythons use kqueue.
7. **Memory correction** (finding 6). Additive linked records `lesson_d4ac6209ce38` (supersedes
   `lesson_762380426dc7`) and `lesson_7240bbe31030` (supersedes the original over-claim
   `lesson_15733a3316ad`). Accurate wording: a same-user process can write a valid attestation
   file; the guard checks the file's contents and age and cannot prove who wrote it; only the
   interactive `attest` command asks a human.
8. **Runbook** (finding 7). The attest command no longer shows `--confirm`; the operator types the
   phrase at the interactive prompt.
9. **Memory ships in PR #516, decided by the operator.** The operator ruled on 2026-11-17 to
   consolidate every change tonight, memory included, on the current pull requests and to open no
   new ones. The "memory on main only" guidance of accepted `lesson_94a6ff5363ae` was explicitly
   overridden for this consolidation; that lesson is not edited.
10. **Lockstep publish order.** Push PT once, set orama `.github/pt-dispatch-test-ref` to the
    pushed PT head, push orama once. No merges. Reply to the open PT thread with the fixing
    commit. Update PT #516's description, because it now changes runtime and budget code and not
    only docs.

### Orama independent review (request changes) and the fixes it led to (lane O6)

These are decided and being implemented; they are not yet verified.

11. A live-cycle abnormal exit kills the whole launcher process group. The launcher starts with
    `start_new_session=True`; on timeout, pipe error or interrupt the group is SIGKILLed before a
    bounded reap, so a grandchild holding the pipes cannot hang the cycle past `timeout_s`.
12. After `Popen` succeeds the request counts as sent: the `finally` never releases a sent
    reservation. If settling fails after send, the reservation is left to its declared hold and
    the error is surfaced, so a sent request is never recorded as zero spend.
13. Receipt binding also compares the card's `delta` with the receipt trace's
    `metric_after - metric_before` (with a tolerance for float rounding), so a receipt for `X@1`
    cannot promote a different card that reuses the id `X@1`.
14. `pin_evaluator` uses a unique temp file (`mkstemp` in the pin's directory), so concurrent
    pinning in one process cannot collide.
15. The sandbox checks that an exit probe exists before starting the child, so a platform with no
    probe fails closed before any model-written code runs.

## Changes per repository

- **PT.** `orchestrator/spend_gate.py` (new); `orchestrator/private_sqlite.py` (new, extracted
  from `dispatch_guard`); `CostGuard` rebuilt on one shared SQLite store with declared holds and a
  one-time legacy import; `.agent/harness/llm.py` routed through SpendGate; docs for the
  per-phase timeout, the fail-closed default, the legacy import and rollback; the additive memory
  records from decision 7; the runbook fix from decision 8.
- **orama.** `bin/agents/seat_contracts.py` (pin, receipt binding, `card_id`);
  `bin/agents/spend_guard.py` (thin forwarder); `bin/agents/biafra_cycle.py` (Popen lifecycle,
  hold, settle unknown); `bin/agents/sandbox_run.py` (group-first cleanup, exit probes); doc 76
  rows G3 and G9 move from Open to Resolved, with the metaresearcher skill and runbook updated.
  Files under `docs/v2/references/biafra/live-cycle-2026-11-17/harness/` were not touched.

## Verification so far

- PT integration (12 commits on `c90feebb`): full suite 3670 passed, 5 failed, 13 skipped at
  `23cdc03`; the same 5 fail at the base (the sandbox lacks Git state discovery). The independent
  PT review approved with no Critical or Important findings; its four Minor items were fixed or
  documented (settle fallback, `.migrated`, per-phase timeout documented, fail-closed default
  documented). A rerun at the final PT head is in progress.
- Orama integration (17 commits on `bd5931a2`): 421 passed, 18 skipped across the affected suites
  against the integrated PT. Docstrings are 100% on all touched files; docstring-only commits were
  proven by `ast.dump` equality with docstrings stripped. The independent orama review returned
  request changes (items 11 to 15). Those fixes are in progress and unverified.

## Behaviour changes operators must know

- CostGuard's default store fails closed when its directory or an ancestor fails the private-store
  checks (previously it degraded to an in-memory budget).
- Spend recorded after migration lives only in the SQLite store; reverting does not move it back.
- The 600 s openai client timeout is per HTTP phase, not a total deadline. A request can outlive
  the 900 s hold; the late commit still records the spend.

## Later TODO list (not done; owner decisions or follow-up work)

- Native macOS verification of the kqueue probe and the 18 macOS-only sandbox tests; Windows was
  not exercised.
- The live cycle reads no pin itself. Enforcing `read_pin` inside `live_cycle` before launch is a
  follow-up (graduation already requires the pin).
- `lesson_371473e17ad0` remains accepted as a redundant shorter correction (its supersedes field
  holds one id).
- Generic filler docstrings ("Test helper or fixture: ...") in older test helpers could be
  rewritten.
- A hard wall-clock deadline for the W&B request, instead of the per-phase timeout.
- `AGENT_PROVIDER=openai` with `OPENAI_BASE_URL` pointed at W&B bypasses the gate (operator
  environment); route or refuse it.
- Open doc 76 items are unchanged: G1 (Anamnesis ledger), G2 (Kungfu), G4 (stall window), G6
  (persona draft), G7 (re-probe provider state before arming), G8 (`_finite` integer precision),
  G10 (metric registry), G11 (Wanda soul card versus Cline W&B route). Tri-level stays off.
- Live gates and serving stay off; arming one bounded live cycle remains a separate operator act.
