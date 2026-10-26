# Release 1–2 serving/effects qualification handoff

**Status:** draft-groundwork only; this handoff neither activates serving nor authorizes a T3 effect.
**Scope:** additive continuation note for PT PR #465. It introduces no v2 runtime dependency into PT.

## Current verified state

- Oramasys Release 1–2 groundwork provides data-free liveness and fail-closed composition readiness.
- Its inert effect driver is restricted to a durable `inert://simulation` proposal destination and a consumed reservation. It cannot settle a real effect destination; a crash after its send marker remains `unknown` and a retry is refused.
- Focused validation passed 87 tests; the isolated Python 3.12 consumer suite passed 1,993 tests with 3 expected skips.

## Non-negotiable qualification gates still open

Releases 1–2 are **not yet fully qualified**. The following remain explicit draft gates:

1. **Trusted effect-grant composition:** the reviewed production adapter must construct the typed verified grant/attempt binding. A plain value object, fixture, or test lookup is not proof of trusted provenance.
2. **Final-boundary authorization:** approval, grant validity, revocation/cascade facts, expiry, principal, scope, reservation, and fencing must be rechecked at the actual dispatch boundary.
3. **Isolation evidence:** serving identity must be demonstrably seed-free and unable to write issuer state; verifier-only composition needs its real process/access proof.
4. **Subprocess crash qualification:** prove every durable boundary, including the window after the send marker and before settlement, in fresh processes. Unknown outcomes are retained and never automatically retried.

## Operator and agent boundaries

- Do not set `ORAMA_GRANT_SERVING`, issue grants, send a provider request, or expose an effect-dispatch route on the basis of this groundwork.
- Do not describe the inert simulation receipt as evidence that an external effect happened.
- Candidate qualification and post-merge qualification must run at the exact final producer/consumer pins. A green earlier head is historical evidence only.
- PT remains a portable v1 memory consumer. This note records cross-repository state; it does not import or depend on Oramasys runtime code.

## Next implementation slice

Build the trusted composition adapter with red/green tests that prove its inputs are verified, bind it to the final dispatch boundary, and then run the process-isolation and subprocess crash matrix. Publish a dated successor receipt only after both candidate and actual merged pins pass.

