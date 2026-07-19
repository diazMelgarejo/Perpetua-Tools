# PR258 Tree-Twin Scrub Surgery — 2026-07-18

## Status

This note records the PR258 history/scrub/reanchor episode for future agents.
It is deliberately scrubbed of private identity literals and secret values.

Current PT PR branch after surgery:

- Branch: `docs/coordination-consolidation-plan-20260717`
- Base and merge-base: `963a5bdd`
- Reanchored head: `1f02d2d1`
- Old remote lease before force update: `524b41da`
- Old branch tree-twin anchor: `0c3e8519`
- Current-main tree twin: `b4a1b429`
- Final PR state observed: `MERGEABLE`, all checks green
- Semantic ahead/behind after repair: ahead `21`, behind `0`

## What Really Happened

The branch appeared to have hundreds of new commits after privacy/attribution
scrub work. That was not a trustworthy semantic-diff signal. It was a rewritten
ancestry symptom: old commits and rewritten commits can contain the same tree
content but have different commit SHAs because metadata, messages, or ancestry
changed.

The correct maneuver was therefore tree-twin surgery, not a normal merge:

1. Record the current remote branch SHA as the force-with-lease target.
2. Build an index of current `origin/main` commit tree IDs.
3. Walk the stale branch first-parent history until a branch commit tree matches
   a current-main tree.
4. Replay only the commits above that twin onto current `origin/main`.
5. Skip branch-side merge-artifact commits that only reintroduced old graph
   shape.
6. Resolve append-only memory files by union and dedup by `id` / `run_id`.
7. Rerender `LESSONS.md` from `lessons.jsonl`; never hand-merge rendered memory.
8. Run hygiene, targeted tests, conflict-marker checks, and forbidden-token /
   metadata scans before force-with-lease.

The direct merge attempt had produced broad synthetic conflicts because Git was
trying to merge stale graph history, not just the branch's real contribution.
The tree-twin replay reduced the branch to the real PR delta.

## CodeRabbit Findings Digest

The restricted CodeRabbit coordination note clarified six findings and how they
were handled against current code, not against stale review line numbers:

- The identity-fragment lesson had already been rewritten with neutral labels.
- A hardcoded private token in a tracked bootstrap path needed to move behind a
  local/secret configuration boundary.
- Attribution pattern parsing needed raw right-hand-side extraction so whitespace
  around `=` could not defeat trimming.
- Allowlist tests had to exercise real exception logic rather than vacuous
  fixtures.
- Owner-name handling had to come from configured/local owner labels with a
  backward-compatible fallback.
- Private-literal scanning must not be gated behind unrelated banned-pattern
  readiness checks.

Two review suggestions were directionally right but unsafe to apply verbatim:

- A string-manipulation suggestion would have used an already transformed value
  as the prefix for stripping the original text.
- A suggested owner-name change would have broken configurations that set only
  the owner email key and relied on a fallback label.

Future agents should treat review diffs as hypotheses. Verify the proposed
patch itself against current behavior before applying it literally.

## What Was Scrubbed

Verified and completed for this PT PR branch:

- Branch-scoped metadata/message-body scrub using mailmap and replace-message.
- PR branch re-created by replay on top of current main with sanitized tracked
  files.
- Current tracked-file forbidden-token scan: clean at the time of reanchor.
- Current PR-branch commit metadata scan above `origin/main`: clean at the time
  of reanchor.
- GitHub checks after force-with-lease: green.

Not proven by that operation:

- It did not prove a repository-wide all-ref blob purge.
- It did not prove every historical memory blob under every ref is clean.
- It did not cover orama-system history unless a separate orama scan/scrub is
  performed and recorded.

The scrub report correctly left an all-ref blob-scan gap. Do not summarize this
episode as "history-wide VERBOTEN memory files removed" unless that all-ref blob
scan actually runs and passes using the local-only forbidden-literal registry.

Accurate wording:

> PT PR258 was reanchored and scrubbed within the PR-branch scope: metadata /
> message-body issues and current tracked-file content were cleaned, then the
> real branch delta was replayed onto current main. A history-wide all-ref blob
> scrub remains a separate verification gate unless explicitly completed.

## Stash Digest

Preserved stash:

- `pr258-reanchor-local-recall-row-20260718`

Contents:

- One append-only row for `.agent/memory/episodic/AGENT_LEARNINGS.jsonl`
- The row records the proactive recall that occurred before the reanchor.
- It was unique relative to the rewritten branch.
- The row was appended to current episodic memory without popping the stash, so
  the stash remains available as a safety copy.

## Doctrine

When a branch shows huge ahead/behind after a scrub:

- Do not merge first.
- Do not trust ahead/behind counts.
- Find the byte-identical tree twin.
- Replay only commits above the twin.
- Preserve safety refs and remote lease targets.
- Treat metadata scrub, current-tree sanitization, PR replay, and all-ref blob
  scan as distinct gates.

## Follow-up Scan and Skill Update

After this note was first written, a safe blob scan was run in PT using
local-only forbidden-pattern sources. The scanner did not print literal values
or matched lines.

Observed counts:

- `HEAD`: `7169` reachable blobs, `219` hits.
- `origin/main`: `7074` reachable blobs, `206` hits.
- `origin/main..HEAD`: `95` PR-unique blobs, `13` hits.
- `--all`: `7276` local all-ref blobs, `248` hits.

The `248` count was therefore not "only this PR branch." It was every local ref
reachable in the PT checkout, including remote refs, local refs, and stash refs.
The current PR branch inherits most historical hits from `origin/main`; the
PR-unique range still has its own smaller set of historical blob hits. These are
history/reachability findings, not current tracked-tree hygiene findings.

That result answers the key question:

- No, the prior PR258 operation should not be described as a history-wide blob
  scrub of all VERBOTEN memory/file contents.
- Yes, the current PR branch and metadata surfaces were scrubbed/validated for
  the PR scope.
- A repository-wide all-ref blob expunge remains separate work if the goal is
  zero reachable historical blob hits.

The Orama canonical `git-history-surgery` skill was updated, uncommitted, to
teach this nuance for future events:

- huge ahead/behind after scrub is a rewritten-ancestry symptom;
- tree-twin reanchor is not a normal merge;
- if blob content changed, there may be no exact tree twin and agents must use a
  reviewed replay instead of calling it a tree-twin proof;
- metadata/message scrub, current-tree sanitization, PR replay, and all-ref blob
  scan are separate gates;
- scanners for private literals must use local-only pattern files and report
  labels/counts only.
