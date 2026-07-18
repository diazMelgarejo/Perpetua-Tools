<!-- /autoplan restore point: ~/.gstack/projects/diazMelgarejo-Perpetua-Tools/pr260-work-autoplan-restore-20260718-183829.md -->
# Coordination Module Consolidation Plan

Date: 2026-07-17 (revised 2026-07-18)
Repository: `diazMelgarejo/Perpetua-Tools`
Status: **revised after /autoplan CEO-phase dual-voice review + an independent parallel Codex engineering audit** — Part 1 ready to implement today; Part 2 (architecture) drafted, not yet executed; Part 3 explicitly deferred with caveats.
Related: `2026-07-17-phase-board-fragmentation-analysis.md` (the bug that motivated this), PT PR #256 (merged — canonical gossip-DB path resolution), PT PR #259 (merged — a *second* independent duplicate-file patch, landed after this plan was first written), `../references/coordination-consolidation-plan-review-2026-07-18.md` (Codex follow-up review), and the [Python `argparse` sub-command documentation](https://docs.python.org/3/library/argparse.html#sub-commands) (primary-source dispatch pattern)

## Revision note — why this doc changed shape

The original plan (2026-07-17) proposed one migration: extract all coordination
logic into 5 canonical modules, in one sequence, with PR #260's merge paused
until the full migration lands. `/autoplan`'s CEO phase ran dual voices (a
Claude subagent + Codex) independently against that plan. Both, unprompted,
converged on the same structural objection: **the plan bundles an urgent,
already-recurring bug fix with a separable, lower-urgency architecture
project, and gates an unrelated PR's merge on the larger piece.** Evidence
for "already-recurring": PR #259, merged 2026-07-17, had to hand-patch the
same two duplicate files (`agent_coordination_core.py`,
`agent_coordination_legacy.py`) for a second, independent bug — confirmed via
`gh pr view 259`.

While that review ran, Codex separately produced an independent engineering
audit, later distilled into the follow-up review linked above, and found something more serious
than either CEO voice: **the live CLI entrypoint bypasses the facade's
corrected, atomic queue-claim implementation.** This session verified it
directly, line by line:

- `scripts/agent_coordination.py:17` sets `_impl = agent_coordination_legacy`.
- `scripts/agent_coordination.py:25-33` imports `main()` from
  `agent_coordination_core`, not from the facade or `_impl`.
- `scripts/agent_coordination.py:580-596` patches the facade's corrected
  handlers (`_queue_claim`, `_phase_list`, all 7 heartbeat handlers, etc.)
  onto `_impl` — i.e., onto **legacy**, via `setattr`.
- `scripts/agent_coordination_core.py`'s own `_amain()` (the function `main()`
  actually calls) resolves `_queue_claim` from **core's own module globals** —
  untouched by the facade's patch loop, since that loop only mutates
  `agent_coordination_legacy`'s namespace.
- Net effect: `main()` → `core._amain()` → `core._queue_claim()`, and the
  facade's patch loop has zero effect on what actually runs.

The concrete consequence, verified by reading both implementations side by
side: the facade's `_queue_claim` calls `_try_atomic_claim()` — a real
`BEGIN IMMEDIATE` transaction against a UNIQUE-constrained `task_claims`
table, with retry-on-lock-contention and documented crash-safety reasoning.
**`_try_atomic_claim` exists in exactly one file: the facade.** Core's own
`_queue_claim` (the one `main()` actually runs) does a plain read-check-then-
emit with no atomic exclusion — a real, exploitable race window where two
agents can both pass the "not already claimed" check and both successfully
claim the same task. In a tool whose entire purpose is preventing exactly
that collision, this is the highest-priority finding in this document.

User direction, given explicitly after seeing both reviews: split the
deliverable, but do not procrastinate — ship Part 1 (the immediate fix)
today, draft Part 2 (the revamped architecture) today as well rather than
deferring it, and lay out anything that genuinely can wait with explicit
caveats. Framing: this is internal-only tooling with no external consumer
today ("rolling release"), and the consolidation is a **prerequisite** for
the eventual v2 migration — the goal is one complete, unambiguous
implementation to carry forward, not four ~94-98%-identical partial ones.
The architecture work is not premature investment in a soon-to-be-replaced
repo; it's cleanup so v2 doesn't inherit the ambiguity.

