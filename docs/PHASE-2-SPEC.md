# Phase 2 Specification: FleetMode Classifier + Topology State

**Date:** 2026-07-11  
**Status:** Complete  
**Integration Timeline:** Phases 2–6 of unified plan  
**Reference:** 2026-07-08 self-healing mesh degradation modes § 4.1–4.3

---

## Overview

Phase 2 implements the **FleetMode enum** and **topology state management** for PT's peer discovery layer. This provides a clean, named vocabulary for peer reachability and enables adaptive degradation modes for distributed mesh operations.

FleetMode is **orthogonal to StartupScenario** (Phase 1):
- **StartupScenario** classifies local backend availability (mac, windows, cloud)
- **FleetMode** classifies peer mesh topology (isolated, point-to-point, full mesh)

Both are available at startup and inform independent routing decisions.

---

## FleetMode Enum

### Definition

```python
class FleetMode(str, Enum):
    """Peer topology classification (Phase 2 — distributed mesh states)."""
    
    SOLO = "SOLO"    # No peers reachable
    PAIR = "PAIR"    # 1 peer, or 2+ peers but not fully cross-reachable
    FLEET = "FLEET"  # 2+ peers AND cross-reachable (full mesh)
```

### States

| Mode   | Peers Reachable | Cross-Reachable | Meaning | Use Case |
|--------|-----------------|-----------------|---------|----------|
| **SOLO** | 0 | N/A | Isolated node, no peer connectivity | Graceful degradation, local-only ops |
| **PAIR** | 1 | N/A | Point-to-point link to one peer | Resilient 2-node mode, gossip to 1 replica |
| **PAIR** | 2+ | False | Fragmented topology (peers can't reach each other) | Degraded mode, async anti-entropy fallback |
| **FLEET** | 2+ | True | Full mesh connectivity (quorum-capable) | Optimal: consensus, sync replication |

---

## Classification Function

### Signature

```python
def classify_fleet_mode(
    peers_reachable: int,
    cross_reachable: bool,
) -> FleetMode:
    """Classify peer fleet topology based on reachability and cross-connectivity.
    
    Pure function: no side effects, no I/O.
    """
```

### Parameters

- **`peers_reachable`** (int): Count of peer nodes this node can reach directly (0, 1, 2+).
  - Must be non-negative; negative values are treated as 0 (SOLO, safe default).
  - Updated by Phase 3 peer discovery (LAN probe, gossip).

- **`cross_reachable`** (bool): Whether peers can reach each other (forms a mesh).
  - Only meaningful when `peers_reachable >= 2`.
  - Ignored for 0 or 1 peer (always PAIR or SOLO regardless).
  - Derived from Phase 3 peer gossip and mesh probe results.

### Return Value

Returns one of three **FleetMode** enum values; never raises.

### Classification Logic (Priority Order)

| Condition | Result |
|-----------|--------|
| `peers_reachable <= 0` | `FleetMode.SOLO` |
| `peers_reachable == 1` | `FleetMode.PAIR` |
| `peers_reachable >= 2` AND `cross_reachable == True` | `FleetMode.FLEET` |
| `peers_reachable >= 2` AND `cross_reachable == False` | `FleetMode.PAIR` (fragmented) |

### Example Invocations

```python
from orchestrator.startup_intelligence import FleetMode, classify_fleet_mode

# Isolated node
assert classify_fleet_mode(0, False) == FleetMode.SOLO
assert classify_fleet_mode(-1, True) == FleetMode.SOLO  # invalid count → safe default

# Point-to-point
assert classify_fleet_mode(1, False) == FleetMode.PAIR
assert classify_fleet_mode(1, True) == FleetMode.PAIR   # cross_reachable ignored

# Full mesh
assert classify_fleet_mode(2, True) == FleetMode.FLEET
assert classify_fleet_mode(10, True) == FleetMode.FLEET  # 10+ peers, fully connected

# Fragmented (2+ peers, no mesh)
assert classify_fleet_mode(2, False) == FleetMode.PAIR
assert classify_fleet_mode(3, False) == FleetMode.PAIR  # not cross-reachable
```

---

## Topology State Management

### FleetTopologyState Dataclass

Immutable snapshot of a node's peer topology state:

```python
@dataclass(frozen=True)
class FleetTopologyState:
    local_node: str              # hostname or node ID of this node
    fleet_mode: FleetMode        # SOLO, PAIR, or FLEET
    peers: list[str]             # reachable peer node IDs
    cross_reachable: bool        # whether peers can reach each other
    timestamp: float             # Unix timestamp when recorded
```

### Persistence

State is persisted to `~/.openclaw/state/fleet_topology.json` with **hash-gated idempotency**:
- **Same content** on re-write = skip write (no file modification)
- Prevents spurious filesystem activity during stable topology states
- Deterministic JSON serialization (sorted keys, UTF-8 encoding)

### Helpers

#### `read_fleet_topology(path: Path | None = None) -> FleetTopologyState | None`

Reads fleet topology state from disk.

- Returns `None` if file doesn't exist or is malformed (never raises)
- Uses safe defaults for missing optional fields

#### `write_fleet_topology(state: FleetTopologyState, path: Path | None = None) -> bool`

Writes topology state with hash-gated idempotency.

- Returns `True` if written (or already same content), `False` on I/O error
- Never raises; logs warnings on permission/disk errors

#### `get_fleet_topology_path() -> Path`

Returns the canonical path `~/.openclaw/state/fleet_topology.json`, creating the directory if needed.

### Example Usage

```python
from orchestrator.fleet_topology import (
    FleetTopologyState,
    read_fleet_topology,
    write_fleet_topology,
    classify_fleet_mode,
)
import time

# Create a topology snapshot
state = FleetTopologyState(
    local_node="mac-node-1",
    fleet_mode=FleetMode.FLEET,
    peers=["win-node-1", "linux-node-2"],
    cross_reachable=True,
    timestamp=time.time(),
)

# Persist to disk (idempotent)
write_fleet_topology(state)

# Read back
state_read = read_fleet_topology()
assert state_read.fleet_mode == FleetMode.FLEET
```

---

## Integration with Agent Launcher

In `src/perpetua_tools/agent_launcher.py`, fleet mode is logged at startup after scenario classification:

```python
# ── Step 7: classify scenario ────
scenario = classify_scenario(mac_ok, mac_lms_ok, win_ok, lms_ok, cloud_ok=_cloud_ok)
print(f"[agent_launcher] ✓  scenario: {scenario.value}")

# ── Step 8: classify fleet mode (Phase 2) ────
fleet_mode = classify_fleet_mode(_peers_reachable, _cross_reachable)
print(f"[agent_launcher] ✓  fleet mode: {fleet_mode.value}")
```

**Note:** In Phase 2, `peers_reachable` defaults to 0 (SOLO). Phase 3 will populate this via peer discovery (LAN probes + gossip).

---

## Testing

### Unit Test Coverage

**Location:** `tests/test_fleet_mode.py` (16 tests, all passing)

#### Classification Tests (6)
- `test_classify_fleet_mode_solo` — 0 peers → SOLO
- `test_classify_fleet_mode_pair_one_peer` — 1 peer → PAIR
- `test_classify_fleet_mode_fleet` — 2+ peers, cross-reachable → FLEET
- `test_classify_fleet_mode_fragmented` — 2+ peers, not cross-reachable → PAIR
- `test_classify_fleet_mode_edge_case_negative_peers` — negative count → SOLO
- `test_classify_fleet_mode_deterministic` — idempotent, no floating-point

#### Serialization Tests (2)
- `test_fleet_topology_state_to_dict` — JSON serialization
- `test_fleet_topology_state_frozen` — immutability

#### I/O & Idempotency Tests (5)
- `test_read_fleet_topology_nonexistent` — graceful handling of missing file
- `test_write_and_read_fleet_topology` — round-trip persistence
- `test_write_fleet_topology_hash_gated_idempotency` — no spurious writes
- `test_read_fleet_topology_malformed_json` — error resilience
- `test_write_fleet_topology_permission_error` — graceful degradation on permission errors

#### Orthogonality Tests (2)
- `test_fleet_mode_orthogonal_to_startup_scenario` — independent enums
- `test_fleet_mode_enum_values` — enum completeness

---

## Key Design Decisions

### 1. Pure Function Classification

`classify_fleet_mode()` has **zero side effects**:
- No I/O, no state mutations, no randomness
- Identical inputs → identical outputs (deterministic)
- Safe to call from anywhere (manager, coder, gossip threads)

### 2. Orthogonality with StartupScenario

FleetMode and StartupScenario are **independent dimensions**:
- StartupScenario answers: "What backends do *I* have?" (local)
- FleetMode answers: "What peers can *I* reach?" (peer topology)
- Both inform routing, but for different concerns

### 3. Hash-Gated Idempotency

Topology state writes check the hash of new content against the existing file:
- Avoids filesystem churn when state is stable
- Prevents spurious `mtime` updates that downstream tools might watch
- Cost: one SHA256 hash computation per write (negligible)

### 4. Graceful Degradation in I/O

All I/O helpers return safe defaults (None, False, or early return) instead of raising:
- Prevents startup crashes due to permission or disk errors
- Logs warnings for troubleshooting
- Allows startup to proceed even if topology file can't be written

---

## Phase 3+ Roadmap

### Phase 3: LAN Peer Discovery

Implements peer detection via LAN probes and gossip:
- `lan_discovery.py` probes known endpoints (seeded from past discoveries)
- Populates `peers_reachable` count
- Gossip module reports back cross-reachability
- Calls `classify_fleet_mode()` with real data

### Phase 4: Adaptive Replication

Uses FleetMode to choose replication strategy:
- **SOLO:** local-only fallback (degraded mode)
- **PAIR:** async anti-entropy to single replica
- **FLEET:** sync replication + quorum commit

### Phase 5–6: Consensus & Healing

Uses FleetMode + PeerObservation to:
- Maintain Raft-like log in FLEET mode
- Fall back to leaderless ops in PAIR/SOLO
- Self-heal topology via discovery + re-probing

---

## Files Modified / Created

| Path | Change | Status |
|------|--------|--------|
| `orchestrator/startup_intelligence.py` | Added `FleetMode` enum + `classify_fleet_mode()` | ✅ |
| `orchestrator/fleet_topology.py` | **Created:** topology state helpers | ✅ |
| `tests/test_fleet_mode.py` | **Created:** 16 unit tests (all passing) | ✅ |
| `src/perpetua_tools/agent_launcher.py` | Integrated fleet mode logging | ✅ |
| `docs/PHASE-2-SPEC.md` | **Created:** this document | ✅ |

---

## References

- **Unified Absorption Plan:** `orama-system/docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md` §§ 0–2
- **Self-Healing Mesh Plan:** `orama-system/docs/plans/2026-07-08-self-healing-mesh-degradation-modes.md` § 4.1–4.3
- **Phase 1 Baseline:** Phase 1.0–1.3 (PeerObservation, confidence scoring, witness quorum)
- **Deliverable 1:** `D1` specification (peer observation schema, confidence thresholds)

---

## Verification

All 16 Phase 2 tests pass:

```
tests/test_fleet_mode.py::test_classify_fleet_mode_solo PASSED
tests/test_fleet_mode.py::test_classify_fleet_mode_pair_one_peer PASSED
tests/test_fleet_mode.py::test_classify_fleet_mode_fleet PASSED
tests/test_fleet_mode.py::test_classify_fleet_mode_fragmented PASSED
tests/test_fleet_mode.py::test_classify_fleet_mode_edge_case_negative_peers PASSED
tests/test_fleet_mode.py::test_classify_fleet_mode_deterministic PASSED
tests/test_fleet_mode.py::test_fleet_topology_state_to_dict PASSED
tests/test_fleet_mode.py::test_fleet_topology_state_frozen PASSED
tests/test_fleet_mode.py::test_read_fleet_topology_nonexistent PASSED
tests/test_fleet_mode.py::test_write_and_read_fleet_topology PASSED
tests/test_fleet_mode.py::test_write_fleet_topology_hash_gated_idempotency PASSED
tests/test_fleet_mode.py::test_read_fleet_topology_malformed_json PASSED
tests/test_fleet_mode.py::test_read_fleet_topology_missing_fields PASSED
tests/test_fleet_mode.py::test_write_fleet_topology_permission_error PASSED
tests/test_fleet_mode.py::test_fleet_mode_orthogonal_to_startup_scenario PASSED
tests/test_fleet_mode.py::test_fleet_mode_enum_values PASSED

============================== 16 passed in 0.35s ==============================
```

All Phase 1 tests remain passing:

```
tests/test_startup_intelligence.py ============== 20 passed in 0.29s ===============
```

**Total: 36 tests passing**
