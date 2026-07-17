# Pattern — Frugal PR-review triage (audit-first, group-by-file)

Status: pattern extracted from live use on PR #256, not a hypothetical.
Applies whenever a PR carries review comments from more than one source
(human digest, GitHub review API, prior automated pass) and some of the
comment set may already be stale.

---

## The failure mode this avoids

Treating each review comment as an independent task — read comment 1, fix
it, re-read the file, read comment 2, fix it, re-read the file again — burns
tool calls and tokens on repeated file reads, and worse, **applies fixes
that are already done**, because line numbers and assumptions in a comment
digest go stale the moment any other commit lands on the branch. On PR #256,
6 of 8 listed action items were already resolved by an earlier pass before
this session touched the branch; fixing them "again" from stale line numbers
would have silently no-op'd, produced misleading diffs, or conflicted.

## The pattern (5 steps, minimum tool calls)

1. **Pull all comment sources into one list, once.** One API call for the
   PR body/review comments, one read of any uploaded digest. Do not fetch
   per-item.
2. **Group the raw list by file, not by comment.** A comment digest is
   usually authored comment-by-comment; the actual work is per-file. Two
   comments in the same file are one read + one edit pass, not two.
3. **Read each affected file once, in full context around every flagged
   region simultaneously** — not once per comment. Use the read to answer,
   for every item touching that file: *is this still true of the current
   content?* Check against the reviewed commit SHA specifically
   (`git merge-base --is-ancestor <reviewed_sha> HEAD`) when a review names
   one — that alone often resolves whether a finding is stale.
4. **Only edit what's confirmed outstanding.** Skip anything already
   present. This is the actual token savings: verification is cheap (a grep
   or a targeted read), re-fixing is not, and a wasted edit still costs a
   diff review cycle downstream.
5. **One verification pass, one commit.** Run the full relevant test suite
   once after all edits for a file/PR are applied — not after each
   individual fix — then one hygiene check, one commit grouping every
   genuinely-changed file together with a commit message that states which
   items were already-resolved-and-skipped vs. actually-fixed. That message
   is itself documentation for the next pass, so staleness doesn't repeat.

## Worked numbers from PR #256

- Comment sources: 1 uploaded digest (4 numbered items, 2 sub-items each) +
  1 GitHub review (2 inline findings) = 6 distinct claims.
- Files actually touching: 3 (`orchestrator/gossip_bus.py`,
  `tests/test_gossip_bus.py`, `tests/test_agent_coordination.py`,
  `docs/next/…analysis.md`) — read once each, full relevant region.
- Confirmed already-resolved on read/verify: 4 of 6 claims (encoding fix,
  `.parent` anchoring guard, two `monkeypatch.chdir` refactors, one
  `importlib.reload` fix) — zero edits, zero risk of double-patching.
- Genuinely outstanding: 2 (one test's chdir+comparison, two markdown fence
  languages) — fixed in one grouped commit, one test run, one hygiene check.
- Net tool calls for the fix phase: ~6 reads + 2 edits + 1 test run + 1
  hygiene check + 1 commit, instead of a naive per-comment loop of
  6× (read + edit + verify).

## When this doesn't apply

Single-file PRs, or a review with exactly one finding — the grouping step
has nothing to group. Use it whenever there's more than one file or more
than one comment source in play.
