# Coordination Module Consolidation Plan

Date: 2026-07-17
Repository: `diazMelgarejo/Perpetua-Tools`
Status: plan only — no migration performed yet
Related: `2026-07-17-phase-board-fragmentation-analysis.md` (the bug that motivated this), PT PR #256 (the point fix — deliberately kept separate from this plan per scope agreement below)

## Why this exists

Today's phase-board crash (`2026-07-17-phase-board-fragmentation-analysis.md`) wasn't a one-off typo — it was a structural consequence of `scripts/agent_coordination.py`'s logic existing in four places at once (`agent_coordination.py`, `_core.py`, `_legacy.py`, `_phases.py`), with a fix landing in one and silently not reaching the others. The same failure mode will recur on the next fix unless the duplication itself is addressed, not just today's instance of it.

Both Claude and Codex independently verified the extent of the duplication and agree on the direction below (cross-checked via two different diff methods, consistent conclusion):

- `agent_coordination_core.py` vs `agent_coordination_legacy.py`: effectively full copies. `git diff` (context-based): 73 changed lines out of ~1300. `git diff --no-index --numstat` (Codex, line-count based): 1321 vs 1317 total lines, only 29 added / 25 removed between them. Either measure: **the two files are ~94-98% byte-identical**, and `core.py`'s only genuine value over `legacy.py` is a `ReorderBuffer` dedup fix and `--seq` claim support — both buried inside a full duplicate rather than expressed as a diff against a shared base.
- `agent_coordination_phases.py` is **orphaned**: not imported by the CLI facade or dispatch path, only by its own dedicated test file. It still carries a fourth copy of `PhaseState`/`_phase_list`/etc.
- Caller graph is clean: nothing outside `scripts/` and `tests/` imports any of these four files directly. A restructure is contained to this corner of the codebase.
- Four live commands have **zero test coverage** today: `_heartbeat_pulse`, `_heartbeat_kill`, `_heartbeat_cleanup`, `_workflow_critical_path`. Migrating these without characterization tests first would mean trusting the migration instead of verifying it.

## Analysis findings (from the phase-board root-cause writeup)

