# PR body anti-clobber enforcement plan

**Status:** enforced (2026-08-01) — Layers 1–6 active  
**Canonical reference:** `orama-system/bin/orama-system/references/pr-body-anti-clobber-incident-ledger.md`

**Trigger:** PT #314 clobbered again despite `lesson_3b13ab0a45d4`, `lesson_4a38f0e95fcf`,
`lesson_6fff093ccb00`, and `append-pr-body.sh` already existing.

## Incident ledger (documented)

| When | PR | Noticed by | Recovery |
| --- | --- | --- | --- |
| 2026-06-27 | PT #154 | Human / review | Integrative restore; became `lesson_3b13ab0a45d4` |
| 2026-07-27 | orama #222 | Human | Restored Summary + Follow-ups; `lesson_6fff093ccb00` |
| 2026-07-29 | PT #298, orama #239 | Human | `lesson_4a38f0e95fcf` |
| 2026-08-01 | PT #314 | Human (again) | Restored integratively this session |

**Documented clobber count:** 5 PRs across 4 incidents.  
**User-estimated silent rate:** ~5× not noticed → **~20–25 total** if the pattern holds.
Treat every `update_pr` with `body=` as high-risk until mechanically gated.

## Root cause (why agents keep forgetting)

1. **Cloud turn-end habit:** “update PR before summary” → `ManagePullRequest update_pr`
   with delta-only `body=` feels correct but **replaces** the whole field.
2. **Lessons ≠ hooks:** Rules live in memory and `.cursor/rules/` but nothing blocks the
   bad write at push time.
3. **Tool ergonomics:** `update_pr` is one call; `append-pr-body.sh` is four steps — agents
   shortcut under time pressure.
4. **Selective recall:** Append-only doctrine is recalled for memory/LESSONS edits, not
   reflexively for PR bodies.

## Enforcement ladder (implement in order)

### Layer 1 — Before any PR body write (mandatory)

```text
READ  → gh pr view <N> --json body
BACKUP → .git/pr-body-backups/<slug>-pr<N>-<ts>.md
MERGE  → original ## Summary + chronological ## Follow-up blocks
WRITE  → append-pr-body.sh OR gh pr edit --body-file merged.md (full body only)
```

**Never:** `update_pr` with `body=` containing only the latest remediation paragraph.

### Layer 2 — After commit, before push (new)

Run when the branch has commits not yet pushed **and** an open PR exists:

```bash
bash scripts/git/remind-pr-body-append-only.sh
```

- Prints open PR number + mandatory workflow if `gh pr list --head` matches.
- Exits 0 (reminder only) — does not block push by default.
- Set `PR_BODY_GUARD_STRICT=1` to **exit 1** unless `PR_BODY_UPDATE_ACK=1` after using
  `append-pr-body.sh`.
- **Default in `publish-clean-branch.sh`:** strict mode on (override with
  `PR_BODY_UPDATE_ACK=1`).

### Layer 3 — Inside audited publisher (new)

`publish-clean-branch.sh` calls `remind-pr-body-append-only.sh` immediately before
`git push --force-with-lease`.

### Layer 4 — Cursor rule always-on (sync gap closed)

- Canonical: `orama-system/.cursor/rules/append-only-pr-body.mdc` (`alwaysApply: true`)
- Add to `sync-attribution-guard-scripts.sh` rule sync list so PT/AlphaClaw get the same file.

### Layer 5 — Cloud agent checklist (process)

At end of every turn with code changes on a PR branch:

1. Did I touch PR body? If yes → prove backup exists under `.git/pr-body-backups/`.
2. Did I use `update_pr`? If yes → verify body still contains original `## Summary`
   (not delta-only).
3. If clobbered → recover before reporting done (see `lesson_6fff093ccb00`).

### Layer 6 — CI gate (active)

- `scripts/git/verify-pr-body-not-clobbered.sh <owner/repo> [pr]` — fail if body lacks
  `## Summary`
- Workflow: `.github/workflows/pr-body-guard.yml` (on PR edit + daily schedule)

## Agent recall anchors

When about to update a PR, proactively load:

- `lesson_3b13ab0a45d4` — append-only PR descriptions
- `lesson_4a38f0e95fcf` — `update_pr` replaces entire body
- `lesson_6fff093ccb00` — recovery procedure
- `scripts/cursor/append-pr-body.sh` — canonical write path

## Success criteria

- Zero delta-only `update_pr` body writes on open PRs with existing Summary.
- Every PR body update has a matching `.git/pr-body-backups/*` file in session artifacts or
  commit notes.

## ECC homunculus derivation (automated pipeline)

Session instincts materialize lessons into homunculus triggers agents recall under pressure.

| Step | Action | Artifact |
| --- | --- | --- |
| 1 | Close incident → append lesson | `lessons.jsonl` + episodic row |
| 2 | Write working doc with PR refs + evidence | `.agent/memory/working/*.md` |
| 3 | Curate 2–4 instincts (not bulk auto-dump) | `.claude/homunculus/instincts/inherited/guard-sync-pr314-2026-08-01.yaml` |
| 4 | Import locally | `/instinct-import <yaml> --dry-run` then `--force` |
| 5 | Verify | `/instinct-status` |
| 6 | Post-merge sync | `/ecc-sync` in each repo |

**PT stack (PR #314):** `guard-sync-pr314-2026-08-01.yaml` — downstream sync,
append-only PR body, remind-before-publish.

**Orama stack (PR #251):** `guard-sync-pr251-2026-08-01.yaml` — canonical-only edits,
tree-twin reanchor, append-only PR body.

**Checklist script (orama canonical):**
`bash ../orama-system/scripts/derive-pr-stack-instincts.sh --check`

User stops catching clobber incidents manually.
