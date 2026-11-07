# Native Windows dry-run handoff

## Prepared candidate update

These are source candidates, not deployment approvals. The earlier snapshot below
is retained as dated provenance; use the following reviewed implementation commits
when freezing the next candidate, then recheck their remote state and CI:

- PT append-only correction: `96c9ddb59ea0f47e04472d1115a4880e5d16d151`.
- PT runtime boundary: `75f0b9228dbbf618d06811a5f815bfe040ff7c37`; existing test-debt
  repair: `14e4f48a82df779db13801f6b3f7a816ce1c8abe`.
- Orama runtime adapters and test-only PT compatibility pin:
  `ba17a1ddc7a7aa5b7056f3fdc24d6928ff85b30a`.
- Phylax portability and native CI candidate:
  `d1ca921c0641fe7b58b54cfc25f51c23dd613a67`. Production consumer pins are unchanged.

Local verification: PT **3,242 passed, 76 skipped**; Phylax **1,019 passed,
1 skipped**, coverage **92.61%**. Orama **3,388 passed, 94 skipped, 4 failed**,
with 21 subtests passed. The same four `test_win_exec.py` process-containment
failures (`escaped:1` rather than `contained`) reproduce on original PR head
`4f6c7bd39e0ec0d4a7c0374ba1c95ac0da6f5fe5`. They were not skipped or repaired by
weakening containment assertions. Preserve this limitation and require fresh
native host results. Touched Python source/test files have complete docstrings.

Before native workload measurement, run the Phylax candidate's actual platform
and producer tests from its checkout, under the selected test interpreter:

```powershell
$env:PYTHONPATH = 'src'
python -m pytest src/tests/test_platform_fs.py src/tests/test_publication_portability.py src/tests/test_revocation_publication.py src/tests/test_dispatch_retention.py --no-cov -v
if ($LASTEXITCODE -ne 0) { throw 'Producer portability failed; do not proceed' }
```

Install the repository's declared development requirements first; on Windows the
platform layer requires `pywin32`, not an `fcntl` stub. Native CI on 3.11/3.12 is
additional source evidence, not service-identity or power-loss qualification.

