# Branch Locality and Review Provenance

Date: 2026-07-12
Context: PR #206 final CodeRabbit remediation

## What happened

A CodeRabbit review was issued against PR #206. Some valid review fixes were initially applied directly to `main` instead of to the reviewed PR branch. This made PR #206 conflict with `main` even though the changes were logically compatible.

The technical edits were not the primary failure. The failure was branch ownership: review-specific work was moved outside the lineage that owned the review.

## Durable lessons

### 1. Branch Locality Principle

A review fix belongs on the exact branch that received the review until that branch merges.

### 2. Review Provenance

Preserve this chain:

```text
review → reviewed branch → remediation commits → CI → merge → main
```

Moving a fix early to another branch destroys provenance and creates avoidable conflicts.

### 3. Canonical integration flow

Feature/review branches are the only place where pending review remediation is implemented. `main` receives the fix through merge, not by parallel transplantation.

### 4. No unsolicited branch switching

Do not change the write target because another branch appears more convenient. Explicit operator direction controls branch ownership.

### 5. Pattern-level remediation

Cluster related review findings by shared invariant and fix the owning abstraction once. Do not accumulate isolated surface patches.

### 6. Frugal repository inspection

Resolve the current branch head first, then inspect each owning file once where practical. Re-fetch only after a known concurrent advance or stale-SHA conflict.

### 7. Preserve integration topology

Agents may read other branches but must not move fixes across branches without authorization. One task has one owning branch until merge.

### 8. Shared coordination is a correctness mechanism

Task claims, heartbeat state, branch identity, file ownership, and explicit handoffs are not administrative overhead. They prevent technically valid agents from producing mutually incompatible histories.

### 9. Restore before replay

When a review fix lands on the wrong branch:

1. restore that branch to its previous content;
2. replay the validated fix on the reviewed branch;
3. verify no review-only changes remain outside the branch;
4. record the lesson so future agents inherit the invariant.

## Canonical reference

All skills and agents should apply:

`.agent/references/branch-local-review-remediation.md`
