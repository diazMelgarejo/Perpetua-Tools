# 2026-11-04: LAN recovery, byte contracts, and additive PR stack

## Contribution envelope

- Agent ID and actor: `codex-reviewer`.
- Runtime model declaration: `gpt-6.1-sol`; no claim of external attestation.
- Author of this chronicle, seven new lessons, Orama byte-contract patch, and stack integration: Codex.
- Contribution type: implementation, local validation, evidence reconciliation, and operator-authorized publication preparation.
- Independent endorsement: not claimed. Native Windows qualification of the final byte-contract candidate remains pending.
- Takeover: operator explicitly requested stack integration and today's memory additions to existing PRs, then confirmed commit/publication. Preserve prior contributors and immutable source references.
- Windows contribution provenance: Windows coordination reply and published source commits below; do not infer a particular model or person from a shared Git identity.

## Scope and corrected interpretation

The operator wanted the existing v1 services and authenticated Mac/Windows
inboxes restored, the accumulated Windows handoffs delivered without duplicates,
the observed newline discrepancy explained and fixed, and the related changes
presented as a low-conflict review stack. No v2 serving activation, firewall
change, credential rotation, or trust weakening was authorized by this work.

The recovery did not establish one permanent root cause for every failure.
Different observations crossed different boundaries: stale receiver processes,
an aggregate diagnostic route slower than the chosen deadline, transport
timeouts, and eventually successful unchanged-credential HTTPS. Earlier claims
that the peer credential was necessarily wrong or outbound-only, or that a
timeout established a proxy failure, were too strong. Preserve those historical
notes and use this correction rather than rewriting them.

## Chronology and evidence

1. Started from fetched Orama main `b1b15812d48eea5cbb7bcce8084ff0d85df25c5e`
   and PT main `fa6b914e9dcaf2f86b0b895da80a284dfe25d0ca`, using isolated
   worktrees. Dirty primary checkouts were not reset or overwritten.
2. Reassessment found the Windows CA-download receipt already in the Mac
   inbox. Earlier inventory had used unsupported macOS `find -printf` and
   suppressed its errors. Replaced the inference with actual `pathlib`
   inventory and stopped the owned temporary public-CA HTTP listener after
   Windows confirmed its verified download. No private key was served.
3. Confirmed existing CA trust through verified HTTPS. Some retries failed
   before TLS with a connection timeout/incomplete ARP; other authenticated
   requests had previously returned refusals. These are bounded observations,
   not interchangeable credential diagnoses. A watcher heartbeat was newer
   than the discovery observation, and model-port liveness was not portal
   liveness. Do not copy obsolete endpoint literals into tracked guidance.
4. Inspected merged portal code: network probes were already parallel, but
   aggregate status still included synchronous CLI inventory work and later
   probes. The fast protected inbox route became the delivery gate instead
   of requiring expensive diagnostics to finish. A mocked healthy-peer test
   lacked its explicit TLS precondition: 31 passed/1 failed normally, then
   32 passed with that test precondition supplied. That test-isolation issue
   was documented, not silently repaired by weakening transport policy.
5. Resumed the existing five-minute monitor, with unchanged failures quiet.
   The link eventually returned authenticated inbox 200 without changing
   receiver credentials or CA trust. Exactly one canary was accepted:
   `mac-canary-20261104T015511Z.md`, received at 2026-11-04T01:55:42Z.
6. After the operator explicitly requested the stale Windows backlog,
   resubmitted six named documents item by item with duplicate checks and
   sent a separate individual-acknowledgement request. Windows reported all
   seven arrivals at 02:39:08-02:39:19Z. The six outbox records are terminal
   delivered; the seventh was a direct accepted drop. No resend is required.
   Seven older other-node or unspecified-destination records remain preserved
   pending ownership mapping. Shared-inbox acceptance is not all-agent consent.
7. Windows' `win-coord-utf8-bytes-20261104.md` independently reported the
   original canary's 905 received bytes versus 916 stored bytes: eleven
   LF-to-CRLF expansions, no BOM. Windows raw SHA-256 was
   `04f9fc42aab946b610a30b4547a83f5469e048a5f0a63f12c2273664673aa606`.
   The reported LF-normalized digest matched the Mac original:
   `baa3d25310372013c574611a4b41bbed805a26a1aef186aba4adf0e8c887059b`.
   This proves the reported legacy newline equivalence, not raw byte identity.
