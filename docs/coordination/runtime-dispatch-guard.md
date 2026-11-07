# PT runtime dispatch guard

PT owns the pre-effect authority in `orchestrator/dispatch_guard.py`. Atlas's SOUL
is navigation and stewardship, not executable authorization. The supervisor and
the PT/Orama spawn adapters consult this guard before provider effects.

## Contract

- Reuse the canonical frugality gate and model-governance planner; do not invent a
  second natural-language policy engine from VISION or persona text.
- Ordinary allowed work needs no operator approval. A configured approval
  requirement needs a trusted verifier returning exactly `True`; task metadata,
  role text and an operator's general adoption statement are not approval proofs.
- A committed SQLite unique claim precedes the effect. Parallel processes sharing
  the same private state directory cannot start the same exact envelope twice.
- `started`, `succeeded` and `unknown` claims remain reserved. Exceptions, failed
  acknowledgements and cancellation cannot prove that the provider did no work.
  There is no expiry, automatic retry release or maintenance daemon.
- Identity is exact, not semantic. Random job/session IDs do not make duplicate
  work new. The default scope is stable for the repository. Intentional new work
  uses an explicit `scope=` in the Python spawn API or supervisor
  `metadata.dispatch_scope`, after reconciling an earlier unknown outcome.
- The ledger stores fingerprints and outcome states, not task prompts or tokens.

`DispatchPolicy` and the approval verifier are trusted supervisor constructor
configuration, not task payload fields. Standalone CLI processes use canonical
default checks; they do not inherit a separately configured supervisor callback.
Do not describe a custom in-process policy as a fleet-wide policy registry.

## Operational boundaries

Every cooperating process must use the same trusted `PT_STATE_DIR`. Independent
directories are independent authorities. Do not delete a ledger to retry work.
Restrict its parent directories to trusted users. POSIX validates ownership,
permissions, symlinks and file identity; Windows uses PT's existing private ACL
helper. SQLite reopens by pathname, so this is not a handle-relative filesystem
sandbox or protection against a hostile same-user process. Native Windows ACL
qualification remains a separate gate.

An implicit provider CLI model remains `provider-default`, not an attested model
selection. Unclassified model tiers retain the existing frugality gate's
no-opinion behavior. Unsupported explicit CLI model/effort/fast overrides are
rejected before any claim or effect; recording an ignored override would give
the same effect multiple identities. These bounds must remain visible in rollout
decisions.

## Verification and rollout

Regression entry points are `tests/test_dispatch_guard.py`,
`tests/test_spawn_dispatch_guard.py`, `tests/test_supervisor_smoke.py`, and Orama's
`tests/test_spawn_dispatch_governance.py` / `tests/test_dispatch_race.py`.
They use isolated state and mocked provider effects. Never validate the guard by
silently launching paid agents or modifying a serving deployment.

This source change does not activate grant serving, qualify a Windows host,
approve a deployment pin, release retained compatibility shims, or authorize
automatic reconciliation. Keep those decisions and receipts separate.