The PT guard needs a protected shared state directory across cooperating callers.
It has no automatic release, expiry, daemon or semantic duplicate detection.
Implicit CLI model defaults remain unattested. Review its
[bounded runtime contract](https://github.com/diazMelgarejo/Perpetua-Tools/blob/75f0b9228dbbf618d06811a5f815bfe040ff7c37/docs/coordination/runtime-dispatch-guard.md)
before adopting it. Early mocked race tests created two test-only claims in the
local default state before isolation was added; no runtime ledger was deleted.
Use isolated test state, never cleanup of an unidentified ledger, for repetitions.

## Earlier preparation snapshot

Prepared 2026-11-07 UTC for the physical Windows session approximately 24 hours after 22:48 UTC.
This is a preparation package, not a host result, qualification, approval, or instruction to
activate serving. Recheck source and authorization at the session; no deadline closes a missing
gate.

## Start here

1. Keep `ORAMA_GRANT_SERVING` unset and library default `governed=False`. Work in disposable
   checkouts and approved local test directories, never production data. Record operator, executor,
   reviewer and their distinct roles. Do not change credentials, trust, firewall, service account,
   ACLs or antivirus configuration to make a test pass.
2. Reconcile the exact source revisions, trees and dependency inventory against the approved
   candidate before running anything. The identities below are a snapshot, not a deployment pin. The
   Phylax portability slice and PT dispatch guard are pending review: do not pretend the snapshot
   includes their finished work. Re-freeze and re-review after any change. Capture actual
   service-manager configuration and the exact interpreter it launches; distinguish it from the
   benchmark interpreter.
3. Establish Windows edition/build, actual service-account class and non-elevation, local NTFS
   volume, protected non-writable ancestors, existing antivirus/indexer treatment and native handle
   capacity. Keep concrete paths, account names and SIDs local. A network share or sync directory is
   unsuitable for SQLite/WAL. No POSIX descriptor estimate substitutes for Windows capacity
   evidence.
4. Collect native runtime and security evidence below. Preserve all skips, failures, stderr and
   unique receipts; stop on failure. Then perform the full C6 workload only once the reviewed
   producer and consumer portability work and exact dependency freeze are ready. The canonical
   runbooks govern the procedure; the receipt template in this folder is a return checklist, not a
   substitute.

## Snapshot and freeze

All identities and worktree statuses in this section are observations from 2026-11-07 UTC, not
claims about current approval or current repository state. A live GitHub API read that day returned
main heads Orama `c21d9028e91a932be7a625a5227dc2ea548b9aee`, Oramasys
`f33d809ac77e708d925d2180c0564e5d8a262484`, and PT `2caeb62662e7d1dffcc2c0db6c08360fc443a1ec`. These
are observed main revisions, not proof of operator approval, equivalence to the candidate, or the
heads at the future session. Recheck live main, candidate, approval, and content reconciliation
then.

| Source                                                                                                                                                                                                                                                                                               | Observed 2026-11-07                                                                                                                                                                                                               | Qualification implication                                                                                                                                                                                                                                                      |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [Canonical C0–C12 register](https://github.com/diazMelgarejo/orama-system/blob/4f6c7bd39e0ec0d4a7c0374ba1c95ac0da6f5fe5/docs/v2/MASTER-CLOSURE-AND-IMPLEMENTATION-PLAN-2026-11-06.md)                                                                                                                | Orama checkout HEAD `4f6c7bd39e0ec0d4a7c0374ba1c95ac0da6f5fe5`; worktree has unrelated uncommitted changes                                                                                                                        | Record approved exact head and tree at execution, including any relevant uncommitted candidate; do not assume this checkout is a clean frozen release.                                                                                                                         |
| [C6 Windows handoff](https://github.com/oramasys/oramasys/blob/f6295a13ef02666d89f64f1f6e9834bc0bde884c/docs/closure/c6-windows-handoff.md) and [qualification runbook](https://github.com/oramasys/oramasys/blob/f6295a13ef02666d89f64f1f6e9834bc0bde884c/docs/closure/c6-qualification-runbook.md) | Oramasys checkout HEAD `f6295a13ef02666d89f64f1f6e9834bc0bde884c`, tree `76a46a30ce5b8a5486c7f88cfd946dfde0d78ed1`; clean when inspected                                                                                          | Reconfirm exact approved producer/consumer and tree, including C6 harness and judge digests, before and after measurement.                                                                                                                                                     |
| [PT entrypoint](https://github.com/diazMelgarejo/Perpetua-Tools/blob/3a8a9c5ad28561d03202c5071cd8cb6a4fb436fc/docs/next/MASTER-CLOSURE-HANDOFF-2026-11-06.md)                                                                                                                                        | PT HEAD `3a8a9c5ad28561d03202c5071cd8cb6a4fb436fc`; runtime guard and tests uncommitted and pending review                                                                                                                        | Do not label this runtime candidate accepted or use a commit SHA as a substitute for its actual tree and review.                                                                                                                                                               |
| Phylax                                                                                                                                                                                                                                                                                               | HEAD `1d2f2bb2ed7792c48f6320da36de9bc7459f0da3` in [baseline source](https://github.com/oramasys/phylax/tree/1d2f2bb2ed7792c48f6320da36de9bc7459f0da3); portability changes were uncommitted and under active work at observation | At the recorded baseline `revocation_publication.py` and `dispatch_retention.py` imported `fcntl` unconditionally. Native producer-first portability was pending review at observation. Do not stub `fcntl` or silently replace the producer. Recheck the final selected tree. |

Freeze full source SHAs and Git tree IDs, approved local modifications if any, producer and consumer
pins, configuration and policy revisions, actual serving and benchmark Python builds, Python-linked
SQLite source ID and compile options, cryptography build, dependency/wheel inventory, harness, judge
and experiment digests. Preserve a protected local mapping to physical identities. Exact
fingerprints must match across comparison cells; changes invalidate the binding. A version floor and
exact comparison fingerprint are different requirements.

## Native entrypoints and evidence

From the reviewed Oramasys checkout, use the executable actually configured for serving, not a
separately installed SQLite CLI or an arbitrary benchmark environment:

```powershell
& $ServingPython -I scripts/c6_runtime.py
if ($LASTEXITCODE -ne 0) { throw 'SQLite serving-runtime qualification failed' }
```

Save its JSON privately. The configured serving interpreter gate requires mainline SQLite >= 3.51.3.
Official 3.44.6 and 3.50.7 backports require separate provenance review and do not pass this minimal
version gate. The previously selected Mac build, Python 3.13.18 / SQLite 3.53.1, is dated evidence;
verify the actual Windows build and architecture. C7/C8 need this runtime evidence on both platforms
because the serving attempt store already uses WAL.

The workspace search did not identify the separately reviewed standard-library locking experiment
named by the Windows handoff. This package includes
[sqlite_lock_preflight.py](sqlite_lock_preflight.py), an **experimental, unreviewed** substitute for
early information, not evidence that the runbook's reviewed-experiment requirement is met. It
creates a fresh directory, tests a real subprocess writer conflict, kills the holder, then checks
WAL reopening and integrity. It does not test power-loss durability, service-account isolation or
the complete adapter. Its receipt and database stay local. Run from this package directory with
`$ServingPython` set to the chosen interpreter and `$ApprovedParent` set to an existing protected
local NTFS directory. Choose three new names; it refuses an existing output directory and never
repairs ACLs:

```powershell
Get-FileHash -Algorithm SHA256 .\sqlite_lock_preflight.py
& $ServingPython -I .\test_sqlite_lock_preflight.py
if ($LASTEXITCODE -ne 0) { throw 'Preflight self-test failed' }
& $ServingPython -I .\sqlite_lock_preflight.py --output (Join-Path $ApprovedParent 'sqlite-preflight-01')
if ($LASTEXITCODE -ne 0) { throw 'Preflight 1 failed; preserve its output' }
& $ServingPython -I .\sqlite_lock_preflight.py --output (Join-Path $ApprovedParent 'sqlite-preflight-02')
if ($LASTEXITCODE -ne 0) { throw 'Preflight 2 failed; preserve its output' }
& $ServingPython -I .\sqlite_lock_preflight.py --output (Join-Path $ApprovedParent 'sqlite-preflight-03')
if ($LASTEXITCODE -ne 0) { throw 'Preflight 3 failed; preserve its output' }
```

Save the digest and each private `receipt.json`. Review this substitute and obtain the
runbook-required reviewed experiment before treating that specific requirement as satisfied. The
included self-test passed on isolated POSIX here; Windows execution remains pending.

After source portability review, run the following runbook entrypoints under the actual non-elevated
service account and then in a separately authorized elevated test shell, in a disposable checkout.
Use the selected interpreter in place of `python` if necessary:

```powershell
$env:PYTHONPATH = 'src'
python -m pytest -q tests/windows/test_private_store_native.py
if ($LASTEXITCODE -ne 0) { throw 'Native security verification failed' }
python -m pytest -q src/tests/test_private_store.py -k 'safe_replace or nonce_lock_failure'
if ($LASTEXITCODE -ne 0) { throw 'Replacement/lock verification failed' }
```

With an approved second principal, create a disposable foreign-owned fixture and set
`ORAMA_TEST_FOREIGN_OWNER_FILE` locally; rerun the native suite. Without it, record the
negative-owner test as skipped. Test actual second-account read/write denials on parent, database,
WAL and SHM; existing administrator-owned object refusal for a different token; trusted-ancestor ACL
and rename restrictions; junction refusal and handle cleanup; actual cross-process lock
serialization; and SQLite WAL create/reopen under the actual service token. Elevated sidecar owner
behavior is a known limitation and needs explicit testing. These checks do not prove isolation
against the same user or an administrator. Consult the
[Windows handoff](https://github.com/oramasys/oramasys/blob/f6295a13ef02666d89f64f1f6e9834bc0bde884c/docs/closure/c6-windows-handoff.md)
for the complete native checklist and limits. Do not modify real data ACLs for a fixture.

For C6 full native qualification, first compare the unchanged adapter/store baseline using the same
corrected harness, runtime and dependencies. Then run no-refresh control A (800 sends), one-sender
refreshing control B (600 sends), and three consecutive operator-run candidate trials of 2,400 sends
each. Use 256 genesis-complete events, eight senders at five sends/second, a separate refresh every
15 seconds, and two 50 ms retries only for the existing retryable refusal. Keep absolute arrival
schedules and all outcomes; report cold initialization separately. Preserve distinct exclusive JSON,
JSONL and stderr files for every attempt, including failures. Use the exact harness entrypoints and
flags in the
[C6 runbook](https://github.com/oramasys/oramasys/blob/f6295a13ef02666d89f64f1f6e9834bc0bde884c/docs/closure/c6-qualification-runbook.md),
adapted only after the Windows portability slice is reviewed. Do not treat its POSIX paths or
resource checks as native Windows evidence.

Acceptance limits are scheduled p95 **and** successful-call send p95 <= 60 ms; scheduled p99 <= 250
ms; first-attempt unavailability <= 1%; final errors <= 0.1%; steady refresh p95 <= 1,000 ms; zero
refresh failures; and zero fail-open in the accompanying adversarial suite. Report counts and
statistical bounds separately: zero errors out of 2,400 has a one-sided 95% independent-binomial
upper bound about 0.1247%, with temporal correlation a further limit. Include actual filesystem,
runtime, dependency, crypto, source and digest evidence and preserve raw samples privately. Failure,
a skip or a missing receipt is not a pass.

## Release gates and return

- D1: PT stays manual; automatic expiry/release with fencing belongs to the v2 Controller. D2:
  retain compatibility shims pending a separate removal decision. D3: both POSIX and native Windows
  qualification are required before promotion.
- C8 requires R4/R5 evidence from both hosts, including actual installed configuration and
  service-identity denials. Windows CI is source evidence, not host/account isolation qualification.
  The existing Mac C6 acceptance does not supply the Windows receipt.
- C9/R6 is independent review binding exact producer, consumer, configuration and host evidence.
  C10/R7 is the approved operator's immutable generation and paired-pin decision. C11/R8 is a
  separate operator activation decision with scope, expiry, canary, monitoring and rollback. None
  follows automatically from a test pass.
- Return the completed [sanitized receipt](RECEIPT-TEMPLATE.md) through the approved channel, with
  receiver acknowledgement; keep raw databases, concrete identities and private topology local.
  Separate author, executor, reviewer, operator acceptance and takeover. A fresh GitHub login
  demonstrates account control, not independent review or a second factor.

Sources:
[master closure register](https://github.com/diazMelgarejo/orama-system/blob/4f6c7bd39e0ec0d4a7c0374ba1c95ac0da6f5fe5/docs/v2/MASTER-CLOSURE-AND-IMPLEMENTATION-PLAN-2026-11-06.md),
[Windows handoff](https://github.com/oramasys/oramasys/blob/f6295a13ef02666d89f64f1f6e9834bc0bde884c/docs/closure/c6-windows-handoff.md),
[C6 qualification](https://github.com/oramasys/oramasys/blob/f6295a13ef02666d89f64f1f6e9834bc0bde884c/docs/closure/c6-qualification-runbook.md),
[PT C6 chronicle](https://github.com/diazMelgarejo/Perpetua-Tools/blob/3a8a9c5ad28561d03202c5071cd8cb6a4fb436fc/.agent/memory/working/2026-11-07-c6-runtime-and-review-chronicle.md),
[review correction](https://github.com/diazMelgarejo/Perpetua-Tools/blob/3a8a9c5ad28561d03202c5071cd8cb6a4fb436fc/.agent/memory/semantic/LAN_COORDINATION_WINDOWS_C6_AND_FLEET_SYNTHESIS_2026-11-08.md),
and
[activation runbook](https://github.com/oramasys/oramasys/blob/f6295a13ef02666d89f64f1f6e9834bc0bde884c/docs/serving-activation-runbook.md).
