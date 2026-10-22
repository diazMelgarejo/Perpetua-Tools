# Direct AntiGravity review: failure and graceful degradation

Author and actor: `codex-primary-orchestrator`.
Scope: four parallel review assignments dispatched directly to the discovered
AntiGravity CLI, with no OpenClaw intermediary. Each process used a separate
detached worktree at its assigned source SHA.

## What failed

Four initial processes exited with status zero but returned empty standard
output. Their diagnostic streams reported that headless mode denied a tool
requiring command permission. They therefore completed no review.

The same diagnostics warned that `--mode plan` had no effect while
`--disable-slash-commands` was enabled. Do not combine these switches and infer
that plan mode is active. Check behavior for the installed CLI version rather
than treating a remembered flag combination as permanent truth.

## What worked

Fresh processes used the direct CLI with `--mode=plan`, an available model
verified through `agy models`, bounded execution, and an attached
`--print=VALUE` argument. The coordinating agent supplied numbered source
text and explicitly required an analysis-only answer without tools. All four
returned substantive review text. No permission bypass or global settings
change was used.

The four reviewers covered E1 operator-decision fidelity, pin-promotion shape,
the PR 50 empty-record fix, and the evidence contract. Each instruction had
separate authority, data/scope, method, return-contract and exact-assignment
layers. Exact source SHAs and review limitations were retained with results.

## Memory writer and guard mismatch

The supported `learn.py --provisional` flow generated a probationary lesson
and candidate, but the candidate validator rejected its `provisional` status
at commit time. The guard now admits that writer-generated state while
retaining the terminal reviewer requirement. A regression failed first on
the real mismatch; the complete focused hook suite then passed nine tests.
No historical memory row was edited and no hook was bypassed.

## What these reviews prove

They are independent reasoning passes over coordinator-supplied source.
They do not independently establish filesystem state, test execution, archive
digests, live PR state, credentials or the authenticity of supplied bytes.
A fresh model process is not a separately controlled authorization principal.
Never turn a source-only review into an independent runtime acceptance.

Codex separately ran 186 focused tests at harness `3332b615` and checked the
two raw archives for run `38916773943`: both archive digests and all 19 sealed
file digests per cell matched, with 1,245 passing tests per cell. This is
maker-involved validation and must be labelled accordingly.

The PR 50 seal suite passed 23 tests. Its new two-case regression failed on
the pre-fix stamper and passed on the fix. An adversarial nonempty record
substituted from another run was still sealed by both revisions: content
hashing alone proves retained-byte integrity, not semantic origin. No actual
substitution was found in the downloaded evidence.

## Durable operating rules

1. Inspect stdout, stderr and the expected result structure, not exit status
   alone. Empty output with status zero is an unsuccessful task.
2. Preserve denied-tool diagnostics; do not bypass permissions or silently
   relabel an attempted command as completed.
3. Degrade to a useful narrower role, explicitly naming its limits.
4. Run command-based validation separately and attribute it to the executor.
5. Verify every reviewer finding; source-supplied models can recommend a
   self-referential commit SHA or confuse metadata with an executable gate.
6. Keep approved commits immutable. Place follow-ups on the existing open
   stack, with a fresh review and approval cycle when bound inputs change.
7. Distinguish authority, coordination records and recovery observations;
   never solve cross-store consistency by claiming a distributed transaction.

## Public anchors

- [Approved harness review PR 46](https://github.com/oramasys/oramasys/pull/46)
- [Empty-member fix PR 50](https://github.com/oramasys/oramasys/pull/50)
- [E1 draft PR 410](https://github.com/diazMelgarejo/orama-system/pull/410)
- [M1 evidence receipt PR 411](https://github.com/diazMelgarejo/orama-system/pull/411)

Neither this note nor a review verdict accepts evidence, ratifies E1,
promotes production pins, enables serving or authorizes a merge.
