# Week Retrospective: PT ↔ orama-system Collaboration Lessons (2026-07-31)

> **Purpose.** A comprehensive, evidence-grounded account of what this
> session actually encountered, got wrong, caught, and fixed across
> Perpetua-Tools and orama-system this week — written for future agents,
> not as a summary that filters detail away. Every incident below is real,
> traceable to specific commits, PRs, or reproduced failures, not
> reconstructed from memory. No detail omitted for brevity where it
> carries a real lesson.

---

## Part 0 — Why this document exists

This week's work kept surfacing the same underlying pattern: a fix for one
surface-level problem, followed to its actual root cause, revealed another
layer — and several of those layers were mistakes made *by this same
agent*, within the *same session*, caught only through explicit
verification rather than trust in a prior step's own "done" claim. The
throughline isn't any single bug. It's that **verification has to be real
and specific, not assumed, and that assumption compounds silently until
something forces a check.**

The human partner's repeated, explicit instructions this week — "never
assume, never guess, always ask," "verify against current code, not the
diff," "run the actual tool, not a description of it," "push once per
repo, don't fragment" — were not friction imposed for its own sake. They
were direct responses to specific failures below, each one costing real
time and, in a few cases, nearly costing real content. The purpose of this
document is to make sure those specific failures don't have to be
rediscovered by a future session before the lesson lands again.

---

## Part 1 — The orama ↔ PT sync policy: documented, then quietly violated

### The policy

Both repos' `AGENTS.md` files document, in matching language, that
`orama-system/scripts/git/*` is canonical and `Perpetua-Tools`'s copies
are downstream, byte-identical mirrors — never hand-edited directly, only
updated via `orama-system/scripts/git/sync-attribution-guard-scripts.sh`.

### The violation

Despite this being documented on both sides, it was violated mid-session:
real fixes (including the `commit-clean.sh` merge-aware parent-lineage
fix — the change that made `commit-clean.sh` correctly preserve both
parents of a merge instead of silently collapsing to one) were made
directly in a PT checkout and never synced back to orama's canonical copy.

### How it was caught

Not by re-reading the policy and assuming it held — by an explicit,
file-by-file `diff` comparison of all ~21 shared `scripts/git/*` files
between the two repos. That comparison found **7 files where PT's copy
was genuinely more advanced than orama's own "canonical" source** —
inverting the intended sync direction entirely.

### What the drift actually contained

One of the 7 was not just drift, it was a real, live bug in orama's
canonical `sync-attribution-guard-scripts.sh`: it synced
`audit_engine.py` and `identity-policy.json` through the *same* loop as
executable shell scripts, meaning any fresh sync would install those two
data files with the wrong Unix permissions (executable instead of
`0644`). PT's already-more-advanced copy had already fixed this — moved
those two files into their own loop with explicit `0644`, and had also
added a third file, `identity-policy.schema.json`, that orama's canonical
list didn't even know about.

**Verified, not assumed:** the fix was proven by actually running the
corrected sync script against a throwaway `git init` target and checking
real `ls -la` output — `audit_engine.py`, `identity-policy.json`, and
`identity-policy.schema.json` landed at `-rw-r--r--`; `commit-clean.sh`
landed at `-rwxr-xr-x`.

### The lesson (Part 1)

A documented policy is necessary but not sufficient. Periodic, explicit,
file-level verification is what actually keeps two repos in sync — not
the existence of a policy document saying they should be. And when
comparing two "identical" copies, don't assume the canonical side is
automatically more correct; read the actual diffs, because the downstream
side can genuinely be ahead if fixes landed there first.

---

## Part 2 — CVE-2025-30066: a real supply-chain compromise, caught by verification discipline

While hardening two new `markdown-lint.yml` workflows (one in each repo),
a CodeRabbit review flagged `tj-actions/changed-files@v45` as an unpinned,
mutable tag reference. This could have been treated as a stylistic
nitpick. It wasn't one.

