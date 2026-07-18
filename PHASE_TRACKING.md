# Phase-Based Workflow Tracking

This document describes the phase tracking and distributed task queue surface of `scripts/agent_coordination.py`.

## Quick Start

The safe, atomic path for handing off work is the **queue**, not the legacy `register/claim/release` board (the legacy board is advisory and unprotected against races):

```bash
# 1. Enqueue a task
python3 scripts/agent_coordination.py queue add "implement-auth" "Phase-1.0" --priority high --notes "add passwordless login"

# 2. Claim it atomically (only one agent wins)
python3 scripts/agent_coordination.py queue claim <task_id> <agent_id>

# 3. Complete it
python3 scripts/agent_coordination.py queue complete <task_id> --notes "merged in commit abc123"
```

## CLI Reference

`scripts/agent_coordination.py` exposes 29 leaf commands grouped in six families.

### Top-level coordination (legacy advisory board)

**`list` and `queue list` are two separate, disjoint surfaces — not two views of the same data.** `list` shows the legacy advisory-board `claim`/`release` entries only. `queue list` (below) shows atomic `queue add`/`queue claim` task entries only. A task enqueued with `queue add` will never appear in plain `list`, and a claim made with plain `claim` will never appear in `queue list`. If you enqueued or claimed something and can't find it, check you're using the matching surface, not the other one.

```bash
python3 scripts/agent_coordination.py register <agent_id> <agent_type> [model] [notes]
python3 scripts/agent_coordination.py agents
python3 scripts/agent_coordination.py claim <agent_id> <task_name> [notes] [--seq N]
python3 scripts/agent_coordination.py release <agent_id> <task_name>
python3 scripts/agent_coordination.py list [task_name]
python3 scripts/agent_coordination.py log <agent_id> <message>
```

### Phase tracking

```bash
python3 scripts/agent_coordination.py phase list
python3 scripts/agent_coordination.py phase status <phase_name>
python3 scripts/agent_coordination.py phase start <phase_name> [--depends-on phase1,phase2] [--agent agent_id]
python3 scripts/agent_coordination.py phase update <phase_name> --tests-passing 50/69 [--agent agent_id]
python3 scripts/agent_coordination.py phase complete <phase_name>
python3 scripts/agent_coordination.py phase block <phase_name> --reason "reason text"
python3 scripts/agent_coordination.py phase unblock <phase_name> --reason "reason text"
```

### Distributed task queue

```bash
python3 scripts/agent_coordination.py queue add <task_name> <phase> [--priority critical|high|normal|low] [--notes "..."] [--depends-on task_id,...]
python3 scripts/agent_coordination.py queue list [--phase <phase>] [--priority <level>] [--agent <agent_id>]
python3 scripts/agent_coordination.py queue claim <task_id> <agent_id>
python3 scripts/agent_coordination.py queue complete <task_id> [--notes "..."]
python3 scripts/agent_coordination.py queue fail <task_id> [--notes "..."]
python3 scripts/agent_coordination.py queue status [--agent <agent_id>]
```

### Heartbeat / liveness

```bash
python3 scripts/agent_coordination.py heartbeat list
python3 scripts/agent_coordination.py heartbeat check <agent_id>
python3 scripts/agent_coordination.py heartbeat dashboard
python3 scripts/agent_coordination.py heartbeat pulse <agent_id>
python3 scripts/agent_coordination.py heartbeat kill <agent_id> --reason "reason text"
python3 scripts/agent_coordination.py heartbeat timeline <agent_id> [--hours N]
python3 scripts/agent_coordination.py heartbeat cleanup
```

### Reorder buffer

```bash
python3 scripts/agent_coordination.py buffer status [--agent <agent_id>]
python3 scripts/agent_coordination.py buffer drain <agent_id>
```

### Workflow analysis

```bash
python3 scripts/agent_coordination.py workflow critical-path
```

## Data Model

### PhaseState

Each phase is represented by a `PhaseState` object with the following fields:

```python
@dataclass
class PhaseState:
    phase_name: str                      # e.g. "Phase-1.0", "Phase-2"
    status: PhaseStatus                  # not_started | in_progress | blocked | complete
    assigned_to: list[str]               # Agent IDs working on this phase
    total_tests: int                     # Expected total test count
    tests_passing: int                   # Current passing test count
    blockers: list[str]                  # List of blocking reasons
    depends_on: list[str]                # List of prerequisite phases
    started_at: Optional[float]          # Unix timestamp when phase started
    completed_at: Optional[float]        # Unix timestamp when phase completed
    notes: str                           # Freeform notes
    estimated_duration_hours: float      # Estimated time to complete
```

### PhaseStatus

Phases progress through these states:

- **NOT_STARTED**: Phase has not begun work
- **IN_PROGRESS**: Phase is actively being worked on
- **BLOCKED**: Phase is waiting for something (see `blockers` field)
- **COMPLETE**: Phase has finished all work

## Example Workflow

### Phase-1.0 (PeerObservation Schema)

```bash
# Start Phase-1.0
python3 scripts/agent_coordination.py phase start Phase-1.0 --agent kimi-g1

# Track progress throughout the phase
python3 scripts/agent_coordination.py phase update Phase-1.0 --tests-passing 35/69
python3 scripts/agent_coordination.py phase update Phase-1.0 --tests-passing 69/69

# Mark complete
python3 scripts/agent_coordination.py phase complete Phase-1.0
```

### Phase-2 (depends on Phase-1.0)

