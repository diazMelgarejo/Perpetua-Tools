# PLAN — agentic-stack Patch Overlay Catalog + Upstream Contribution

Date: 2026-07-16
Status: **plan only, not executed** — for manual review before any branch/PR
is created
Author context: written immediately after fixing and validating the
learn.py episodic-mirror gap (PT `main` @ `702f08f`), while that fix is the
freshest, cleanest, most-proven candidate for upstream contribution

---

## Investigation summary (Phase 0 evidence, already gathered)

- `vendor/agentic-stack` is a git submodule pinned at `00eda65c`
  (upstream `codejunkie99/agentic-stack`, branch `master`).
- **PT's pin is current**: `git compare 00eda65c...master` → `ahead_by: 0,
  behind_by: 0, status: identical`. The submodule itself is not stale.
- The "mutation" is entirely in the **blended overlay** —
  `.agent/.agentic-stack-blend-state.json` tracks 16 files under
  `last_blend.applied_clean` that carry local patches on top of the
  vendored skeleton (UTF-8 encoding fixes, context-manager fixes, PT's
  `path_hygiene.sanitize_tracked_path_leaks` integration, and now the new
  episodic-mirror fix, not yet recorded).
- No fork of `codejunkie99/agentic-stack` exists yet under `diazMelgarejo`.
- Diffed PT's blended `tools/learn.py` against the actual vendor file at
  the pinned SHA directly (fetched via GitHub API/raw). Confirmed exactly
  6 categories of local patch, cleanly separable:

| # | Patch | Portable upstream? | Depends on PT-only code? |
|---|---|---|---|
| 1 | UTF-8 stdout/stderr reconfigure at import | Yes | No |
| 2 | `_lesson_already_appended`: bare `open()` → `with open(..., encoding="utf-8")` | Yes | No |
| 3 | `path_hygiene.sanitize_tracked_path_leaks` on claim + rationale | No — imports a PT-only module | Yes |
| 4 | Candidate-file write: `open(path, "w")` → `open(path, "w", encoding="utf-8")` | Yes | No |
| 5 | **`_append_episodic_mirror()` — the episodic-mirror fix** | Yes | No (uses only `os`, `json`, stdlib) |
| 6 | Call site wiring for #5 inside `stage()` | Yes | No |

**5 of 6 categories are portable as-is.** Only #3 needs PT's own
`path_hygiene` module, so it stays PT-local — not a candidate for this
upstream batch.

---

## Goal 1 — PT-side: keep the patch overlay catalog current (own repo)

### Pilot branch: `PT` → `agentic-stack-blend-state-sync`

**Scope:**
- Update `.agent/.agentic-stack-blend-state.json`: add a new
  `last_blend` entry (or append to `applied_clean` with a dated sub-note)
  recording the episodic-mirror fix, following the file's own existing
  precedent (the 2026-07-12 entry already documents a prior blend event
  with a lesson learned — same shape, new event).
- Cross-link `scripts/git/agentic-stack-vendor.md`'s "Current pin" section
  to the new catalog entry so a future reader doesn't have to reconstruct
  this investigation from scratch.
- **Do not** touch `vendor/agentic-stack` itself (union-merge doctrine:
  never commit blended output into the submodule — this stays a
  PT-side-only tracking update).

**Acceptance criteria:**
- `.agent/.agentic-stack-blend-state.json` is valid JSON, `last_blend`
  reflects the current state accurately (target_sha, applied_clean list,
  any conflicts).
- Repo hygiene passes.
- No changes to `vendor/agentic-stack` gitlink (pin stays `00eda65c` since
  it's already current).

**Non-goals:**
- Not bumping the submodule pin (nothing to bump — already at upstream tip).
- Not touching the 15 other already-catalogued files in this pass — only
  adding the new entry.

---

## Goal 2 — Upstream contribution: fork + stacked PRs

### Setup (one-time, before any pilot PR)

1. Fork `codejunkie99/agentic-stack` → `diazMelgarejo/agentic-stack`.
2. Clone the fork, add `upstream` remote pointing at
   `codejunkie99/agentic-stack`, confirm `master` matches PT's pinned SHA
   (`00eda65c`) exactly — already confirmed via API diff above.
3. Base branch for the whole stack: `master` (upstream's default branch,
   as named in the request).

### Stacking model

```
upstream/master (00eda65c)
  │
  └── fork/atomic-01-episodic-mirror-fix        (PR #1 — pilot)
        │
        └── fork/atomic-02-utf8-encoding-fixes  (PR #2, stacked on #1)
              │
              └── fork/atomic-03-context-manager-fix  (PR #3, stacked on #2)
```

Each branch is created FROM the previous one (`git checkout -b atomic-02
atomic-01`), so PR #2's diff view only shows its own delta once PR #1
merges — standard stacked-PR practice. Each PR opens against **upstream**
`codejunkie99/agentic-stack:master`, not against the fork's own default
branch.

### Pilot: PR #1 — `atomic-01-episodic-mirror-fix`

**This is "the last one we did"** — the freshest, most proven improvement,
and the best pilot because:
- Fully self-contained (stdlib only, no PT-specific imports).
- Already validated twice: unit tests (`tests/test_learn_episodic_mirror.py`,
  3/3) AND real-world use (6 real `learn.py` invocations, 6/6 evidence_ids
  verified to resolve, committed as `61dee0d` on PT).
- Fixes a genuine bug in the vendored tool itself, not a PT-specific
  customization — squarely in scope for upstream, not something PT should
  have to carry as a local patch forever.

**Branch:** `atomic-01-episodic-mirror-fix` (on the fork, based on
upstream `master` @ `00eda65c`)

**File touched:** `.agent/tools/learn.py`

**Diff to replay** (translated onto the **unmodified vendor file**, not
PT's blended copy — the vendor file has none of patches #1–4 or #6 above,
so this diff must apply cleanly to the pristine upstream version):

```diff
--- a/.agent/tools/learn.py
+++ b/.agent/tools/learn.py
@@ -54,6 +54,37 @@ def _lesson_already_appended(cid):
     return False
 
 
+def _append_episodic_mirror(cid, claim, ts, source="learn"):
+    """Mirror a manual stage into AGENT_LEARNINGS.jsonl so evidence_ids
+    referencing `ts` resolve to a real episodic record — matching the
+    auto-derived candidate path's existing behavior. Never raises; a
+    failure here must not block staging.
+    """
+    episodic_path = os.path.join(BASE, "memory/episodic/AGENT_LEARNINGS.jsonl")
+    entry = {
+        "timestamp": ts,
+        "skill": "learn",
+        "action": f"manual-stage:{cid}",
+        "result": "success",
+        "detail": f"Manually staged lesson {cid} via .agent/tools/learn.py: {claim!r}",
+        "pain_score": 1,
+        "importance": 6,
+        "reflection": "",
+        "confidence": 0.9,
+        "source": {"skill": "learn", "profile": "manual", "run_id": f"manual_{cid[:6]}"},
+        "evidence_ids": [ts],
+    }
+    try:
+        with open(episodic_path, "a", encoding="utf-8") as f:
+            f.write(json.dumps(entry) + "\n")
+    except OSError:
+        pass  # fail-open: staging must succeed even if the mirror write fails
+
+
 def stage(claim, conditions, source="learn", importance=7):
     os.makedirs(CANDIDATES, exist_ok=True)
     cid = pattern_id(claim, conditions)
@@ -78,6 +109,7 @@ def stage(claim, conditions, source="learn", importance=7):
     path = os.path.join(CANDIDATES, f"{cid}.json")
     with open(path, "w") as f:
         json.dump(candidate, f, indent=2)
+    _append_episodic_mirror(cid, claim, now, source)
     return cid, path
```

**Test to include** (adapted from `tests/test_learn_episodic_mirror.py`,
already proven against this exact function — needs path adjustment only,
since upstream's repo layout is `.agent/tools/learn.py` directly at repo
root rather than nested under a PT-style `tests/` directory; confirm
upstream's actual test convention before placing the file).

**PR description should include:**
- The bug: `stage()` writes `evidence_ids: [now]` but never creates a
  matching episodic record — a promise with nothing behind it.
- The fix: minimal, additive, fail-open.
- The proof: link to (or inline) the validation evidence — 3 unit tests +
  6 real-world invocations with 6/6 verified resolving evidence_ids.
- Explicit note that this was found and fixed downstream (PT), and is
  being contributed back per this project's own dogfooding practice.

### Later stacked PRs (catalog only, not detailed here — do after #1 merges)

- **PR #2** (`atomic-02-utf8-encoding-fixes`): patches #1 and #4 from the
  table above — stdout/stderr UTF-8 reconfigure, `encoding="utf-8"` on
  the candidate-file write. Low-risk, mirrors upstream's own likely
  Windows-compatibility interest.
- **PR #3** (`atomic-03-context-manager-fix`): patch #2 — bare `open()` →
  context-managed `open()` in `_lesson_already_appended`. Resource-safety
  fix, same class as this session's earlier CodeRabbit sweep findings.
- Beyond these 3, the other 13 files in the `applied_clean` catalog need
  the same diff-against-pristine-vendor treatment before they can be
  scoped into further stacked PRs — not done in this plan, flagged as
  follow-up once the pilot's reception from upstream is known.

---

## Open questions for review (do not proceed past these without answers)

1. **Fork ownership**: create under `diazMelgarejo`, or a different
   account/org? (Plan assumes `diazMelgarejo` — matches the pattern of
   this project's other repos.)
2. **PR #1 test placement — checked, and there's nothing to match.**
   Searched the full vendor tree at the pinned SHA: **zero test files of
   any kind** (`.py`, `.mjs`, `.js`) anywhere in `codejunkie99/agentic-stack`.
   No existing convention to follow. Options: (a) include the 3 tests
   inline in the PR as the first test file the project gets, in a
   sensible default location (e.g. `.agent/tools/test_learn.py` next to
   the module, plain `unittest`/no dependency, since there's no pytest
   config to hook into either); (b) submit the fix without tests and
   mention the PT-side test suite exists as a reference if upstream wants
   it; (c) ask in the PR description which the maintainer prefers before
   assuming. **Recommend (a)** — a fix plus its regression test is a
   stronger, more mergeable contribution than a fix alone, and zero
   existing convention means no risk of conflicting with one.
3. **Timing**: open PR #1 alone first and wait for upstream feedback
   before stacking #2/#3, or prepare all 3 stacked branches up front and
   open them in sequence regardless of #1's review status? (Plan defaults
   to the former — lower risk, standard stacked-PR practice waits for the
   base PR's review signal before continuing to stack, though the branches
   can still be prepared locally in advance.)
4. **`CONTRIBUTING.md` / PR template — checked, neither exists.** No
   contribution guide, no PR template anywhere in the tree. The repo has
   4 open issues (per the API check above) but that wasn't cross-referenced
   against this specific fix — worth a quick look before opening PR #1 in
   case someone already reported this exact bug, to reference the issue
   number in the PR rather than duplicating the report.

---

## EXECUTION STATUS — 2026-07-17 (fork created, branches pushed, PRs need manual creation)

All planning decisions approved by operator. Fork created by operator at
https://github.com/diazMelgarejo/agentic-stack. All 3 stacked branches
pushed successfully (`contents:write` was sufficient for pushing to our own
fork). PR creation against `codejunkie99/agentic-stack` still returns 403
(`Resource not accessible by personal access token`) — same limitation hit
on every PR-creation attempt this session; opening a PR against a repo we
don't own needs `pull_request:write`, which this token doesn't have.

**Ready-to-paste titles, bodies, and compare URLs for all 3 PRs:**
`.agent/memory/working/2026-07-17-agentic-stack-pr-bodies-ready-to-paste.md`

### Issue background check (Goal 2, done)

- Upstream open issues: only #51 (OpenCode warning) and #54 (partnership
  inquiry) — neither related.
- Searched all issues/PRs for `episodic`, `evidence_ids`, `mirror`: the only
  `episodic` hits are #45 (upgrade verb) and #13 (pi adapter missing
  tool-call logging). **#13 confirmed NOT our bug** — it's about adapters not
  auto-populating the episodic log at all; ours is `stage()` not mirroring a
  specific manual event. No duplicate report exists. PR #1 introduces the
  topic fresh.
- Upstream has **no** `CONTRIBUTING.md`, **no** PR template, **no** test
  suite anywhere in the tree. Titles follow Conventional Commits
  (`feat:`, `feat(memory):`).

### The constellation (Goal 2) — 3 stacked branches, built on pristine upstream `00eda65c`

Prepared in a scratch checkout (`agentic-stack-fork/`, sibling to the repo
checkouts), bundled to `agentic-stack-atomic-prs.bundle`, patches in
`agentic-stack-patches/`. All 3 branches are now live on the fork itself
(see EXECUTION STATUS below) — the local scratch copy was working storage,
not a tracked artifact.

```
upstream/master (00eda65c, pristine — verified identical to PT's vendor pin)
  └── atomic-01-episodic-mirror-fix     PR #1 (pilot)
        │   commit 1: fix(memory): stage() mirrors manual lessons ...
        │   commit 2: test(memory): cover the manual-stage episodic mirror  ← separable
        └── atomic-02-utf8-encoding-fixes   PR #2 (stacked on #1)
              │   commit: fix(io): force UTF-8 on stdout/stderr + candidate writes
              └── atomic-03-context-manager-fix   PR #3 (stacked on #2)
                    commit: fix(io): context manager in _lesson_already_appended
```

**Task-3 decisions, all honored:**
- **(a) test in a separate commit** so the maintainer can cherry-pick it out —
  done, commit 2 on PR #1 is the test alone.
- **(b) reference the PT test** — the test file's docstring and the PR body
  both cite the downstream PT suite that proved the fix.
- **(c) politely ask the maintainer's preference** — PR #1 body (below) asks
  whether they want the test included or dropped.
- **Timing: do all, be transparent** — all 3 prepared at once; each PR body
  states it stands on its own merit but is one of a set meant to land
  together, "stars in a constellation."

**Validation done locally:**
- PR #1 patch applies cleanly to pristine upstream (not just to PT's blended
  copy); syntax-checked; isolated functional test confirms `stage()` writes
  exactly one episodic mirror whose timestamp equals the candidate's
  `evidence_ids[0]`.
- Standalone `unittest` (no pytest dep, since upstream has no test harness)
  passes 3/3 at the top of the stack.
- Final stacked `learn.py` diffed against PT's proven version: differs ONLY
  by PT's `path_hygiene` import + `sanitize_tracked_path_leaks` calls
  (correctly excluded — PT-local, patch #3) and a docstring trimmed of the
  PT-specific diagnosis-doc reference for the upstream audience.

### To finish Goal 2 (needs a PR-capable token — everything else is done)

1. ~~Fork `codejunkie99/agentic-stack`~~ — done, `diazMelgarejo/agentic-stack`.
2. ~~Push all 3 branches~~ — done: `atomic-01-episodic-mirror-fix`,
   `atomic-02-utf8-encoding-fixes`, `atomic-03-context-manager-fix`, all
   live on the fork right now.
3. Open PR #1 (base `master`), then PR #2 (base
   `atomic-01-episodic-mirror-fix`), then PR #3 (base
   `atomic-02-utf8-encoding-fixes`) — titles, bodies, and direct compare
   URLs are all in the ready-to-paste file above. Nothing left to write or
   test; this is a paste-and-click operation once a suitable token or the
   GitHub UI is available.

### Goal 1 (PT-side catalog) — DONE

Branch `agentic-stack-blend-state-sync` (commit `308fe4b`), pushed. Updates
`.agent/.agentic-stack-blend-state.json` (new patch catalogued, prior event
preserved under `blend_history`) + `scripts/git/agentic-stack-vendor.md`
(pin-current note + patch-overlay-catalog section). No submodule bump (pin
already current). Ready for its own PR.
