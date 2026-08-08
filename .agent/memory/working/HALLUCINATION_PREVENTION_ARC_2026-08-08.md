# Arc: Hallucination Prevention (Commit Claims + Stranded Work)

**Date:** 2026-08-07 → 2026-08-08
**Parent essay:** `SESSION_BIRDSEYE_TRUST_INFRASTRUCTURE_2026-08-08.md`
**Repo:** orama-system canonical, synced to PT

## The incident that started it

A commit message said "Added to `guard-sync-manifest.sh`'s
`GUARD_SYNC_EXECUTABLES`" — the intent was real, but the actual staged diff
that commit only touched a header *comment*, never the array body. The
array entry got added in a *later* commit. Caught only because a sync
script that depended on the array silently produced nothing, not because
anyone re-read the diff against the message.

This is a narrow, structural, checkable claim — not a judgment call — which
is exactly the category of thing worth automating rather than re-catching
by vigilance each time.

## What got built

**`scripts/git/check_commit_message_claims.py`** (new, wired into
`.githooks/commit-msg`), two independent checks in one script:

1. **Identifier-claim check.** Scans the commit message for an
   add/register/introduce verb within ~40 characters of a code-symbol-
   looking token — either backtick-quoted, or a bare `UPPER_SNAKE_CASE`
   identifier (the bare form matters: the real incident commit never used
   backticks around the array name). If the claimed identifier doesn't
   appear in any `+`-prefixed line of `git diff --cached`, the commit is
   blocked.

2. **Git-state-claim check.** Scans for "pushed to `<ref>`", "merged into
   `<ref>`", "on branch `<ref>`" and verifies each against real git state
   (remote-tracking ref existence, ancestor-reachability, current branch)
   rather than trusting the prose.

**`scripts/git/find_stranded_work.sh`** (new, read-only) — a broader net
for the same failure family: crawls every known sibling repo and every git
worktree of any of them, flags branches with no upstream at all, branches
ahead of their upstream (unpushed commits — printed with sha + subject),
and dirty worktrees. This is the mechanical version of "discovered during
spring cleaning, 2-3 months later."

## Calibration: why block instead of warn

Prior art surfaced during research (`dos-kernel`'s `commit-audit`,
`blasrodri/truth`) block on this same category — a *structural* fact
check (does the diff contain the named token; does the ref actually
resolve), not free-form NLP inference over prose. `ProofGate` deliberately
keeps NLP-parsed claims warning-only, because "reading authorship intent
out of English is not reliable enough to stop an honest merge." Both
checks built here stay on the blocking side of that line on purpose:
identifier-presence and ref-resolution are binary, checkable facts, not
inferred intent.

## Two real bugs found while building this, not before

- **`set -e` + a bare failing command-substitution assignment.** A
  refactor introduced `path="$(cmd)"; rc=$?` at the top level of a
  function under `set -euo pipefail` — under bash's rules, the assignment
  itself is subject to `errexit`, so a non-zero `cmd` aborted the whole
  script silently, before the `rc=$?` line ever ran. Fixed by folding the
  rescue into the same statement: `path="$(cmd)" || rc=$?`.
- **Bash 3.2's empty-array-under-`set -u` pitfall** — see the bird's-eye
  essay's Gold Nuggets; found independently here while writing the
  generic crawler this check shares with the sibling-repo resolver (see
  `SIBLING_REPO_DISCOVERY_ARC_2026-08-08.md`).
- **CI-only test failure**: a test helper's `git init -q` relied on the
  ambient `init.defaultBranch` config being `main` — true on the dev
  machine, not guaranteed on the CI runner. Fixed with an explicit
  `git init -q -b main`.

## Explicitly not built (named, not silently skipped)

- No Claude-Code-level "phantom edit" checksum hook (checksum a file
  before Write/Edit, compare after, catch "I updated the file" when it's
  byte-identical) — real prior art (`spyrae/truthguard`) does this, but
  it's a different wiring layer (Claude Code tool hooks) than the git
  hooks built here. Flagged as a future option, not implemented.
- No general "tests pass" receipt-verification (`blasrodri/truth`'s
  strongest feature — refuses a "tests pass" claim with no recorded run).
  Out of scope for this arc; the two checks here are narrowly about git
  state and diff content, not command-execution claims.

## Cross-references

- `SESSION_BIRDSEYE_TRUST_INFRASTRUCTURE_2026-08-08.md` — why this arc
  exists in the first place.
- `SIBLING_REPO_DISCOVERY_ARC_2026-08-08.md` — shares the generic
  marker-based crawler primitive with `find_stranded_work.sh`.
- `GUARD_SYNC_HARMONIZATION_ARC_2026-08-08.md` — how these new scripts got
  wired into both repos' commit-msg hook chains without forcing the hooks
  system onto a repo that never opted in.
