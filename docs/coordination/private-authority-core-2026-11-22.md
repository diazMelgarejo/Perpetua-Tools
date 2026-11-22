# Private queue authority core — bounded candidate

This is an unactivated, nondeployable building block for the F slice, not the
V1-2 authority and not a migration or protected queue. Existing manual PT queue
operation remains unchanged. No service or caller routes to this core.

| Layer | Current candidate | Remaining work |
| --- | --- | --- |
| Persistence | Separate private SQLite file via PT's existing opener; requires POSIX and SQLite >=3.51.3; records the SQLite build. The core checks DELETE journal mode inside every locked transaction and refuses other modes. Task generation and version, audit, and redacted outbox changes commit together. | WAL/SHM, backup, recovery and actual service-interpreter qualification. Schema checking detects unknown table sets, not all same-name schema tampering. No existing-store import; unfamiliar stores refuse. |
| Contract | Local acquisition handle carries claim ID, generation, version and incarnation reference. Matching is under the write lock. | Authentication, error mapping, reservations, idempotent receipts, uncertainty policy, time high-water and safe recovery are not implemented. A handle is not worker authentication. |
| Callers | No existing writer or shim changed. | Inventory and route every writer; prevent old/direct writers; no service-down fallback. |
| Transport | No transport or publication. Outbox rows explicitly say non-authoritative and omit claim and incarnation. | Authority endpoint, freshness metadata, authenticated admission and real gossip projection delivery. |
| Lifecycle | Explicit local opening only; no worker, daemon or cleanup. Existing stores reopen with generation intact. | Durable import and legacy-unverified holds, singleton service, real process-death commit tests and restart/rollback rehearsal. |
| Operations | No activation or store migration; stop using the candidate by not opening it. | Review, POSIX and native Windows qualification and separately authorized cutover. A private file under the same OS user is not hostile-worker isolation. |

The candidate's release operation is a low-level transition and is **not** a
safe recovery procedure for an unknown-effect or legacy claim. Do not expose it
to operators or production callers until the required recovery policy exists.
The prototype has no reservations and must not be used to transfer them. No
claimant-crypto or slice-A guarantee is implied.

## Verification and review

The final focused core, existing queue and cleanup-regression suite passes
**76 tests, zero skipped**, on Python 3.12.14 with SQLite 3.53.1. All ten spawned
contenders report readiness before the parent releases the start barrier.
The final regression changes journal mode after construction and verifies
refusal without task mutation. All 32 new Python documentation items have
docstrings; signatures are annotated. A noneditable wheel imported outside
the checkout passes package-origin checks and an add/claim/complete sequence.

The first integrated snapshot passed the full PT suite: **3,737 passed,
12 skipped**, with nine retained legacy warnings. Same-session review then
identified the constructor-only journal check; the correction and stronger
readiness barrier are covered by the final 76-test run above. That earlier
full-suite result is not claimed as an exact-final-tree rerun.

Positive core tests explicitly skip on unsupported interpreters/platforms;
the old-SQLite refusal test still executes on POSIX. Those skips cannot qualify
the required runtime or a Windows client. Source tests do not establish
crash durability, authority-host identity, a service boundary or deployment.
