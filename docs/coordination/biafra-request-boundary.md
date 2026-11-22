# Biafra provider request boundary

This source candidate continues PT #516 and the paired Orama #519 contents.
It does not enable serving, arm a live cycle, attest an account or authorize
publication. PT remains the sole owner of spending state.

## Admission and migration

The generic OpenAI-compatible path refuses W&B endpoint identities before SDK
construction. Callers must explicitly choose the guarded W&B provider. URL
identity is parsed through PT's canonical endpoint policy, not a second parser.
Unrelated valid OpenAI-compatible endpoints remain supported; credential-bearing
or malformed custom URLs fail closed.

The guarded provider reserves once in the parent. A private stdin pipe delivers
the request to `src/perpetua_tools/wandb_worker.py`; credentials are absent from
arguments and returned errors. Only JSON with closed outcome variants crosses
back. No response pickle, worker-owned ledger or extra admission engine exists.

| Outcome | Accounting |
| --- | --- |
| Worker cannot start or reports SDK startup before dispatch | Release the unsent reservation |
| Provider gives a definitive refusal below HTTP 500 | Release; 402/429 stop without retry |
| Successful answer | Settle content and billed completion-token accounting |
| Timeout, crash, invalid result or uncertain post-dispatch failure | Settle full reservation as unknown |
| Settlement fails after a paid answer | Preserve answer and attempt conservative unknown settlement |

The worker disables SDK retries. A monotonic deadline covers worker startup
and communication; after expiration the parent immediately kills the worker,
reaps with bounded waits and closes all pipes. OS process creation cannot be
preempted by this Python mechanism, and cleanup adds bounded wall time after
execution stops. This is not a hard real-time guarantee. The reservation keeps
its margin. Optional Weave initialization remains inside the timed child.

Existing budget SQLite and legacy migration semantics are unchanged. Rollback
must not restore stale spending state or resurrect expired reservations. New
worker code belongs under `src`; existing harness edits retain their established
legacy entrypoint rather than introducing a new root runtime package.

## Evidence and remaining gates

Offline regressions exercise routing refusal, strict worker outcomes, real local
child timeout/crash, unsent startup, settlement, interruption and resource cleanup.
Old SDK mocks must be replaced at the subprocess boundary: a parent-side mock
does not constrain a separately started interpreter. Tests must not inherit
operator credentials or contact the provider.

The paired Orama implementation owns metric validation, evaluator pin and
same-day provider-evidence checks. Operator persona and route decisions, real
account billing state, native platform qualification and live activation remain
separate. Final integrated test results and publication state are recorded in
the execution handoff, not inferred from earlier PR descriptions.

## November 20 publication and deferred debt

The user released the earlier publication hold for the existing PT #516 and
Orama #519, with one push per repository and no merge instruction. Publish PT
first, then pin its actual remote head in Orama before the Orama push.

The canonical deferred-debt inventory is in the paired Orama PR:
`docs/v2/references/biafra/unrelated-failure-catalogue-2026-11-20.md`.
It enumerates seven unchanged-base Orama failures (three TLS trust-isolation
assertions and four POSIX process-containment assertions), resolved setup issues,
historical-only reports and warning debt. The recorded PT full run passed 3700
tests with 12 skips and 15 warnings; this is earlier run evidence, not a fresh
full suite on the November 20 publication commit. Neither failures nor native
qualification gates are waived by publication.
