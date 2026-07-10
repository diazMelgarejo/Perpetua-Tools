"""
tests/test_fleet_mode.py — Unit tests for Phase 2 FleetMode and topology state.

Tests:
  1. FleetMode classification (3 modes + edge cases)
  2. FleetTopologyState serialization
  3. Topology file round-trip (read/write with idempotency)
  4. Integration with startup scenario (orthogonal enums)

All tests run fully offline — no network, no persistent filesystem outside .../tmp.
"""

from __future__ import annotations

import sys
import json
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator.startup_intelligence import (
    FleetMode,
    classify_fleet_mode,
    StartupScenario,
    classify_scenario,
)
from orchestrator.fleet_topology import (
    FleetTopologyState,
    read_fleet_topology,
    write_fleet_topology,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FleetMode Classification Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_classify_fleet_mode_solo():
    """Zero peers reachable → SOLO."""
    assert classify_fleet_mode(0, False) == FleetMode.SOLO
    assert classify_fleet_mode(0, True) == FleetMode.SOLO  # cross_reachable ignored


def test_classify_fleet_mode_pair_one_peer():
    """One peer reachable → PAIR."""
    assert classify_fleet_mode(1, False) == FleetMode.PAIR
    assert classify_fleet_mode(1, True) == FleetMode.PAIR  # cross_reachable ignored (only 1 peer)


def test_classify_fleet_mode_fleet():
    """Two or more peers, cross-reachable → FLEET."""
    assert classify_fleet_mode(2, True) == FleetMode.FLEET
    assert classify_fleet_mode(3, True) == FleetMode.FLEET
    assert classify_fleet_mode(10, True) == FleetMode.FLEET


def test_classify_fleet_mode_fragmented():
    """Two or more peers, not cross-reachable → PAIR (fragmented topology)."""
    assert classify_fleet_mode(2, False) == FleetMode.PAIR
    assert classify_fleet_mode(3, False) == FleetMode.PAIR
    assert classify_fleet_mode(10, False) == FleetMode.PAIR


def test_classify_fleet_mode_edge_case_negative_peers():
    """Negative peer count is invalid; treated as SOLO (safe default)."""
    assert classify_fleet_mode(-1, False) == FleetMode.SOLO


def test_classify_fleet_mode_deterministic():
    """Same inputs always produce same output (deterministic, no floating-point)."""
    for _ in range(3):
        assert classify_fleet_mode(2, True) == FleetMode.FLEET
        assert classify_fleet_mode(1, True) == FleetMode.PAIR
        assert classify_fleet_mode(0, False) == FleetMode.SOLO


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FleetTopologyState Serialization Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_fleet_topology_state_to_dict():
    """FleetTopologyState.to_dict() produces JSON-serializable output."""
    ts = time.time()
    state = FleetTopologyState(
        local_node="node-a",
        fleet_mode=FleetMode.FLEET,
        peers=["node-b", "node-c"],
        cross_reachable=True,
        timestamp=ts,
    )
    d = state.to_dict()

    # All fields present
    assert d["local_node"] == "node-a"
    assert d["fleet_mode"] == "FLEET"  # Enum → string
    assert d["peers"] == ["node-b", "node-c"]
    assert d["cross_reachable"] is True
    assert d["timestamp"] == ts

    # JSON-serializable
    json_str = json.dumps(d)
    assert "FLEET" in json_str


def test_fleet_topology_state_frozen():
    """FleetTopologyState is frozen (immutable)."""
    state = FleetTopologyState(
        local_node="node-a",
        fleet_mode=FleetMode.PAIR,
        peers=["node-b"],
        cross_reachable=False,
        timestamp=time.time(),
    )

    # Attempting to modify raises FrozenInstanceError
    try:
        state.local_node = "node-x"  # type: ignore[misc]
        assert False, "Should not be able to modify frozen dataclass"
    except (AttributeError, TypeError):
        pass  # Expected


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Topology File I/O Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_read_fleet_topology_nonexistent():
    """Reading from a nonexistent file returns None (no error)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "nonexistent.json"
        result = read_fleet_topology(path)
        assert result is None


def test_write_and_read_fleet_topology():
    """Write and read back produces the same state."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "fleet_topology.json"
        ts = time.time()

        # Write
        state = FleetTopologyState(
            local_node="mac-node-1",
            fleet_mode=FleetMode.FLEET,
            peers=["win-node-1", "linux-node-2"],
            cross_reachable=True,
            timestamp=ts,
        )
        written = write_fleet_topology(state, path)
        assert written is True
        assert path.exists()

        # Read back
        read_state = read_fleet_topology(path)
        assert read_state is not None
        assert read_state.local_node == "mac-node-1"
        assert read_state.fleet_mode == FleetMode.FLEET
        assert read_state.peers == ["win-node-1", "linux-node-2"]
        assert read_state.cross_reachable is True
        assert read_state.timestamp == ts


def test_write_fleet_topology_hash_gated_idempotency():
    """Writing the same content twice does not modify the file (hash-gated idempotency)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "fleet_topology.json"
        ts = time.time()

        state = FleetTopologyState(
            local_node="node-a",
            fleet_mode=FleetMode.PAIR,
            peers=["node-b"],
            cross_reachable=False,
            timestamp=ts,
        )

        # First write
        written1 = write_fleet_topology(state, path)
        assert written1 is True
        mtime1 = path.stat().st_mtime
        content1 = path.read_bytes()

        # Small delay
        time.sleep(0.01)

        # Second write (same content)
        written2 = write_fleet_topology(state, path)
        assert written2 is True
        mtime2 = path.stat().st_mtime
        content2 = path.read_bytes()

        # File should not have been modified (mtime unchanged, content identical)
        assert mtime1 == mtime2, "File was unnecessarily written (hash gate failed)"
        assert content1 == content2


def test_read_fleet_topology_malformed_json():
    """Reading malformed JSON returns None (no error)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "bad.json"
        path.write_text("{ invalid json")
        result = read_fleet_topology(path)
        assert result is None


def test_read_fleet_topology_missing_fields():
    """Reading JSON with missing optional fields uses defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "minimal.json"
        # Only required fields, others missing
        path.write_text(json.dumps({"local_node": "node-a"}))
        result = read_fleet_topology(path)
        assert result is not None
        assert result.local_node == "node-a"
        assert result.fleet_mode == FleetMode.SOLO  # default
        assert result.peers == []  # default
        assert result.cross_reachable is False  # default


def test_write_fleet_topology_permission_error():
    """write_fleet_topology gracefully handles permission errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "fleet_topology.json"
        state = FleetTopologyState(
            local_node="node-a",
            fleet_mode=FleetMode.SOLO,
            peers=[],
            cross_reachable=False,
            timestamp=time.time(),
        )

        # Create a read-only directory
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o444)

        # Attempt write to read-only path should return False, not crash
        written = write_fleet_topology(state, path / "fleet_topology.json")
        assert written is False

        # Clean up
        path.chmod(0o755)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Orthogonality Tests (FleetMode ⊥ StartupScenario)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_fleet_mode_orthogonal_to_startup_scenario():
    """FleetMode and StartupScenario are independent (both can exist)."""
    # Same startup scenario can have different fleet modes
    startup = classify_scenario(True, False, False, False)  # MAC_OLLAMA_ONLY
    fleet1 = classify_fleet_mode(0, False)  # SOLO
    fleet2 = classify_fleet_mode(2, True)   # FLEET

    assert startup == StartupScenario.MAC_OLLAMA_ONLY
    assert fleet1 == FleetMode.SOLO
    assert fleet2 == FleetMode.FLEET

    # Same fleet mode can occur in different startup scenarios
    assert classify_fleet_mode(1, False) == FleetMode.PAIR
    assert classify_fleet_mode(1, True) == FleetMode.PAIR


def test_fleet_mode_enum_values():
    """FleetMode enum has exactly three values."""
    modes = list(FleetMode)
    assert len(modes) == 3
    assert FleetMode.SOLO in modes
    assert FleetMode.PAIR in modes
    assert FleetMode.FLEET in modes
    assert FleetMode.SOLO.value == "SOLO"
    assert FleetMode.PAIR.value == "PAIR"
    assert FleetMode.FLEET.value == "FLEET"