Partially reassuring, partially a correction: the user separately raised "the
database is scattered in 5 places." An earlier pass confirmed 5 call sites
(`orchestrator/memory_node.py`, `orchestrator/supervisor.py` ×2,
`orchestrator/lan_gossip_bridge.py` ×2) all route through the canonical
`resolve_gossip_db_path()` / `_canonical_repo_state_dir()` resolver PR #256
introduced — that part is genuinely fixed. **What that pass missed: the
`agent_coordination*.py` file family — the exact subject of this plan — has
its own, separate, triplicated path resolver that does NOT go through
`resolve_gossip_db_path()` at all.** `agent_coordination_core.py:298-307`,
`agent_coordination_legacy.py` (same lines), and `agent_coordination_phases.py`
each independently define their own `canonical_repo_root()` /
`canonical_db_path()` via a direct `git rev-parse --git-common-dir` call —
none of them read `PT_STATE_DIR`, `GOSSIP_DB_PATH`, or any env var. `main()`'s
real dispatch path (`core._amain()`) calls this non-canonical, env-blind
version, not `gossip_bus.py`'s resolver. Caught by this session's Eng-phase
Claude subagent review, independently of both CEO voices and Codex's
engineering audit — the same "fix landed in one copy, not others" failure
class this plan exists to fix, recurring a third time, this time in path
resolution rather than business logic. See Part 1's revised verification
section and the new provenance-table row below.

## Why this exists

Today's phase-board crash (`2026-07-17-phase-board-fragmentation-analysis.md`) wasn't a one-off typo — it was a structural consequence of `scripts/agent_coordination.py`'s logic existing in four places at once (`agent_coordination.py`, `_core.py`, `_legacy.py`, `_phases.py`), with a fix landing in one and silently not reaching the others. The queue-claim bypass documented above is the same failure class recurring a second time, this time undiscovered until this review. The same failure mode will recur on the next fix unless the duplication itself is addressed, not just today's instances of it.

Both Claude and Codex independently verified the extent of the duplication and agree on the direction below (cross-checked via two different diff methods, consistent conclusion):

- `agent_coordination_core.py` vs `agent_coordination_legacy.py`: effectively full copies. `git diff` (context-based): 73 changed lines out of ~1300. `git diff --no-index --numstat` (Codex, line-count based): 1321 vs 1317 total lines, only 29 added / 25 removed between them. Either measure: **the two files are ~94-98% byte-identical**, and `core.py`'s only genuine value over `legacy.py` is a `ReorderBuffer` dedup fix and `--seq` claim support — both buried inside a full duplicate rather than expressed as a diff against a shared base.
- `agent_coordination_phases.py` is **not import-orphaned but not import-referenced either** — nothing in `scripts/` imports it, but `PHASE_TRACKING.md` documents direct CLI invocation of it in 24+ places, and the file itself received a real bug fix as recently as 2026-07-17 (`9642ae24`, the original phase-sort-key fix). Treat it as a live, directly-invoked tool with unknown current usage, not dead code — deletion requires a compatibility path, not a straight `rm`.
- Caller graph (import-level) is clean: nothing outside `scripts/` and `tests/` *imports* any of these four files directly — but "imported" and "used" are not the same thing, per the `phases.py` finding above and per the CLI's own direct-invocation usage pattern (all of these are also invoked as standalone scripts via `python3 scripts/agent_coordination*.py ...`, not only as libraries).
- Four live commands have **zero test coverage** today: `_heartbeat_pulse`, `_heartbeat_kill`, `_heartbeat_cleanup`, `_workflow_critical_path`. Migrating these without characterization tests first would mean trusting the migration instead of verifying it.
- **New finding (this revision):** a fifth, more serious gap — `_queue_claim`'s atomic-claim protection (`_try_atomic_claim`) is *facade-only* and is currently bypassed entirely by the live CLI path. See "Revision note" above.

## Analysis findings (from the phase-board root-cause writeup)

The full diagnosis is in `2026-07-17-phase-board-fragmentation-analysis.md`
(authored on the PR #256 branch; on `main` once #256 merges — #256 has since
merged). The four load-bearing findings, and how each maps onto this plan:

1. **The crash was structural, not a typo.** `_phase_list` / its sort-key
   helper existed three times (`_core.py`, `_legacy.py`, facade
   `agent_coordination.py`); the fix landed only in the facade, while the
   copy the live CLI actually runs (`_core.py`, via `main()`/`_amain()`)
   still carried the bug. → *Target structure: single source of truth.*
2. **A passing test coexisted with a broken CLI.** The existing test
   imported `_phase_list` from the facade, resolving to the good, unused
   implementation — real test, passed, wrong code path. Green tests do not
   prove the CLI works when the tested symbol and the invoked symbol have
   drifted apart. → *Parity tests must go through the real CLI path
   (`main()`/subprocess), not facade imports — this revision's Part 1 fix
   and Part 2's Phase 4 both apply this directly.*
3. **A subtler second bug was avoided by the correct fix.** The good version
   used a tuple-of-ints sort key on purpose — a naive float cast mis-orders
   minor versions past two digits (`Phase-2.10` before `Phase-2.9`). → carry
   the tuple-of-ints `_phase_sort_key`, never re-introduce the float cast
   (already landed everywhere via `9642ae24`; preserve it in every future
   move).
