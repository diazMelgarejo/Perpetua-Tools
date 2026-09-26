# Session follow-up lessons — after PT #399 / orama #366 (2026-09-26)

The private-range gate lessons themselves already landed on
`main` via Perpetua-Tools PR #399 (`b2ccd30d`, merge `33186a1b`) and the
working narrative
`.agent/memory/working/2026-09-26-staged-private-range-gate-pt399-orama366.md`
(`lesson_ef546c0b6d79` and siblings `lesson_665bf32d698c` …
`lesson_392f8817a393`).

This file records **additional** lessons from the same operating day after
those PRs merged: remote-worker board binding, Kungfu Wave 0 review jobs,
and post-merge documentation channel choice.

## Already on main (do not re-graduate)

| ID | Topic |
| --- | --- |
| `lesson_665bf32d698c` | complete `ipaddress` tokens |
| `lesson_5e615e7b7866` | hunk-aware `+++` |
| `lesson_2f4e1642302e` | UTF-8 git subprocess |
| `lesson_1276b14ab68a` | diff-filter `ACMRT` |
| `lesson_886258809448` | cached vs CI three-dot range |
| `lesson_793c8a605f43` | lockstep scanner text incl. docstrings |
| `lesson_4ed523cc3d15` | full-SHA reply then resolve; review stays COMMENTED |
| `lesson_392f8817a393` | do not sweep identity-policy / PR-body dirt |
| `lesson_ef546c0b6d79` | pointer to the gate narrative |

PR closeout comment (full table):
https://github.com/diazMelgarejo/Perpetua-Tools/pull/399#issuecomment-5843549161

## New lessons in this follow-up PR

| ID | Rule |
| --- | --- |
| `lesson_b4b39bd86ecd` | Cloud workers cannot atomically claim a Mac-local GossipBus; use PR comments + handoff files remotely; pulse on same-machine summons. |
| `lesson_a17856504b2a` | Empty `depends_on` does not authorize claiming a job whose notes require a published `source_ref` / `expected_base_sha`. |
| `lesson_ec064e8b08df` | Kungfu Wave 0: Python validator is fail-closed authority; schema is shape-only until it encodes ownership routing; pytest must load the real inventory. |
| `lesson_a8a799f105d2` | After lockstep merge, put the session closeout + lesson table on the merged PT PR as a **comment**, not a body rewrite under body-guard mode. |
| `lesson_7e8df60c294f` | Refresh the local coordination handoff registry and board snapshot after consequential board writes. |

## Merged pair (context)

| Repo | PR | Merge |
| --- | --- | --- |
| Perpetua-Tools | #399 | `33186a1bf25dc4eeb5477d4fc110682ee7ca1d59` |
| orama-system | #366 | `e12374d59486948e1f2da4b4e7aa099b88ee65ab` |

## Kungfu Wave 0 board jobs (same day)

| Job | Disposition |
| --- | --- |
| W0-C1 manifest ownership | completed (288 rows, 0 active, routes clean) |
| W0-A1 contract/negative fixtures | completed (16 tests; schema≠Python gap recorded) |
| W0-R1 Cursor shared-claim transport | **held** pending published PT `source_ref` |
