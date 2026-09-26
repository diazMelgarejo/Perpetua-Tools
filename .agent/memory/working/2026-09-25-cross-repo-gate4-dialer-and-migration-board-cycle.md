# Cross-Repo Cycle — Gate 4 Dialer, Migration Board, and Dispatch Fix (2026-09-25)

**Agent:** `cline-session-20260907` (type `coordination/claude`, model `cline`)
**Repos touched:** Perpetua-Tools (PT), oramasys/oramasys (v2), orama-system (methodology)
**Board:** PT GossipBus — `.state/perpetua_core.db`
**Landed on:** PT PR #399 branch (private-range gate). Note that #399 itself is already
merged to `main` as `33186a1b`; this record rides the PR branch so the memory travels
with the change that motivated it.

## Perpetua-Tools

| Commit | Change | Push state |
| ------ | ------ | ---------- |
| `547e8a94` | Launcher dial-target validation: DNS-resolve every candidate and address-classify each answer before dialing (Gate 4 Half B). Rejects metadata/link-local, Teredo, 6to4, 6to4 relay anycast, CGNAT and public answers; allows loopback and RFC1918/ULA. Both probe functions gate through one resolver, and the LM Studio path validates **before** the Authorization header is attached so a hostile DNS answer cannot harvest the token. | on origin (verified ancestor of the halfb remote tip) |
| `ef8f7663` | Memory path-hygiene fix: `sanitize_tracked_path_leaks` only matched the scratch-directory path form (directory plus a trailing segment), so a **bare** directory mention with no trailing segment passed through verbatim and reached tracked memory, and matching inside a path left a telltale parent-directory prefix behind. Added an optional parent-directory group plus a bare-directory pattern with a negative lookahead; 3 regression tests; 23/23 pass. | local |
| `2ff46898` | Attribution guards synced from the orama-system canonical via the sanctioned sync script, adding `cline.bot` as a well-known co-author domain. PT's copy had drifted; the fix was to sync, not hand-edit, and the trailer was then proven accepted by running the guard directly. | local |
| `a86a11a2` | Memory capture of this cycle (8 lessons + 3 episodic reflections + session record). | local |

**Board work.** Six `MigrationProgram` reminder rows were reconciled **closed against
their verified implementation lanes** (never claimed for implementation, per the
program's own invariant), the seventh was left queued because it is operator-only, and
a claim stranded by a verifiably DEAD agent was cleared with a disclosed takeover.
Counts were re-measured in clean detached worktrees rather than trusted from the
lane notes: 18/18 discovery tests at the C1 commit, 13/13 guard tests at
`5ab05db`, and the Kungfu manifest at exactly 288 rows = 46 candidate / 96 blocked /
146 superseded with both pinned revisions resolving as real commits.

**Codex hand-off.** A read-only K1 source-provenance audit had been dispatched to a
Cline worker identity that was DEAD with no deliverable. The audit was completed and
attributed to the live identity rather than spoofing a pulse for a stopped agent, and
the dispatch-blocking shell defect it reported was reproduced and fixed (below).

## oramasys / orama-system

| Commit | Change | Push state |
| ------ | ------ | ---------- |
| `059cd4c1` | Gateway dialer now treats the **6to4 relay anycast** prefix `192.88.99.0/24` as prohibited, matching its Teredo and 6to4 siblings. Shared infrastructure any attacker-adjacent network can answer on. 45/45 dialer tests. | on remote |
| `88209503` | ClinePass dispatch wrapper: `auto_args` / `reasoning_args` are legitimately empty when the installed CLI advertises neither flag pair, and under `set -u` on stock macOS bash 3.2 an empty-array expansion is an **unbound-variable error**, so dispatch aborted instead of running. Length-guarded both expansions; reproduced the abort end-to-end with a stubbed CLI; 128 `set -u` scripts scanned and this was the only defective site. | local |

Gate 4 Half A (the dedicated dialer itself, `db35f4b`) had already merged as
oramasys PR #3 (`98b2e6b`); this cycle contributed the Half B launcher adoption on
the PT side and the 6to4 gap on the v2 side, keeping the two layers in parity.

## Cross-repo findings

1. **Denylist parity is a set, not a point.** The v2 dialer carried Teredo and 6to4
   but not the relay anycast prefix; the v1 launcher carried none of them. Both sides
   now classify the same families, reimplemented natively because PT must not import
   a v2 package across the regime boundary.
2. **The RFC1918 tracked-literal gap was real and is now closed independently.**
   Staging a config file containing a real LAN address made the pre-commit hook exit
   0, and the private-literal store did not contain it, so the inline "never commit
   real IPs" rule was doctrine-only. Records show PR #399 (`33186a1b`) subsequently
   added exactly that gate, so the finding was confirmed rather than merely asserted.
3. **LAN-IP working tree resolved correctly.** The address now lives in gitignored
   `.env.local` and the tracked config files match HEAD, so environment-local values
   stay local by construction.
4. **A board snapshot is a volatile observation.** The same rows were observed open,
   terminal, held, and re-claimed inside one hour; every per-task claim in this
   record is therefore sourced from that task's own ordered event timeline, and one
   earlier statement of mine was explicitly corrected on the board rather than left
   standing.

## Lessons graduated this cycle

Board/lane discipline · dead-claimant recovery · cleanup requeues a retry-exhausted
task · operator-only evidence integrity · temp-worktree commit reachability ·
detached-worktree verification against a diverged checkout · board-snapshot
volatility · bash 3.2 `set -u` empty-array recurrence · denylist parity across
layers (`lesson_ad1dc8dc22d7`) · memory-merge discipline (`lesson_4121f37d8f08`).

The last two were learned while producing this very record: the first from auditing
the sibling dialer layer, the second from a gate rejection caused by carrying
sanitized claim text into a graduated candidate whose id must stay a tooling
derivation of that exact claim.

## Open items for humans

Physical canary evidence (operator-only, runbook published) · push of the local
commit batches · A1 acceptance pending steward review of the blocked ownership
slices in `sources/k1-blockers.md`.