4. **Five hypotheses ruled out first** (stale bytecode, a shadowing
   site-packages copy, `sorted()` skipping `key()` on a 1-element list, a
   `conftest.py` swallowing the error, a duplicate test definition) — all
   documented so the path isn't re-walked. → *Characterization-first,
   verify-don't-trust posture throughout the migration — this revision
   extends that posture to a fifth, newly-found bypass (queue-claim).*

The through-line: **a fix landing in one of several duplicate
implementations doesn't help unless every caller actually reaches it.** Two
separate bugs (phase-sort, queue-claim) have now demonstrated this in the
same file pair. This plan removes the duplication so the next fix lands once.

## Scope boundary (agreed)

This plan is **deliberately not part of PR #256**. PR #256 is the point fix (canonical gossip-DB path resolution + the phase-sort-key fix) and stays scoped to that — it has since merged. This plan is a separate, later PR/PRs, now split into three parts (below) per explicit user direction after the CEO-phase review.

## Non-goals

- **Not feature flags.** Feature flags exist to toggle behavior that's legitimately optional or needs staged rollout. This isn't that — the four implementations of `_phase_list` (and now `_queue_claim`) aren't different *behaviors* someone might want to choose between, they're accidental copies that drifted. Flagging them would preserve the duplication and add a runtime switch on top of it. The fix is one implementation, not a flag choosing among several.
- No behavior changes bundled into Part 2's migration beyond what Part 1 explicitly fixes. Every command's observable output before and after must match — Part 2 is a structural refactor, not a feature change.
- No new capabilities added while consolidating.
- **Not premature v2 investment.** This work is scoped as a prerequisite for a clean v2 migration (one complete implementation to carry forward instead of four ~98% ones), not as new architecture for a repo the org has separately marked for eventual replacement. Keep Part 2's package boundaries mechanical and evidence-backed (per the provenance table below), not speculative platform design.

---

## Part 1 — Immediate fix (today, small, no module extraction)

**Goal:** eliminate the live queue-claim atomicity bypass, while verifying that the already-landed phase-sort correction remains reachable through the real CLI. Do this without touching `legacy.py` or `phases.py` and without starting the package migration. This is a correctness fix to the file `main()` actually executes, using the same "test through the real CLI path" discipline the root-cause doc itself established.

**Scope — move into `agent_coordination_core.py`, replacing its own inferior versions in place (not a new module, not a deletion of `legacy.py`/`phases.py`):**

| Symbol | Source to promote into `core.py` | Why |
|---|---|---|
| `canonical_repo_root`, `canonical_db_path` | delegate to `orchestrator.gossip_bus`'s `resolve_gossip_db_path()`/`resolve_default_state_dir()` instead of re-deriving independently | **New (Eng-phase finding):** core's own version of these two functions is a third, undiscovered duplicate — env-var-blind, doesn't honor `PT_STATE_DIR`/`GOSSIP_DB_PATH`. `agent_coordination_legacy.py` and `agent_coordination_phases.py` carry byte-for-byte copies. This is required for Part 1's own verification gate to actually run isolated — without it, every "isolated" subprocess test below silently writes to the real repo's live coordination database. |
| `_try_atomic_claim`, `_release_claim_with_event` | facade (`agent_coordination.py:131-182, 193-232`) | The only implementations with real atomicity (`BEGIN IMMEDIATE` + UNIQUE-constrained `task_claims` table + retry-on-lock). Core's current versions have no such protection. (`_release_claim`, the bare no-event variant, has zero call sites anywhere in `scripts/`, `orchestrator/`, or `tests/` — confirmed by grep. Drop it rather than promote unused surface area.) |
| `_queue_claim`, `_queue_complete`, `_queue_fail` | facade | Facade's versions call the atomic helpers above; core's don't. |
| `_phase_list` | already fixed identically in both (post-`9642ae24`) — no change needed, just confirm both stay in sync until Part 2 deletes the duplicate | — |
| 7 heartbeat handlers (`list`, `check`, `dashboard`, `pulse`, `kill`, `timeline`, `cleanup`) | no Part 1 move | Core already parses and dispatches all seven leaves through lazy facade imports. Characterize that live path in Phase 0F, then migrate the handlers once into `liveness.py` in Part 2. |

**Verification (required before landing Part 1):**

The original draft of this section had two bugs found by this session's own Eng-phase review, corrected below: the race script's hardcoded task ID never matches what `_queue_add` actually generates (`f"{phase}-{task_name}-{uuid.uuid4().hex[:8]}"`, not the literal string passed in), and `PT_STATE_DIR` doesn't isolate anything until the `canonical_db_path` fix above lands — both are folded into the corrected script:

