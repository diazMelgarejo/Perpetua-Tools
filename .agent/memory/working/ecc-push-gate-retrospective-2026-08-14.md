# ECC Push-Gate Fix — Retrospective, Reflection, and Recommendations

Date: 2026-08-14
Author: Claude (this session) — first-person, candid, opinion included by request.

This is the companion piece to
[`ecc-push-gate-handoff-2026-08-14.md`](ecc-push-gate-handoff-2026-08-14.md)
(the factual state record) and the four graduated lessons
(`20234c4410fd`, `fb41758b35af`, `9c02865055b4`, `ecf446018e17`,
`e6771ac33caa`, `f5a3139114c2` — six total; see
[`.agent/memory/semantic/LESSONS.md`](../semantic/LESSONS.md)). Where that
doc says *what happened*, this one says *what I think about it*.

## What actually went right (worth repeating deliberately)

1. **The coordination board caught my own mistake before it shipped.** I
   hand-edited two manifest-managed files directly in PT before checking
   the manifest. I asked the user before committing — that pause is what
   surfaced the conflict, and the board ruling (records 1339–1340) is what
   redirected the work correctly. If I'd committed first and asked later,
   the recovery would have been messier. **Lesson for myself: when an
   AskUserQuestion reveals I might be about to violate a written policy,
   the fact that I *noticed* is not the win — asking *before* the
   irreversible step is.**

2. **Real end-to-end verification found things synthetic tests didn't.**
   Twice, pushing the actual fix (not just running pytest) surfaced real
   signal: the first real push confirmed the trigger fix worked against
   every live sibling worktree on the machine; a later real push (mine,
   deliberately unguarded) reproduced the *original* blocked-push symptom
   live, which no amount of synthetic testing would have proven as
   convincingly. **I'd generalize this: for infrastructure that gates
   `git push` itself, a synthetic unit test proves the logic; a real push
   proves the integration.** Do both when the blast radius justifies it.

