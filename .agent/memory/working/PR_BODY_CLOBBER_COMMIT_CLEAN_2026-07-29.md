# PR body clobber incident — commit-clean PR stack (2026-07-29)

## What happened

Cloud agent called `ManagePullRequest update_pr` with **delta-only** `body=` on PT #298 and orama #239, replacing the original Summary with the latest follow-up text. Same failure mode as PR #222 (Hermes) and `lesson_3b13ab0a45d4`.

## Recovery

1. Reconstructed original Summary from PR create record / session cache
2. Appended chronological `## Follow-up:` blocks (verify-staged dep, require_merge, sync/CI hygiene)
3. Restored via `ManagePullRequest update_pr` with **integrative full body** (raw markdown only — no `CURSOR_AGENT_PR_BODY_*` markers; API rejects them)

## Permanent fix

| Artifact | Location |
|----------|----------|
| Append script | `orama-system/scripts/cursor/append-pr-body.sh` |
| Cursor command | `orama-system/.cursor/commands/pr.md` |
| Cloud snippet | `scripts/git/snippets/AGENTS-cursor-cloud-git.md` |
| Wiki | `docs/wiki/12-cursor-cloud-commit-attribution.md` |
| CIDF | `bin/orama-system/cidf/SKILL.md` + `integrative-editing-examples.md` §1 |
| PT lesson | `lesson_4a38f0e95fcf` |

## Agent rule

**READ → backup → append → write full body.** Never `update_pr` with only the new paragraph.