```bash
# Confirm main() now resolves the atomic-safe implementations:
python3 -c "
import asyncio, inspect
from scripts.agent_coordination_core import _queue_claim
print(inspect.getsource(_queue_claim))
"  # must show _try_atomic_claim in the body, not a plain emit

# Real CLI-path race test — the actual bug being fixed. Requires the
# canonical_db_path delegation above to be in place first, or this pollutes
# the live repo's coordination database instead of testing in isolation.
python3 -c "
import os, re, subprocess, sys, tempfile, concurrent.futures
os.environ['PT_STATE_DIR'] = tempfile.mkdtemp()
add = subprocess.run(
    [sys.executable, 'scripts/agent_coordination.py', 'queue', 'add', 'race-task', 'test', '--priority', 'HIGH'],
    capture_output=True, text=True, check=True,
)
m = re.search(r'enqueued: (\S+)', add.stdout)
assert m, f'could not parse task_id from queue add output: {add.stdout!r}'
task_id = m.group(1)
def claim(agent_num):
    return subprocess.run(
        [sys.executable, 'scripts/agent_coordination.py', 'queue', 'claim', task_id, f'agent-{agent_num}'],
        capture_output=True, text=True,
    )
with concurrent.futures.ThreadPoolExecutor(4) as ex:
    results = list(ex.map(claim, range(4)))
successes = [r for r in results if 'claimed:' in r.stdout]
assert len(successes) == 1, f'expected exactly 1 successful claim, got {len(successes)}: {[r.stdout for r in results]}'
assert all('ERROR:' in r.stdout for r in results if r not in successes), [r.stdout for r in results]
print('OK: exactly one claim succeeded under 4-way concurrency')
"

uv run --offline python -m pytest tests/ -k "coordination or gossip" -v
python3 scripts/review/repo_hygiene.py .
```

Reference: the in-repo tests already do this correctly and can be used as a template — `tests/test_agent_coordination_queue.py::test_multiple_agents_cannot_claim_same_task` and `::test_queue_claim_concurrent_race_only_one_succeeds` both extract the real `task_id` from the emitted event before claiming, rather than assuming it.

**Effort:** small — moving/replacing ~5 functions plus the path-resolver delegation, within one existing file, plus one corrected race-condition test. No new files, no deletions, no dispatch-table rewrite. Directly actionable today.

### Part 1b — database-error contract (separate follow-up)

`GossipBus.emit()` and `GossipBus.tail()` currently surface raw exceptions for
SQLite lock, disk, and corruption failures. Normalizing those failures into a
stable CLI error is useful, but it is a separate observable behavior change,
not part of the queue-claim atomicity repair. Implement it in a separate commit
with real-entrypoint tests that cover representative read and write failures
across command families. Do not normalize only the functions touched by Part 1,
which would leave the CLI with inconsistent error behavior.

**Scope note (Eng-phase finding):** this must also cover the atomic-claim code
Part 1 promotes, not only plain `emit()`/`tail()`. `_try_atomic_claim` and
`_release_claim_with_event` already handle `aiosqlite.IntegrityError` and
lock-related `OperationalError` cleanly, but any other exception (disk full,
corruption) falls through their bare `except Exception: rollback; raise` with
no clean CLI message — inconsistent with the rest of the file post-Part-1. If
Part 1b is scoped to only `gossip_bus.py`'s two functions, this gap will be
missed since it's a different code path.

---

## Part 2 — Revamped architecture draft (drafted now, not deferred; execution scheduled separately)

Incorporates Codex's parallel engineering audit and the corrections recorded in `../references/coordination-consolidation-plan-review-2026-07-18.md`. This supersedes the original plan's "Target structure" and "Migration sequence" sections below.

### Target structure (revised — adds `liveness.py` and `__init__.py`)

```text
orchestrator/coordination/
  __init__.py        # NEW — public API surface, explicit re-exports
  paths.py           # canonical_repo_root, canonical_db_path, current_worktree_label
  claims.py          # register/claim/release/list/agents/log — the original basic claim board
  reorder_buffer.py  # ClaimSequence, ReorderBuffer, _claim_with_seq, _buffer_status, _buffer_drain
  task_queue.py      # TaskPriority, QueuedTaskState, _queue_add/_claim/_complete/_fail/_list/_status
                      # (post-Part-1: includes _try_atomic_claim, _release_claim, _release_claim_with_event)
  phases.py          # PhaseStatus, PhaseState, _phase_start/_update/_complete/_block/_unblock/_list/_status,
                      # _detect_blockers, _workflow_critical_path — using the already-fixed _phase_sort_key
  liveness.py         # NEW — the 7 heartbeat handlers + adapter boundary around orchestrator.heartbeat_monitor
                      # (Codex's finding: the original 5-module target silently omitted heartbeat/liveness
                      # ownership entirely, which would have reproduced "no business logic in scripts/"
                      # as a false claim — pulse/kill/cleanup are not print formatting)
```

### Source-provenance table (replaces the original plan's coarse "generally core.py's" heuristic)

Per Codex's audit: a file-level heuristic is too coarse for a mixed implementation. Every row must name the winning source, why, and what verifies equivalence before the losing implementation is deleted.

