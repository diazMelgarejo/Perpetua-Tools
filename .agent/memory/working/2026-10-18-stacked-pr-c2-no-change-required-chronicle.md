# 2026-10-18 chronicle: stacked-PR rescue, E1 C2 permit guards, and a reviewer's "no change"

**Status:** working record for 2026-10-18 UTC, written by the Claude session registered on the
GossipBus as `claude-sonnet-20261018`, at the operator's direction. Facts were re-checked
against live GitHub and git state while writing; anything not re-checked is marked.

**Why this exists:** the day produced a reusable method lesson (a reviewer's "No change is
required" is a conclusion drawn from a proxy), one real hardening fix, and a stacked-PR rescue
procedure. Ten lessons were graduated (section 8). This file keeps the narrative and the
evidence behind them.

## 1. What shipped

| Item | State at writing |
| --- | --- |
| oramasys#63, E1 C2 binding digest and permit decision logic | Open, `MERGEABLE`/`CLEAN`, 15 of 15 checks pass, head `87e18be` |
| oramasys#62, ruff cleanup, stacked on #63 | Open, `MERGEABLE`/`CLEAN`, head `da580b9` (operator's lease-pinned push, `319d447` to `da580b9`) |
| oramasys stack #64 | `main` <- #63 <- #62, linear, merge bottom-up (#63 first) |
| oramasys#22, Knowledge Portal (not our PR) | Merged 09:36Z as `e179bba`, after our fix commits `23ae397` and `aca6508` |
| orama-system#421, Kimi/Windsurf MCP sync and stale-lock fix | Merged, last pushed commit `54c1707a` |
| GossipBus | 10 orphaned claims released, M1-Q4b completed, mapping and corrections posted |

Trajectory in oramasys: C2 tests 26 to 32; full suite 1450, then 1477 (after PR #22 landed on
`main`), then 1483 passed; repo-wide ruff 18 errors on the rebased #63 base to 0 at the stack
tip.

## 2. The headline: "No change is required"

### What happened

CodeRabbit's review of oramasys#63 (review `5562419447`, body-level "Additional comments", no
inline threads) ended its note on `decide_permit` with "No change is required." The copy relayed
to the session had lost that last sentence and read as an open "Check the digest comparison"
item. Fetching the review body from the API exposed the omission before any code was touched.
The operator then asked for the finding to be analyzed anyway, with the AFRP gate and the
oramasys method.

### Claim by claim

| CodeRabbit's claim | Verdict | Evidence |
| --- | --- | --- |
| `!=` on the digest is fine, a digest is not a secret | Holds, code left alone | SHA-256 over nine request fields, no key material, authenticates nothing |
| No `grant_id` check, low risk because a wrong-grant permit passes only if digests match | Premise real, reasoning incomplete | `grant_id` and `binding_digest` are independent stored fields; a wrong-grant permit with a matching digest was returned as an identical retry |
| Safe for the nonterminal-state contract, which the store owns | Not covered, the larger gap | `decide_permit` never read `existing.state`; an `expired` or `abandoned` permit with a future `expires_at` was returned as live |

The first pass found three of the four gaps (store grant, issuer grant, issuer digest). The
nonterminal-state guard came from the second pass the operator asked for.

### The change (oramasys#63, commit `87e18be`)

`decide_permit` now asserts the documented postconditions of its two injected ports before any
protocol decision, raising `ValueError` and returning or storing nothing:

- store `get_nonterminal_permit_for_grant`: the permit is for the requested grant and its state
  is `issued` or `finalized`;
- `issue_new(request, digest)`: the permit carries the requested `grant_id` and the digest it
  was handed.

`ValueError` is deliberate. A collaborator bug is not a protocol refusal, so the closed
`permit.*` vocabulary is unchanged and a store bug is never reported to a requester as
`permit.conflict`.

### Evidence

- Tests first: the two terminal-state tests failed with "DID NOT RAISE" against the code as it
  stood, so the gap was demonstrated rather than argued.
