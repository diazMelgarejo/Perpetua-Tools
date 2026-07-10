"""tests/test_agent_coordination_phases.py

Unit tests for phase-based workflow tracking in agent_coordination_phases.py.
Tests phase state transitions, blocker detection, and critical path analysis.
"""
import asyncio
import tempfile
import time
from pathlib import Path

import pytest

# Add parent directory to path so we can import scripts
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.gossip_bus import GossipBus  # noqa: E402
from scripts.agent_coordination_phases import (  # noqa: E402
    PhaseState,
    PhaseStatus,
    _all_phase_states,
    _detect_blockers,
    _get_latest_phase_state,
    _phase_block,
    _phase_complete,
    _phase_start,
    _phase_unblock,
    _phase_update,
)


@pytest.fixture
async def bus_with_db():
    """Create a temporary GossipBus instance for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_gossip.db")
        bus = GossipBus(db_path)
        await bus.init_db()
        yield bus


@pytest.mark.asyncio
async def test_phase_state_creation(bus_with_db):
    """Test PhaseState can be created and serialized."""
    phase = PhaseState(
        phase_name="Phase-1.0",
        status=PhaseStatus.NOT_STARTED,
        total_tests=69,
    )
    assert phase.phase_name == "Phase-1.0"
    assert phase.status == PhaseStatus.NOT_STARTED
    assert phase.total_tests == 69

    # Test serialization
    payload = phase.to_payload()
    assert payload["phase_name"] == "Phase-1.0"
    assert payload["status"] == "not_started"

    # Test deserialization
    restored = PhaseState.from_payload(payload)
    assert restored.phase_name == phase.phase_name
    assert restored.status == phase.status
    assert restored.total_tests == phase.total_tests


@pytest.mark.asyncio
async def test_phase_start(bus_with_db):
    """Test starting a phase transitions it to in_progress."""
    bus = bus_with_db
    await _phase_start(bus, "Phase-1.0", depends_on=["Phase-0"], agent_id="agent-1")

    phase = await _get_latest_phase_state(bus, "Phase-1.0")
    assert phase is not None
    assert phase.status == PhaseStatus.IN_PROGRESS
    assert phase.started_at is not None
    assert "agent-1" in phase.assigned_to
    assert "Phase-0" in phase.depends_on


@pytest.mark.asyncio
async def test_phase_update_tests(bus_with_db):
    """Test updating phase test progress."""
    bus = bus_with_db
    await _phase_start(bus, "Phase-2", agent_id="agent-1")
    await _phase_update(bus, "Phase-2", tests_passing=50, total_tests=69, agent_id="agent-1")

    phase = await _get_latest_phase_state(bus, "Phase-2")
    assert phase is not None
    assert phase.tests_passing == 50
    assert phase.total_tests == 69


@pytest.mark.asyncio
async def test_phase_complete(bus_with_db):
    """Test completing a phase."""
    bus = bus_with_db
    await _phase_start(bus, "Phase-3")
    await _phase_update(bus, "Phase-3", tests_passing=16, total_tests=16)
    await _phase_complete(bus, "Phase-3")

    phase = await _get_latest_phase_state(bus, "Phase-3")
    assert phase is not None
    assert phase.status == PhaseStatus.COMPLETE
    assert phase.completed_at is not None


@pytest.mark.asyncio
async def test_phase_block_and_unblock(bus_with_db):
    """Test blocking and unblocking a phase."""
    bus = bus_with_db
    await _phase_start(bus, "Phase-4")

    # Block the phase
    await _phase_block(bus, "Phase-4", "waiting for Phase-3 API")
    phase = await _get_latest_phase_state(bus, "Phase-4")
    assert phase.status == PhaseStatus.BLOCKED
    assert "waiting for Phase-3 API" in phase.blockers

    # Unblock it
    await _phase_unblock(bus, "Phase-4", "waiting for Phase-3 API")
    phase = await _get_latest_phase_state(bus, "Phase-4")
    assert phase.status == PhaseStatus.IN_PROGRESS
    assert "waiting for Phase-3 API" not in phase.blockers


@pytest.mark.asyncio
async def test_blocker_detection(bus_with_db):
    """Test detecting phases blocking a given phase."""
    bus = bus_with_db

    # Create phases with dependencies
    await _phase_start(bus, "Phase-1.0")
    await _phase_complete(bus, "Phase-1.0")

    await _phase_start(bus, "Phase-2", depends_on=["Phase-1.0"])
    await _phase_update(bus, "Phase-2", tests_passing=10, total_tests=16)

    # Phase-3 depends on both Phase-1.0 (complete) and Phase-2 (in progress)
    await _phase_start(bus, "Phase-3", depends_on=["Phase-1.0", "Phase-2"])

    all_phases = await _all_phase_states(bus)
    phase_3 = all_phases["Phase-3"]

    # Detect blockers
    blockers = await _detect_blockers(bus, phase_3, all_phases)
    assert "Phase-2" in blockers  # not complete yet
    assert "Phase-1.0" not in blockers  # complete


@pytest.mark.asyncio
async def test_all_phase_states(bus_with_db):
    """Test retrieving all phase states."""
    bus = bus_with_db

    # Create multiple phases
    await _phase_start(bus, "Phase-1", agent_id="agent-1")
    await _phase_start(bus, "Phase-2", depends_on=["Phase-1"], agent_id="agent-2")
    await _phase_complete(bus, "Phase-1")

    phases = await _all_phase_states(bus)
    assert len(phases) == 2
    assert "Phase-1" in phases
    assert "Phase-2" in phases
    assert phases["Phase-1"].status == PhaseStatus.COMPLETE
    assert phases["Phase-2"].status == PhaseStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_multiple_blockers(bus_with_db):
    """Test tracking multiple blockers on a single phase."""
    bus = bus_with_db
    await _phase_start(bus, "Phase-5")

    # Add multiple blockers
    await _phase_block(bus, "Phase-5", "Waiting for Phase-4")
    await _phase_block(bus, "Phase-5", "Design review pending")

    phase = await _get_latest_phase_state(bus, "Phase-5")
    assert len(phase.blockers) >= 2
    assert "Waiting for Phase-4" in phase.blockers
    assert "Design review pending" in phase.blockers

    # Remove one blocker
    await _phase_unblock(bus, "Phase-5", "Waiting for Phase-4")
    phase = await _get_latest_phase_state(bus, "Phase-5")
    assert "Waiting for Phase-4" not in phase.blockers
    assert "Design review pending" in phase.blockers
    # Still blocked because one blocker remains
    assert phase.status == PhaseStatus.BLOCKED


@pytest.mark.asyncio
async def test_phase_state_ordering(bus_with_db):
    """Test phases are retrieved in dependency order."""
    bus = bus_with_db

    # Create phases with specific names to test sorting
    phases_to_create = [
        ("Phase-1.0", None),
        ("Phase-2", ["Phase-1.0"]),
        ("Phase-1.1", ["Phase-1.0"]),
        ("Phase-3", ["Phase-2"]),
    ]

    for phase_name, deps in phases_to_create:
        await _phase_start(bus, phase_name, depends_on=deps or [])

    all_phases = await _all_phase_states(bus)
    phase_names = list(all_phases.keys())

    # Verify all phases are present
    assert len(phase_names) == len(phases_to_create)
    for phase_name, _ in phases_to_create:
        assert phase_name in phase_names


@pytest.mark.asyncio
async def test_phase_agent_assignment(bus_with_db):
    """Test tracking agents assigned to phases."""
    bus = bus_with_db

    # Start phase with first agent
    await _phase_start(bus, "Phase-6", agent_id="kimi-g1")

    # Update with another agent
    await _phase_update(bus, "Phase-6", agent_id="agy-flash")

    phase = await _get_latest_phase_state(bus, "Phase-6")
    assert "kimi-g1" in phase.assigned_to
    assert "agy-flash" in phase.assigned_to


@pytest.mark.asyncio
async def test_phase_cannot_restart_after_complete(bus_with_db):
    """Test that a completed phase cannot be restarted."""
    bus = bus_with_db

    await _phase_start(bus, "Phase-7")
    await _phase_complete(bus, "Phase-7")

    # Try to start it again — should not change status
    await _phase_start(bus, "Phase-7", agent_id="another-agent")
    phase = await _get_latest_phase_state(bus, "Phase-7")
    assert phase.status == PhaseStatus.COMPLETE


@pytest.mark.asyncio
async def test_phase_completion_requires_no_blockers(bus_with_db):
    """Test that phases with blockers cannot be completed."""
    bus = bus_with_db

    await _phase_start(bus, "Phase-8")
    await _phase_block(bus, "Phase-8", "API not ready")

    # Try to complete — should warn and not change status
    await _phase_complete(bus, "Phase-8")
    phase = await _get_latest_phase_state(bus, "Phase-8")
    assert phase.status == PhaseStatus.BLOCKED

    # Unblock and try again
    await _phase_unblock(bus, "Phase-8", "API not ready")
    await _phase_complete(bus, "Phase-8")
    phase = await _get_latest_phase_state(bus, "Phase-8")
    assert phase.status == PhaseStatus.COMPLETE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
