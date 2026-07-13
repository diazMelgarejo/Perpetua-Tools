---
title: Branch-Local Pattern Remediation Reference Card
status: active
created: 2026-07-13
scope: multi-agent code-review remediation
applies_to:
  - code-review
  - oramasys-method
  - agent-methodology
  - autoresearch
  - git-discipline
  - gossip-bus
---

# Branch-Local Pattern Remediation Reference Card

Use this card when a PR receives many review comments that appear unrelated but likely share a smaller number of underlying failure classes.

This discipline was crystallized during Perpetua-Tools PR #206 / PR #211 remediation, where treating CodeRabbit comments as a checklist caused repeated branch drift, stale-SHA writes, and surface fixes. The successful pattern was to group comments by invariant, inspect the owning files once, and fix the abstraction boundary rather than each symptom.

## Core rule

**Fix the failure class, not the comment. Work only on the PR branch unless the operator explicitly authorizes a base-branch reset.**

A review comment is a symptom. The correct target is the smallest stable contract that prevents the same symptom class from recurring.

## When to apply

Apply this reference when any of the following are true:

- CodeRabbit or another reviewer leaves 3+ findings across related files.
- Multiple agents are working on the same branch or sibling branches.
- The PR branch is moving while remediation is happening.
- The same file has been edited by multiple agents.
- The proposed fix would require full-file replacement in a large or sensitive file.
- The user says to use `/oramasys-method`, `/code-review`, or asks for first-principles remediation.

## Five-stage operating loop

### 1. Freeze the target branch

Before editing:

```text
repo: <owner/repo>
PR: <number>
base: <base branch + SHA>
head: <head branch + SHA>
write target: PR branch only
```

Never assume `main` is the current write target just because the issue affects CI. If the user says “fix in PR branch,” use the PR head branch exclusively.

### 2. Cluster findings by failure class

Do not preserve the reviewer’s ordering. Re-group by invariant:

| Failure class | Typical symptom | Owning abstraction |
|---|---|---|
| Identity mismatch | local `row_id` used as global event identity | storage/event model |
| Initialization race | first request touches missing DB/schema | lifecycle/startup + lazy init |
| Auth gap | peer endpoint accepts arbitrary caller | endpoint guard + peer client headers |
| Persistence leak | secret/path stored before redaction | write boundary |
| Lifecycle duplication | candidate exists in two states after partial failure | move transaction / rollback |
| Branch drift | fix lands on `main` instead of PR branch | git discipline |

The owner is where the fix belongs. Downstream call sites should become simpler, not more defensive.

### 3. Inspect each owning file once

Use frugal reads:

```text
- PR metadata first
- review threads second
- changed-file patches third
- full file only for files that must be written
```

Avoid repeatedly fetching the same large file. If a tool only supports full-file replacement and the file is large or security-sensitive, prefer fixing the lower abstraction boundary when that is valid.

### 4. Patch the abstraction boundary

Use the smallest coherent commit series:

1. Storage/model invariant.
2. Transport/API invariant.
3. Caller integration.
4. Tests.
5. Documentation/reference card.

Do not make one commit per review comment when several comments share the same root cause.

### 5. Verify and leave reviewable

Minimum verification checklist:

```text
[ ] PR head advanced only on intended branch
[ ] unresolved review threads rechecked
[ ] tests added/updated for the failure class
[ ] PR remains unmerged for human review when requested
[ ] final summary separates fixed, already-fixed, and intentionally deferred items
```

## PR #211 example: LAN Gossip Bridge

Reviewer comments clustered into three failure classes:

| Class | Problem | Correct fix |
|---|---|---|
| F1: Global event identity | SQLite `row_id` is local-only and cannot deduplicate peer events | Add `event_uuid`, return it from `emit()`, deduplicate by UUID |
| F2: Canonical DB init | FastAPI fallback could touch a default/uninitialized DB | Make `GossipBus()` resolve canonical `.state/perpetua_core.db` and lazily initialize before reads/writes |
| F3: Peer auth | Gossip endpoints allowed arbitrary peer callers | Add shared-secret endpoint guard and client header forwarding |

The elegant fix was not to add row-id special cases to `LanGossipBridge.tail()`. The right model is:

```text
Global logical event identity: event_uuid
Local ordering identity: row_id
Merge key: event_uuid
Sort tie-breaker: (ts, row_id)
```

This preserves local SQLite ordering while making cross-peer aggregation stable.

## Cross-skill usage

### `/oramasys-method`

Use this card in Stage 1 and Stage 3:

- Stage 1 Context Immersion: establish branch, base, head, and current review threads.
- Stage 3 Ruthless Refinement: collapse checklist items into failure classes.
- Stage 4 Masterful Execution: patch abstraction boundaries and verify with tests.

### `/code-review`

Use this card after collecting review comments:

- classify comments by invariant;
- decide which are already fixed in current code;
- patch only live defects;
- add tests for the class, not for the reviewer wording.

### `/agent-methodology`

Before coordinating multiple agents:

- assign each failure class to one lane;
- avoid two agents writing the same file;
- record current PR head SHA before each lane starts;
- one integrator owns final merge/harmonization.

### `/git-discipline`

Branch-local rule:

- PR review fixes go to the PR head branch.
- Base-branch resets require explicit operator authorization.
- Do not use revert when the operator explicitly asks for reset-to-ancestor cleanup.
- Do not merge the PR automatically when the operator says they will review it.

### `/gossip-bus`

For event replication work:

- never use local database row IDs as cross-peer identity;
- use stable event UUIDs for logical identity;
- preserve local row IDs for ordering/debugging only;
- make public bus operations safe on a fresh canonical bus;
- peer failures are best-effort but logged at debug level.

## Anti-patterns

- “Fixing” each comment literally without identifying the shared invariant.
- Landing remediation on `main` while the PR remains open.
- Reverting many commits when reset-to-ancestor is the intended cleanup.
- Replacing a whole sensitive file because a small endpoint concern exists.
- Letting unknown top-level request fields silently drop critical transport identity.
- Resolving review threads before code/tests prove the class is fixed.

## Review handoff template

```text
PR: #<number>
Head before work: <sha>
Head after work: <sha>
Failure classes addressed:
- F1: <class> — <commit>
- F2: <class> — <commit>
Already fixed / no action:
- <item> — <evidence>
Deferred intentionally:
- <item> — <reason>
Validation:
- <tests/checks>
Merge status: unmerged, ready for human review
```
