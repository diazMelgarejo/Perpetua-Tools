# Guard sync divergence guard — completion (2026-08-01)

Companion to `GUARD_SYNC_EPIC_SAGA_COMPLETION_2026-08-01.md` (on this branch).

## What shipped

| Layer | Artifact |
| ----- | -------- |
| Checker | `scripts/git/check-guard-sync-divergence.sh` |
| Sync gate | `sync-attribution-guard-scripts.sh` calls `--workspace` first |
| Pre-push | `.githooks/pre-push` when `scripts/git/` changes |
| Skill | `orama-system/bin/orama-system/skills/guard-sync-divergence-guard/` |
| Hookify | `.claude/hookify.guard-sync-divergence.local.md` (orama) |
| Tests | `tests/test_check_guard_sync_divergence.py` (3 cases) |

## One PR per repo (do not fragment)

| Repo | PR | Branch |
| ---- | -- | ------ |
| PT | #319 | `cursor/guard-audit-hardening-f559` |
| orama | #255 | `2026-07-31-010-remediation-doctrine-phase6-sync` |
| AlphaClaw | #26 | `cursor/sync-attribution-guards-6421` |

## Agent rule

Before `sync-attribution-guard-scripts.sh`:

```bash
WORKSPACE_ROOT=/agent/repos bash scripts/git/check-guard-sync-divergence.sh --workspace
```

Exit 1 → HITL: promote sibling improvements to orama canonical on the open PR, then sync.

## Merge order

PT #319 → orama #255 → AlphaClaw #26