| Capability | Canonical source to preserve | Notes |
|---|---|---|
| Paths and DB resolution | `orchestrator.gossip_bus` public resolvers | Already canonical via PR #256 — reuse, do not re-derive. |
| Basic register/claim/release/list/agents/log | legacy/facade aliases | Preserve established basic board behavior — these are the original claim board, distinct from queued-task claim below. |
| Reorder buffer and sequenced claim | core | Includes first-arrival dedup and drain-marker replay fixes. |
| Queue add and queue data types | core/legacy after equivalence proof | Do not assume equivalence; verify it with a diff-based test before choosing. |
| Queue claim/complete/fail/list/status | **facade** (post-Part-1: promoted into core) | Includes atomic claim/release transactions, retries, corrected display semantics — see Part 1 above, already resolved by the time Part 2 executes. |
| Phase state mutations/status/workflow | core/legacy after equivalence proof | Keep tuple-of-integers phase ordering (`_phase_sort_key`), never re-introduce the float cast. |
| Corrected phase state fold/list | facade or proven tree-twin | Already identical post-`9642ae24` — confirm, don't re-derive. |
| Heartbeat commands (7) | facade plus `orchestrator.heartbeat_monitor` | Needs the new explicit `liveness.py` target module — was previously unowned in the target structure. |

For every row, before extraction: record source file, symbol, current CLI reachability, tests that exercise it, and the reason it wins. "Best" must be evidence-backed, not asserted.

**`claim` vs `queue claim` — distinct semantics, do not conflate.** These are two different claim mechanisms (the original basic board claim vs. the atomic queued-task claim) that happen to share the verb "claim" in the CLI surface. Keep separate adapter and domain-function names for each even where they overlap syntactically.

**`task_queue.py` breaks the package's own abstraction boundary (Eng-phase finding).** The other five modules touch only `GossipBus.emit()`/`tail()` — an event-log-only interface. `_try_atomic_claim`/`_release_claim_with_event` reach past that: they call `bus.connect()` directly, issue raw `BEGIN IMMEDIATE`, own a private `task_claims` table, and catch `aiosqlite.IntegrityError`/`OperationalError` by name. `task_queue.py` is the only module with a second, SQLite-specific dependency surface the package boundary doesn't abstract. Resolve one of two ways during Phase 1 (package skeleton): promote a proper `GossipBus.atomic_claim()` public primitive so `task_queue.py` stays on the same interface as its siblings, or explicitly document the asymmetry in this table rather than let it stay implicit.

### Migration sequence (revised — adds Phase 0F freeze + mandatory temporary re-exports)

**Phase 0F — freeze the executable contract (new, run first, before any extraction):**
1. Enumerate all 29 parser leaves and their arguments (see command inventory below).
2. Record current runtime handler identity for each leaf — which file's function actually executes, verified the same way this revision verified the queue-claim bypass (read the real dispatch path, don't assume).
3. Record the chosen canonical source for each symbol, using the provenance table above.
4. Identify any remaining current-runtime-vs-best-implementation divergence beyond what Part 1 already fixed.
5. Add characterization tests that cover state and side effects, not just non-empty stdout (see corrected examples below).

**Phase 1 — canonical package skeleton:** create the 6-file structure above (5 modules + `__init__.py`), empty/stub bodies, no behavior yet.

**Phase 2 — capability extraction, one at a time, with temporary re-exports (not a bare move):**

The original plan's "move, don't copy" instruction breaks mid-migration — a literal move without a compatibility shim breaks every other file's imports the moment one capability moves. Copying preserves the exact duplication this plan removes. Correct sequence per capability:

