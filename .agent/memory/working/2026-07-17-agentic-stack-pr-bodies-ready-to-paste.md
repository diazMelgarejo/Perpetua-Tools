# agentic-stack Upstream PRs — ready to paste

Fork: https://github.com/diazMelgarejo/agentic-stack (created 2026-07-17)
All 3 branches pushed and ready. PR creation blocked on token scope
(`contents:write` only, no `pull_request:write` against a repo we don't
own) — same limitation hit on every PR-creation attempt this whole session.
Compare links below open GitHub's PR-creation form pre-filled with the diff;
paste the title + body, then click "Create pull request".

---

## PR #1 (pilot) — base `master`

**Compare:** https://github.com/codejunkie99/agentic-stack/compare/master...diazMelgarejo:agentic-stack:atomic-01-episodic-mirror-fix?expand=1

**Title:** `fix(memory): stage() mirrors manual lessons into AGENT_LEARNINGS.jsonl`

**Body:**

```markdown
## Summary

`stage()`'s manual-lesson path writes a candidate with `evidence_ids: [now]`,
promising an episodic record exists at that timestamp in
`AGENT_LEARNINGS.jsonl` — but never writes one. The auto-derived candidate
path mirrors correctly; the manual path doesn't. Result: a graduated
lesson's `evidence_ids` can point at a timestamp with no matching episodic
record.

## Fix

Adds `_append_episodic_mirror()`, using the same timestamp so
`evidence_ids[0]` resolves to a real episodic record. Manual staging
**enforces mirror-write success**: the candidate is serialized to a temp
file in `CANDIDATES`, the mirror append runs next (write errors
propagate), and only then is the candidate published with `os.replace`.
A visible staged candidate never carries a dangling `evidence_ids`
value. Minimal, additive, stdlib-only.

## Verification

- Applied cleanly to `master` @ `00eda65c`, syntax-checked.
- Isolated functional test: `stage()` now writes exactly one episodic
  mirror whose timestamp equals the candidate's `evidence_ids[0]`.
- 3 unit tests (see commit 2, kept separate — see below), all passing.
- Found and fixed downstream in
  [Perpetua-Tools](https://github.com/diazMelgarejo/Perpetua-Tools), which
  vendors this project (`vendor/agentic-stack`). Validated there in two
  ways: 3 unit tests, and 6 real, non-test invocations of the fixed
  `learn.py` — all 6 evidence_ids verified programmatically to resolve to
  exactly one matching episodic record. Both are on PT `main`, commits
  `95f047f` (fix) and `61dee0d` (real-world validation), if useful
  cross-reference.

## Two commits, intentionally separate

1. `fix(memory): ...` — the fix alone.
2. `test(memory): ...` — a standalone `unittest` (no pytest or other
   third-party dependency, since this project doesn't currently ship a
   test harness). Kept as a **separate commit specifically so you can
   cherry-pick it out** if you'd rather merge the fix without introducing
   the project's first test file this way.

**Question for you:** would you like the test included as-is, dropped, or
adapted to a different location/convention? Fully open to whatever fits
this project — this is offered as a starting point, not a requirement.

## Background check

Searched open/closed issues and PRs for `episodic`, `evidence_ids`,
`mirror` — no duplicate report. (#13 is a related-but-different gap:
adapters not auto-populating the episodic log at all; this fix is about
the manual-stage path specifically not mirroring.)

## Note on this PR and its siblings

This is PR 1 of 3 prepared together as a small, related set (each stacked
on the previous: #2 will be based on this branch, #3 on #2) — separated so
each can be reviewed and merged on its own merit, but designed as a set.
Opening this one first; happy to hold #2/#3 until this lands, or open them
now for visibility — your call, mentioned here for transparency rather
than surprising you with a queue.
```

---

## PR #2 — base upstream `master` (stacked branch ancestry on the fork; open after #1 for cleaner review, but the GitHub base is always `master`)

**Compare:** https://github.com/codejunkie99/agentic-stack/compare/master...diazMelgarejo:agentic-stack:atomic-02-utf8-encoding-fixes?expand=1

**Title:** `fix(io): force UTF-8 on stdout/stderr and candidate writes`

**Body:**

```markdown
## Summary

Two related Windows-compatibility fixes in `.agent/tools/learn.py`:

- Reconfigure `stdout`/`stderr` to UTF-8 (`errors=replace`) at import, so a
  lesson claim containing non-ASCII text doesn't raise
  `UnicodeEncodeError` under a `cp1252` console on Windows.
- Write the candidate JSON with explicit `encoding="utf-8"` rather than the
  platform default, so candidates round-trip identically across OSes.

Both are additive and safe (the `stdout` reconfigure is guarded by
`hasattr`, a no-op where unavailable).

## Verification

Applied cleanly on top of #1 (this branch is based on
`atomic-01-episodic-mirror-fix`), syntax-checked. Found and applied
downstream in Perpetua-Tools; contributing back.

## Stack

2 of 3 in a small related set — based on #1, #3 will be based on this. See
#1's description for the full context; each stands on its own merit.
```

---

## PR #3 — base upstream `master` (stacked branch ancestry on the fork; open after #2 for cleaner review, but the GitHub base is always `master`)

**Compare:** https://github.com/codejunkie99/agentic-stack/compare/master...diazMelgarejo:agentic-stack:atomic-03-context-manager-fix?expand=1

**Title:** `fix(io): use a context manager in _lesson_already_appended`

**Body:**

```markdown
## Summary

The read-only probe in `_lesson_already_appended` opened `lessons.jsonl`
with a bare `open()` and relied on GC to close the handle. Wraps it in a
`with` statement (plus explicit `encoding="utf-8"` for cross-platform
consistency) so the file descriptor is released deterministically.
Behavior is otherwise unchanged.

## Verification

Applied cleanly on top of #2, syntax-checked, full stack's tests still
pass (3/3). Found and applied downstream in Perpetua-Tools; contributing
back.

## Stack

3 of 3 in a small related set — based on #2 (which is based on #1). See
#1's description for the full context.
```

---

## Order of operations

1. Open PR #1 against upstream `master` (compare URL above).
2. Open PR #2 against upstream `master` (same base). Until #1 merges, the
   GitHub diff is cumulative (`#1` + `#2` commits); after #1 merges it
   collapses to `#2`'s own delta. Preferred review order is still #1 then
   #2, but the merge base stays `master` — never a fork-only predecessor.
3. Open PR #3 against upstream `master` the same way.

All 3 branches and their commits already exist on the fork right now —
this ordering is about review clarity, not about doing any more code
work. Fork predecessor branches remain the *git* parents of later
branches; they are not used as GitHub PR bases on upstream.
