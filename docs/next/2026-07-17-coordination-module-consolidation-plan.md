# Coordination Module Consolidation Plan

Date: 2026-07-17
Repository: `diazMelgarejo/Perpetua-Tools`
Status: plan only — no migration performed yet
Related: `docs/next/2026-07-17-phase-board-fragmentation-analysis.md` (the bug that motivated this), PT PR #256 (the point fix — deliberately kept separate from this plan per scope agreement below)

## Why this exists

Today's phase-board crash (`docs/next/2026-07-17-phase-board-fragmentation-analysis.md`) wasn't a one-off typo — it was a structural consequence of `scripts/agent_coordination.py`'s logic existing in four places at once (`agent_coordination.py`, `_core.py`, `_legacy.py`, `_phases.py`), with a fix landing in one and silently not reaching the others. The same failure mode will recur on the next fix unless the duplication itself is addressed, not just today's instance of it.

Both Claude and Codex independently verified the extent of the duplication and agree on the direction below (cross-checked via two different diff methods, consistent conclusion):

- `agent_coordination_core.py` vs `agent_coordination_legacy.py`: effectively full copies. `git diff` (context-based): 73 changed lines out of ~1300. `git diff --no-index --numstat` (Codex, line-count based): 1321 vs 1317 total lines, only 29 added / 25 removed between them. Either measure: **the two files are ~94-98% byte-identical**, and `core.py`'s only genuine value over `legacy.py` is a `ReorderBuffer` dedup fix and `--seq` claim support — both buried inside a full duplicate rather than expressed as a diff against a shared base.
- `agent_coordination_phases.py` is **orphaned**: not imported by the CLI facade or dispatch path, only by its own dedicated test file. It still carries a fourth copy of `PhaseState`/`_phase_list`/etc.
- Caller graph is clean: nothing outside `scripts/` and `tests/` imports any of these four files directly. A restructure is contained to this corner of the codebase.
- Four live commands have **zero test coverage** today: `_heartbeat_pulse`, `_heartbeat_kill`, `_heartbeat_cleanup`, `_workflow_critical_path`. Migrating these without characterization tests first would mean trusting the migration instead of verifying it.

## Scope boundary (agreed)

This plan is **deliberately not part of PR #256**. PR #256 is the point fix (canonical gossip-DB path resolution + the phase-sort-key fix) and stays scoped to that. This is a separate, later PR/PRs.

## Non-goals

- **Not feature flags.** Feature flags exist to toggle behavior that's legitimately optional or needs staged rollout. This isn't that — the four implementations of `_phase_list` aren't different *behaviors* someone might want to choose between, they're accidental copies that drifted. Flagging them would preserve the duplication and add a runtime switch on top of it. The fix is one implementation, not a flag choosing among several.
- No behavior changes bundled into the migration. Every command's observable output before and after must match — this is a structural refactor, not a feature change.
- No new capabilities added while consolidating.

## Target structure

Single source of truth per capability, under `orchestrator/coordination/` as first-class importable modules (not `scripts/`, since this is genuine orchestration logic other code may eventually want to import, not a one-off script):

```
orchestrator/coordination/
  paths.py           # canonical_repo_root, canonical_db_path, current_worktree_label
  claims.py          # register/claim/release/list/agents/log — the original basic claim board
  reorder_buffer.py  # ClaimSequence, ReorderBuffer, _claim_with_seq, _buffer_status, _buffer_drain
  task_queue.py       # TaskPriority, QueuedTaskState, _queue_add/_claim/_complete/_fail/_list/_status
  phases.py          # PhaseStatus, PhaseState, _phase_start/_update/_complete/_block/_unblock/_list/_status,
                      # _detect_blockers, _workflow_critical_path — using the already-fixed phase_sort_key
```

`scripts/agent_coordination.py` shrinks to pure CLI plumbing: argparse setup, subcommand dispatch, and thin `print()`-formatting calls into the modules above. No business-logic function bodies live in `scripts/` after this.

`agent_coordination_core.py`, `agent_coordination_legacy.py`, and `agent_coordination_phases.py` are deleted once migration is complete and verified — not kept as deprecated shims, since the caller-graph audit confirmed nothing external depends on them.

## Migration sequence (agreed with Codex)

1. **Characterization tests first**, for the four currently-uncovered live commands (`_heartbeat_pulse`, `_heartbeat_kill`, `_heartbeat_cleanup`, `_workflow_critical_path`), against the *current* code, before touching structure. These tests must fail if behavior changes during the later steps — that's what makes the migration verifiable rather than trusted.
2. **Extract each module** under `orchestrator/coordination/`, one capability at a time (`paths` first — smallest, already touched by PR #256's gossip-path fix, good warm-up; then `claims`, `reorder_buffer`, `task_queue`, `phases` last since it's the one with the most duplication and the most recent bug). For each: take the *best* existing version of each function (generally `core.py`'s, since it has the ReorderBuffer fix and `--seq` support `legacy.py` lacks; `phases.py`'s already-fixed `phase_sort_key` is now identical to `core.py`'s post-`9642ae24`, so either source works there), move it — not copy it — into its new module, update imports, run the full suite before moving to the next module.
3. **Shrink `scripts/agent_coordination.py`** to CLI plumbing only, importing from the five new modules.
4. **Delete the three old files** — only after parity tests cover the real CLI path (via `main()`/`_amain()`), not just facade-level imports, so the exact bug pattern from today (test passes, CLI doesn't) can't hide a regression here too.
5. **Full verification gate**, every subcommand smoke-tested live, not just unit-tested:

```bash
python3 scripts/review/repo_hygiene.py .
uv run --offline python -m pytest tests/ -k "coordination or gossip" -v

# Live smoke test — every subcommand, not just the ones with existing tests:
python3 scripts/agent_coordination.py register/claim/release/list/agents/log/...
python3 scripts/agent_coordination.py queue add/claim/complete/fail/list/status
python3 scripts/agent_coordination.py phase start/update/complete/block/unblock/list/status
python3 scripts/agent_coordination.py heartbeat list/check/dashboard/pulse/kill/timeline/cleanup
python3 scripts/agent_coordination.py buffer status/drain
python3 scripts/agent_coordination.py workflow critical-path
```

## Verdict

The three-file split was a reasonable evolutionary safety move at the time (freeze what works, layer new features without touching frozen code) but has crossed into maintenance debt now that a single bug required three separate patches to actually fix. Replace it with characterization-first consolidation into one canonical module per capability — not another layer of patching across copies.
