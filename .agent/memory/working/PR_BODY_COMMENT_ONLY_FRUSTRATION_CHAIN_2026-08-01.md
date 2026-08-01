# PR body frustration chain — comment-only doctrine (2026-08-01)

> **Status:** active Layer 0 prohibition on Cursor agents  
> **Open PR:** [#319](https://github.com/diazMelgarejo/Perpetua-Tools/pull/319) (`cursor/guard-audit-hardening-f559`)  
> **Canonical ledger:** `orama-system/bin/orama-system/references/pr-body-anti-clobber-incident-ledger.md`

## User intent (spirit of the plan)

Stop agents from **automatically rewriting PR summaries**. Progress belongs in **comments**,
not in the description field. The description is a historical record; agents kept treating
turn-end "update the PR" as permission to replace the whole body with the latest paragraph.

If a human **explicitly** authorizes a body edit, append-only rules still apply — never
delta-only clobber.

## Frustration chain (this wave)

| Step | What happened | Why it hurt |
| ---- | ------------- | ----------- |
| 1 | PT #314 merged guard manifest; CodeRabbit nitpicks left open | Drift between "merged" and "done" |
| 2 | PR #315 falsely claimed to supersede #314 | Would have removed tests — duplicate PR trap |
| 3 | Blind orama→PT `sync-attribution-guard-scripts.sh` risked clobbering PT hardening | Anti-clobber divergence guard born |
| 4 | PT #319 opened as **one PR** for guard wave | Correct consolidation |
| 5 | Agent `ManagePullRequest update_pr` with **delta-only** body on #319 | Erased original Summary + template sections |
| 6 | User asked if PR bodies were clobbered across 3 repos | PT #319 yes; orama #255 / AC #26 no |
| 7 | Integrative restore + Layer 7 hooks (append-only) | Still not enough — agents bypass by habit |
| 8 | **Layer 0** — comment only, hooks block **all** body writes | Top prohibition; override → Layers 1–6 |

## Layer 0 — what agents do now

| Do | Never (automatic) |
| -- | ----------------- |
| `ManagePullRequest post_comment` | `update_pr` with `body=` |
| `gh pr comment` | `gh pr edit`, `append-pr-body.sh` |

## Human override

```bash
export CURSOR_PR_BODY_HUMAN_OVERRIDE_ACK=1
```

Then: READ → BACKUP → MERGE → WRITE (`append-pr-body.sh` or `gh pr edit --body-file`).

## Enforcement stack

1. `.cursor/rules/pr-body-comment-only.mdc` (alwaysApply, top)
2. `.cursor/rules/append-only-pr-body.mdc` (override only)
3. Cursor hooks: `beforeSubmitPrompt`, `preToolUse`, `beforeMCPExecution`, `beforeShellExecution`
4. `scripts/cursor/hooks/pr-body-guard-core.py` (single decision core)
5. Hookify: `.claude/hookify.pr-body-comment-only.local.md`
6. `remind-pr-body-append-only.sh` at push time
7. CI: `verify-pr-body-not-clobbered.sh`

## Related memory on this branch

- `GUARD_SYNC_EPIC_SAGA_COMPLETION_2026-08-01.md`
- `GUARD_SYNC_DIVERGENCE_GUARD_2026-08-01.md`
- `PR_BODY_ANTI_CLOBBER_ENFORCEMENT_PLAN.md`

## Merge order (unchanged)

PT #319 → orama #255 → AlphaClaw #26
