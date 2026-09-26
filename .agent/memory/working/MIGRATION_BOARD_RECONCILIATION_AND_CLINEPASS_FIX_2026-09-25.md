# Migration Board Reconciliation + ClinePass Dispatch Fix (2026-09-25)

**Agent:** `cline-session-20260907` (type `coordination/claude`, model `cline`)
**Board:** PT GossipBus — `.state/perpetua_core.db`
**Regime:** the ClinePass nounset fix is committed locally and unpushed. The two
dialer commits in the table below are already on their remote branches. No
merges; no v1 behaviour change.
**Scope:** close the migration reminder batch without duplicating implementation lanes,
deliver the codex-dispatched K1 audit, and fix the dispatch-blocking shell defect.

## Delivered

| Item | Commit | Push state |
| ---- | ------ | ---------- |
| PT launcher DNS-resolve + address-classify dial targets (Gate 4 Half B) | `547e8a94` | **on origin** — verified ancestor of the `gate4/halfb-dialer-adoption-20260907` remote tip |
| oramasys dialer 6to4 relay-anycast prohibition (`192.88.99.0/24`) | `059cd4c1` | **on remote** — local SHA identical to the remote branch tip |
| ClinePass empty-array nounset fix | `88209503` | **unpushed** — branch `fix/clinepass-bash32-nounset-empty-array-20260925` |

Board reconciliation closed **6 of 7** queued migration rows as superseded
reminders against verified lanes. Counts were re-measured at the claimed
commits in separate worktrees: Seth's cloud Cursor agents were writing in
parallel, and the MacBook Pro Orchestrator canonical checkout stayed in
place. The 7th row was left queued because it is operator-only. A claim
stranded by a verifiably DEAD agent was cleared with a disclosed takeover.

## Evidence artifacts (non-git workspace)

- `references/2026-09-25-k1-source-provenance-audit-cline.md` — codex-assigned audit
- `references/2026-09-25-migration-reminder-reconciliation-and-canary-handover.md`
- `references/2026-09-25-physical-canary-operator-runbook.md`

## Open items for humans

1. **Physical canary** (operator-only): run the reviewed collector on each host and
   attach genuine redacted UTC outputs. The collector has **no CLI and no flags**,
   emits **no timestamp**, and its repo tests are synthetic-only.
2. **Push `88209503`** — blocked on credentials, not on code.
3. **K1 `dirty-worktree` caveat** still gates A1 acceptance (source pins are complete).
4. Merges remain behind HITL for the migration PR stack.

## Lessons graduated this session

Board/lane discipline (reminder rows are not lanes; verify from each task's event
timeline), dead-claimant recovery, cleanup-requeues-exhausted-task, operator-only
evidence integrity, temp-worktree commit reachability, detached-worktree
verification against diverged checkouts, and the recurring bash 3.2 `set -u`
empty-array defect — see `semantic/lessons.jsonl` entries dated 2026-09-25.