The full diagnosis is in `2026-07-17-phase-board-fragmentation-analysis.md`
(authored on the PR #256 branch; on `main` once #256 merges). The four
load-bearing findings, and how each maps onto this plan:

1. **The crash was structural, not a typo.** `_phase_list` / its sort-key
   helper existed three times (`_core.py`, `_legacy.py`, facade
   `agent_coordination.py`); the fix landed only in the facade, while the
   copy the live CLI actually runs (`_core.py`, via `main()`/`_amain()`)
   still carried the bug. → *Target structure: single source of truth.*
2. **A passing test coexisted with a broken CLI.** The existing test
   imported `_phase_list` from the facade, resolving to the good, unused
   implementation — real test, passed, wrong code path. Green tests do not
   prove the CLI works when the tested symbol and the invoked symbol have
   drifted apart. → *Step 4: parity tests through the real CLI path
   (`main()`/subprocess), not facade imports.*
3. **A subtler second bug was avoided by the correct fix.** The good version
   used a tuple-of-ints sort key on purpose — a naive float cast mis-orders
   minor versions past two digits (`Phase-2.10` before `Phase-2.9`). → *Step
   2 sourcing rule: carry the tuple-of-ints `phase_sort_key`, never
   re-introduce the float cast.*
4. **Five hypotheses ruled out first** (stale bytecode, a shadowing
   site-packages copy, `sorted()` skipping `key()` on a 1-element list, a
   `conftest.py` swallowing the error, a duplicate test definition) — all
   documented so the path isn't re-walked. → *Characterization-first,
   verify-don't-trust posture throughout the migration.*

The through-line: **a fix landing in one of several duplicate
implementations doesn't help unless every caller actually reaches it.** One
bug took three separate patches across three copies today; this plan removes
the duplication so the next fix lands once. The analysis also flags the
exact follow-up this plan fulfills — true de-duplication into one canonical
implementation all callers import, rather than N copies kept consistent by
hand.

## Scope boundary (agreed)

This plan is **deliberately not part of PR #256**. PR #256 is the point fix (canonical gossip-DB path resolution + the phase-sort-key fix) and stays scoped to that. This is a separate, later PR/PRs.

## Non-goals

- **Not feature flags.** Feature flags exist to toggle behavior that's legitimately optional or needs staged rollout. This isn't that — the four implementations of `_phase_list` aren't different *behaviors* someone might want to choose between, they're accidental copies that drifted. Flagging them would preserve the duplication and add a runtime switch on top of it. The fix is one implementation, not a flag choosing among several.
- No behavior changes bundled into the migration. Every command's observable output before and after must match — this is a structural refactor, not a feature change.
- No new capabilities added while consolidating.

## Target structure

Single source of truth per capability, under `orchestrator/coordination/` as first-class importable modules (not `scripts/`, since this is genuine orchestration logic other code may eventually want to import, not a one-off script):

```text
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

## Scaffolding (reference only — NOT applied while the codebase is frozen)

Everything below is target-state reference for whoever executes the
migration. **None of it is applied in this PR** — several agents depend on
the current code being frozen as-is, so this plan documents the shape of
the work without performing it. Signatures below were read from the live
code at this commit and are accurate as of freeze; re-verify against the
tree before use.

### Step 1 — characterization tests for the 4 uncovered commands

The point of a characterization test is to pin *current* behavior exactly,
so a later structural move that changes output fails loudly. These assert
against the real CLI-reachable functions, not facade aliases. Live
signatures at freeze: `_heartbeat_pulse(bus, agent_id)`,
`_heartbeat_kill(bus, agent_id, reason)`, `_heartbeat_cleanup(bus)` (all
defined in `scripts/agent_coordination.py`), and
`_workflow_critical_path(bus)` (in `_core.py`/`_legacy.py`).

```python
# tests/test_agent_coordination_characterization.py  (NEW — step 1)
"""Pin CURRENT behavior of the 4 previously-uncovered coordination commands
before any consolidation move. If any assertion here changes during the
migration, the migration changed behavior — which this refactor forbids."""
import pytest

from orchestrator.gossip_bus import GossipBus


@pytest.fixture
async def bus(tmp_path):
    b = GossipBus(str(tmp_path / "char.db"))
    await b.init_db()
    return b


@pytest.mark.asyncio
async def test_heartbeat_pulse_emits_and_prints(bus, capsys):
    from scripts.agent_coordination import _heartbeat_pulse, _register
    await _register(bus, "agent-x", "worktree-a")
    await _heartbeat_pulse(bus, "agent-x")
    out = capsys.readouterr().out
    # Characterize the exact current contract (update RHS to match observed
    # output when first run — this is a pin, not an aspiration):
    assert "agent-x" in out


@pytest.mark.asyncio
async def test_heartbeat_kill_marks_agent(bus, capsys):
    from scripts.agent_coordination import _heartbeat_kill, _register
    await _register(bus, "agent-y", "worktree-b")
    await _heartbeat_kill(bus, "agent-y", "manual stop")
    assert "agent-y" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_heartbeat_cleanup_runs_clean_with_no_stale(bus, capsys):
    from scripts.agent_coordination import _heartbeat_cleanup
    await _heartbeat_cleanup(bus)
    # No stale claims → the "nothing released" path. Pin whichever string
    # the current code prints.
    assert capsys.readouterr().out  # non-empty; tighten to exact text on first run


@pytest.mark.asyncio
async def test_workflow_critical_path_on_empty_board(bus, capsys):
    from scripts.agent_coordination_core import _workflow_critical_path
    await _workflow_critical_path(bus)
    assert capsys.readouterr().out  # pin exact output on first run
```

> First-run protocol: run once, read the actual stdout, then replace each
> loose `assert ... in out` / non-empty check with the exact observed
> string. A characterization test is only as good as the precision of what
> it pins.

### Step 2 — module extraction pattern (move, don't copy)

Each new module is the *single* home for its capability. Take the best
existing version of each function (per the plan's step-2 sourcing rules),
`git mv`-in-spirit it (move the body, delete the source), and leave the old
files importing nothing new. Example for the smallest capability, `paths`:

```python
# orchestrator/coordination/paths.py  (NEW — step 2, `paths` first)
"""Canonical repo/worktree/db path resolution — single source of truth.

Moved (not copied) from scripts/agent_coordination_core.py at consolidation.
The gossip-DB half of this already went canonical in PR #256
(orchestrator/gossip_bus.py::_canonical_repo_state_dir); this module is the
coordination-side counterpart so both agree on one repo root per worktree.
"""
from __future__ import annotations

from pathlib import Path

# Reuse the already-canonical resolver rather than re-deriving it — the
# PR #256 fix is the single source of truth for "the repo root shared by
# every worktree", and coordination paths must not fork from it.
from orchestrator.gossip_bus import _canonical_repo_state_dir


def canonical_repo_root() -> Path:
    state = _canonical_repo_state_dir()
    if state is None:
        raise RuntimeError(
            "canonical_repo_root requires a git-backed repo; "
            "_canonical_repo_state_dir() returned None"
        )
    return state.parent


def canonical_db_path() -> str:
    from orchestrator.gossip_bus import resolve_gossip_db_path
    return resolve_gossip_db_path()


def current_worktree_label() -> str:
    # Move the current implementation verbatim; do not "improve" it here —
    # behavior parity is the contract for this refactor.
    ...
```

Per-module loop (run in full before starting the next module):

```bash
# For each capability in order: paths → claims → reorder_buffer → task_queue → phases
uv run --offline python -m pytest tests/ -k "coordination or gossip" -v
python3 scripts/review/repo_hygiene.py .
# Stage only the files that belong to this capability's move — never `git add -A`,
# which can sweep in unrelated agent/doc/user changes sitting in the tree.
# Or, leave commit creation to the operator entirely.
git add orchestrator/coordination/<mod>.py scripts/agent_coordination.py tests/<relevant_test_file>.py
git commit -m "refactor(coord): extract <capability> to orchestrator/coordination/<mod>.py (move, no behavior change)"
```

### Step 3 — `scripts/agent_coordination.py` becomes CLI-only

After extraction, the facade holds argparse wiring + dispatch + `print()`
formatting, importing every function from the new modules. No business-logic
bodies remain in `scripts/`. Shape:

```python
# scripts/agent_coordination.py  (SHRUNK — step 3)
from orchestrator.coordination import paths, claims, reorder_buffer, task_queue, phases

_DISPATCH = {
    ("register",): claims._register,
    ("claim",):    claims._claim,
    ("queue", "add"):    task_queue._queue_add,
    ("phase", "list"):   phases._phase_list,
    ("workflow", "critical-path"): phases._workflow_critical_path,
    # ... one row per subcommand; this table IS the CLI surface now
}

def main() -> int:
    args = _build_parser().parse_args()
    handler = _resolve(_DISPATCH, args)      # maps subcommand tuple → coroutine
    return asyncio.run(_run(handler, args))

if __name__ == "__main__":
    raise SystemExit(main())
```

### Step 4 — parity tests on the REAL CLI path, then delete

The exact trap from today's bug (facade test passes, live CLI crashes) is
avoided only if parity is asserted through `main()`/`_amain()`, not through
facade-level imports. Drive the CLI as a subprocess so the test exercises
the same entrypoint a user hits:

```python
# tests/test_agent_coordination_cli_parity.py  (NEW — step 4, gate before deletion)
import os, subprocess, sys
from pathlib import Path

def _cli(*args, env=None, timeout=30):
    return subprocess.run(
        [sys.executable, "scripts/agent_coordination.py", *args],
        capture_output=True, text=True, encoding="utf-8",
        env=env, timeout=timeout,
    )

def test_phase_list_via_real_cli_does_not_crash_on_nonnumeric(tmp_path: Path):
    # The regression class from the phase-board bug: must run the CLI path,
    # not import _phase_list from the facade (which historically resolved to
    # a different, already-fixed copy than the one main() actually calls).
    # Isolate state so the subprocess cannot touch the developer's live DB.
    env = {**os.environ, "PT_STATE_DIR": str(tmp_path)}
    started = _cli(
        "phase", "start", "StateTransitionManager-Integration", "--agent", "a",
        env=env,
    )
    assert started.returncode == 0, started.stderr
    r = _cli("phase", "list", env=env)
    assert r.returncode == 0, r.stderr
    assert "StateTransitionManager-Integration" in r.stdout
```

Only once this passes for every migrated command are
`agent_coordination_core.py`, `agent_coordination_legacy.py`, and
`agent_coordination_phases.py` deleted (single commit, so the deletion is
atomic and revertible).

## Verdict

The three-file split was a reasonable evolutionary safety move at the time (freeze what works, layer new features without touching frozen code) but has crossed into maintenance debt now that a single bug required three separate patches to actually fix. Replace it with characterization-first consolidation into one canonical module per capability — not another layer of patching across copies.

## Deferred to next PR (TODO)

This PR is docs-only — the plan above, plus interim hardening fixes on the frozen
modules. None of the migration steps in "Scaffolding" are applied here. Parked
explicitly rather than started partially, so the next PR begins from a clean,
fully-scoped list instead of a half-migrated tree:

- [ ] **Execute the migration sequence** (Steps 1-4 above): characterization
      tests for the 4 uncovered commands → extract `orchestrator/coordination/{paths,claims,reorder_buffer,task_queue,phases}.py`
      one capability at a time (move, not copy) → shrink `agent_coordination.py`
      to CLI-only → CLI-parity tests on the real entrypoint → delete
      `agent_coordination_core.py`, `agent_coordination_legacy.py`,
      `agent_coordination_phases.py` in one atomic, revertible commit.
- [ ] **Integrate the clinebot idempotent install pattern** into `install.sh`/
      `start.sh` (`npm view <pkg> version` compare-before-install, `command -v`
      guard, fail-open on unreachable registry). Pattern captured in PT
      `.agent` memory as `lesson_6125fbdf46ec`. Job-board task
      `Agent-Setup-Integrate clinebot idempotent install pattern into
      install.sh/start.sh-595d71da`, currently claimed by
      `claude-sonnet-g7-impl`, unimplemented.
- [ ] **Merge PR #258** once the migration above lands and passes CI — merge
      remains explicitly paused until then.

Both TODO items were deliberately not started in this PR per explicit
instruction to pause implementation pending a joint session with Codex.

## Handoff to Codex — status before the scrub/surgery session

What landed on this branch since the TODO above was parked (interim
hardening only, still no migration steps started):

- **CodeRabbit review 4727106123, all 6 findings resolved.** 1 was already
  fixed by prior work (verified, not re-touched); the other 5 were
  genuinely still open despite the branch's privacy-hardening scope and
  are now fixed: a hardcoded token removed from a tracked bootstrap script
  (now sources from a CI secret or local config, synthetic placeholder as
  last resort — never a real identity), a key-trim fix in the attribution
  parser (implemented more robustly than the review's own literal
  suggestion, which had a latent bug — verified functionally), a
  previously-vacuous allowlist test now genuinely exercises its own logic,
  `check_identity` now honors a configured private owner name instead of a
  hardcoded fallback (kept backward compatible on purpose), and a
  private-literal check that was wrongly gated behind an unrelated
  readiness flag now runs unconditionally.
- **New prevention mechanism, source-side.** `.agent/memory/path_hygiene.py`
  gained `sanitize_private_identity_leaks()`, chained into the existing
  `sanitize_tracked_path_leaks()` so every `.agent/memory` writer — `learn.py`
  included — now redacts configured private identity/attribution literals
  *before* they can reach `lessons.jsonl`, not just at the pre-commit gate
  afterward. Pre-commit hooks were checked and were already correctly
  wired (`repo_hygiene.py`'s `main()` already calls
  `scan_private_verboten_literals`); the gap was entirely upstream, at the
  point memory gets written. 7 new tests, full suite green.
- **Current tracked tree on this branch: clean.** No forbidden-label hits,
  consistent with the branch scrub report at
  `docs/security/2026-07-18-pt-branch-metadata-scrub.md`.

**Before proceeding with the scrub/surgery session:** that report
explicitly scoped PT's side only and deferred orama-system "for a separate
decision," noting orama-system history was not rewritten in that pass. If
the same class of literal leak exists on the orama-system side, the
source-side prevention fix above (or its equivalent) is worth landing
there too before or alongside that repo's own history operation — same
rationale: catching it at the write boundary means a future agent can't
reintroduce the leak even if a pre-commit gate is ever bypassed or
misconfigured. Otherwise nothing on the PT branch itself blocks the
session from proceeding; the two TODO items above (migration execution,
clinebot install pattern) remain exactly as parked.
