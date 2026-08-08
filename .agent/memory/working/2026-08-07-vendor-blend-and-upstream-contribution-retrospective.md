# RETROSPECTIVE — vendor blend, stacked-PR recovery, and upstream contribution arc

Date: 2026-08-07
Branch: `bump-agentic-stack-vendor-pin` (historical / live PT PR #338 head name; kept as-is to
preserve the open PR ref rather than renaming to `yyyy-mm-dd-NNN-brief-summary`)
Scope: reflective synthesis requested alongside 7 new lessons graduated in
the same commit range — `lesson_15aa463fd07c`, `lesson_005f2a16600d`,
`lesson_05c055046864`, `lesson_70713965dc1b`, `lesson_0f66a36ee1cc`,
`lesson_76cbf68d38b1`, `lesson_fcf6fe38c82e`. This document is the "why it
matters," not a restatement of the "what happened" — that's in the lessons
themselves and in `scripts/git/agentic-stack-vendor.md` § Current pin.

## What actually happened, compressed

Over this arc: fixed a curated CodeRabbit review batch on orama PR #280,
distilled lessons from that fix into PT's `.agent/memory`, decided *not* to
merge a stale competing PR (#281→#280) rather than merging on reflex, then
took on the harder problem — bumping PT's `vendor/agentic-stack` submodule
to a new upstream version while simultaneously stacking 3 of PT's own
not-yet-merged upstream fixes on top of it, discovering and fixing 2 more
real bugs along the way (one in the vendored `upgrade.py`, one in PT's own
blend script), and opening 4 upstream PRs to `codejunkie99/agentic-stack`
as a result. Every PR got cross-referenced with its siblings. The CI ratchet
caught one more pre-existing lint debt on the way out, fixed before this
document was written.

## The deeper pattern: contribution as a side effect of correct use

None of the 4 upstream PRs were planned as a "let's go contribute upstream"
initiative. Each one was found because a tool was actually *used* for its
real purpose — running `--dry-run`, reading its output carefully, and
noticing the output didn't match reality. The `upgrade.py` path-doubling bug
surfaced because someone actually looked at what `--dry-run` printed instead
of trusting it ran clean. The blend script's `__pycache__` leak surfaced
because someone actually read the promote catalog line-by-line instead of
trusting "clean merge, 30 files applied."

This is the same instinct as `lesson_70713965dc1b` (verify clean labels, not
just conflicts) generalized one level up: **the deepest bugs hide behind
successful-looking output**, not behind error messages. A tool that exits 0
and prints a plausible summary is not more trustworthy than one that
crashes — it is *less* scrutinized, and therefore more dangerous. The
repercussion for how this team works going forward: any "verify before
done" pass should spend more attention on the success path's actual
content than on chasing down conflicts/errors, precisely because errors
already announce themselves and successes don't.

## The deeper pattern: judgment doesn't compress into a rule

`lesson_005f2a16600d` (no blanket ours/theirs) is the least "actionable" of
the 7 lessons in the narrow sense — it doesn't tell you what command to run.
That's the point. The `learn.py` conflict and the `recall.py` conflict
happened in the *same blend pass*, touched by the *same two contributors*
(PT and upstream agentic-stack), and were resolved in *opposite directions*
— and both resolutions were correct. A rule that said "always keep PT's
local customization" would have been wrong for `recall.py` (upstream's
shared helper was strictly better). A rule that said "always take
upstream's newer version" would have been wrong for `learn.py` (PT's
fail-closed atomic-publish was strictly more robust than upstream's simpler
version). The repercussion: any future attempt to automate merge-conflict
resolution with a static policy (a script, a CI bot, a "prefer ours" git
merge driver) will silently make the wrong call in exactly the cases where
getting it right matters most — the cases where the two sides are both
plausible and non-trivial. Judgment-requiring conflicts should be flagged
for a human/agent read, not resolved by policy, no matter how tempting the
automation is.

## The deeper pattern: trust is a property of documentation, not intent

`lesson_0f66a36ee1cc` (3-place `.gitmodules` fork-repoint documentation) is
about a genuinely uncomfortable state: PT's vendored dependency pin, for a
window of time, points at a personal fork instead of the real upstream.
That's a real risk — if forgotten, it silently diverges from upstream
forever, or breaks if the fork disappears. The mitigation wasn't "remember
to fix this later" (intent, which decays) — it was documenting the *exact*
revert path in 3 independent places that get read at different times for
different reasons (someone editing `.gitmodules` directly sees the inline
comment; someone doing routine vendor maintenance reads the tracking doc;
someone auditing the blend catalog reads the state file's note). The
repercussion: temporary, uncomfortable states in a codebase are not
inherently bad — they're a normal and sometimes correct way to make forward
progress without upstream in your control loop. What's bad is a temporary
state that depends on a single person's memory to end. The general
principle this generalizes to: **any time-boxed workaround needs the exit
condition written down somewhere durable, in the actual paths future
readers will independently arrive at** — not just one canonical doc, if the
whole point is that different people/agents will find it different ways.

## The deeper pattern: the mechanics of git are more forgiving than they look

`lesson_15aa463fd07c` (rebase auto-drops patch-equivalent commits) is a
genuine relief when you first see it: a branch family that could have
needed manual cherry-pick surgery across a squash-merge boundary just...
resolved itself, because git's rebase patch-equivalence detection is smarter
than the mental model most people carry around ("rebase = replay commits
verbatim, conflicts are your problem to sort out by hand"). The repercussion
for how this team approaches git surgery in general: before reaching for a
manual, error-prone recovery procedure (cherry-pick, manual diff-and-reapply,
`git reanchor_scan.sh`-style forensics), try the simpler mechanical
operation first and read its output carefully — `git rebase` printing
"dropping `<sha>` ... patch contents already upstream" is git *telling you*
the recovery already happened, not a problem to route around.

## Why this matters beyond this specific branch

The wider repercussion, tying all of the above together: this arc is
evidence that the discipline this team has been building — verify claims
over labels, judge case-by-case over apply-a-rule, document exit paths for
temporary states, read tool output instead of trusting exit codes — is not
overhead bolted onto "real work." It *is* the work that turned a routine
vendor bump into 4 upstream contributions and 2 real bug fixes that would
otherwise have shipped silently broken (or not been found at all). The
return on this discipline compounds: PT's `.agent/memory` now carries 7 more
lessons that make the *next* vendor blend, the *next* 3-way conflict, and
the *next* stacked-PR recovery faster and safer than this one was — which
is the entire premise of `.agent/memory` existing as a portable brain in
the first place, rather than each session re-deriving the same judgment
calls from scratch.

## Cross-references

- `scripts/git/agentic-stack-vendor.md` § Current pin — the concrete,
  non-reflective record of what changed and why.
- `.agent/.agentic-stack-blend-state.json` → `last_blend.note` — provenance
  chain for the 2 hand-resolved conflicts referenced above.
- `.agent/memory/working/2026-07-16-agentic-stack-upstream-contribution-plan.md`
  — the original contribution-planning doc this arc executed against.
- orama-system `docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md` § 1 — the
  coordinator/orchestrator scope-note fix that opened this arc, for anyone
  tracing the full session chronologically.