- Mutation: removing all four guards fails 5 of the 6 new tests. The original 5 decision tests
  and the "finalized is still allowed" test pass either way, so the guards bite and do not
  over-reject.
- Full suite at the stack tip: 1483 passed, 2 skipped; ruff clean repo-wide.
- Reviewer response: on the replies CodeRabbit re-analyzed and wrote that its earlier reasoning
  "was incomplete: digest equality does not validate the independent stored fields". It agreed
  the plain `!=` should stay, recorded a learning to that effect, and confirmed the docstring
  fix. It states it did not run the tests, so our evidence is the local runs and CI.

### What the dropped sentence did and did not do

- **The omission was not itself a gain.** Removing a verdict removes an anchor toward inaction,
  but it can equally anchor toward manufacturing work. The gain came from two deliberate acts
  after it was noticed: checking the pasted text against the source review, then analyzing on
  the merits anyway.
- **Gained:** a replay-protection decision core that fails closed on a misbehaving store or
  issuer; a reviewer that revised its own conclusion; replies that state the reviewer's real
  position instead of crediting it with a demand it did not make; and a reusable method
  (lessons below).
- **Not gained:** no incident was reproduced, and the consumer re-checking its own bindings
  remains a second line. The replies call this defense in depth, which is what it is.
- **Cost:** about 12 production lines, 6 tests, and a second analysis pass mid-task.
- **Discipline to keep:** decide claim by claim. The `!=` point held and was left alone.

## 3. Timeline

1. **Upstream check.** `vendor/ecc-tools/docs/CODEX-NAVIGATION-GUIDE.md` is genuine upstream
   (affaan-m/everything-claude-code PR #2525, commit `a3130f9e`; PT's pin `d8409a4b` is an
   ancestor of upstream main). It is not a PT-local addition, so it survives submodule bumps.
   Codex was told on the board; the session identity was registered.
2. **`claude rc`.** Two parallel subagents: Claude Code 2.1.302 was already current (native
   install, channel `latest`), and `.clauderc` is not a real mechanism (settings live in
   `~/.claude/settings.json` and `~/.claude.json`).
3. **Board pass.** 71 identities, 1 live. Ten `M1-QUALIFICATION-GROUNDWORK` claims held by dead
   agents were released with `heartbeat cleanup` after operator confirmation. M1-Q4b was
   completed; M1-D1 (ADR-71) is the one true orphan. Three of my own statements were corrected
   along the way (section 4).
4. **Exa and Firecrawl for Kimi and Windsurf.** The two `*-mcp.stack.json` templates already
   existed but nothing merged them into the per-machine configs, which is why the "wire CRG into
   remaining harnesses" task failed three times. Added `exa` and `firecrawl` (keyless
   `mcp-remote`), wrote `sync-kimi-mcp.sh` and `sync-windsurf-mcp.sh`, backed up the live
   configs first. CRG itself had already been wired by `kimi-for-coding` on 2026-09-11.
