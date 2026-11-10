# Mac POSIX evidence and lock boundaries, 2026-11-10

Status: provisional domain knowledge and dated chronicle, not platform qualification,
review approval, operator authority, or permission to dispatch. This entry adds to
the existing Windows catalogue and lessons; it does not replace them.

Attribution envelope: originating source review by the Mac Codex sidecar;
native test execution and integration by `codex-primary-orchestrator`;
memory synthesis and canonical writer operations by Kuhn,
instance `01a1c1a7-6372-7793-b344-ba212e4eb144`. All identities are
self-reported, `identity_verified=false`. Endorsement is bounded software
evidence only; takeover of Windows operations: none. Windows implementation
remains attributed to Claude Code acting as `win-researcher`.

Companion synthesis: Orama
`docs/guides/autoresearcher-posix-review-and-evidence-2026-11-10.md`
is being prepared in [PR 487](https://github.com/diazMelgarejo/orama-system/pull/487)
and is not asserted to exist at the historical baseline SHA. Consult the PR's
actual published head for the guide.

## Evidence and provenance

The parent supplied historical baseline Mac software-test receipts for Python 3.13.18,
SQLite 3.53.1 and macOS 27.2 arm64. The synthesis actor checked the named
receipt files and their hashes, not the original test executions. Source heads
and platform are integral to the observations:

| Scope | Exact source head | Parent receipt | Raw artifact SHA-256 |
| --- | --- | --- | --- |
| Orama, seven focused files, [PR 487](https://github.com/diazMelgarejo/orama-system/pull/487) | `71ab35601ac43c43a8538aff836bb47084cad7a4` | 154 passed, 13 skipped, 1 warning | `pr487-71ab3560.xml`: `200a32bd9a465953292c17b74912fc4ced5bd69ac1be71f6ee9c1c886b98b510` |
| PT, `tests/test_state_authority_record.py` | `b728015fc2b4462924c210c2292cba0b3f3ddf76` | 20 passed, 2 warnings | `pt-state-authority.xml`: `a27aa985a0babb48f905bbeb2cfba48484606149a534e4686f77229a87b03fd7` |
| Phylax, four focused portability/publication/retention files | `2c11d15820532f43e588a732f7b2b6509551a1f2` | 121 passed, 1 skipped | `phylax-posix.xml`: `626ddda41a281880ed500b6a95dbf4b909ceb661193b76bb1302bedd1e152077` |

Artifacts are retained locally under the operator-selected `$MAC_POSIX_RESULTS`
directory; filenames and hashes above identify exact bytes without embedding a
workstation path. The Orama warning was an unrecognized `asyncio_mode` pytest
configuration option; PT reported that warning and an unrecognized
`asyncio_default_fixture_loop_scope` option. The Phylax skip concerned POSIX
same-handle relock conversion. No global coverage claim is made; these are not
full-suite or native Windows results. This synthesis is intended for
[PT PR 489](https://github.com/diazMelgarejo/Perpetua-Tools/pull/489), not a
claim about its current remote status.

## Review and operating lessons

- Synthetic fault injection against Orama `71ab35601ac43c43a8538aff836bb47084cad7a4`
  reported that post-send usage-like output or a post-spawn `OSError` could
  classify an ambiguous outcome as `not-sent` and clear its lock. It also
  reproduced one descriptor left open after `PermissionError`. This is a
  bounded synthetic review result, not a live provider call. Artifact
  `review-fault-injection.json` SHA-256:
  `2166a0380ffd4d17bd041daaa98f9fa9ad141f36203f94b5722925024c0baca1`.
  Do not infer that later PR heads remain defective or that fixes are merged.
  The parent reports Windows' `ee9c65d6` preserves a separate spawn boundary
  and descriptor cleanup, but identified an immediate-stderr classification
  concern and is reviewing a newer head. Neither later head nor a final fix is
  verified by this chronicle; do not relabel the `71ab` receipts as later tests.
- Preserve earlier `lesson_3413c1a3ed12` as historical evidence of observed
  pre-send CLI failures, but do not generalize that usage text or any launch
  `OSError` proves pre-send: effectful work can already have started. Unknown
  outcomes remain held for reconciliation absent reliable pre-send proof.
- In a separate temporary macOS `flock` scenario on Python 3.13.18, a second
  process acquired after the first explicitly unlocked while the first remained
  alive. Qualified receipt SHA-256:
  `60e29666179c347e1a3cc5d4b905778cee66be14170a16daeab0105840d92f7a`;
  harness SHA-256:
  `f75675bc4a66d0bc75614a0b85cec58f8520da3ebcaf494525d3b2ec196fd9bf`.
  Lock availability alone does not prove prior process death or downstream
  completion. The earlier Python 3.13.0 observation is distinct, not erased.
- A model's completed response or advice is not authority for effects, approval,
  acceptance or activation. Distinguish source evidence, execution, operator
  decisions and native host qualification. PT's POSIX authority record verifier
  is not a Windows ACL verifier; its manual cleanup remains manual.
- Existing provisional `lesson_1fd9e4a5651a` already requires matched endpoint,
  temperature, template and thinking mode before attributing benchmark
  differences to transport. Retain it rather than creating a duplicate; small
  samples and different configurations do not establish a route winner.

## Additional boundaries

- Check the actual version, help, install layout and potentially dangerous
  defaults before using a tool; a source snapshot or help text is not authority
  to execute against real data. Two unmatched benchmark samples do not establish
  causality, even when one route's measured average is lower.
- A per-I/O timeout is not a deadline for DNS, the full process, or the entire
  workflow. Keep ambiguous effect outcomes separate from timeout diagnostics.
- Preserve and verify exact raw bytes and their digest; normalized hashes are
  diagnostic, not proof of byte identity. Transport acceptance, authenticated
  readback, a recipient's actual reading and individual consent are distinct.
- Namespace task IDs by their source plan: original P-W1/P-W2/P-W4 and later
  WIN-W1/WIN-W2/WIN-W4 describe different work. Do not infer one closes another.
- The parent reports current Phylax source uses `platform_fs`; an older
  unconditional `fcntl` finding belongs to the older producer. A verify-only
  recovery pin is intentionally not the full producer; absent full-producer
  modules alone do not establish a broken pin.
- D1 keeps PT cleanup manual and does not authorize a Doc 69 retrofit to legacy
  Core. Per operator context, periodic coordination is paused while existing v1
  and TLS services remain running; this is a reported operating boundary, not
  a fresh service-health observation or authorization to restart scheduling.

Native Windows execution, service-account isolation, later-head remediation,
independent release review and operator acceptance remain outside these receipts.

## Later remediation addendum

The historical receipts above remain unchanged. The primary Mac actor then
verified regressions, integrated Windows' subsequent `ee9c65d6` process-start
and descriptor repair and `d15ebce5` inspect/recheck/isolation hardening, and
strengthened outcome handling: every launched nonzero exit remains unknown,
even for short immediate stderr. HTTP localhost now uses a literal loopback
without DNS; HTTPS hostname identity is preserved and URL userinfo refuses.
Acquisition failure cleanup covers record inspection and classification as
well as initial locking. Seven dispatch/acquisition regressions failed before
the fix. The nine-file combined working-tree run passed 185 tests, 13
Windows-only skips, one disabled-plugin warning, with contained child cleanup.
Fix: `dc8ae1e37a72323a8c11089ec7c66d49cb158408`; concurrent Windows integration:
`32d57051d2077967db77b8cab9a66903cc910b11`; companion guide:
`0d52360ad29c94078a989f61ac8ad70a4074aecc` (Orama). A clean final-head receipt
belongs in publication evidence; do not infer it from this working-tree run.

Canonical `learn.py --provisional` operations produced exactly one candidate,
canonical lesson, rendered entry and episodic evidence record for each of:
`lesson_d50d160e077e`, `lesson_750ffa8b09da`, `lesson_5b810f647298`.
Both append-only JSONL files retain their exact prior byte prefixes. The
primary actor reran the memory-writer/contract slice on qualified Python
3.13.18: 23 passed, two disabled-plugin configuration warnings, contained
child, credential-free temporary home. The earlier sidecar's 23-pass run used
system Python 3.13.0 and remains a separate observation.

Integration order: retain PT PR487 then PR488 then this PR489 by the reported
stack relationship, rechecking live heads/mergeability first. User authorized
one publication per existing Orama487/PT489 after local verification; no
merge, deployment, credentials, pin promotion or activation was authorized.
Windows reviews/runs the final Orama head natively before platform acceptance.