1. Move the implementation into the canonical module (`orchestrator/coordination/<mod>.py`).
2. Replace the old definitions in `core.py`/`legacy.py`/`phases.py` with temporary `from orchestrator.coordination.<mod> import <symbol>` re-exports — scaffolding for the migration window, explicitly not final deprecated shims.
3. Run focused tests (`coordination or gossip`) + repo hygiene.
4. Continue capability by capability: `paths` → `claims` → `reorder_buffer` → `task_queue` → `phases` → `liveness` (smallest/lowest-risk first, `liveness` last since it's newly-scoped and touches `orchestrator.heartbeat_monitor`).
5. Delete all three compatibility modules (`core.py`, `legacy.py`, `phases.py`) atomically, in one revertible commit, only after every capability routes through the canonical package and the Phase 4 gate below passes.

**Phase 3 — parser-owned dispatch (replaces the original plan's hand-maintained `_DISPATCH` dict):**

Per [Python's official `argparse` docs](https://docs.python.org/3/library/argparse.html#sub-commands), a separately-maintained parser and dispatch table can drift silently — which is structurally the same failure class as everything else in this document. Use `set_defaults(handler=...)` on each leaf subparser instead, so parser registration and handler registration are one operation:

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(required=True)

    queue = commands.add_parser("queue")
    queue_commands = queue.add_subparsers(required=True)
    queue_claim = queue_commands.add_parser("claim")
    queue_claim.set_defaults(handler=handle_queue_claim)
    # ... one add_parser + set_defaults pair per leaf, nested to match "queue claim" etc.

    return parser


async def handle_queue_claim(args: argparse.Namespace, bus: GossipBus) -> None:
    await task_queue.claim(bus, task_id=args.task_id, agent_id=args.agent_id)


async def run(args: argparse.Namespace) -> int:
    bus = make_gossip_bus(resolve_gossip_db_path())
    await getattr(bus, "local", bus).init_db()
    await args.handler(args, bus)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(run(args))
```

Each handler stays a thin async adapter translating `argparse.Namespace` into a call on one canonical capability module — no business logic in the adapter layer, matching the original plan's own stated goal but now structurally enforced (no separate table to drift).

**Real command inventory (29 leaf commands, replaces the original plan's 4-row illustrative example):**
- 6 top-level: `register`, `agents`, `claim`, `release`, `list`, `log`
- 7 phase: `start`, `update`, `complete`, `block`, `unblock`, `list`, `status`
- 1 workflow: `critical-path`
- 6 queue: `add`, `claim`, `complete`, `fail`, `list`, `status`
- 7 heartbeat: `list`, `check`, `dashboard`, `pulse`, `kill`, `timeline`, `cleanup`
- 2 buffer: `status`, `drain`

**Phase 4 — exhaustive real-entrypoint parity (gate before deletion):**

```python
# tests/test_agent_coordination_cli_parity.py  (NEW — gate before deletion)
import os, subprocess, sys
from pathlib import Path

def _cli(*args, env=None, timeout=30):
    return subprocess.run(
        [sys.executable, "scripts/agent_coordination.py", *args],
        capture_output=True, text=True, encoding="utf-8",
        env=env, timeout=timeout,
    )

def test_parser_exposes_exactly_29_leaf_commands():
    """Golden contract test -- deriving expected AND actual from the same
    parser only proves the parser agrees with itself. This list is the
    external, hand-maintained source of truth; an intentional CLI change
    requires an intentional edit here, not an automatic pass."""
    from scripts.agent_coordination import build_parser
    EXPECTED = {
        ("register",), ("agents",), ("claim",), ("release",), ("list",), ("log",),
        ("phase", "start"), ("phase", "update"), ("phase", "complete"),
        ("phase", "block"), ("phase", "unblock"), ("phase", "list"), ("phase", "status"),
        ("workflow", "critical-path"),
        ("queue", "add"), ("queue", "claim"), ("queue", "complete"),
        ("queue", "fail"), ("queue", "list"), ("queue", "status"),
        ("heartbeat", "list"), ("heartbeat", "check"), ("heartbeat", "dashboard"),
        ("heartbeat", "pulse"), ("heartbeat", "kill"), ("heartbeat", "timeline"),
        ("heartbeat", "cleanup"),
        ("buffer", "status"), ("buffer", "drain"),
    }
    assert len(EXPECTED) == 29
    actual = _enumerate_leaf_paths(build_parser())  # recursive subparser walk
    assert actual == EXPECTED, f"missing={EXPECTED - actual} extra={actual - EXPECTED}"

def test_phase_list_via_real_cli_does_not_crash_on_nonnumeric(tmp_path: Path):
    # The regression class from the phase-board bug AND the queue-claim bypass:
    # must run the CLI path, not import from the facade (which historically
    # resolved to a different, already-fixed copy than the one main() calls).
    env = {**os.environ, "PT_STATE_DIR": str(tmp_path)}
    started = _cli("phase", "start", "StateTransitionManager-Integration", "--agent", "a", env=env)
    assert started.returncode == 0, started.stderr
    r = _cli("phase", "list", env=env)
    assert r.returncode == 0, r.stderr
    assert "StateTransitionManager-Integration" in r.stdout

# Repeat the 4-way race test from Part 1's verification section here as a
# permanent regression test, not a one-off manual check.
```

Cadence (per Codex's finding that the original plan's "full suite" language and the shown filtered command disagreed):
- Per module (Phase 2 loop): focused `coordination or gossip` tests + repo hygiene.
- Before old-file deletion (Phase 4): all 29-command contract tests + subprocess parity tests.
- Before merge: full repository suite (`pytest tests/` unfiltered), repo hygiene, all 29 isolated CLI smoke cases.

**Phase 5 — atomic compatibility deletion:** delete `core.py`, `legacy.py`, `phases.py` in one revertible commit, only after Phase 4's full gate passes. Not kept as deprecated shims — same rationale as the original plan, now with actual evidence (the caller-graph + direct-invocation audit above) rather than an unverified assumption.

### Corrected characterization test examples (Codex's audit: the original scaffold wasn't runnable)

The original plan's sample called `_register(bus, "agent-x", "worktree-a")` against a live signature of `_register(bus, agent_id, agent_type, model, notes)` — both pulse and kill samples would have raised `TypeError` before pinning any real behavior. Corrected:

```python
# tests/test_agent_coordination_characterization.py  (NEW — Phase 0F)
"""Pin CURRENT behavior of the previously-uncovered coordination commands
before any consolidation move. Assertions cover state transitions, event
payloads, database rows, exit status, stdout, and stderr -- loose substring
or non-empty-stdout checks are insufficient characterization."""
import pytest
from orchestrator.gossip_bus import GossipBus


@pytest.fixture
async def bus(tmp_path):
    b = GossipBus(str(tmp_path / "char.db"))
    await b.init_db()
    return b


@pytest.mark.asyncio
async def test_heartbeat_pulse_emits_exact_event(bus, capsys):
    from scripts.agent_coordination import _heartbeat_pulse, _register
    await _register(bus, "agent-x", "worktree-a", "sonnet", "")
    await _heartbeat_pulse(bus, "agent-x")
    events = await bus.tail(limit=10, event_type="heartbeat")
    pulse_events = [e for e in events if e["payload"].get("kind") == "agent_pulse"]
    assert len(pulse_events) == 1
    assert pulse_events[0]["payload"]["agent_id"] == "agent-x"
    # No secret or local-topology fields beyond the frozen current contract:
    assert set(pulse_events[0]["payload"].keys()) <= {"kind", "agent_id", "worktree", "timestamp"}
    assert "agent-x" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_heartbeat_kill_marks_agent_and_liveness_interpretation(bus, capsys):
    from scripts.agent_coordination import _heartbeat_kill, _register
    await _register(bus, "agent-y", "worktree-b", "sonnet", "")
    await _heartbeat_kill(bus, "agent-y", "manual stop")
    events = await bus.tail(limit=10, event_type="heartbeat")
    kill_events = [e for e in events if e["payload"].get("kind") == "agent_killed"]
    assert len(kill_events) == 1
    assert kill_events[0]["payload"]["reason"] == "manual stop"
    assert "agent-y" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_heartbeat_cleanup_releases_actually_stale_claim(bus, capsys, monkeypatch):
    # An empty-board no-op does not characterize cleanup -- create a real
    # stale claim first.
    from scripts.agent_coordination import _heartbeat_cleanup, _claim, _register
    from orchestrator import heartbeat_monitor
    real_now = heartbeat_monitor.time.time()
    await _register(bus, "agent-z", "worktree-c", "sonnet", "")
    await _claim(bus, "agent-z", "stale-task", "")
    monkeypatch.setattr(
        heartbeat_monitor.time,
        "time",
        lambda: real_now + heartbeat_monitor.LIVENESS_STALLED_SEC + 1,
    )
    await _heartbeat_cleanup(bus)
    events = await bus.tail(limit=10, event_type="heartbeat")
    releases = [e for e in events if e["payload"].get("kind") == "agent_release"]
    assert len(releases) == 1
    assert releases[0]["payload"]["task"] == "stale-task"
    assert releases[0]["payload"]["auto_released"] is True


@pytest.mark.asyncio
async def test_workflow_critical_path_orders_by_dependency(bus, capsys):
    # Eng-phase finding: the original version of this test captured output
    # spanning both _phase_start calls, so it passed on _phase_start's own
    # "started: Phase-1 ..." print noise -- not on _workflow_critical_path's
    # actual output. Isolate the capture to just the call under test.
    from scripts.agent_coordination_core import _workflow_critical_path, _phase_start
    await _phase_start(bus, "Phase-1", None, "agent-a")
    await _phase_start(bus, "Phase-2", ["Phase-1"], "agent-b")
    capsys.readouterr()  # discard setup noise from the two _phase_start calls
    await _workflow_critical_path(bus)
    out = capsys.readouterr().out
    assert out.index("Phase-1") < out.index("Phase-2")  # dependency ordering, not just non-empty
```

**Real bug this isolation exposes, not just a test artifact:** with the capture
correctly isolated, this test currently *fails* against live code. Both phases
have zero `estimated_duration_hours`/elapsed time, and `longest_chain`'s chain-
extension check (`agent_coordination_core.py:840`) uses strict `sub_duration +
current_duration > max_duration`. With both sides `0.0`, `0.0 > 0.0` is `False`,
so the chain never extends past a single node — `Phase-2` never appears in the
"Longest chain" output at all. This is a real, currently-shipping bug in
`_workflow_critical_path`, not introduced by this plan, but it means the
"already fixed, no change needed" characterization test in Step 1 of Part 2's
Phase 0F cannot simply pin current behavior as correct — it needs to pin the
bug's existence and decide whether to fix it (change `>` to `>=`, or add an
explicit tie-break) as part of this migration, or explicitly defer the fix to
Part 3 while the test documents the known-broken behavior instead of a
non-existent-correct one.

> First-run protocol unchanged: run once against real code, verify the assertions actually hold, tighten any placeholder before treating a characterization test as pinned.

---

## Part 3 — Explicitly deferred, with caveats (do not silently drop; revisit before v2)

These are real, evidence-backed follow-ups surfaced during this review. Deferred deliberately, not overlooked — each has a caveat naming what happens if left open.

- [ ] **Local topology embedded in runtime event labels.** `current_worktree_label()` includes the absolute current working directory, and queue/heartbeat events carry it into shared coordination state. Today's portable-memory/security work (this same session, `bin/orama-system/skills/security/SKILL.md`) classifies concrete workstation topology as sensitive local data. **Caveat: do not fix this inside Part 2's behavior-preserving refactor** — it's a genuine behavior change (event payload shape), and mixing it into Part 2 would violate that part's own non-goal. Track as a standalone security follow-up: replace the absolute path with a portable branch/repo label or opaque stable ID, then migrate stored historical events deliberately.
- [ ] **`agent_coordination_phases.py`'s actual current usage is unverified.** `PHASE_TRACKING.md` documents direct invocation, but nobody has confirmed whether those documented workflows are still followed day-to-day or are themselves stale docs. **Caveat: Phase 5's deletion gate must re-check this specifically** (e.g., a deprecation-warning period on the standalone-invocation path before outright removal), not just confirm the Python-level caller graph is clean — the whole point of this finding was that caller-graph alone missed it once already.
- [ ] **Integrate the clinebot idempotent install pattern** into `install.sh`/`start.sh`. Pattern captured in PT `.agent` memory as `lesson_6125fbdf46ec`. Job-board task `Agent-Setup-Integrate clinebot idempotent install pattern into install.sh/start.sh-595d71da`, currently claimed by `claude-sonnet-g7-impl`, unimplemented. **Caveat: fully unrelated to coordination consolidation** — kept here only because it was riding along in the prior revision's TODO list; track it independently, it has no dependency relationship to Parts 1-2.
- [ ] **Merge PR #260.** Per the CEO-phase consensus (both dual voices, independently): **un-gate this.** The prior revision paused #260's merge on completing the full migration; both reviews flagged that as sitting on already-reviewed, unrelated value (CodeRabbit fixes, the portable-memory prevention mechanism, 7 passing tests) for an artificial dependency. Caveat: this is a reversal of an explicit prior instruction from earlier in this session — flagging it rather than silently changing it. Recommend merging #260 on its own merits once its own review gates pass, independent of Part 1/2/3's timeline.
- [ ] **Fixed-window event replay can silently drop terminal state under real load (Eng-phase finding, pre-existing).** Every read path in this file family (`_latest_task_snapshots` limit=1000, `_all_phase_states`/`_get_latest_phase_state` limit=500, `find_agent_heartbeats`/`find_open_claims` limit=200-500, `_get_reorder_buffers` limit=1000) folds the most recent N events *across all kinds*, not the most recent N events for the specific task/phase/agent being queried. Under sustained heartbeat/pulse traffic — the exact load this tool is built for — an older task's `task_complete` event can scroll past the window before a later `_queue_claim` check runs, causing a false `ERROR: task not found` for a task that genuinely completed. **Caveat: predates this plan, Part 2's "no behavior change" scope carries it forward unexamined by design** — worth its own follow-up (per-key windowing or a materialized-state table) rather than folding into a behavior-preserving refactor.
- [ ] **`_try_atomic_claim`/`_release_claim_with_event` retry budget is unvalidated past 4-way concurrency (Eng-phase finding).** `_LOCK_RETRIES = 3`, `_LOCK_RETRY_SECONDS = 0.05` gives ~150-300ms of backoff before returning an ambiguous "another agent won or the database remained busy" message. Part 1's corrected race test only proves correctness at 4-way concurrency, not at this org's actual observed multi-agent swarm sizes. **Caveat: not a known bug, just an unproven assumption** — worth a load test at realistic fleet size before relying on the retry budget under real contention, not blocking Part 1's landing.

## Verdict

The three-file split was a reasonable evolutionary safety move at the time (freeze what works, layer new features without touching frozen code) but has crossed into maintenance debt — a single bug class (fix lands in one copy, not others) has now recurred twice (phase-sort, queue-claim), and the second instance carried a real concurrency-safety consequence, not just an inconsistency. Part 1 closes both known instances of that failure class today, using the same file `main()` already executes — no new surface, no deletion, no migration risk. Part 2 is the evidence-backed architecture to prevent a third instance, drafted now per explicit direction rather than deferred, sequenced with a frozen-contract phase and mandatory re-export scaffolding so no intermediate commit is ever in a half-migrated, import-broken state. Part 3 names what can genuinely wait, with a reason attached to each item so "deferred" doesn't become "forgotten."