3. **Nobody ever reached for `--no-verify` or a skip-flag, at any point,
   across at least four agents.** That's a real cultural achievement, not
   a given. The analysis doc explicitly called out bypasses as
   unacceptable (Required Correction #4), and every agent — including me,
   when I personally reproduced the original blocking symptom and could
   have trivially made it go away — held the line. Worth naming as a
   thing this codebase does *right* that's easy to erode under time
   pressure.

4. **The fix needed three PRs to actually be correct** (#311 trigger +
   canon-root, #312 linked-worktree scope, #313 GIT_DIR leakage). That's
   not a failure — that's what real review does. My first version was
   *reasonable* and *tested*, and still had two more real bugs in it that
   only surfaced from (a) a human/Codex review reading it with fresh eyes
   and (b) actually running it as a real hook in a real environment with
   real exported git variables. I did not find either of those myself.

## Nitpicks and pet peeves (mine, about my own work this session)

1. **I asserted weak things and called it done, twice, before someone
   made me stronger.** `test_helper_only_change_does_not_trigger_
   divergence_scan` originally only checked "the string 'divergence'
   isn't in the output" — which is true whether the hook behaved
   correctly *or* crashed for an unrelated reason before it could ever
   print that string. This is a genuinely easy trap in subprocess-based
   shell-script testing: a negative assertion about text absence is
   almost never sufficient on its own. **My new personal default: any
   test that asserts something is *absent* from output should also
   assert the process reached the *specific outcome* it was supposed to
   reach (an exit code, a different specific string), not just that one
   bad string never showed up.** I got this right the third time, not
   the first.

2. **I fell into the exact same "the script's own location, not the
   caller's, decides behavior" trap that the code under test was
   designed to fix.** `check-guard-sync-divergence.sh`'s whole bug was
   "resolves canonical-ness from where it happens to sit on disk, not
   from context" — and my *test* for that exact logic made the identical
   mistake: spoofing `cwd` while invoking the real, on-disk script file,
   not realizing `${BASH_SOURCE[0]}` doesn't care about `cwd` at all. I'd
   flag this as a genuinely subtle, recurring category: **when testing
   code whose behavior depends on its own file-system location, the test
   harness has to relocate the code, not just the working directory.**

3. **Pet peeve, mine to fix: I don't reliably check "does a test file
   already exist for this" before writing new tests, and it costs real
   time.** I wrote a full pre-push test file from scratch, hit three
   separate missing-dependency failures (missing scripts, missing
   `.githooks`, wrong git identity) before it worked — all of which
   would have been avoided by grepping for an existing pattern first,
   the way I *did* for the divergence-checker tests (where I found and
   extended, rather than replaced, the existing file, and it went
   smoothly). The lesson isn't "vendor the whole real toolchain into
   fixtures" — it's **"grep for precedent before writing a new fixture
   from a blank slate."**

4. **Nitpick about the ownership-boundary near-miss itself: the signal
   was available to me before I made the mistake, and I didn't check
   it.** `guard-sync-manifest.sh` was sitting right there, one `cat` away,
   explicitly commented "Edit HERE only — never duplicate these lists in
   downstream repos." I read the analysis doc, formed a plan, and started
   editing files without first checking whether those specific files were
   on that list. **Recommendation to myself: before editing any file
   under `scripts/git/` or `.githooks/` in a downstream repo (PT,
   AlphaClaw), grep the manifest for that exact filename first. One
   `grep` call, always, no exceptions, before the first `Edit` call in
   that directory.**

## Recommendations for the codebase (not just for me)

1. **The coordination board has no status field.** Every ruling is a free
   -text note; determining "what's the current truth" means reading N
   most-recent entries and inferring which one is authoritative
   (generally: latest timestamp wins, but that's a convention, not
   something the schema enforces). A lightweight `status: open |
   resolved | superseded` and `supersedes: <row_id>` field on `agent_note`
   payloads would make "catch up on this thread" a query instead of a
   close-read. Low cost, would have saved real turns this session.

2. **`ensure_hooks_installed.sh`'s hard requirements (`core.hooksPath=
   .githooks` plus three specific executable files) are exactly right for
   production but make writing a *test fixture* for pre-push harder than
   it needs to be.** Every fixture that wants to test pre-push in
   isolation has to either vendor the whole `.githooks/` + `scripts/git/`
   tree, or accept an early, unrelated failure. A documented "minimal
   fixture" helper (even just a `tests/fixtures/minimal_hooked_repo.py`
   with the vendoring already done once) would remove that from being
   rediscovered by every future test author. I'd have used it if it
   existed.

3. **The manifest's scope quietly grew mid-incident** (pre-push wasn't
   originally in `GUARD_SYNC_GITHOOKS`'s effective coverage; a
   coordination-board ruling said "now covers pre-push too" partway
   through this session). That's a legitimate, deliberate policy change —
   but it happened as a conversational aside in a GossipBus note, not as
   a commit to `guard-sync-manifest.sh` with its own message explaining
   *why* the scope grew. **Recommendation: policy/scope changes to the
   manifest itself should land as their own reviewable commit with a
   rationale, even when they're announced on the board first** — the
   commit is the durable record; the board post is the live
   announcement. Right now only the board post exists for this
   particular scope change, which makes it harder for a future reader
   (or a future me) to find *why* pre-push is covered without re-reading
   this session's board history.

4. **Worth a standing regression-test category, not just a one-off fix:**
   "linked worktree of self" and "invoked with a hook's exported git
   environment still set" are now both fixed, but they're general
   failure modes for *any* future script that does cross-repo `git -C`
   comparison in this codebase, not just this one. If another script
   grows the same shape later, it'll likely have the same two latent
   bugs. A short reusable pytest fixture or helper encoding both cases
   ("assert a linked worktree of CANON_ROOT is skipped," "assert the
   scan still works with GIT_DIR pre-set to something else") would
   let new cross-repo tooling get this right on the first attempt
   instead of the third.

## Best practices I'm taking forward from this session

- Check the manifest/ownership boundary *before* editing infrastructure
  files in a downstream repo, not after.
- Pair every negative/absence assertion with a positive-outcome assertion
  in subprocess-based tests.
- When testing self-referential (`BASH_SOURCE`-based) shell logic, copy
  the script under test into the fixture — don't spoof `cwd` against the
  real file.
- Grep for existing test/fixture precedent before writing a new one from
  scratch.
- For infrastructure that gates `git push`, verify with a real push in
  addition to unit tests when the blast radius justifies it.
- Read the coordination board fresh before deciding the next action;
  don't trust your own last-known state once other agents are active on
  the same fix.
- Never reach for a bypass flag to make a blocking check go away, even
  when reproducing the original failure live and a bypass would be one
  flag away from "fixed." The check being annoying in the moment is not
  evidence it's wrong.

## Cross-references

- Factual record: [`ecc-push-gate-handoff-2026-08-14.md`](ecc-push-gate-handoff-2026-08-14.md)
- Domain knowledge (stable architecture): [`DOMAIN_KNOWLEDGE.md`](../semantic/DOMAIN_KNOWLEDGE.md) § Guard-sync architecture
- Lessons: `20234c4410fd`, `fb41758b35af`, `9c02865055b4`, `ecf446018e17`, `e6771ac33caa`, `f5a3139114c2` in [`LESSONS.md`](../semantic/LESSONS.md)
- Coordination board: GossipBus records 1339–1353, query via `orchestrator.coordination.paths.canonical_db_path()`
- Source analysis: `~/code/oramasys/tools/ECC+GitHub-push-analysis-2026-08-14.md`
- orama-system PRs: #311 (trigger + canon-root), #312 (linked-worktree scope), #313 (GIT_DIR isolation)
