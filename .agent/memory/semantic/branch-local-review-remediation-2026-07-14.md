# Branch-Local Review Remediation Discipline

Date: 2026-07-14
Repository: Perpetua-Tools
Scope: PR #206 final review/remediation round

## What happened

A review-remediation pass for PR #206 drifted across `main` and the PR branch. Some correct fixes were first committed to `main` even though the operator later clarified that all final-round work must happen strictly on PR #206's branch to keep merge review simple.

A separate earlier commit, `1de6a8767fd3973aa652c9f386a78b9bca8450e1`, attempted to add globally unique GossipBus event UUIDs. The concept was valid, but the implementation changed the public return contract of `GossipBus.insert_event()` from `(row_id, safe_payload)` to `(row_id, event_uuid, safe_payload)`. Transactional callers that combine a claim/release row with a heartbeat event still expected the two-value return, so the change created signature drift and made the coordination API harder to merge safely.

## Core lessons

1. **Final review fixes must land on the PR branch unless the operator explicitly asks for `main`.** Do not pre-commit speculative fixes to `main` because later branch review becomes harder, even if the individual patch is correct.

2. **Resetting `main` to the last common ancestor can be cleaner than revert storms when rogue commits polluted `main`.** A revert preserves the unwanted commits in the ancestry and can make PR merge conflicts worse; a direct ref reset to the common ancestor removes the bad lineage from the merge problem. This requires explicit operator authorization because it rewrites `main`.

3. **Do not change a shared transaction primitive's tuple shape casually.** If a new field such as `event_uuid` is needed, prefer a compatibility-preserving shape such as a dict result or additive helper. All callers that combine DB mutations in one transaction must be updated atomically and covered by tests.

4. **Pattern-level CodeRabbit remediation beats comment-by-comment patching.** Group comments by failure class: sanitized persistence, explicit encoding, lifecycle atomicity, timeout-bounded subprocesses, authenticated ordering/equivocation, and branch-local review discipline.

5. **FastAPI/API surface replacements must be reviewed as whole-file artifacts before upload.** Large file replacements should be provided as a reviewable file or exact branch/blob reference, not buried inside unrelated remediation commits.

## Shared reference card

### Use this when

- CodeRabbit emits many comments across related files.
- A PR branch has drifted from `main`.
- Multiple agents are working on the same remediation branch.
- A fix affects shared APIs, transaction helpers, persistence formats, or generated memory.

### Procedure

1. Identify the intended write branch from the operator's latest instruction.
2. Verify the PR head and base before every commit.
3. Cluster findings by invariant, not by file.
4. Inspect each owning file once; avoid repeated broad reads.
5. Patch the owning abstraction first.
6. Add or update regression tests at the contract boundary.
7. Commit cohesive groups only.
8. Re-check PR mergeability and CI.
9. Leave the PR unmerged for operator review when requested.

### Red flags

- A fix changes a return tuple used by transaction callers.
- A generated file or memory render is hand-edited directly.
- A branch-local fix is committed to `main` during final PR review.
- A revert is proposed when the problem is polluted ancestry.
- A large API file is replaced without a reviewable artifact.

## Cross-reference targets

Skills and agents should cross-reference this card from:

- code review workflows,
- agent coordination / heartbeat skills,
- git hygiene / history surgery guidance,
- AutoPlan / Gstack plans,
- PT `.agent` memory review procedures.
