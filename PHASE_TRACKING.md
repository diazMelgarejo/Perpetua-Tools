# Phase-Based Workflow Tracking

This document describes the phase tracking system for Perpetua-Tools, which enables orchestration and visibility into multi-phase work streams.

## Overview

Phase-based workflow tracking provides:

- **Phase State Tracking**: Monitor each phase's status (not_started, in_progress, blocked, complete)
- **Test Progress**: Track test counts and passing rates per phase
- **Agent Assignment**: Record which agents are working on each phase
- **Dependency Management**: Define inter-phase dependencies and detect automatic blockers
- **Critical Path Analysis**: Calculate the longest dependency chain and estimated time to completion (ETA)
- **Blocker Management**: Explicitly block phases and track reasons for blockage

## Quick Start

### 1. Initialize a Phase

```bash
python3 scripts/agent_coordination_phases.py phase start Phase-1.0 --agent kimi-g1
```

### 2. Track Progress

```bash
# Update test counts (50/69 passing)
python3 scripts/agent_coordination_phases.py phase update Phase-1.0 --tests-passing 50/69 --agent kimi-g1

# Or just update passing count
python3 scripts/agent_coordination_phases.py phase update Phase-1.0 --tests-passing 69
```

### 3. List All Phases

```bash
python3 scripts/agent_coordination_phases.py phase list
```

### 4. Get Detailed Status

```bash
python3 scripts/agent_coordination_phases.py phase status Phase-1.0
```

### 5. Complete a Phase

```bash
python3 scripts/agent_coordination_phases.py phase complete Phase-1.0
```

### 6. Manage Blockers

```bash
# Block a phase
python3 scripts/agent_coordination_phases.py phase block Phase-2 --reason "waiting for Phase-1.0 API"

# Unblock when ready
python3 scripts/agent_coordination_phases.py phase unblock Phase-2 --reason "waiting for Phase-1.0 API"
```

### 7. Critical Path Analysis

```bash
# Show the longest dependency chain and ETA
python3 scripts/agent_coordination_phases.py workflow critical-path
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
python3 scripts/agent_coordination_phases.py phase start Phase-1.0 --agent kimi-g1

# Track progress throughout the phase
python3 scripts/agent_coordination_phases.py phase update Phase-1.0 --tests-passing 35/69
python3 scripts/agent_coordination_phases.py phase update Phase-1.0 --tests-passing 69/69

# Mark complete
python3 scripts/agent_coordination_phases.py phase complete Phase-1.0
```

### Phase-2 (depends on Phase-1.0)

```bash
# Define dependency
python3 scripts/agent_coordination_phases.py phase start Phase-2 --depends-on Phase-1.0 --agent agy-flash

# If Phase-1.0 is blocked, this will show as a blocker
python3 scripts/agent_coordination_phases.py phase status Phase-2

# Once Phase-1.0 completes, proceed with work
python3 scripts/agent_coordination_phases.py phase update Phase-2 --tests-passing 16/16
python3 scripts/agent_coordination_phases.py phase complete Phase-2
```

### Parallel Phases

Phases can run in parallel if they have no dependencies:

```bash
# Start Phase-3 and Phase-4 in parallel
python3 scripts/agent_coordination_phases.py phase start Phase-3 --depends-on Phase-2 --agent kimi-g1
python3 scripts/agent_coordination_phases.py phase start Phase-4 --depends-on Phase-2 --agent agy-flash

# Both can progress concurrently
python3 scripts/agent_coordination_phases.py phase list
# Both show "🔄 IN_PROGRESS" simultaneously
```

## Blocker Detection

The system automatically detects which phases are blocking a given phase by checking unfulfilled dependencies:

```bash
# If Phase-3 depends on Phase-2 and Phase-4 isn't complete:
python3 scripts/agent_coordination_phases.py phase status Phase-3

# Output shows:
# Dependencies: Phase-2, Phase-4
# Phase-2 may be blocked if it hasn't completed yet
```

## Critical Path Analysis

Shows the longest chain of dependent phases and the total time to complete if run sequentially:

```bash
python3 scripts/agent_coordination_phases.py workflow critical-path
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

Phases are sorted using a numeric pattern matcher:

- "Phase-1.0" → (1, 0.0)
- "Phase-1.1" → (1, 0.1)
- "Phase-2" → (2, 0.0)
- "Phase-10.5" → (10, 0.5)

This ensures correct ordering even with mixed naming conventions.

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

## Integration with agent_coordination.py

The phase tracking module (`agent_coordination_phases.py`) is designed to complement the existing agent coordination system in `scripts/agent_coordination.py`:

- **Legacy API** (agent_coordination.py): Register agents, claim/release tasks
- **Phase Tracking** (agent_coordination_phases.py): Track multi-phase workflows

They share the same GossipBus database, so you can use both systems together:

```bash
# Register an agent
python3 scripts/agent_coordination.py register kimi-g1 cli-tool kimi-code

# Track phase workflow
python3 scripts/agent_coordination_phases.py phase start Phase-1.0 --agent kimi-g1

# Claim specific tasks within the phase
python3 scripts/agent_coordination.py claim kimi-g1 "Phase-1.0::PeerObservation"
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
python3 scripts/agent_coordination_phases.py phase start Phase-1.0
```

### Cannot complete phase with blockers

Blockers must be removed before completion:

```bash
# See what's blocking
python3 scripts/agent_coordination_phases.py phase status Phase-2

# Remove each blocker
python3 scripts/agent_coordination_phases.py phase unblock Phase-2 --reason "waiting for API"
python3 scripts/agent_coordination_phases.py phase unblock Phase-2 --reason "design review"

# Now you can complete
python3 scripts/agent_coordination_phases.py phase complete Phase-2
```

### Cannot restart a completed phase

Completed phases cannot be restarted. To track a new instance, use a different phase name:

```bash
# Instead of restarting Phase-1.0
python3 scripts/agent_coordination_phases.py phase start Phase-1.0b --agent new-agent
```