**Verification, not assumption:** checked whether this specific action
had any history of compromise. It did — CVE-2025-30066, a real repository
compromise where tags v1 through v45.0.7 were retroactively re-pointed by
an attacker to a commit that exfiltrated secrets from CI logs. This
wasn't a theoretical risk; it was a documented, dated incident affecting
the exact tag both workflows were using.

**Verification of the fix, not just the finding:** the correct pin SHA
for the current safe release (v47.0.6) was obtained by running
`git ls-remote --tags` directly against the real
`tj-actions/changed-files` repository — not by trusting a search result.
This mattered: a third-party blog's claimed SHA for the *same version*
was checked against the real repo's tag list and found to be **wrong**
(fabricated or copy-paste-corrupted). Had that blog's SHA been trusted
and pinned instead, the fix would have looked complete while pinning to
an arbitrary, unverified commit — potentially worse than the mutable tag
it was meant to replace.

### The lesson (Part 2)

Security-relevant fixes need the same verification discipline as
everything else, arguably more — and "verify" means checking the primary
source directly, not the first plausible-looking answer a search returns.

---

## Part 3 — CI workflow consolidation: efficiency work that cascaded into three more real bugs

The original ask was straightforward: reduce redundant CI passes. Two
near-identical security-invariant workflows were running almost the same
test suite twice on every push; `docs-sync` was a separate job doing a
redundant checkout for two lightweight script calls that the sibling job
`git-hygiene` could run as extra steps.

Each consolidation step, once actually landed and tested, surfaced a real
bug that the consolidation itself had caused or exposed:

### 3a. `check_endpoint_policy_core.py` — a structural self-check, correctly tripped

This script hardcodes a list of files that must exist and must run the
policy test suite, specifically so CI enforcement can't be silently
removed. Deleting the two old security-invariant workflow files as part
of consolidation correctly tripped this check — from the script's own
perspective, two required enforcement files had vanished. This was fixed
independently by someone else mid-session (a concurrent commit,
`c8f0c53`) while this same fix was being worked out in parallel; the two
were compared and found identical in intent, and the concurrent fix was
kept rather than duplicated.

### 3b. A live 403 on the PR-comment step — a real regression, not flagged by any review

