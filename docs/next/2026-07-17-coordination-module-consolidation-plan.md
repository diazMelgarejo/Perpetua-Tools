<!-- /autoplan restore point: ~/.gstack/projects/diazMelgarejo-Perpetua-Tools/pr260-work-autoplan-restore-20260718-183829.md -->
# Coordination Module Consolidation Plan

Date: 2026-07-17 (revised 2026-07-18)
Repository: `diazMelgarejo/Perpetua-Tools`

> **2026-07-22 closure update:** Parts 1/1b/1c/1d **confirmed landed** —
> squash-merged via `28c425f9 fix(coord): implement coordination-module
> consolidation Parts 1-1d + PR #260 review fixes (#263)`. Part 2 remains
> **deferred to v2 oramasys** (post-migration): its gate — "Phase 0F's live
> re-verification" — doesn't correspond to any `Phase 0F` document or
> artifact anywhere in this repo, so the block is genuinely ambiguous, not
> just unstarted. Part 3 stays explicitly deferred per its own text below.
> Full ledger + reasoning:
> `orama-system/docs/plans/2026-07-22-cross-repo-out-of-scope-closure.md`
> (item #7) and `orama-system/references/tiered-model-implementation-
> navigator.md` § Cross-Repo Plan Register.

Status: **`/autoplan` CLOSED — dispatch-ready for Part 1/1b/1c/1d.** Sequence: CEO-phase dual-voice review → independent parallel Codex engineering audit → systematic re-audit against Codex's 7-finding follow-up review (`../references/coordination-module-consolidation-plan-review-2026-07-18.md`) → two Codex-board-flagged blockers resolved (queue-ownership runtime-owner labeling; queue complete/fail authorization decision) → final adversarial gate (Codex + Kimi, independent). Codex's final gate pass caught one more real, code-verified gap (the queue-ownership promotion overclaimed `list`/`status` alongside `claim`/`complete`/`fail`) — fixed by splitting the provenance-table row rather than expanding Part 1's scope. Kimi's parallel gate pass was run against a stale primary-checkout copy of this file (dispatch error — wrong `--add-dir`) and its findings do not apply to this text; spot-checked its specific claims (heartbeat module ownership, `task_queue.py`/`phases.py` helper functions, `--seq` legacy support) against the current plan directly and confirmed each was already addressed. **Parts 1/1b/1c/1d ready to implement today** (atomic-claim promotion + scoped queue-ownership correction, DB-error contract, exit-code/stderr/split-message fix, `PHASE_TRACKING.md` rewrite + quick-start); Part 2 (architecture) drafted, not yet executed, gated behind Part 1 landing and Phase 0F's live re-verification; Part 3 explicitly deferred with caveats.
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
| `_queue_claim`, `_queue_complete`, `_queue_fail` | facade | Facade's versions call the atomic helpers above; core's don't. **Confirmed (Codex review 2026-07-18): this promotion fixes a second, independent bug, not just the race condition** — core's current `_queue_fail` emits the `task_failed`/`task_abandoned` event but never calls `_release_claim_with_event`, so a failed task's `task_claims` row stays locked forever even though the event log shows it as requeued/abandoned — every future claim attempt on that `task_id` would hit a stale "already claimed" error permanently. The facade's version already correctly releases the row in both the retry and abandon branches (see the explanatory comment at `agent_coordination.py:318-321`); promoting it fixes claim-lifecycle stranding as a side effect of fixing the race condition, not a separate follow-up. |
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
# Codex Eng-voice finding: GOSSIP_DB_PATH takes absolute precedence over
# PT_STATE_DIR in resolve_gossip_db_path() (orchestrator/gossip_bus.py:56-64).
# Setting only PT_STATE_DIR does not isolate this test if GOSSIP_DB_PATH
# happens to be set in the ambient shell -- clear it explicitly.
os.environ.pop('GOSSIP_DB_PATH', None)
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

**Mechanics — copy, then re-export, not a destructive move (Codex board note, 2026-07-18: "the queue ownership row still needs to be tied to the actual runtime owner" — resolved here).** "Move into `core.py`" above was ambiguous about what happens to the facade's own definitions afterward, and that ambiguity is exactly what made the Part 2 provenance table's "canonical source" label for queue claim/complete/fail incorrect. Resolved: the same copy-then-re-export pattern Part 2 Phase 2 already uses for the larger migration, applied here in miniature:

1. Copy `_try_atomic_claim`, `_release_claim_with_event`, `_queue_claim`, `_queue_complete`, `_queue_fail` into `agent_coordination_core.py`, replacing core's own inferior versions in place — this is the version `main()` actually calls after Part 1 lands.
2. In the facade (`agent_coordination.py`), replace its own local definitions of these five symbols with `from scripts.agent_coordination_core import _try_atomic_claim, _release_claim_with_event, _queue_claim, _queue_complete, _queue_fail` re-exports. This is required, not optional: the facade's existing patch loop (`agent_coordination.py:580-596`) still does `setattr(_impl, "_queue_claim", _queue_claim)` onto `agent_coordination_legacy`, and that loop must keep patching legacy with the atomic-safe versions — without this re-export step, the patch loop would silently start patching legacy with core's now-identical-but-independently-drifting copy instead of a single shared source, recreating the exact duplication-drift failure class this plan exists to fix, one Part earlier than intended.
3. Net effect after Part 1: **`core.py` is the canonical implementation owner for `claim`/`complete`/`fail`; the facade is a re-exporting pass-through for those three that keeps `legacy.py`'s standalone invocation path patched correctly.** This is the runtime-owner correction the provenance table row below now reflects directly, rather than the ambiguous pre-Part-1 "facade" label.
4. **Scope boundary, verified (Codex, final gate, 2026-07-18):** `queue list` and `queue status` are deliberately **not** part of this promotion — `agent_coordination.py:66-67` still aliases `_queue_list`/`_queue_status` straight from `_impl` (legacy), unchanged. These are read-only display commands, not part of the atomicity/claim-stranding bugs Part 1 fixes; including them here would be scope creep. The provenance table splits this into two rows accordingly — do not read "Queue claim/complete/fail/list/status" as one uniformly-promoted group.

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

### Part 1c — exit code / stderr / split-message fix (today, standalone — see "DX-phase findings" below for full spec)

**Committed, not deferred, not gated on Part 2 Phase 3** (self-audit correction, fourth review pass — an earlier draft incorrectly said this fix bundles into Phase 3's parser rewrite; verified `main()`'s exit path has no structural dependency on argparse dispatch). Full spec, code citations, and the corrected three-part fix (non-zero exit, `sys.stderr` routing, `WON`/`LOST_RACE`/`CONTENTION` result-enum split) live in the "DX-phase findings" section below, under the bullet beginning "Exit code is always `0`" — kept there rather than duplicated here since it's tightly cross-referenced with the Claude/Kimi/Codex attribution chain that found and refined it across three review passes. Effort: small — one return-type change in `_try_atomic_claim`/`_release_claim_with_event`, `sys.exit()`/exception propagation in `main()`, `print(..., file=sys.stderr)` on error paths. No new files, no dispatch-table rewrite.

### Part 1d — `PHASE_TRACKING.md` rewrite (doc-only, zero code risk, land alongside Part 1)

**Committed here, not deferred** (self-audit correction, third review pass: the
earlier draft filed this under Part 3's "Deferred" list with only "worth doing
early" as a caveat — the same under-specified-gap pattern already corrected
for Findings #4/#7 above; the fix belongs as a concrete deliverable, not a
flagged idea). Verified before committing to this scope: `grep -n
"PHASE_TRACKING" README.md CLAUDE.md` returns zero matches in either file —
the discoverability gap is real, not assumed. `PHASE_TRACKING.md` is 304
lines; heading count shows roughly 8 of the 29 real leaf commands documented.

Concrete deliverable (one commit, doc-only):

1. **Restructure CLI-surface-first**, per Codex's recommendation: real CLI
   surface (`scripts/agent_coordination.py <cmd>`) first, then examples, then
   historical/edge-case notes — not the reverse.
2. **Cover all 29 leaf commands**, grouped by the same 6 families the parser
   itself already uses (top-level, `phase`, `workflow`, `queue`, `heartbeat`,
   `buffer` — see the real command inventory table above), not the current
   ~8/29 (~28%).
3. **Replace every `agent_coordination_phases.py` direct-invocation example**
   with the equivalent `agent_coordination.py` invocation — per the DX-phase
   finding below, `phases.py` bypasses LAN replication (`GossipBus(...)`
   directly vs. `make_gossip_bus(...)`), so every worked example currently
   models the one entrypoint proven to silently drop LAN propagation.
4. **Fix the stale sort-key example.** Current doc (lines ~208-217) shows the
   pre-fix float-cast algorithm (`"Phase-10.5" → (10, 0.5)`) as if current;
   code has used the tuple-of-ints `_phase_sort_key` since `9642ae24`. Replace
   with the real, current example.
5. **Add the Quick Start section** (folds in Recommendation #6's first half,
   steelmanned per the DX-phase correction below — the safe path, not the
   unprotected basic-board path): `queue add` → `queue claim` → `queue
   complete`, placed at the top, before the full command reference.
6. **Fix discoverability.** Add a one-line pointer to `PHASE_TRACKING.md` in
   both `README.md` and `CLAUDE.md` (currently absent from both — verified by
   grep above) so a new agent doesn't need to already know to search for the
   file.

Sequencing: steps 1-4 and 6 land as one doc-only commit alongside Part 1/1c
today — no code dependency, no migration risk. Step 5 (Quick Start) is the
same commit, not a separate one, since splitting doc-accuracy from
quick-start would let the quick-start section teach a structure the rest of
the doc doesn't yet reflect.

---

## Part 2 — Revamped architecture draft (drafted now, not deferred; execution scheduled separately)

Incorporates Codex's parallel engineering audit and the corrections recorded in `../references/coordination-consolidation-plan-review-2026-07-18.md`. This supersedes the original plan's "Target structure" and "Migration sequence" sections below.

### Target structure (revised — adds `liveness.py`, `types.py`, and `__init__.py`)

```text
orchestrator/coordination/
  __init__.py        # NEW — public API surface, explicit re-exports
  types.py            # NEW (Codex Eng-voice finding) — ClaimSequence, ReorderBuffer,
                      # TaskPriority, QueuedTaskState, PhaseStatus, PhaseState: shared
                      # dataclasses/enums currently duplicated between core.py and
                      # legacy.py. Every capability module below imports from here,
                      # not from each other or from the compat shims.
  paths.py           # canonical_repo_root, canonical_db_path, current_worktree_label
  claims.py          # register/claim/release/list/agents/log — the original basic claim board
  reorder_buffer.py  # _claim_with_seq, _buffer_status, _buffer_drain (types from types.py)
  task_queue.py      # _queue_add/_claim/_complete/_fail/_list/_status (types from types.py)
                      # (post-Part-1: includes _try_atomic_claim, _release_claim_with_event)
  phases.py          # _phase_start/_update/_complete/_block/_unblock/_list/_status,
                      # _detect_blockers, _workflow_critical_path — using the already-fixed
                      # _phase_sort_key (types from types.py)
  liveness.py         # NEW — the 7 heartbeat handlers + adapter boundary around orchestrator.heartbeat_monitor
                      # (Codex's CEO-phase finding: the original 5-module target silently omitted
                      # heartbeat/liveness ownership entirely, which would have reproduced "no
                      # business logic in scripts/" as a false claim — pulse/kill/cleanup are
                      # not print formatting)
```

### Source-provenance table (replaces the original plan's coarse "generally core.py's" heuristic)

Per Codex's audit: a file-level heuristic is too coarse for a mixed implementation. Every row must name the winning source, why, and what verifies equivalence before the losing implementation is deleted.

| Capability | Canonical source to preserve | Notes |
|---|---|---|
| Paths and DB resolution | `orchestrator.gossip_bus` public resolvers | Already canonical via PR #256 — reuse, do not re-derive. |
| Basic register/claim/release/list/agents/log | legacy/facade aliases | Preserve established basic board behavior — these are the original claim board, distinct from queued-task claim below. |
| Reorder buffer and sequenced claim | core | Includes first-arrival dedup and drain-marker replay fixes. |
| Queue add and queue data types | core/legacy after equivalence proof | Do not assume equivalence; verify it with a diff-based test before choosing. |
| Queue claim/complete/fail | **`core.py`** (Part 1's actual runtime owner post-landing; facade re-exports from core, it does not compete with it — see Part 1's "Mechanics" note above) | Includes atomic claim/release transactions and retries. Corrected label: earlier drafts bolded "facade" here, which was accurate pre-Part-1 but became stale the moment Part 1's copy-then-re-export mechanics were specified (Codex board note, 2026-07-18) — Phase 0F's runtime-identity re-verification step must confirm this against live code regardless, not trust this table blindly. |
| Queue list/status | **legacy** (via facade alias — unchanged by Part 1) | **Row split from the row above, third review pass (Codex, verified 2026-07-18): `agent_coordination.py:66-67` shows `_queue_list = _impl._queue_list` and `_queue_status = _impl._queue_status` — plain aliases to `legacy`, not touched by Part 1's promotion.** Part 1 deliberately scopes to the three atomicity/lifecycle-critical symbols (claim/complete/fail) and does not touch these two read-only display commands — expanding Part 1 to cover them would be scope creep unrelated to the race-condition/claim-stranding bugs it exists to fix. Equivalence between core's and legacy's `_queue_list`/`_queue_status` (both currently unpromoted) must still be proven, not assumed, during Part 2's `task_queue.py` extraction — same "do not assume equivalence" discipline as every other row in this table. |
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

**Codex Eng-voice finding — re-exports must not touch each file's own entrypoint.**
`core.py`, `legacy.py`, and `phases.py` are not just importable modules — each has
its own complete, independently-invocable `main()`, its own `argparse` parser
construction, and its own `if __name__ == "__main__": raise SystemExit(main())`
block (verified: `agent_coordination_phases.py` and `agent_coordination_core.py`
both end this way). `PHASE_TRACKING.md` documents real direct invocation of
`phases.py` this way. Step 2's re-exports must replace only the *capability*
function bodies (`_phase_list`, `_queue_claim`, etc.) — never the `main()`/
parser-building/`__main__` plumbing in any of the three files — or standalone
invocation (`python3 scripts/agent_coordination_phases.py phase list`) breaks
mid-migration, before Phase 5's atomic deletion even runs. This is separate from
(and sharper than) Part 3's existing "`phases.py` usage is unverified" item —
that item is about whether deletion is safe at all; this is about not breaking
the documented standalone-invocation path *during* the migration, regardless of
what Phase 5 eventually decides.

**Shared schema types need an explicit home (Codex Eng-voice finding).**
`ClaimSequence`, `ReorderBuffer`, `TaskPriority`, `QueuedTaskState`,
`PhaseStatus`, and `PhaseState` are currently duplicated between `core.py` and
`legacy.py` (verified: identical dataclass/enum definitions in both, e.g.
`agent_coordination_core.py:97` and `agent_coordination_legacy.py:98`), but the
target structure above names only capability modules plus `__init__.py` — no
shared types module. Without one, extraction either imports through the
package root (coupling every module to `__init__.py`'s import order) or keeps
reaching back into the compatibility shims Phase 5 is supposed to delete —
recreating the same duplication this plan exists to remove, one directory
level higher. **Add `orchestrator/coordination/types.py`** to the Phase 1
skeleton (package listing above) for these six shared dataclasses/enums; every
capability module imports from it, not from each other or from the compat
shims.

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

**DX-phase finding, folded in here:** the current `main()` (`agent_coordination_core.py:1195-1330`) already puts `help=` strings on most leaves, but 5 of the 6 top-level commands (`register`, `agents`, `release`, `list`, `log`) have none — only `claim` does. Since every `add_parser(...)` call is being rewritten in this phase anyway, add the missing `help=` text here at zero incremental cost rather than as a separate patch to a function this phase is about to replace.

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

def test_leaf_argument_signatures_unchanged():
    """Codex Eng-voice finding: leaf-count alone protects existence, not shape.
    'queue add' could silently regress from positional 'phase' back to a
    '--phase' flag (the exact bug Part 1's original verification script hit)
    and the count-based test above would still pass. Snapshot each leaf's
    argument names, whether positional or flag, and required-ness."""
    from scripts.agent_coordination import build_parser
    EXPECTED_SIGNATURES = {
        ("queue", "add"): [("task_name", "positional"), ("phase", "positional"),
                            ("--priority", "flag"), ("--notes", "flag"), ("--depends-on", "flag")],
        ("queue", "claim"): [("task_id", "positional"), ("agent_id", "positional")],
        ("phase", "start"): [("phase_name", "positional"), ("--depends-on", "flag"), ("--agent", "flag")],
        # ... one row per leaf; fill in against the real parser at Phase 0F time,
        # this is a template showing the shape, not the complete set.
    }
    actual = _enumerate_leaf_arguments(build_parser())  # walk each leaf's own argument list
    for leaf, expected_args in EXPECTED_SIGNATURES.items():
        assert actual[leaf] == expected_args, f"{leaf}: expected {expected_args}, got {actual[leaf]}"

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

**Phase 5 — atomic compatibility deletion:** delete `core.py`, `legacy.py`, `phases.py` in one revertible commit, only after Phase 4's full gate passes. Not kept as deprecated shims — same rationale as the original plan, now with actual evidence (the caller-graph + direct-invocation audit above) rather than an unverified assumption. **Same commit, update every test file that imports the three deleted modules directly** (e.g. `tests/test_agent_coordination_queue.py`, `tests/test_agent_coordination_phases.py`) to import from the new `orchestrator/coordination/` package instead — Phase 4's unfiltered full-suite gate would catch a missed import as a hard failure before merge regardless, but naming it here avoids a same-day scramble discovering it live.

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
`_workflow_critical_path`, not introduced by this plan.

**Committed fix (Codex, second review pass — earlier draft of this note left
the fix as an unresolved either/or; that was an under-specified gap, corrected
here).** Simply changing `>` to `>=` is not sufficient — it would make whichever
candidate is iterated last in `for dependent, deps in graph.items()` win ties,
which is dict/graph insertion order (event-arrival order in the gossip log),
not a semantically meaningful tiebreak. Codex's review is right to reject that.
Fix: compare a full deterministic key, not a bare float — duration first
(existing signal), then chain length (prefer the more complete/longer chain on
a tie — a real product choice: showing more of the actual dependency sequence
is more informative than an arbitrary single node), then the path itself as a
lexicographic tuple (final, always-deterministic tiebreak, matching the
`_phase_sort_key` precedent already in this file for exactly this reason):

```python
def longest_chain(node: str, visited: set[str]) -> tuple[list[str], float]:
    if node in visited:
        return ([], 0.0)
    visited.add(node)
    phase = phases.get(node)
    if not phase:
        return ([], 0.0)
    current_duration = phase.estimated_duration_hours or 0.0
    if phase.completed_at and phase.started_at:
        current_duration = (phase.completed_at - phase.started_at) / 3600

    def sort_key(path: list[str], duration: float) -> tuple[float, int, tuple[str, ...]]:
        # Deterministic: duration, then chain length, then lexicographic path.
        # Never compares on dict/graph iteration order.
        return (duration, len(path), tuple(path))

    max_path: list[str] = []
    max_duration = 0.0
    best_key = (0.0, 0, ())
    for dependent, deps in graph.items():
        if node in deps:
            sub_path, sub_duration = longest_chain(dependent, visited.copy())
            candidate_path = [node] + sub_path
            candidate_duration = sub_duration + current_duration
            candidate_key = sort_key(candidate_path, candidate_duration)
            if candidate_key > best_key:
                best_key, max_duration, max_path = candidate_key, candidate_duration, candidate_path

    if not max_path:
        max_path = [node]
        max_duration = current_duration
    return (max_path, max_duration)
```

The outer `for root in roots: if duration > longest_duration:` loop
(`agent_coordination_core.py:850-854`) has the identical bare-float comparison
bug across roots and needs the same `sort_key`-based fix, not just the inner
recursive comparison.

**Required regression fixtures (Codex's explicit requirement — add all three,
not just the zero-duration case this session found):**
1. **Zero-duration branches** — the case above (`Phase-1` → `Phase-2`, both
   `estimated_duration_hours=0`): must select the 2-node chain, not collapse
   to 1 node.
2. **Equal-duration branches** — two sibling dependents of the same node with
   identical nonzero durations but different downstream chain lengths: must
   deterministically prefer the longer chain, and must return the *same*
   result across repeated runs regardless of dict insertion order (assert by
   running the computation with the graph's dependents inserted in two
   different orders and comparing output).
3. **Mixed-duration branches** — one shorter-but-longer-chain path vs. one
   longer-single-hop path: must correctly prefer strictly greater total
   duration over chain length (duration is the primary key, length only
   breaks exact ties) — proves the fix didn't accidentally invert the
   priority order.

This is currently-shipping behavior, not introduced by this plan, but Phase 0F's
"already fixed, no change needed" characterization posture doesn't apply here —
this fix should land as part of Part 2's `phases.py` extraction (the function
is being moved anyway), with the three fixtures above as permanent regression
coverage, not deferred to Part 3.

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

### DX-phase findings (dual voices: Claude subagent + Codex + Kimi as a third independent voice)

**Strongly recommend folding into Part 1 as "Part 1c" rather than deferring** — this
one compounds every other verification script in this plan, including Part 1's own:

- [ ] **Exit code is always `0`, regardless of `ERROR:`/`WARNING:` output (Claude subagent + Kimi, independently — Kimi confirmed live: `python3 scripts/agent_coordination.py queue claim nonexistent-task agent-x` prints `ERROR: task nonexistent-task not found` and exits `0`).** `main()` in `agent_coordination_core.py:1361-1500` ends `return 0` unconditionally — no exception path, no `sys.exit(1)` — verified directly, no other statement between `_amain()`'s call and the unconditional return. Every scripted `subprocess.run(..., check=True)` caller (including this plan's own Part 1/Phase 4 verification scripts, which had to resort to `'ERROR:' in r.stdout` instead of checking return codes) cannot detect failure the normal way. **Caveat for why this isn't just deferred like the rest:** it's not a business-logic behavior change (Part 2's non-goal) — it's a scriptability contract fix, and every test this plan's own Phase 0F/4 gates depend on is already working around its absence.
  **Landing site, corrected (self-audit, fourth review pass): this does NOT require Part 2 Phase 3's parser rewrite.** An earlier draft of this note said to bundle the fix into Phase 3's dispatch rewrite — that was an unnecessary coupling, not a real dependency. Verified: `main()` (`agent_coordination_core.py:1361`) is a plain function wrapping `asyncio.run(_amain(args))` with nothing structurally tying it to argparse's dispatch mechanism — a nonzero-exit signal can propagate through today's dispatch just as easily as tomorrow's `set_defaults(handler=...)` one. **Part 1c is therefore a real, standalone, today-scoped fix**, consistent with this plan's own Status line ("Parts 1/1b/1c/1d ready to implement today") — not deferred to Part 2.

**Two more pieces of this same finding (Codex, second review pass — the earlier
note above only committed to the exit-code half; under-specified, corrected
here):** the fix is incomplete without also (a) routing `ERROR:`/`WARNING:`
through `sys.stderr` instead of `print()`'s default stdout, so the two signals
(stream + exit code) agree once both land together, and (b) splitting bundled
ambiguous outcomes into distinct messages — concretely,
`_try_atomic_claim`'s caller-facing text ("another agent won or the
coordination database remained busy. Retry safely.",
`agent_coordination.py:280-283`) collapses two genuinely different causes
(lost a real race vs. hit lock contention) into one string. Verified precisely:
`_try_atomic_claim` (`agent_coordination.py:164-176`) already distinguishes
them internally via two separate `except` clauses (`aiosqlite.IntegrityError`
→ lost the race; `aiosqlite.OperationalError` after retries exhausted →
contention) — but both currently `return False`, collapsing the distinction at
the *return* site, before it ever reaches the caller or the print statement.
Fix: change the return type from bare `bool` to a small enum/result type
(e.g. `WON | LOST_RACE | CONTENTION`) so the two `except` branches return
distinct values instead of the same `False`; the caller then prints two
distinct `ERROR:` messages. The information already exists at the exact point
it's needed (each `except` clause knows which case it's in) — the fix is
threading it through the return value, not gathering new information. All
three (non-zero exit, stderr routing, split messages) are one scriptability-
contract change, landing together in **Part 1c, today** — see the corrected
landing-site note above; none of the three requires Part 2 Phase 3's parser
rewrite.

**Not deferred — see Part 1d above (self-audit correction, third review pass):**

- [x] **`PHASE_TRACKING.md` is actively wrong, not just incomplete.** Verified: it documents the *pre-fix* float-encoded sort-key algorithm (`"Phase-10.5" → (10, 0.5)"`) as current, when the code has used tuple-of-ints since `9642ae24`; it covers only ~8 of 29 commands (~28%) — the entire `queue`/`heartbeat`/`buffer`/basic-`claim` surface is undocumented; every worked example invokes `agent_coordination_phases.py` directly, the one entrypoint confirmed to bypass LAN replication (see the `liveness`/bus-constructor finding below); and `README.md`/`CLAUDE.md` don't reference this doc or the CLI at all (re-verified via `grep -n PHASE_TRACKING README.md CLAUDE.md` — zero matches in both), so discoverability depends on already knowing to grep for it. **Was mis-filed as "Deferred/doc-only, worth doing early" with no concrete commitment — the same under-specification pattern already corrected on Findings #4/#7. Corrected: now Part 1d, a scoped, committed, doc-only deliverable landing alongside Part 1 today**, not a flagged idea for later.

Deferred (do not block Part 1/2, but do not silently drop either):
- [ ] **`agent_coordination_phases.py` uses a different bus constructor than `core.py`/`legacy.py` (Claude DX subagent, confirmed by Codex and Kimi independently).** `phases.py:433` calls `GossipBus(canonical_db_path())` directly; `core.py:1094`/`legacy.py:1085` call `make_gossip_bus(canonical_db_path())`, which returns a `LanGossipBridge` instead of a plain local bus when `GOSSIP_PEERS` is configured (verified in `orchestrator/lan_gossip_bridge.py:195-205`) — this org's actual Mac+Win LAN setup. **Concrete consequence: `phase start`/`phase list`/etc. run via the standalone `phases.py` entrypoint never propagate across LAN, while the identical command via `agent_coordination.py` does.** A third, independently-discovered instance of the "silent divergence between copies" failure class this whole plan exists to fix — add to Phase 0F's inventory (record which bus constructor each entrypoint uses, not just which function handles the leaf), per the Eng-phase task_queue.py note above.
- [ ] **Basic `claim`/`release` have zero collision/ownership protection, and it's undocumented (Claude DX subagent; Kimi independently confirmed `release` extends the same gap).** `_claim` (`agent_coordination_core.py:371-389`) does no pre-check before emitting — last-write-wins by design (an existing test asserts this as intended behavior), and `_release` lets any agent release any other agent's claim. Neither is documented as such anywhere; a new agent reasonably assumes `claim` (shorter, more discoverable than `queue claim`) has the same protection the plan is busy adding to `queue claim`. **Fix, cheap:** a one-line `--help`/docstring warning ("no collision protection — use `queue add`/`queue claim` for exclusive ownership") costs nothing and can land with Part 1's other doc touches.
- [x] **`queue complete`/`queue fail` don't verify caller identity against the claim owner — explicit decision made (Claude DX subagent; Codex board note, 2026-07-18, flagged the earlier either/or phrasing as blocking final sign-off).** Verified directly: neither `queue complete` nor `queue fail`'s parser (`agent_coordination_core.py:1287-1293`) even accepts an `agent_id` argument — only `task_id` and `--notes` — so there's no caller identity available to check without also changing the CLI signature, not just the implementation. Any agent can complete or fail a task it never claimed. Same failure class as the queue-claim bug (missing protection in the tool whose purpose is preventing exactly this), just an authorization gap, not a race condition.
  **Decision: explicitly deferred to a standalone follow-up PR, not bundled into Part 1 or Part 2.** Earlier drafts left this as an either/or ("close during extraction, or re-defer") — under-specified, now resolved. Reasoning: adding caller-identity enforcement requires a CLI signature change (a new `agent_id` argument on two leaves) plus a decision on failure behavior for existing unauthenticated callers — that is a genuine new capability/behavior change, which both Part 1 ("no dispatch-table rewrite... directly actionable today," i.e., no new args) and Part 2 (Non-goals: "No new capabilities added while consolidating," "No behavior changes bundled into Part 2's migration beyond what Part 1 explicitly fixes") explicitly rule out bundling. Structurally identical to the already-deferred "local topology in event labels" item below: a real, evidence-backed security gap, deliberately excluded from this consolidation's behavior-preserving scope rather than silently dropped. Caveat: track as its own authorization-hardening follow-up (add `agent_id` to both leaves, verify against `assigned_agent`, decide the rejection contract) — do not fold into `task_queue.py`'s Part 2 extraction, since extraction is supposed to be a structural move with zero behavior change, and this fix is a behavior change riding on the same file.
- [ ] **Unreachable dead code: a second, unreachable `elif args.cmd == "claim"` branch in `agent_coordination_legacy.py` (Kimi, verified: lines 1091 and 1182).** The `--seq` handling at line 1182 can never execute — the first branch at 1091 always matches first. Harmless today (Part 1 doesn't touch `legacy.py`, and the live CLI runs through `core.py` where this bug doesn't exist), but it's a fourth, independently-found instance of "same code, divergent bugs," this time in dispatch order rather than business logic — worth noting so Phase 2's `legacy.py` migration doesn't accidentally try to preserve the unreachable branch's behavior as if it were live.
- [ ] **No machine-readable output; every consumer must regex stdout (Claude DX subagent).** `queue add`'s generated `task_id` (`f"{phase}-{task_name}-{uuid.uuid4().hex[:8]}"`) is only ever printed as `enqueued: <task_id> (...)` — this plan's own Part 1 verification script has to `re.search(r'enqueued: (\S+)', ...)` to recover it. A `--json` flag on the mutating commands would be cheap to add during Part 2's extraction, since every handler is already being touched.
- [ ] **`heartbeat kill` doesn't cascade to `heartbeat cleanup` (Claude DX subagent).** `kill` only marks an agent `DEAD` (`orchestrator/heartbeat_monitor.py:114,126`); it does not release that agent's claims — a separate `cleanup` call is required, and this two-step dance is undocumented anywhere. Consider a `--and-release` flag, or at minimum document the two-step requirement, during `liveness.py`'s Part 2 extraction.
- [x] **No canonical "first-run" path (Codex, second review pass) — characterization corrected, fix now committed.** Codex's finding described "29 commands presented flat." Re-verified directly against `scripts/agent_coordination_core.py:1195-1330` (`main()`'s `build_parser` logic) before accepting that framing: it's **not accurate** — the parser already groups all 29 leaves into 6 subcommand families (`phase`, `workflow`, `queue`, `heartbeat`, `buffer`, plus 6 top-level), and most leaves already carry a terse `help=` string (e.g. `queue_sub.add_parser("claim", help="Claim a queued task")`). The real, narrower gap: (a) the top-level `ArgumentParser(description=...)` shows no quick-start guidance — `--help` at the root gives no on-ramp; (b) 5 of the 6 top-level leaves (`register`, `agents`, `release`, `list`, `log`) are missing `help=` strings entirely (only `claim` has one) — confirmed by reading `main()`'s parser-construction block directly, not assumed from the finding text.
  Steelmanned fix, split by where it lands (Phase 3 already rewrites this exact function wholesale, so land there rather than hand-patching a function about to be replaced):
  1. **Quick Start on-ramp**: `queue add` → `queue claim` → `queue complete`, the safe atomic path — explicitly **not** `register`/`claim`/`release`, which is the unprotected basic-board path per the finding above (Codex's original suggested sequence pointed at the wrong, unsafe commands; corrected here). Lands in Part 1d's `PHASE_TRACKING.md` rewrite today (doc-only, no code dependency) — not deferred to Phase 3.
  2. **Missing top-level `help=` strings**: add during Part 2 Phase 3's `set_defaults()`-based parser rewrite, since every `add_parser(...)` call in the file is already being touched there — a one-line addition per leaf at zero incremental migration cost, not a separate follow-up.

**One claim checked and NOT incorporated (for the record):** Codex's DX voice also
reported a "queue retry behavior diverges between core (`retry_count <= max_retries`)
and legacy (`retry_count == max_retries`)" finding. Read both implementations
directly (`agent_coordination_core.py:978-1005`, `agent_coordination_legacy.py:969-996`)
— they are byte-for-byte identical, both using `retry_count < max_retries`. False
positive, not incorporated. (Codex's other DX finding — reorder-buffer drain-marker
handling diverges between core and legacy — is real and verified, but it confirms
rather than adds to the provenance table's existing "reorder buffer and sequenced
claim | core" guidance, so no plan edit was needed for it.)

## Related open work (does not block this plan, but shares the same closure discipline)

`docs/phase-0-specifications/` (this repo, 28 files) tracks a **different**
Phase 0 — the StateTransitionManager/peer-observation/heartbeat-liveness work,
not the `agent_coordination*.py` consolidation this plan covers. Named here
per explicit user direction, because the same "flagged but not committed"
under-specification pattern this session corrected twice in this plan (§
Findings #2/#6 above, and the two Codex board-flagged items just resolved in
Part 1/Part 2) recurs there too, and a reader closing out this plan should
know where the parallel open work lives rather than assume it's unrelated:

- **`PHASE-0-TASK-LIST.md`** carries its own explicit supersession banner:
  "superseded by the shipped STM path under `orchestrator/membership.py`...
  keep this file for provenance; do not treat the task list as active work" —
  already closed, not a live TODO list.
- **Ranked closure state for the rest of that directory:**
  [`phase0-and-orama-closure-rankings-2026-07-18.md`](../../../../references/phase0-and-orama-closure-rankings-2026-07-18.md)
  (off-repo handoff doc) is the authoritative, already-maintained tracker —
  ranks 1-3 done, ranks 5/7 active, rank 6 deferred-to-v2, rank 4 TODO-only.
  Do not re-derive this list here; it would drift from the maintained copy.
- **Structural parallel worth naming explicitly:** that ranking doc's own
  crosslinks section has a path typo (`../perpetua-api/Perpetua-Tools/...`
  where the real path is `perplexity-api/Perpetua-Tools/...`, per this repo's
  own path in this plan's file header) — noted here for whoever next edits
  that file, not fixed in this plan since it's a different document's bug.
- **Board-job source-line schema, cross-repo status:** `.agent/AGENTS.md`'s
  "Board-job source line" doctrine (referenced by this plan's own concurrent
  CodeRabbit-fix work on `_queue_add`) now has its cross-repo documentation
  in `orama-system` at `docs/v2/48-board-job-source-line-schema.md` (OQ20 in
  that repo's `06-open-questions.md`) — optional/provisional, not enforced,
  since orama-system has no board/queue producer of its own to coordinate a
  hard-required rollout with yet. Named here for the same reason as the
  Phase 0 pointer above: a reader closing out this plan should know the
  doctrine's cross-repo half is documented, not that it was silently dropped.

## Verdict

The three-file split was a reasonable evolutionary safety move at the time (freeze what works, layer new features without touching frozen code) but has crossed into maintenance debt — a single bug class (fix lands in one copy, not others) has now recurred twice (phase-sort, queue-claim), and the second instance carried a real concurrency-safety consequence, not just an inconsistency. Part 1 closes both known instances of that failure class today, using the same file `main()` already executes — no new surface, no deletion, no migration risk. Part 2 is the evidence-backed architecture to prevent a third instance, drafted now per explicit direction rather than deferred, sequenced with a frozen-contract phase and mandatory re-export scaffolding so no intermediate commit is ever in a half-migrated, import-broken state. Part 3 names what can genuinely wait, with a reason attached to each item so "deferred" doesn't become "forgotten."