8. Implemented the byte-preserving transport slice in Orama only: binary
   source reads, inbox/outbox writes and readback; binary UTF-8/LF sidecars;
   writer-derived bytes and SHA-256. Preserve explicit BOM and trailing
   newlines. Keep actual-file receipt hashing instead of trusting cached
   metadata, which cannot detect later edits. No historical file migration.
9. Portable Windows-write simulation reproduced 11 failures/4 passes before
   the body fix. Sidecar tests reproduced 13 failures/3 passes before that
   extension. Final focused suite passed 71 tests. Ruff, hygiene, diff check,
   and docstrings 61/61 passed. Native Windows qualification remains separate.
10. Published [Orama PR 469](https://github.com/diazMelgarejo/orama-system/pull/469)
    as a draft, originally at `5229f6213bbe15abcc78c498ccbd22350350c87f`,
    with one logical commit and one normal push. Windows received the exact-head
    handoff and owns review/native tests before any patched-receiver receipt.
11. Operator then requested all related PRs stacked. Changed paths were
    disjoint. Preserved each contributor's file bytes and original commits,
    using regular merge commits rather than a force-push or squash. Combined
    validation: 85 passed, 4 Windows-only skips; hygiene and pending-operation
    guards passed. Updated both affected Orama branches in one atomic push.

## Immutable publication and stack references

| PR | Original contribution | Integrated head | GitHub base |
| --- | --- | --- | --- |
| [Orama 467](https://github.com/diazMelgarejo/orama-system/pull/467) | Windows portal status cache, `addde2bdd6fe951cf3fda6470bc31cc93e8d0ae1` | unchanged | `main` |
| [Orama 468](https://github.com/diazMelgarejo/orama-system/pull/468) | Windows launcher job escape, `153832bb13dc2d0a5b035be0c4f2ac46a9423c79` | `cc94860720218c46bdb145fe46bfd722f19ef3ed` | PR 467 branch |
| [Orama 469](https://github.com/diazMelgarejo/orama-system/pull/469) | Codex byte contract, `5229f6213bbe15abcc78c498ccbd22350350c87f` | `d9cdc23c7a542512f442fac12e4538df0298aa74` | PR 468 branch |
| [PT 477](https://github.com/diazMelgarejo/Perpetua-Tools/pull/477) | Windows memory head `93ae1ed02031df960baf36424a27ecc40be3a465` preserved underneath this addition | current PR head is live state, not frozen here | `main` |

Merge order: Orama 467 into main, retarget 468 to main if GitHub has not done
so, merge 468, then retarget/merge 469 after its review and Windows gates.
Use regular merge commits; do not squash or merge a child into a predecessor
branch by accident. PT 477 is an independently based memory companion, not
a cross-repository Git stack. Recheck live heads and checks before merging.

The two stack commits preserve all original parents. Byte comparisons
confirmed each original contribution's paths are unchanged at the leaf.
Existing PR identities and branch names were retained to avoid fragmentation.

## Privacy and diagnostic lesson

An earlier overly broad local env-file search displayed a credential-bearing
line. This record deliberately omits every credential and machine-specific
path. Inspect key presence and protected process loading, not raw secret
values. Credential exposure handling remains operator-owned; do not silently
rotate, copy, or normalize credentials while diagnosing a network failure.

## Durable lessons added through supported tooling

- `lesson_e03157bb000b`: distinguish TCP, TLS, auth, latency, and receipt evidence.
- `lesson_4894c94af395`: portable inventory and visible tool failures.
- `lesson_48f743de79dc`: preserve exact UTF-8 body bytes end to end.
- `lesson_5cd503b5684d`: raw versus LF-normalized hashes and historical evidence.
- `lesson_007d21c5b645`: duplicate-safe queue reconciliation and per-agent acknowledgement.
- `lesson_80f8180e392b`: additive published-PR stacks and unchanged contribution proofs.
- `lesson_5a28c6c95da0`: secret-safe environment diagnostics.

## Remaining gates

- Windows review/native testing at the final published Orama head; CI must
  rerun after stack integration, and old green results do not qualify new heads.
- Operator-authorized patched receiver update, then a fresh canary/receipt.
- Individual active-agent acknowledgements; the single Windows convention
  agreement is not a fleet-wide endorsement.
- Ownership/destination mapping for the seven preserved historical items.
- The known mocked-probe environment-isolation issue and model-port/portal
  discovery coupling remain documented follow-up work, not completed fixes.

No claim of full-repository test coverage, native Windows execution by Mac,
completed PR merge, or live deployment is made by this chronicle.