5. **Stale-lock false positive (orama-system#421).** `scan_stale_git_locks` reported every lock
   under the git directory, including the `index.lock` git holds for the whole pre-commit run,
   so every commit through the hook failed. Reproduced three times, each with a new PID in the
   `next-index-<pid>.lock` name. Fixed with a 300 s age gate and a regression test (62 of 62).
6. **Branch drift and a parallel session (#421).** The branch was 69 commits behind `main`; the
   push guard `GIT_SCOPE_E_FILE_DELETION` correctly refused what looked like mass deletion (a
   stale base, not real deletions), so I rebased. Another session had already pushed a superset
   fix (`f3a636c8`: target directory created after the shell opened the redirect, pin `0.14.3`,
   installer docs). I merged non-destructively because a hard reset was hook-blocked and a
   fast-forward merge was denied by the safety layer.
7. **Cline's local work reviewed.** Nitpick fixes for #421; 22 ruff errors that became
   oramasys#62; the C2 digest and replay semantics confirmed spec-only with no executable code.
8. **C2 implementation.** Two parallel subagents in separate worktrees (digest module, permit
   lifecycle) against a frozen import contract. I read `decide_permit` line by line, corrected
   the digest encoding to the manifest's `canonical_digest`, integrated, and opened oramasys#63.
9. **Four CodeRabbit threads.** Docstring coverage on #421, #63 and #62, and two real findings on
   #22 (id-less A2A and MCP requests: the review cited `a2a.py`, the route lives in
   `routes.py`; fixed with four regression tests in `23ae397`, docstring pass `aca6508`). A
   first attempt at #22 reported a false "blocked" from a stale environment banner.
10. **Onboarding draft.** `/team-onboarding` produced `ONBOARDING.md` and a share link; it still
    awaits the operator's team name, starter task and team tips.
11. **Stacked-PR rescue.** Read GitHub's stacked-PR docs (`gh.io/stacks` and
    `gh.io/stacks-resolving-conflicts`, via Firecrawl and Exa, cross-checked). Stack #64 is
    `main` <- #63 <- #62; the `64` in `gh stack checkout 64` is a stack number. #62 showed
    `CONFLICTING` because `main` had gained PR #22's own ruff-cleanup commit. A cascading rebase
    onto the server-rebased #63 resolved two conflicts. A safety hook blocked my force-push, so
    I verified locally and handed the operator a lease-pinned command; the operator ran it
    (`319d447` to `da580b9`, forced update).
12. **The "No change is required" finding.** Section 2. After it, #62 was re-seated onto #63's
    new tip before the operator's push.
13. **Storage question.** The ~11 GB shown for the Cowork runtime is the sandbox VM image
    (section 7); nothing was deleted.

## 4. Errors and false premises caught

