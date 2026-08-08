# Arc: AlphaClaw OSSF-1 Audit (Read-Only — AlphaClaw Itself Not Touched)

**Date:** 2026-08-08
**Parent essay:** `SESSION_BIRDSEYE_TRUST_INFRASTRUCTURE_2026-08-08.md`
**Boundary:** AlphaClaw is a mirror of an external upstream
(`chrysb/alphaclaw`) and this session's standing instruction was to leave
its engineering alone. This essay records a **diagnostic-only** pass —
reading, diffing, and reporting, never editing AlphaClaw's tree. See
`GUARD_SYNC_HARMONIZATION_ARC_2026-08-08.md` for where that boundary was
also respected on the guard-tooling side.

## Two direct questions, answered with evidence, not paraphrase

### 1. Is the rewritten git history universal across all local branches/worktrees?

Ran the canonical tree-twin scan (`reanchor_scan.sh`, orama-system) across
every local AlphaClaw branch. Every branch — including the one under
active discussion — reports `NEEDS-REANCHOR` against the *same* rewritten
`origin/main` root commit. Read correctly, that is the consistent answer:
every branch measures divergence against one shared rewritten baseline,
so the rewrite is universal, not partial or inconsistent. `NEEDS-
REANCHOR` alone is expected staleness for any long-lived branch that
hasn't rebased recently — per the tree-twin doctrine, it requires a
`git cherry -v` pass per branch before treating the flagged commit count
as real lost work, not an automatic alarm.

A third, forgotten scratch worktree turned up during the same pass,
detached HEAD, which `git worktree list` itself already flags
`prunable`. Noted, not removed — cleanup is a separate, explicit action.

### 2. Did the OSSF-1 progressive-disclosure split lose material from the prior synthesis?

Diffed the pre-OSSF-1 376-line monolithic `SKILL.md` against the new
orchestrator (≤200 lines) plus its four reference cards, section by
section, then confirmed every suspected drop with a repo-wide `grep`
across the new files (not just a visual scan).

**Genuinely dropped, confirmed absent:**

- The `isMacOS()` code example under Platform-Specific Support.
- The "Don't write vague commit messages" bullet.
- The "thin Hermes stub bodies" specific detail under the
  don't-hand-edit-`~/.openclaw/` rule (the broader rule survived; this
  one example under it did not).
- 3 of 8 original commit-message examples — 2 were non-conventional-
  style outliers arguably worth trimming on purpose, 1
  (`fix(platform): address code review issues...`) was a legitimate
  example lost with no replacement.

**Looked dropped, actually just relocated:**

- The `new-feature.js` implementation-plus-test example moved into the
  main `SKILL.md`'s golden-path section.
- Several Do/Don't bullets moved from a "Best Practices" section into
  the orchestrator's `Instructions` step list instead of its `Boundaries`
  section.

**Genuine improvements, not losses:**

- "Ask First" is a new third tier the old flat Do/Don't list never had.
- The pytest-ban and Express-4-only rules were promoted from buried prose
  mentions into explicit, scannable boundary bullets.

**The irony worth naming:** this exact skill's own `Never Do` list says
never let a merge "silently drop ECC bundle paths — restore additively,"
and its own synthesis-lineage reference file prides itself on merging
generations "rather than letting any single version replace the others."
The OSSF-1 pass itself dropped a few small details without logging them
in that same file's "Fixed, not preserved" ledger — which lists three
legitimate, deliberate fixes but is silent on the four items above.
Small stakes (examples and single bullets, not rules or workflows), but
exactly the kind of gap this skill's own stated standard would flag if
applied to itself.

### 3. An unasked but load-bearing third question: is this actually mergeable?

The PR's real base branch is not `main` — checked via `gh pr view`, which
also reports the PR as `CONFLICTING`. Confirmed the specific cause with
`git merge-tree` against the actual base: a **second, parallel skill
mirror** exists at a different path from the one reviewed above (a
`.agents/`-rooted copy, distinct from the `.claude/`-rooted one that
received the OSSF-1 treatment). That second mirror never got the same
refactor and has independently drifted from the PR's real base on the
same set of files (the ECC manifest, an identity file, a harmonization
report doc). Pushing the reviewed branch's current local head as-is would
land a PR with real conflicts to resolve, not a clean fast-forward.

## Why this matters for the mirror-drift pattern named elsewhere

The PT/orama synergy critique (cursor-agent's pass, see
`PT_ORAMA_SYNERGY_SYNTHESIS_METHOD_2026-08-08.md`) separately flagged
PT's own `.agents/skills/` mirror forest as "positive synergy when
synced, silent drift when not" — a hypothesis, not a confirmed problem,
at the time it was written. This AlphaClaw audit is a live, concrete
instance of exactly that failure mode occurring in a *different* repo's
*own* dual-bundle setup (`.claude/` vs `.agents/`) — the same architectural
pattern, the same risk, independently confirmed rather than merely
theorized.

## Cross-references

- `SESSION_BIRDSEYE_TRUST_INFRASTRUCTURE_2026-08-08.md`
- `GUARD_SYNC_HARMONIZATION_ARC_2026-08-08.md` — the "leave AlphaClaw's
  engineering alone" boundary this essay's diagnostic-only framing
  respects.
- `PT_ORAMA_SYNERGY_SYNTHESIS_METHOD_2026-08-08.md` — the mirror-drift
  hypothesis this audit independently confirms in a sibling repo.
- `ALPHACLAW_UPSTREAM_SYNC_CRON_CI_2026-07-31.md` — the branch-role model
  (`main` = pure upstream mirror, `feature/MacOS-post-install` = the real
  integration line) this audit's findings should be read against.
