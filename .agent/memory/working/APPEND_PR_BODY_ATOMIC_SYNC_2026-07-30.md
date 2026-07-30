# append-pr-body hardening + atomic guard sync (2026-07-30)

Follow-up to orama PR #239 CodeRabbit reviews `4813279644` and `4814845056`.

## orama PR #239 status (2026-07-30)

| Tip | `8948ccc4` |
|-----|------------|
| State | OPEN, MERGEABLE |
| CI | All green (CodeRabbit SUCCESS) |
| mergeStateStatus | UNSTABLE (aguara scan in progress at last check — non-blocking) |

Commits on branch:
- `654f8617` — append-pr-body hardening (TOCTOU, delimiters, title normalize, git-common-dir backups)
- `8948ccc4` — `atomic_install_file` in `sync-attribution-guard-scripts.sh`

## append-pr-body.sh invariants (canonical: orama `scripts/cursor/`)

1. **Mutual exclusion** — exactly one of `--file` or `--message`; error if both.
2. **Delimiter safety** — reject append content containing `CURSOR_AGENT_PR_BODY_END` or CodeRabbit marker; abort if existing body has >1 of either marker.
3. **Single insertion** — `${merged/pattern/repl}` (one replace), not global `//`.
4. **TOCTOU** — re-fetch `gh pr view` body immediately before `gh pr edit`; abort if changed since snapshot.
5. **Backups** — resolve `.git/pr-body-backups` via `git rev-parse --git-common-dir` (linked worktrees); `mktemp` suffix avoids same-second collisions.
6. **Title** — `normalize_follow_up_title()` ensures `Follow-up:` prefix without duplication.
7. **Temp cleanup** — `trap 'rm -f "$out"' EXIT` on body temp file.
8. **Docs** — manual workflows must `mkdir -p .git/pr-body-backups` before redirect (`integrative-editing-examples.md`, `AGENTS-cursor-cloud-git.md`).

**Skipped (hallucination):** CodeRabbit requests for LM Studio `LM_STUDIO_WIN_ENDPOINTS` preflight inside `append-pr-body.sh` or `sync-attribution-guard-scripts.sh` — no canonical guard exists under `scripts/git/`; unrelated to PR body / file sync.

## sync-attribution-guard-scripts.sh — atomic install

```bash
atomic_install_file() {
  tmp="$(mktemp "${dest_dir}/.$(basename "$dest").sync.XXXXXX")"
  install -m "$mode" "$src" "$tmp" || { rm -f "$tmp"; return 1; }
  mv -f "$tmp" "$dest" || { rm -f "$tmp"; return 1; }
}
```

Applies to all guard scripts, `append-pr-body.sh`, `pr.md`, and `.cursor/rules/*.mdc`. Preserves `target_input` in skip message when path is not a git repo.

## Propagation gap (PT #298 merged 2026-07-30)

PR #298 merged to `main` at `0732b9c` with append-pr-body hardening (`06d6ad4`) but **before** atomic sync (`8948ccc4`). Follow-up commit on `main` required for `sync-attribution-guard-scripts.sh` only.

**Do not commit** incidental local guard drift (truncated `audit_attribution.sh`, etc.) when pushing this follow-up — sync script only unless intentionally re-syncing full guard parity from orama.

## PR stack (updated)

| Repo | Branch | PR | Notes |
|------|--------|-----|-------|
| orama-system | `cursor/commit-clean-merge-aware-f559` | #239 | Ready to merge |
| Perpetua-Tools | `main` | — | #298 merged; atomic sync follow-up on main |
| AlphaClaw | `cursor/commit-clean-merge-aware-f559` | #19 | `af71699` includes atomic sync |
| periscope | — | — | Excluded from guard sync; PR #34 merged guard removal |

## Lessons staged

- `lesson_07171bc24c52` — append-pr-body TOCTOU/delimiter/title rules
- `lesson_622f5fa85352` — atomic_install in sync-attribution-guard-scripts
- `lesson_44bd40ba128b` — post-merge main follow-up when orama canonical advances after PR merge
