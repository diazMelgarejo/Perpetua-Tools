# Branch Garbage — Parked for Later Disposal — 2026-07-19

## Status

Not yet deleted. Classified via `scripts/git/reanchor_scan.sh . origin/main all`
(tree-twin methodology — see `PR258_TREE_TWIN_SCRUB_SURGERY_2026-07-18.md`,
this note's direct predecessor) plus targeted `git cherry -v` verification.
User explicitly asked to park these rather than delete now. Do not garbage
these without a fresh `reanchor_scan.sh` re-run first — this list is a
snapshot at commit `896fb934b` (PT `origin/main` tip, PR #260 merge).

Already executed same-session (not parked, already gone): 4 local branches +
1 remote branch confirmed MERGED/in-main and deleted (`fix/gossip-db-canonical-resolution-20260717`
local+remote, `pr205-lessons-local`, `worktree-phase-1-impl`,
`worktree-pt-pr258-fixes-20260718`), 2 worktrees removed
(`pr-merge-conflict-resolution`, `phase-1-impl`). `pr204-clean` is also
confirmed MERGED/in-main but blocked on `git branch -D` by a safety hook
("blocked for safety during autoresearch sessions") — needs the user to run
it directly. `replace/pr258-clean-snapshot-20260718` (PR #260's actual head,
local + origin) deliberately left untouched, archived, not garbage.

## Parked candidates (likely-delete, not yet confirmed safe enough to force)

All reference points are against `origin/main` @ `896fb934b` unless noted.

| Branch | Scope | Unique commits | Twin | Verdict basis |
|---|---|---|---|---|
| `origin/cursor/inline-comment-resolution-09ea` | remote | 9 (7 confirmed via `cherry -v`) | `b4a1b429c` | Twin hash matches `PR258_TREE_TWIN_SCRUB_SURGERY_2026-07-18.md`'s "Current-main tree twin: b4a1b429" — this is almost certainly a pre-reanchor snapshot of the same `docs/coordination-consolidation-plan-20260717` lineage that PR #258 later superseded via scrub/reanchor, then PR #260 superseded again via "clean replay." **Uncertain piece**: one commit, `bff9a226 fix(coord): merge task snapshots and safe phase sort in CLI path (#259)`, is a real CLI-behavior fix, not just docs/memory. `git cherry` patch-id equivalence says it's NOT found in main, but PR #263's Part 1c rewrote large sections of the same CLI path — plausible the behavior is subsumed by a differently-shaped fix, not verified. Check this one commit's actual diff against PR #263's current `agent_coordination_core.py` CLI section before deleting; don't just trust the docs-heavy majority of the branch. |
| `origin/fix6-ci` | remote | 2 | `433ca8ca9` | `fix(ci): allow prebuilt mcp-profiles.js in repo hygiene` + `chore(env): add Gemini API key slots to example`. Grepped for both in current main (`repo_hygiene.py` for `mcp-profiles.js`, `.env.example` for `GEMINI`) — **neither found**. Unlike the other parked branches, this one is NOT yet confirmed to be duplicate/superseded content — it may be genuinely small unmerged work worth its own quick PR rather than deletion. Re-verify before treating as garbage. |
| `pr-211` (local) | local | 3 unique vs `pr-211-lessons-salvage` | `32f0b76bf` | Smaller, mostly-subsumed by `pr-211-lessons-salvage` (106 commits the other direction) — likely dupe of a dupe. |
| `pr-211-lessons-salvage` (local) | local, backs a temporary `pt-kimi-reanchor-review-20260715-001` worktree (absolute path omitted) | 32 | `963a5bdd3` | PR #261's title was literally "memory: salvage PR #211 lessons..." and merged into the chain that reached main via #260 — this branch's content is very likely the pre-salvage source material, now represented (possibly reshaped) in main via #261/#260. Not yet cherry-verified against current main's memory files specifically. |
| `pr258-work` (local) | local | 21 vs `pr260-work` | `963a5bdd3` | Confirmed via `git cherry -v pr260-work pr258-work`: 21 commits not equivalent to anything in `pr260-work` (now PR #263). This is almost certainly an earlier, now-superseded iteration of the same coordination-consolidation implementation work — PR #263 is the more complete, more recently reviewed version. Worth a quick scan for anything PR #263 might have genuinely dropped, but low suspicion. |
| `replace/pr258-clean-snapshot-20260718` (**local** copy, not origin) | local, backs a temporary `pt-pr258-clean-snapshot-20260718` worktree (absolute path omitted) | 32 | `963a5bdd3` | Distinct from the origin copy of the same branch name, which IS tree-twin-confirmed merged (`origin/replace/pr258-clean-snapshot-20260718` → tip twin `896fb934b`) and is the one the user said to archive, not delete. This **local** ref appears to be a stale/diverged copy that never got fast-forwarded to match its own origin counterpart after PR #260 merged. Needs a plain `git fetch && git reset --hard origin/replace/pr258-clean-snapshot-20260718` in that worktree (or just delete the stale local ref) rather than tree-twin surgery — likely simple staleness, not real divergent content. Re-check before assuming it's genuine unique work. |
| `rescue/pt-uncommitted-2026-06-30` (local) | local | 1 | `e925310d3` | Old one-commit rescue snapshot from 2026-06-30. Single commit, low risk either way; hasn't been individually cherry-verified. |
| `safety/pr215-pre-reanchor-20260715` (local) | local | 1 | `65916c81e` | Pre-reanchor safety snapshot for a different PR (#215) surgery, dated 2026-07-15. Same category as the PR258 surgery snapshots above — likely safe once that PR's own history is confirmed stable, not yet re-verified. |
| `salvage/state-transition-manager-06ce1309` (local) | local | 2 | `cea4b20a3` | Not yet individually cherry-verified against current main's state-transition-manager code. |
| `worktree-pr-203-stm-integration` (local) | local, backs still-existing `pr-203-stm-integration` worktree | 3 | `cea4b20a3` | Same twin as `salvage/state-transition-manager-06ce1309` — likely related/overlapping content (both STM-related). Worktree is still live; don't touch the branch without removing the worktree first (same pattern as `phase-1-impl`/`pr-merge-conflict-resolution` this session — check for uncommitted content in that worktree before any worktree-remove). |

## orama-system

Not yet scanned this session. `reanchor_scan.sh` needs to run there
separately (`bash scripts/git/reanchor_scan.sh <orama-path> origin/main all`)
before any orama branch can be classified. Known worktrees as of this
session: primary checkout (on `2026-07-19-001-clinebot-idempotent-install`,
committed, not yet PR'd), temporary `orama-launcher-cli-parity-20260715` and
`orama-pr183-launcher-harmonization-20260715` worktrees (absolute paths
omitted) — none classified.

## Doctrine reminder (inherited from PR258_TREE_TWIN_SCRUB_SURGERY)

Do not use ahead/behind or `git branch -d`'s ancestry check as the verdict —
both disagree with tree-twin post-rewrite, which is exactly why several of
the confirmed-safe deletions this session needed `-D` (blocked by hook) even
though `reanchor_scan.sh` had already proven them merged by content. Re-run
the scan fresh before acting; don't reuse these hashes past this repo's next
significant history event.
