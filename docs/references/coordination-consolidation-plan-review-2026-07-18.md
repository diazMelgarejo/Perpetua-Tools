# Coordination Consolidation Plan Review

Date: 2026-07-18
Reviewer: Codex primary orchestrator
Reviewed revision: local commit `e98efe48`
Disposition: architecture approved in direction; executable details require correction before implementation

## What improved

- The urgent atomic queue-claim defect is separated from the larger consolidation.
- Phase 0F freezes all 29 CLI leaves before migration.
- The source-provenance table replaces the unsafe file-level "prefer core" heuristic.
- `liveness.py` gives heartbeat behavior explicit ownership.
- Leaf-local `argparse.set_defaults(handler=...)` binds parser registration and dispatch.
- Compatibility re-exports make the migration incremental and reversible.
- Deletion is gated on real-entrypoint parity rather than facade-import tests.

## Required corrections

### 1. Fix the Part 1 race command

The plan used:

```bash
queue add race-task --phase test --priority HIGH
```

The live parser defines `phase` as a positional argument. Use:

```bash
queue add race-task test --priority HIGH
```

Use deterministic distinct agent IDs in the concurrent workers and assert both
the single success and the expected losing output contract.

### 2. Make the cleanup characterization test executable

The current implementation emits heartbeat payload `kind=agent_release`, not
`kind=claim_released`. The test must also age the agent beyond the DEAD
threshold, preferably by injecting or patching time, before invoking cleanup. A
placeholder comment does not satisfy a characterization gate.

### 3. Remove heartbeat promotion from Part 1

The live core entrypoint already parses all seven heartbeat leaves and dispatches
them through lazy imports from the facade. Heartbeat ownership is fragmented,
but it is not currently an absent-dispatch defect. Promoting all seven handlers
into core would create another temporary copy while expanding the urgent patch.

Keep Part 1 limited to the atomic queue mutation path. Characterize heartbeat
behavior in Phase 0F, then migrate it once into `liveness.py` during Part 2.

### 4. Separate database error normalization

Converting raw SQLite or filesystem failures into stable CLI errors is valuable,
but it is a distinct observable behavior change. Treat it as Part 1b or a small
follow-up with its own error-contract tests. Do not partially normalize only the
functions touched by the atomicity repair.

### 5. Repair the evidence links

The plan named two `references/...` files that were stored in a shared off-repo
handoff area, not inside Perpetua-Tools. Those links were broken for repository
readers. Keep complete evidence inline, cite portable primary sources, and place
sanitized durable review material under `docs/references/`.

Do not add workstation-specific paths to explain where private handoffs live.

## Recommended Part 1 boundary

1. Add a failing real-entrypoint concurrency test.
2. Promote the atomic claim/release primitives and queue claim/complete/fail
   behavior into the implementation actually reached by `main()`.
3. Run focused coordination/GossipBus tests, the deterministic race test, and
   repository hygiene.
4. Commit the narrow correctness fix independently.
5. Execute Part 1b and Part 2 only as separately reviewable changes.

## Verdict

Proceed after the five corrections above. The target architecture is coherent;
the remaining problems are plan executability, scope control, and portable
evidence, not a reason to redesign the consolidation again.
