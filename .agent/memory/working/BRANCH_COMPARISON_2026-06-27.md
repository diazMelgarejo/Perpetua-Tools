# Branch catalog (tree-twin / reanchor_scan)

Generated: **2026-06-27** (corrected — supersedes mistaken merge-base catalog)

> **Method:** `scripts/git/reanchor_scan.sh . origin/main heads` + `git cherry -v` for `+` commits.
> **Never use** ahead/behind counts or `merge-base exit 1` alone after a history rewrite — see
> [`docs/LESSONS.md`](docs/LESSONS.md) § 2026-06-05 and orama
> [git-history-surgery `reanchor-after-rewrite.md`](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/git-history-surgery/references/reanchor-after-rewrite.md).

## Correction: `cursor/critical-bug-investigation-0df5`

The prior snapshot classified this branch as **unrelated history** (no merge-base) and implied
**647 behind** `origin/main`. That was **wrong** — a rewrite-boundary artifact.

| Field | Mistaken (merge-base) | Correct (tree-twin) |
|-------|----------------------|---------------------|
| Status | unrelated / orphan | **MERGED/in-main** |
| Tip on branch | `c1ae82e` | twin on main: `ad702c5` (same tree, same subject) |
| Action | do not rebase | **re-anchor ref to twin** or delete local branch |
| Work remaining | unknown | **none** (`git cherry` shows no `+` commits vs main) |

**Re-anchor applied (local):** worktree `pt-pr50-review` detached at `ad702c5`; branch ref
`cursor/critical-bug-investigation-0df5` → `ad702c5`.

## Perpetua-Tools — reanchor_scan summary

Run: `scripts/git/reanchor_scan.sh . origin/main heads`

### MERGED/in-main (safe to delete local after review)

`2026-05-27-009-fix4-5-path-boundary-mcp`, `2026-05-28-004-dependabot-security-bumps`,
`2026-06-06-001-model-bump-opus-4-8-and-prompt-caching`,
`cursor/critical-bug-investigation-0df5`, `cursor/critical-bug-investigation-a924-followup`,
`feat/ip-aware-discovery`, `feat/perpetua-submodule-upgrade`, `fix/pt71-clean`,
`lesson-pt126-local`, `rebase-pt126-local`, `rebase-pt127-local`, `wip/preserve-20260614`

### NEEDS-REANCHOR (graft onto twin — verify `+` with cherry before PR)

| Branch | Graft | Cherry `+` highlights |
|--------|-------|----------------------|
| `chore/domain-knowledge-windows-shims` | 1 onto `9db5cf4` | DOMAIN_KNOWLEDGE Windows shims doc |
| `clean-pt127` | 1 onto `668bf91` | routing idempotency bundle (check vs main) |
| `2026-06-11-001-win-endpoint-discovery-sync` | 5 onto `bea476a` | live probe routing + gateway precedence |
| `fix/ci-69`, `fix/ci-71`, `fix/pt71-*` | varies | see LESSONS § salvage audit — many already in main as tree diffs |
| `2026-04-25-perpetua-recovery`, `tmp-pr42-test`, `wt-pr42`, `temp-recovery`, `recover/*` | 1–2 | investigate before delete |

### Open PR candidates (non-rewrite metrics)

| Priority | Branch | Notes |
|----------|--------|-------|
| P1 | `chore/domain-knowledge-windows-shims` | 1 doc commit; landed on main working tree this session |
| P2 | `2026-06-11-001-win-endpoint-discovery-sync` | routing — diff vs main before PR |
| P3 | `clean-pt127` | subset of routing branch |

## orama-system — reanchor_scan summary

All local branches share merge-base with `origin/main` (no ORPHAN class). Large June branches
(`2026-06-13/14-*`) show **+ahead / -behind** vs old merge-base `a156104` — treat as **stale
integration branches**, not unrelated history. Prefer tree-twin + cherry before any rebase.

| Branch | Action |
|--------|--------|
| `fix/pr135-lint006-windows` | LINT-006 Windows paths — landed on main working tree |
| `wip/vitest-scratch` | TDD gate + vitest — merged into main working tree |
| `feat/hermes-harness-onboarding` | merged via PR #108; local branch behind origin |

## Hermes harness — offline vs live Windows

| Phase | Status | Blocker |
|-------|--------|---------|
| 1–5, 7–8 | on main via PR #108 | — |
| 6 canaries | script + tests + `--prepare` | live Win localhost |
| 9 thin wrappers | `install_hermes_thin_skills.py` | live Win localhost |
| 11 installer verify | pytest `test_hermes_thin_skills.py` | partial on Mac |

**When Win Coder is online (localhost):** run
`verify_partner_canaries.py` and `install_hermes_thin_skills.py --verify` per
`bin/orama-system/skills/hermes-harness/references/win-localhost-runtime-checklist.md`.

## Commands (canonical)

```bash
# Perpetua-Tools
cd perplexity-api/Perpetua-Tools
scripts/git/reanchor_scan.sh . origin/main heads
git cherry -v origin/main <tip> <twin-base-from-scan>

# Case A re-anchor (tip already in main)
git branch -f <branch> <twin-sha>   # or detach worktree at twin first
```
