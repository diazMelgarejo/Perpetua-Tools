# 2026-10-14 — lockstep gates, T2 review fixes, fork-main scripts (events)

Working memory for the orama-system PR 404 / Perpetua-Tools PR 441 lockstep pair and the
oramasys PR 36 review fixes. Times are UTC with the operator's PHT (UTC+8) equivalent where
the date differs. Lessons are in `lessons.jsonl`; this note is the *sequence* and the
*why*, so a later session can tell what was decided and what is still open.

## Sequence

| # | Event | Outcome |
| --- | --- | --- |
| 1 | oramasys PR 36 reported as "merge conflicts" | Not a conflict: `BEHIND`, `MERGEABLE`. `merge-tree` clean; 726 tests on the merged tree. Ruleset has strict up-to-date policy, so `update-branch` (non-force) then required checks. `lesson_bc8a328bb7ea` |
| 2 | Operator: "Merge now" | Merge was denied by the permission classifier; left for the operator. Not worked around |
| 3 | CodeRabbit Major carried from PR 31: BoundedObserver worker cancellation released accounting while the thread ran | Root cause: `to_thread` await cancelled, thread kept holding the event. Fix owned by thread completion; 4 tests red first. `lesson_a0981e39e9d2` |
| 4 | CodeRabbit on PR 36: shutdown can return normally with the circuit tripped | Clean path recorded `completed`. Now `DeliveryDrainIncomplete` -> `unknown` / `delivery.shutdown_incomplete`. `lesson_05079ae0790d` |
| 5 | Review on PR 404 flagged "Oct 14 vs Oct 13" | Timezone artefact: accepted 2026-10-13T20:00:58Z = 2026-10-14 04:00 PHT. Dual stamps added. `lesson_0011a00a007f` |
| 6 | Same review: publish recipe re-resolved the expected head and relied on the lease alone | Capture once after the fetch; require ancestry before push. `lesson_129c8d545b61` (refines `lesson_590ae6342a41`) |
| 7 | `clone_sibling` reset an existing checkout unconditionally | Gated `mirror_sync_checkout`; `checkout -B <sha>` on a verified-clean tree, no hard reset. `lesson_fdcff1271292` |
| 8 | Operator asked for the original purpose before the fork-main fix | Recalled from PT memory (below); confirmed the design |
| 9 | Fork-main scripts gated | Found: `git fetch origin upstream` never fetched the remote; AlphaClaw's second step dropped unpushed integration commits and reported success; my first gate counted `origin/HEAD` as a holder. `lesson_7fa7d6219657`, `lesson_9fd72be1baa7` |
| 10 | Lockstep audit | 108/108 cited lesson ids present at PT head, none retracted; guard-sync re-run into PT changed nothing |

## Why the fork-main scripts exist (first principles, from PT memory)

- Periscope: `main` and `agentsview` are upstream mirrors; `merged` is the only integration
  base; a rewrite recovery must preserve both mirror parents and the proven `merged` tree
  (`lesson_fdb82283644f`). The script exists because three dependabot PRs were merged into the
  mirror by mistake, so those three commits are the only ones it may drop.
- AlphaClaw: the integration branch never merges into `main`; PRs into `main`, sync upstream
  into `main`, then reverse-merge `main` into the integration branch, union, never delete
  (`lesson_881de77084d5`); session start syncs `main` fast-forward-only
  (`lesson_9fffe4530a95`).

## Calibration notes (what went wrong in my own work)

- My first ledger of the eight reapply formulations had wrong dates and wording for rows 2-7,
  written from memory; the audit against `lessons.jsonl` caught it. Audit before quoting.
- My recipe for publishing used a lease alone; a reviewer showed it permits a non-fast-forward.
  A claim about git semantics needs the same verification as a claim about code.
- The gate I wrote for `clone_sibling` over-refused (a commit another branch holds is not at
  risk); the fork-main scripts exposed it. Precision about *what is actually lost* is the
  difference between a gate that is used and one that is bypassed.
- The destructive-command hook blocked harmless text four times. It is a stop sign for the
  action, not a lint to route around (`lesson_8efd05953754`).

## Open items

- PR 36 merge (operator decision; permission was denied to the agent). Order: orama PR 404
  before PT PR 441.
- PT PR 441 lessons cited by orama as pending-merge must be re-verified after it lands.
- The periscope lease protects the push window only; a rewind-and-re-add between fetch and push
  is bounded by the declared-commit allowlist and the backup ref, not detected.
- oramasys PR 31 / phylax contract items from earlier sessions are unchanged by this work.
