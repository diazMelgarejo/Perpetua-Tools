# Session Bird's-Eye: Trust Infrastructure Across PT + orama-system

**Date:** 2026-08-08 (session spanned 2026-08-07 into 2026-08-08)
**Type:** index essay — reads first, links out to the detail essays
**Scope:** decodes the *why* behind a long multi-thread session before any
of the *what*. Per AFRP discipline: profile intent before delving into
specifics.

## AFRP read: what was the user actually optimizing for?

Taken thread by thread, this session looks like five unrelated jobs: a
version-bump reconciliation, a sibling-repo path resolver, a commit-message
hallucination check, a guard-hook harmonization, and a PT/orama synergy
plan. Read together, they are one motivation wearing five outfits:

**Stop trusting labels. Verify against reality, mechanically, before the
next person (human or agent) has to discover the gap the hard way.**

Every thread this session either (a) found a place where a *label* (a
commit message, a status report, a "safe to skip" default, a plan marked
`COMPLETE`) had quietly diverged from the *thing it described*, or (b)
built a small piece of infrastructure so that divergence gets caught
mechanically next time instead of by luck. This is not a new value for this
codebase — `docs/LESSONS.md` and PT's own `.agent/memory` are full of prior
instances of exactly this pattern (see Gold Nuggets below) — but this
session is the point where the pattern itself got automated rather than
re-applied by hand each time.

**The pinnacle framing the user asked for:** months of this project's
recurring lesson — "verify claims over labels," "an unconflicted merge is
not proof a fix survived," "trust the record, verify before acting" — is
what got *built into tooling* this session, not just re-learned. A commit-
msg hook that mechanically checks the exact failure mode a past commit
message once got away with. A scanner that finds the exact "discovered
during spring cleaning" pattern before the spring cleaning happens. A
sibling-repo resolver that replaces a guessed path with an actual git-marker
crawl. That is the throughline connecting five otherwise-separate arcs.

## The five threads, one paragraph each (detail essays linked)

1. **Hallucination prevention** — a commit message claimed an array entry
   was added; the diff only touched a comment. Built a mechanical check for
   exactly that, plus its sibling case (claiming a push/merge/branch state
   that doesn't match reality), plus a scanner for the adjacent failure
   mode (work claimed pushed that's actually stranded in a branch/worktree).
   → `HALLUCINATION_PREVENTION_ARC_2026-08-08.md`

2. **Sibling-repo discovery** — orama already had a robust crawler to find
   PT; PT had no equivalent, and several PT scripts guessed orama's
   location with a relative-path assumption that's wrong on this exact
   machine. Extracted the crawler into a shared, generic, marker-based
   primitive; built the missing reverse-direction resolver; fixed six sites
   that guessed wrong.
   → `SIBLING_REPO_DISCOVERY_ARC_2026-08-08.md`

3. **Guard-sync harmonization** — orama's and PT's `.githooks/commit-msg`
   had independently drifted into different shapes. Reconciled into one
   canonical, existence-guarded file; promoted two scripts that already
   happened to be byte-identical by coincidence into the formal sync
   manifest, closing a real (if quiet) zero-fragmentation gap.
   → `GUARD_SYNC_HARMONIZATION_ARC_2026-08-08.md`

4. **PT/orama synergy synthesis** — three independent research passes
   (one first-draft brief, two adversarial critiques that disagreed with
   *each other*, not just the brief) reconciled by hand into four minimal,
   doc-only fixes — deliberately not a list of "everything wrong," a list
   of "everything verified and worth fixing."
   → `PT_ORAMA_SYNERGY_SYNTHESIS_METHOD_2026-08-08.md`

5. **AlphaClaw OSSF-1 audit** — a separate automation's work (not built by
   this session), reviewed on request: a progressive-disclosure skill
   refactor and a "is history universal" question. Read-only diagnosis,
   found real small content drops and a real merge conflict against the
   PR's actual base — explicitly not touched, per the standing instruction
   to leave AlphaClaw's own engineering alone.
   → `ALPHACLAW_OSSF1_AUDIT_2026-08-08.md`

## Gold nuggets (small, digestible, load-bearing)

- **A tool that exits 0 is not more trustworthy than one that crashes — it
  is less scrutinized.** (Restated this session; first landed as
  `lesson_70713965dc1b`, 2026-08-07 vendor-blend retrospective.) Every arc
  above exists because a green checkmark or a clean-looking status report
  hid a real gap.
- **Bash 3.2's `"${empty_array[@]}"` raises "unbound variable" under
  `set -u` even after an explicit `arr=()`.** `"${#arr[@]}"` (count) is
  safe unconditionally; guard any `[@]` expansion with a count check first.
  Bit the sibling-repo crawler once, independently rediscovered while
  writing its test suite.
- **A CI test fixture that relies on ambient `init.defaultBranch` git
  config will pass locally and fail on any runner with a different
  default.** Pin the branch name explicitly (`git init -b main`) instead of
  trusting the environment.
- **`git diff --cached --diff-filter=U` (index-level) plus a literal
  `<<<<<<<`/`>>>>>>>` content scan are BOTH required** to confirm a
  cherry-pick or merge resolved clean — the index can be clean while a
  conflict marker was accidentally staged as literal file content, and
  rename/delete conflicts leave no textual markers at all. (Reconfirmed
  from PT's own AlphaClaw retrospective, `ALPHACLAW_UPSTREAM_SYNC_CRON_CI_
  2026-07-31.md`.)
- **A `--workspace`-style convenience shortcut that globs one directory
  level deep will silently skip any repo nested one level deeper** — and
  report `PASS` while doing it. Found in `check-guard-sync-divergence.sh`
  (PT sits under `perplexity-api/`), then found again independently in a
  hardcoded `$REPO_ROOT/../orama-system` default in six PT scripts. Same
  bug shape, two unrelated code paths — worth grepping for a third instance
  before assuming it's fully closed.
- **When two adversarial reviewers disagree with each other, don't average
  them — read the disputed file yourself and rule.** The synergy-plan
  synthesis found three points where the two critiques flatly contradicted
  each other; every one resolved cleanly once someone actually re-read the
  cited file instead of trusting either critique's prose.
- **"Leave X alone" and "review/diagnose X" are not the same instruction.**
  Read-only audits (reanchor scans, content diffs, `merge-tree` conflict
  checks) are compatible with a standing "don't touch" boundary; mutating
  the repo is not. Worth naming explicitly rather than assuming either
  reading.

## Cross-references

- `../../../docs/LESSONS.md` — PT's chronological lesson log; several of
  today's nuggets are restatements of entries already there, not new
  discoveries. This essay exists to connect them, not replace them.
- `$ORAMA_SYSTEM_PATH/docs/plans/2026-08-07-pt-orama-minimal-synergy-plan.md`
  — the actual synergy plan artifact (thread 4's output); resolve with
  `scripts/resolve_orama_root.sh` if the env var isn't set.
- `ALPHACLAW_UPSTREAM_SYNC_CRON_CI_2026-07-31.md` — prior-session AlphaClaw
  branch-model context this session's audit (thread 5) depended on.