Investigating (a) surfaced something no review had caught: the
consolidated `security-invariants.yml`'s PR-comment-on-failure step was
independently failing with `Resource not accessible by integration`. Root
cause: an *earlier*, unrelated permissions-hardening pass in this same
session had narrowed the workflow's `permissions:` block to `contents:
read` only, without accounting for the `createComment()` step already
present in the file being hardened. Fixed by adding the correct scope
(`issues: write`, not `pull-requests: write` — verified against
`actions/github-script`'s own documented convention for
`issues.createComment()`, even when the target is technically a PR).

### 3c. `docs-sync` folded into `git-hygiene` — and initially, silently coupled to it

The first version of this fold was wrong in a way that wasn't obvious
until a review caught it: GitHub Actions skips later steps in a job by
default once an earlier step fails. Folding `docs-sync`'s steps directly
into `git-hygiene` without `if: ${{ !cancelled() }}` meant a hygiene or
banned-token failure earlier in the job would silently skip the
docs/config sync checks entirely — contradicting the "same failure
behavior, one fewer job" claim the consolidation had originally made.
Fixed, and — critically — **verified the fix was real** by tracing
through GitHub Actions' actual step-skipping semantics, not by assuming
`if: always()` vs `if: !cancelled()` was a stylistic choice (`!cancelled()`
correctly still respects a genuine manual cancellation; `always()` would
not).

### The lesson (Part 3)

An efficiency change is not "done" when the redundant thing is removed.
It's done when every path that used to work independently still works
independently, and that has to be checked against the actual mechanics
(GitHub Actions' step-skip default, in this case), not assumed from the
surface-level diff looking clean.

---

## Part 4 — The `mv`-into-existing-directory trap: a bug nearly dismissed as a bad test

### The near-miss

While writing a regression test for a different, already-fixed bug
(`atomic_append_snippet`'s brace-group exit-status issue), a test
covering "what if `dest` turns out to be a directory" was written almost
reflexively — and the un-fixed function *didn't fail* on that input. The
almost-immediate reaction was to treat this as a poorly-designed test
("that's not what this function is for") and discard it.

### What tracing it to ground actually revealed

`mv -f "$stage" "$dest"` where `$dest` is an *existing directory* is
documented POSIX behavior, not a bug in `mv`: it moves the source file
**into** the directory rather than replacing it or erroring. Reproduced
directly, empirically, before writing anything about it:

```text
$ mkdir dest_dir && echo "real content" > dest_dir/AGENTS.md
$ atomic_append_snippet dest_dir 0644 snippet.txt   # pre-fix version
$ echo $?
0
$ ls dest_dir/
AGENTS.md   .dest_dir.sync.sCYhhk      <- stray file, snippet content only
$ cat dest_dir/AGENTS.md                             <- completely unchanged
real content
```

The un-fixed function reported success. It appended nothing to the file
it was asked to append to. The content it was supposed to write ended up
in a garbage-named sibling file inside the directory, invisible unless
someone thought to look. This is a genuine, reachable, silent-success
bug — the exact failure mode this entire week's verification discipline
exists to prevent — and it was one reflexive "that test is wrong" away
from never being found.

### The tell that made the fix obvious once found

`atomic_install_file`, the *sibling function in the same file*, already
had the exact defensive check this bug needed (`[[ -d "$dest" ]]`) —
`atomic_append_snippet` was simply missing the safety invariant its own
neighbor had already established. This is itself a generalizable
signal: when one function in a file has a defensive check another
lacks, that asymmetry is worth investigating on its own, independent of
whatever specific bug happened to surface it.

### The lesson

A surprising test result is a signal to trace the real function's
behavior to ground, not a cue to discard the test as testing the wrong
thing. The instinct to reframe a test as "not what I meant to test" is
precisely the moment a real bug is most likely to be quietly walked
past.

---

## Part 5 — `git am` vs `git rebase`: two different operations sharing one directory, misreported as one

`.git/rebase-apply/` is used internally by *both* a real rebase and a
`git am` patch-apply session. `check_no_pending_merge.sh` reported both
as `REBASE`, which sends an operator stuck mid-`am` toward `git rebase
--continue`/`--abort` — neither of which is the correct recovery command
for an `am` session.

Fixed by checking for the `rebase-apply/applying` marker file, present
only during `git am`, never during an actual rebase (which uses
`rebasing` instead). The regression test that proves this puts a repo
into a **real** stuck `git am` session — `format-patch` plus a genuinely
conflicting local commit plus a real `git am` invocation that gets
stuck — rather than fabricating the marker file directly, so the test
exercises the actual git mechanics, not a description of them.

---

## Part 6 — Append-only historical records: the rule was written, then immediately violated by its own author

### The violation (Part 6)

Earlier in the week, real errors were found in existing `lessons.jsonl`
entries — a wrong count ("six" conflict porcelain codes instead of the
actual seven listed), a broken, non-copyable shell fragment, an
incomplete cherry-pick-safety claim. Each was fixed by directly mutating
the existing JSON record's `claim` field in place — `json.load()`,
modify, `json.dump()` — including on a graduated candidate snapshot.

### Why this was wrong, not just stylistically

`lessons.jsonl`, `AGENT_LEARNINGS.jsonl`, and the graduated candidate
snapshots are append-only historical records specifically *because* their
value depends on an intact trace of what was actually claimed and when.
A direct in-place edit destroys the original wording with no queryable
trace within the data itself — exactly the auditability the record
exists to provide, gone, by the same action meant to *fix* a data-quality
problem.

### How it was caught (Part 6)

Not self-caught. An external review (CodeRabbit, on orama PR #250) found
it — specifically, found that a *doctrine document actively being
written this same session* to codify good remediation practice had used
this exact incident as its own worked example, without noticing the
example demonstrated the anti-pattern the surrounding text claimed to
prevent.

### The correction

Append-only records now require appending a new, superseding entry that
references the original, never mutating the original's fields. The
doctrine document's worked example was corrected to name the incident as
the mistake the guidance exists to prevent, not a model to replicate.

### The deeper lesson

Writing documentation about a lesson learned is not exempt from the
failure mode the lesson describes. A process doc needs the same external
scrutiny as any other diff — self-review missed this specifically
because the doctrine text read as authoritative, which made the
contradiction inside it easy to skim past.

---

## Part 7 — This session's own doctrine work got the hierarchy backwards, then had to be corrected by direct instruction

### What happened

While adding a new reference card for the worktree-based merge procedure
above, real overlap was found with an existing, more mature doctrine —
`multi-agent-collaboration-protocol.md`'s Nested-Branch Merge Protocol,
which already covered simulate-first, present-both-sides-to-human, and a
7-strategy resolution table. Correctly recognizing this as real overlap
(not wanting to ship duplicate doctrine, a real value this project holds
— single source of truth, duplication treated as a defect), the new card
was reduced to a "thin addendum" to the existing, more comprehensive
protocol.

### Why this was backwards

The existing protocol is scoped for a genuinely rare, hard problem:
concurrent multi-agent edits to the same repo, or reconciling something
like a soft fork separated from its upstream by months of drift (the
exact kind of merge periscope's relationship to its source represents).
Treating that heavyweight protocol as the *default* an agent reads first,
with the simpler, everyday case relegated to a subordinate footnote,
inverts which one actually serves the common case. Nearly every merge an
agent does in the course of ordinary work is the simple case — one
branch, one agent, no concurrent editing — and pointing that agent at
topological merge ordering and a formal multi-strategy table first is the
wrong-sized tool for the job actually in front of it.

### The correction, direct from the human partner

Explicitly instructed to restore the original, fuller draft as its own
standalone, complete, default procedure — not subordinate to the mature
protocol, its peer, scoped by actual use case. The mature protocol gained
an explicit "not your situation? use the simpler card" redirect
immediately under its own heading; the simpler card gained an explicit
"escalate here only if..." note at its own top. Both docs were also found
to have several pre-existing framing bugs in the same direction — one
inline summary in `using-git-worktrees/SKILL.md` read as if the advanced
protocol applied to *any* merge into `main`, not just the concurrent
case — corrected at the same time, since they were the same
miscalibration appearing in multiple places.

### The lesson, stated as directly as possible

Recognizing real overlap and wanting to avoid duplication is the right
instinct. But "avoid duplication" doesn't automatically mean "make the
newer, simpler thing subordinate to the older, more complex thing" — it
means figuring out which one actually serves which situation, and making
each the right size for its own job. Getting this backwards wasn't
caught by re-reading the doctrine's own stated values (which correctly
say duplication is bad); it needed the human partner's direct
intervention, because the mistake was in *which direction* to resolve the
overlap, not in whether overlap existed.

---

## Part 8 — Recurring tooling and API gotchas, hit more than once, each costing real time

Collected here because each one recurred, meaning the first encounter
alone wasn't enough to prevent the second:

- **The PR-list API's `merged` field is unreliable.** Observed `null`
  for PRs later confirmed genuinely merged via the single-PR endpoint
  (`GET /pulls/{number}`). Hit this specific confusion more than once
  this week before treating "always check the individual endpoint" as a
  hard rule rather than a one-off gotcha.
- **Squash-merged branches never show as git ancestors.**
  `git merge-base --is-ancestor` correctly returns false for a
  squash-merged branch's relationship to the branch it merged into — this
  is expected, not a sign the merge failed, but it looks alarming the
  first several times it's encountered. The reliable check is whether the
  specific content/IDs the branch introduced now exist in the target,
  not ancestry.
- **A `git stash` used mid-merge, even for an unrelated purpose, can
  silently revert already-resolved conflicts.** This happened for real,
  once, this week: a stash used to test something unrelated mid-merge
  silently reverted three carefully-merged memory files back to their
  pre-resolution state on pop, with no warning, no conflict marker — and
  the reverted state was committed and pushed before being caught by an
  unrelated later line-count check, not by anything at the time of the
  stash pop itself.
- **A local checkout that's fallen behind a push made moments earlier in
  the same session diverges silently.** Rebuilding a merge or rebase from
  a stale local branch — rather than fetching the actual remote tip
  first — produced work based on state that was already wrong, discovered
  only when the subsequent push was rejected.
- **This session's own GitHub token cannot create PRs, cannot edit PR
  bodies, and cannot post PR comments** — confirmed repeatedly across
  both repos, not assumed from one failure. Every PR this week that
  needed opening required the human partner to open it manually from a
  provided compare URL; every PR-body update needing to happen this way
  too. This is a hard, structural limitation of the current tooling, not
  something to keep re-attempting in the hope it resolves differently.
- **Diff-scoped CI lint still checks the *whole* file once any line in it
  is touched**, not just the changed hunk — `markdownlint-cli2` (and
  presumably most whole-file linters) doesn't do hunk-level checking.
  Touching any file with pre-existing violations pulls all of them into
  scope for the first time. The correct response depends on what kind of
  file it is: fix hand-authored prose/doctrine properly (it should have
  been compliant anyway); exclude machine-rendered, append-only logs
  (line-length rules don't meaningfully apply to a rendered lessons file
  where each entry is one line by design).

---

## Part 9 — What this is actually about (the deeper motivation, stated directly)

The specific bugs above are not really the point. The point is what they
have in common: each one was caught only because something forced a real
check — a deliberate empirical reproduction, a diff read in full rather
than skimmed, a test written and actually run rather than assumed to
pass, an external review reading a doctrine document as carefully as it
would read code.

Effective cooperation between a human partner and multiple agents working
across multiple repos, multiple sessions, and sometimes concurrently with
each other, depends on judgment developed in one session surviving into
the next one in a form an agent can actually *act on* — not just a
transcript a human has to re-explain from scratch every time. That's what
the explicit guardrails this week were for: not process for its own sake,
but the mechanism by which a lesson learned once doesn't have to be
re-learned, at real cost, by the next agent or the next session of this
same agent.

The repeated instruction to "never assume, never guess, always ask" is
not a lack of trust in agent capability. It's a recognition that an
agent's confidence a task is complete and the task actually being
complete are two different things, and the gap between them is exactly
where the incidents in this document happened. Asking, verifying,
tracing to ground — these aren't obstacles to efficient work. Based on
this week's evidence, they're the only thing that reliably distinguishes
efficient work from work that merely looks efficient until someone checks.

---

## Evidence index (commits and PRs referenced above, for direct verification)

- PT: `#306`–`#316` (this session's PR sequence), `cursor/guard-sync-parity-74e2`
- orama-system: `#250`, `#251`, `#253`, `#255`
- The `mv`-into-directory fix: `scripts/git/sync-attribution-guard-scripts.sh`,
  `atomic_append_snippet`, orama PR #251, review 4830042706
- The append-only violation and correction: `lesson_405373a130f9`,
  `lesson_legacy_276d1f34052f`, `lesson_legacy_2d0595195747`,
  `lesson_e773f6f957c2`
- CVE-2025-30066 pin: `.github/workflows/markdown-lint.yml`,
  `.github/workflows/security-invariants.yml` (both repos)