| Error or false premise | Whose | Caught by | Outcome |
| --- | --- | --- | --- |
| `mcp-remote@0.1.10` pinned in a nitpick fix (and again in a later relayed message) | subagent, relay | registry check (`npm view`) | Not on the registry; real pins are `0.14.3` (parallel session) and `0.1.43` (PT decision) |
| Default `json.dumps` separators in the binding digest | my brief to a subagent | review of the integrated code | Compact separators per `manifest.py` `canonical_digest` |
| "Existing convention in a `_fingerprint` helper" | my brief | the subagent | Helper absent in that checkout; real convention found |
| Sync scripts created the target directory too late | me | parallel session | Fixed in `f3a636c8` |
| "Kimi and Windsurf lack CRG" | me | reading the live configs | Already wired on 2026-09-11 |
| "Three FAILED rows need a decision" | me | board log history | Already terminal-closed on 2026-09-11 with reasons |
| "No code evidence for the M1 claims" | me | the consolidated plan | Work moved to cross-repo PRs tracked elsewhere |
| `ruff --fix` hoisted an import above a `sys.path` guard | me (earlier #62 fix) | rebase conflict | `main`'s `# noqa: E402` form kept |
| Auto-merged hunk re-added the hoisted import (imported twice) | rebase mechanics | re-diff against the base | Base file restored wholesale |
| First pass missed the nonterminal-state guard | me | operator's steer to re-analyze | Added test-first |
| Hygiene scan treated git's own `index.lock` as stale | repo hygiene hook | three reproductions | Age gate |
| Subagent "blocked: not a git repository" | stale environment banner | direct `git status` | False alarm, retried |
| Stale "binding_digest does not exist" docstring | PR #63 | CodeRabbit | Removed in `e03971f` |
| Relayed finding missing "No change is required" | relay | fetching the source review | Verdict restored, replies reworded |

## 5. Decisions

- Keep the digest `!=` comparison; a constant-time compare would be false assurance.
- Collaborator violations raise `ValueError` and stay outside the closed refusal vocabulary.
- Plain-git cascading rebase instead of installing the `gh-stack` extension; the operation is
  the same and no tooling was added to the operator's machine.
- When a safety hook blocked the only correct mechanism (a lease-pinned push), finish and verify
  everything, then hand the operator the exact command. No `+refspec` workaround.
- One PR-level reply per finding on #63, each with its own SHA, because the review had no
  inline threads.
- Leave the on-disk `0.1.43` stack pins alone (they match the PT decision of 2026-08-22) and do
  not re-sync the live editor configs without being asked.
- Do not delete the Cowork VM image; explain it and wait for a go-ahead.

## 6. Open items

- A known-answer test for the binding digest is recommended and not added; the current tests
  cannot detect a different JSON encoding.
- The `0.1.43` stack-template edits in the orama-system worktree were uncommitted at last check,
  on a branch whose PR has since merged; the live Kimi and Windsurf configs still carry
  `0.14.3` until the sync scripts are re-run.
- That worktree also holds another session's uncommitted gossip-bus work, including a
  `.codex/AGENTS.md` pointer to a policy document that is still untracked. Commit them together
  or the pointer breaks.
- Merge order for the stack is #63 then #62. The operator decision register (13 items) from the
  Cline pass is untouched.
- M1-D1 (ADR-71 note) has no successor tracker and needs an explicit decision. The operator-only
  physical-canary row stays queued.
- The onboarding draft awaits the operator's answers.
- Local scratch worktrees from today are disposable: the stale local copies of the old #62 and
  #63 branches must not be pushed from.

## 7. Reusable commands and facts

```bash
# the source review, to compare against a pasted finding
gh api repos/<owner>/<repo>/pulls/<n>/reviews/<review-id> --jq .body

# does a pinned version exist, and how old is it?
npm view <pkg> versions --json
npm view <pkg> time --json

# cascading rebase of an upper stack layer onto a changed lower tip (no gh-stack needed)
git rebase --onto <new-lower-tip> <old-lower-tip> <upper-branch>
# then a lease-pinned push naming the ref and the SHA you expect it to hold on the remote
```

Mutation proof for new guard tests: copy the file aside, strip the guards, run only the new
tests (they must fail), restore from the copy, and compare checksums.

The Cowork runtime shown in the desktop app is a VM image under
`~/Library/Application Support/Claude/vm_bundles/claudevm.bundle/`: `rootfs.img` is 10 GiB
(about 9.2 GB on disk), `rootfs.img.zst` is the 1.2 GB compressed download, and the only
per-session file is `sessiondata.img` at 29 MB. Removing the bundle frees about 11 GB and makes
Cowork rebuild it on next use; the Claude Code CLI and repositories are unaffected.

## 8. Lessons graduated today

| Lesson | Topic |
| --- | --- |
| `lesson_eccc672953c8` | "No change is required" is a proxy conclusion; re-derive with the method that tests it |
| `lesson_9154fade3391` | Compare pasted review text with the source review; word replies to the reviewer's real position |
| `lesson_2098f68bb79c` | Assert injected ports' documented postconditions; ValueError outside the refusal vocabulary |
| `lesson_979234ff54c7` | Stacked PRs: linear chain, cascading rebase, stack numbers, lease-pinned push, hook handoff |
| `lesson_eb5bab06d3c2` | Rebase onto a base with the same fix: classify hunks, re-diff, never hoist above a path guard |
| `lesson_e3c883a81242` | Prove a pinned npm version exists before committing it |
| `lesson_c0f079de3537` | Reuse the codebase's own canonical digest when the spec names an encoding |
| `lesson_48829035c8ff` | Read board history and find the successor tracker before characterizing board state |
| `lesson_ae8bbfa8e3e2` | Parallel subagents need separate worktrees, frozen contracts, and your own verification |
| `lesson_1c191f838964` | A hygiene scan inside a hook must age-gate locks; do not just delete them |

## 9. Process notes

- One uniquely tagged stash was used around a snapshot commit despite the shared-stack warning;
  the change was restored from a checksummed copy and only that entry was dropped.
- The board log was read with direct read-only SQL to see full task payloads; every write went
  through the supported coordination CLI.
- The safety layer blocked a hard reset and force pushes and denied a fast-forward merge. Each was
  handled by a non-destructive route or an operator handoff, never a bypass.