```bash
# Define dependency
python3 scripts/agent_coordination.py phase start Phase-2 --depends-on Phase-1.0 --agent agy-flash

# If Phase-1.0 is blocked, this will show as a blocker
python3 scripts/agent_coordination.py phase status Phase-2

# Once Phase-1.0 completes, proceed with work
python3 scripts/agent_coordination.py phase update Phase-2 --tests-passing 16/16
python3 scripts/agent_coordination.py phase complete Phase-2
```

### Parallel Phases

Phases can run in parallel if they have no dependencies:

```bash
# Start Phase-3 and Phase-4 in parallel
python3 scripts/agent_coordination.py phase start Phase-3 --depends-on Phase-2 --agent kimi-g1
python3 scripts/agent_coordination.py phase start Phase-4 --depends-on Phase-2 --agent agy-flash

# Both can progress concurrently
python3 scripts/agent_coordination.py phase list
# Both show "🔄 IN_PROGRESS" simultaneously
```

## Blocker Detection

The system automatically detects which phases are blocking a given phase by checking unfulfilled dependencies:

```bash
# If Phase-3 depends on Phase-2 and Phase-4 isn't complete:
python3 scripts/agent_coordination.py phase status Phase-3

# Output shows:
# Dependencies: Phase-2, Phase-4
# Phase-2 may be blocked if it hasn't completed yet
```

## Critical Path Analysis

Shows the longest chain of dependent phases and the total time to complete if run sequentially:

```bash
python3 scripts/agent_coordination.py workflow critical-path
```

Example output:

```
=== Critical Path Analysis ===
Longest chain: Phase-1.0 → Phase-2 → Phase-3 → Phase-4
Total duration: 31.5 hours
ETA (if started now): +31.5 hours

  ✅ Phase-1.0               8.0h
  ✅ Phase-2                 5.0h
  🔄 Phase-3                 7.5h
  🔄 Phase-4                 5.0h
```

## Implementation Details

### Storage

All phase events are stored in GossipBus using "phase_event" events:

```json
{
  "kind": "phase_event",
  "phase_name": "Phase-1.0",
  "status": "in_progress",
  "assigned_to": ["kimi-g1"],
  "total_tests": 69,
  "tests_passing": 50,
  "blockers": [],
  "depends_on": [],
  "started_at": 1689123456.789,
  "completed_at": null,
  "notes": "Running integration tests",
  "estimated_duration_hours": 8.0
}
```

### State Retrieval

- `_get_latest_phase_state(bus, phase_name)` — Retrieves the most recent state for a given phase
- `_all_phase_states(bus)` — Retrieves the latest state for all phases
- GossipBus returns events newest-first, so the first match is always the latest state

### Deterministic Sorting

Phases are sorted using a numeric component matcher. Each dot-separated component is parsed as an integer and compared as a tuple, so two-digit minor versions order correctly:

- "Phase-1.0" → `(0, (1, 0), "Phase-1.0")`
- "Phase-1.1" → `(0, (1, 1), "Phase-1.1")`
- "Phase-2" → `(0, (2,), "Phase-2")`
- "Phase-2.10" → `(0, (2, 10), "Phase-2.10")`
- "Phase-10.5" → `(0, (10, 5), "Phase-10.5")`
- "OtherName" → `(1, (), "OtherName")`

This ensures `Phase-2.10` sorts after `Phase-2.9`, which a naive float encoding would get wrong.

## Test Coverage

See `tests/test_agent_coordination_phases.py` for comprehensive unit tests covering:

- Phase state creation and serialization
- State transitions (start → in_progress → complete)
- Test progress tracking
- Blocker management and unblocking
- Blocker detection via dependency checking
- Multiple blockers on a single phase
- Phase agent assignment tracking
- Prevention of restarting completed phases
- Completion validation (no blockers allowed)
- All phases retrieval and sorting

Run tests with:

```bash
python3 -m pytest tests/test_agent_coordination_phases.py -v
```

## Integration with the Queue

The queue and phase systems share the same GossipBus database. Use phases for coarse-grained workflow state and the queue for atomic task handoff:

```bash
# Track phase workflow
python3 scripts/agent_coordination.py phase start Phase-1.0 --agent kimi-g1

# Enqueue and claim specific tasks within the phase
python3 scripts/agent_coordination.py queue add "PeerObservation" "Phase-1.0" --priority high
python3 scripts/agent_coordination.py queue claim <task_id> kimi-g1
python3 scripts/agent_coordination.py queue complete <task_id>
```

## Future Extensions

Planned enhancements:

1. **Parallel Phase Tracking**: Track parallel paths separately in critical path
2. **Web Dashboard**: Real-time phase visualization
3. **Phase Completion Checks**: Automatically verify test counts and docs before allowing completion
4. **Notifications**: Alert when phases are blocked or completed
5. **Historical Analysis**: Track phase duration trends across multiple runs
6. **Phase Templates**: Pre-defined phase sequences with standard dependencies

## Troubleshooting

### Phase not found

If you get "Phase 'X' not found", ensure you ran `phase start` first:

```bash
python3 scripts/agent_coordination.py phase start Phase-1.0
```

### Cannot complete phase with blockers

Blockers must be removed before completion:

```bash
# See what's blocking
python3 scripts/agent_coordination.py phase status Phase-2

# Remove each blocker
python3 scripts/agent_coordination.py phase unblock Phase-2 --reason "waiting for API"
python3 scripts/agent_coordination.py phase unblock Phase-2 --reason "design review"

# Now you can complete
python3 scripts/agent_coordination.py phase complete Phase-2
```

### Cannot restart a completed phase

Completed phases cannot be restarted. To track a new instance, use a different phase name:

```bash
# Instead of restarting Phase-1.0
python3 scripts/agent_coordination.py phase start Phase-1.0b --agent new-agent
```
