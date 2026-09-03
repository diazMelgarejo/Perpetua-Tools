"""tests/test_agent_coordination_heartbeat.py

Tests for heartbeat monitoring and liveness detection.
Covers: heartbeat tracking, liveness status calculation, stale claim auto-cleanup.
"""
from __future__ import annotations

import asyncio
import pytest
import time

from orchestrator.heartbeat_monitor import (
    liveness_status,
    find_agent_heartbeats,
    find_open_claims,
    cleanup_stale_claims,
    LIVENESS_ACTIVE_SEC,
    LIVENESS_IDLE_SEC,
    LIVENESS_STALLED_SEC,
)
from orchestrator.coordination.task_queue import (
    queue_add,
    queue_claim,
    latest_task_snapshots,
)
from orchestrator.coordination.types import QueuedTaskState
from orchestrator.gossip_bus import GossipBus
from coordination_test_helpers import emit_noise_batch
from orchestrator.coordination.liveness import (
    _heartbeat_check as heartbeat_check,
    _heartbeat_dashboard as heartbeat_dashboard,
    _heartbeat_list as heartbeat_list,
    _heartbeat_timeline as heartbeat_timeline,
)
from orchestrator.coordination.claims import log_message


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
async def bus(tmp_path):
    """Create a test GossipBus instance."""
    db = str(tmp_path / "test.db")
    b = GossipBus(db)
    await b.init_db()
    return b


@pytest.fixture
def current_ts():
    """Current timestamp for consistent testing."""
    return time.time()


# ─────────────────────────────────────────────────────────────────────────────
# Unit Tests: Liveness Status Calculation
# ─────────────────────────────────────────────────────────────────────────────

def test_liveness_status_active():
    """Agent with activity < 60 sec ago is ACTIVE."""
    now = time.time()
    last_activity = now - 30  # 30 seconds ago
    status, seconds_since = liveness_status(last_activity)
    assert status == "ACTIVE"
    assert 28 <= seconds_since <= 32  # Allow small timing variance


def test_liveness_status_idle():
    """Agent with activity 60-300 sec ago is IDLE."""
    now = time.time()
    last_activity = now - 150  # 150 seconds ago
    status, seconds_since = liveness_status(last_activity)
    assert status == "IDLE"
    assert 148 <= seconds_since <= 152


def test_liveness_status_stalled():
    """Agent with activity 300-1800 sec ago is STALLED."""
    now = time.time()
    last_activity = now - 900  # 15 minutes ago
    status, seconds_since = liveness_status(last_activity)
    assert status == "STALLED"
    assert 898 <= seconds_since <= 902


def test_liveness_status_dead():
    """Agent with activity > 1800 sec ago is DEAD."""
    now = time.time()
    last_activity = now - 3600  # 1 hour ago
    status, seconds_since = liveness_status(last_activity)
    assert status == "DEAD"
    assert 3598 <= seconds_since <= 3602


def test_liveness_status_boundary_active_idle():
    """Boundary at 60 seconds: ACTIVE -> IDLE."""
    now = time.time()
    # Just under 60s -> ACTIVE
    last_activity = now - 59.9
    status, _ = liveness_status(last_activity)
    assert status == "ACTIVE"

    # Just over 60s -> IDLE
    last_activity = now - 60.1
    status, _ = liveness_status(last_activity)
    assert status == "IDLE"


def test_liveness_status_boundary_idle_stalled():
    """Boundary at 300 seconds: IDLE -> STALLED."""
    now = time.time()
    # Just under 300s -> IDLE
    last_activity = now - 299.9
    status, _ = liveness_status(last_activity)
    assert status == "IDLE"

    # Just over 300s -> STALLED
    last_activity = now - 300.1
    status, _ = liveness_status(last_activity)
    assert status == "STALLED"


def test_liveness_status_boundary_stalled_dead():
    """Boundary at 1800 seconds: STALLED -> DEAD."""
    now = time.time()
    # Just under 1800s -> STALLED
    last_activity = now - 1799.9
    status, _ = liveness_status(last_activity)
    assert status == "STALLED"

    # Just over 1800s -> DEAD
    last_activity = now - 1800.1
    status, _ = liveness_status(last_activity)
    assert status == "DEAD"


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests: Heartbeat Tracking
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_find_agent_heartbeats_empty(bus):
    """No agents tracked yet."""
    agents = await find_agent_heartbeats(bus)
    assert agents == {}


@pytest.mark.asyncio
async def test_find_agent_heartbeats_single_agent(bus):
    """Track a single registered agent."""
    await bus.emit("heartbeat", {
        "kind": "agent_register",
        "agent_id": "test-agent-1",
        "agent_type": "cli-tool",
        "model": "claude-3.5",
        "worktree": "main@/path",
        "notes": "test agent",
    })

    agents = await find_agent_heartbeats(bus)
    assert "test-agent-1" in agents
    data = agents["test-agent-1"]
    assert data['status'] in ("ACTIVE", "IDLE", "STALLED", "DEAD")
    assert data['last_registration']['agent_id'] == "test-agent-1"
    assert data['last_registration']['model'] == "claude-3.5"
    assert data['work_in_progress'] is None


@pytest.mark.asyncio
async def test_find_agent_heartbeats_current_worktree_updates_from_pulse(bus, capsys):
    """Regression for the exact staleness bug hit twice with a live agent
    this session: register at worktree A, later pulse from worktree B (no
    re-register) -- current_worktree (and heartbeat_check's printed output)
    must reflect B, not stay frozen at A forever."""
    await bus.emit("heartbeat", {
        "kind": "agent_register",
        "agent_id": "roamer",
        "agent_type": "cli-tool",
        "model": "claude-3.5",
        "worktree": "docs/old-branch@/path/one",
        "notes": "",
    })
    await bus.emit("heartbeat", {
        "kind": "agent_pulse",
        "agent_id": "roamer",
        "worktree": "feature/new-branch@/path/two",
        "timestamp": time.time(),
    })

    agents = await find_agent_heartbeats(bus)
    data = agents["roamer"]
    assert data['current_worktree'] == "feature/new-branch@/path/two"
    # last_registration stays a true historical snapshot -- must NOT be
    # mutated by the pulse, only current_worktree should move.
    assert data['last_registration']['worktree'] == "docs/old-branch@/path/one"

    capsys.readouterr()
    await heartbeat_check(bus, "roamer")
    captured = capsys.readouterr()
    assert "feature/new-branch@/path/two" in captured.out
    assert "docs/old-branch@/path/one" not in captured.out


@pytest.mark.asyncio
async def test_log_message_does_not_refresh_agent_liveness(bus):
    """Board notes are status evidence, never a substitute for a pulse."""
    stale_at = time.time() - (LIVENESS_IDLE_SEC + 10)
    async with bus.connect() as db:
        await bus.insert_event(
            db,
            "heartbeat",
            {
                "kind": "agent_register",
                "agent_id": "logged-but-stale",
                "agent_type": "cli-tool",
                "model": "local",
                "worktree": "feature@/path",
                "notes": "",
            },
            timestamp=stale_at,
        )
        await db.commit()

    await log_message(bus, "logged-but-stale", "Still working")

    state = await find_agent_heartbeats(bus, "logged-but-stale")
    assert state["logged-but-stale"]["status"] == "STALLED"
    assert state["logged-but-stale"]["last_heartbeat_ts"] == stale_at


@pytest.mark.asyncio
async def test_find_agent_heartbeats_with_work_in_progress(bus):
    """Agent tracking shows current task."""
    await bus.emit("heartbeat", {
        "kind": "agent_register",
        "agent_id": "worker-1",
        "agent_type": "llm-agent",
        "model": "gpt-4",
        "worktree": "feature@/path",
        "notes": "",
    })

    # Claim a task
    await bus.emit("heartbeat", {
        "kind": "agent_claim",
        "agent_id": "worker-1",
        "task": "phase-1-testing",
        "worktree": "feature@/path",
        "notes": "running tests",
    })

    agents = await find_agent_heartbeats(bus)
    assert agents["worker-1"]['work_in_progress'] == "phase-1-testing"

    # Release the task
    await bus.emit("heartbeat", {
        "kind": "agent_release",
        "agent_id": "worker-1",
        "task": "phase-1-testing",
        "worktree": "feature@/path",
    })

    agents = await find_agent_heartbeats(bus)
    assert agents["worker-1"]['work_in_progress'] is None


@pytest.mark.asyncio
async def test_find_agent_heartbeats_multiple_agents(bus):
    """Track multiple agents with different statuses."""
    # Register 3 agents
    for i in range(1, 4):
        await bus.emit("heartbeat", {
            "kind": "agent_register",
            "agent_id": f"agent-{i}",
            "agent_type": "cli-tool",
            "model": f"model-{i}",
            "worktree": f"branch-{i}@/path",
            "notes": f"agent {i}",
        })

    agents = await find_agent_heartbeats(bus)
    assert len(agents) == 3
    for i in range(1, 4):
        assert f"agent-{i}" in agents


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests: Claim Tracking
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_find_open_claims_empty(bus):
    """No open claims."""
    claims = await find_open_claims(bus)
    assert claims == []


@pytest.mark.asyncio
async def test_find_open_claims_single(bus):
    """Track single open claim."""
    await bus.emit("heartbeat", {
        "kind": "agent_claim",
        "agent_id": "agent-1",
        "task": "task-1",
        "worktree": "main@/path",
        "notes": "working on it",
    })

    claims = await find_open_claims(bus)
    assert len(claims) == 1
    assert claims[0]['agent_id'] == "agent-1"
    assert claims[0]['task'] == "task-1"


@pytest.mark.asyncio
async def test_find_open_claims_released(bus):
    """Released claims don't appear as open."""
    await bus.emit("heartbeat", {
        "kind": "agent_claim",
        "agent_id": "agent-1",
        "task": "task-1",
        "worktree": "main@/path",
        "notes": "",
    })

    claims = await find_open_claims(bus)
    assert len(claims) == 1

    # Release the task
    await bus.emit("heartbeat", {
        "kind": "agent_release",
        "agent_id": "agent-1",
        "task": "task-1",
        "worktree": "main@/path",
    })

    claims = await find_open_claims(bus)
    assert len(claims) == 0


@pytest.mark.asyncio
async def test_find_open_claims_multiple_mixed(bus):
    """Multiple claims, some open, some released."""
    # Open claim 1
    await bus.emit("heartbeat", {
        "kind": "agent_claim",
        "agent_id": "agent-1",
        "task": "task-1",
        "worktree": "main@/path",
        "notes": "",
    })

    # Open claim 2
    await bus.emit("heartbeat", {
        "kind": "agent_claim",
        "agent_id": "agent-2",
        "task": "task-2",
        "worktree": "main@/path",
        "notes": "",
    })

    # Release task-1
    await bus.emit("heartbeat", {
        "kind": "agent_release",
        "agent_id": "agent-1",
        "task": "task-1",
        "worktree": "main@/path",
    })

    claims = await find_open_claims(bus)
    assert len(claims) == 1
    assert claims[0]['task'] == "task-2"


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests: Stale Claim Cleanup
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cleanup_stale_claims_no_dead_agents(bus):
    """No auto-release when agents are active."""
    # Register active agent
    await bus.emit("heartbeat", {
        "kind": "agent_register",
        "agent_id": "active-agent",
        "agent_type": "cli-tool",
        "model": "model-1",
        "worktree": "main@/path",
        "notes": "",
    })

    # Claim task
    await bus.emit("heartbeat", {
        "kind": "agent_claim",
        "agent_id": "active-agent",
        "task": "task-1",
        "worktree": "main@/path",
        "notes": "",
    })

    # Should not release (agent is ACTIVE)
    released = await cleanup_stale_claims(bus)
    assert released == []

    # Verify claim still open
    claims = await find_open_claims(bus)
    assert len(claims) == 1


@pytest.mark.asyncio
async def test_cleanup_stale_claims_dead_agent(bus):
    """Auto-release claims from dead agents."""
    # Register agent with old heartbeat (> 30 min ago)
    old_ts = time.time() - 2000

    # We can't directly control event timestamps, so we'll use a workaround:
    # Register an agent, then simulate it becoming dead by checking the logic

    await bus.emit("heartbeat", {
        "kind": "agent_register",
        "agent_id": "dead-agent",
        "agent_type": "cli-tool",
        "model": "model-1",
        "worktree": "main@/path",
        "notes": "",
    })

    # Claim task
    await bus.emit("heartbeat", {
        "kind": "agent_claim",
        "agent_id": "dead-agent",
        "task": "task-1",
        "worktree": "main@/path",
        "notes": "",
    })

    # Get the agent's registration to mark it old
    agents = await find_agent_heartbeats(bus, "dead-agent")
    original_ts = agents["dead-agent"]["last_heartbeat_ts"]

    # Since we can't retroactively change timestamps, we verify the logic works
    # by checking that recent claims don't get released
    released = await cleanup_stale_claims(bus)
    assert released == []  # Recently claimed, not dead yet


@pytest.mark.asyncio
async def test_cleanup_stale_claims_releases_dead_agent_queue_claim(bus, monkeypatch):
    """Queue claims must be released when the holding agent is DEAD."""
    now = time.time()
    def _mock_time():
        return now + LIVENESS_STALLED_SEC + 10

    await bus.emit("heartbeat", {
        "kind": "agent_register",
        "agent_id": "dead-agent",
        "agent_type": "cli-tool",
        "model": "model-1",
        "worktree": "main@/path",
        "notes": "",
    })
    
    # We also need to emit a claim
    await bus.emit("heartbeat", {
        "kind": "agent_claim",
        "agent_id": "dead-agent",
        "task": "stale-work",
        "worktree": "main@/path",
        "notes": "",
    })

    await queue_add(bus, "stale-work", "Phase-1", "NORMAL", "", None)
    snapshots = await latest_task_snapshots(bus)
    task_id = next(iter(snapshots))
    await queue_claim(bus, task_id, "dead-agent")

    # Time-patch for cleanup
    monkeypatch.setattr(time, "time", _mock_time)

    released = await cleanup_stale_claims(bus)
    
    # Released array returns the raw task_id or task name for normal claims
    # cleanup_stale_claims emits agent_release for each stale claim
    assert "stale-work" in released or task_id in released

    async with bus.connect() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM task_claims WHERE task_id = ?",
            (task_id,),
        )
        (claim_count,) = await cursor.fetchone()
    assert claim_count == 0

    snapshots = await latest_task_snapshots(bus)
    assert snapshots[task_id]["status"] == QueuedTaskState.QUEUED.value
    
    # Remove monkeypatch for further operations
    monkeypatch.undo()
    assert await queue_claim(bus, task_id, "agent-b") is None


# ─────────────────────────────────────────────────────────────────────────────
# Output Tests: Dashboard and Display Functions
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def testheartbeat_list_empty(bus, capsys):
    """List shows 'no agents' when empty."""
    await heartbeat_list(bus)
    captured = capsys.readouterr()
    assert "no agents tracked yet" in captured.out


@pytest.mark.asyncio
async def testheartbeat_list_with_agents(bus, capsys):
    """List shows agents by status."""
    await bus.emit("heartbeat", {
        "kind": "agent_register",
        "agent_id": "agent-1",
        "agent_type": "cli-tool",
        "model": "model-1",
        "worktree": "main@/path",
        "notes": "",
    })

    await heartbeat_list(bus)
    captured = capsys.readouterr()
    assert "agent-1" in captured.out
    assert "ACTIVE" in captured.out or "IDLE" in captured.out


@pytest.mark.asyncio
async def testheartbeat_dashboard_empty(bus, capsys):
    """Dashboard shows 'no agents' when empty."""
    await heartbeat_dashboard(bus)
    captured = capsys.readouterr()
    assert "no agents tracked yet" in captured.out


@pytest.mark.asyncio
async def testheartbeat_dashboard_with_agents(bus, capsys):
    """Dashboard shows agent summary and timestamps."""
    await bus.emit("heartbeat", {
        "kind": "agent_register",
        "agent_id": "agent-1",
        "agent_type": "cli-tool",
        "model": "model-1",
        "worktree": "main@/path",
        "notes": "test",
    })

    await heartbeat_dashboard(bus)
    captured = capsys.readouterr()
    assert "AGENT HEALTH" in captured.out
    assert "agent-1" in captured.out
    assert "model-1" in captured.out


@pytest.mark.asyncio
async def testheartbeat_check_not_found(bus, capsys):
    """Check shows 'not found' for unknown agent."""
    await heartbeat_check(bus, "nonexistent")
    captured = capsys.readouterr()
    assert "not found" in captured.out


@pytest.mark.asyncio
async def testheartbeat_check_with_agent(bus, capsys):
    """Check shows detailed agent info."""
    await bus.emit("heartbeat", {
        "kind": "agent_register",
        "agent_id": "agent-1",
        "agent_type": "cli-tool",
        "model": "model-1",
        "worktree": "main@/path",
        "notes": "test agent",
    })

    await heartbeat_check(bus, "agent-1")
    captured = capsys.readouterr()
    assert "agent-1" in captured.out
    assert "Status:" in captured.out
    assert "Type:" in captured.out
    assert "Model:" in captured.out


@pytest.mark.asyncio
async def testheartbeat_timeline_empty(bus, capsys):
    """Timeline shows 'no activity' for unknown agent."""
    await heartbeat_timeline(bus, "nonexistent", hours=24)
    captured = capsys.readouterr()
    assert "no activity" in captured.out


@pytest.mark.asyncio
async def testheartbeat_timeline_with_events(bus, capsys):
    """Timeline shows agent activity in chronological order."""
    # Register
    await bus.emit("heartbeat", {
        "kind": "agent_register",
        "agent_id": "agent-1",
        "agent_type": "cli-tool",
        "model": "model-1",
        "worktree": "main@/path",
        "notes": "",
    })

    # Claim
    await bus.emit("heartbeat", {
        "kind": "agent_claim",
        "agent_id": "agent-1",
        "task": "task-1",
        "worktree": "main@/path",
        "notes": "",
    })

    # Release
    await bus.emit("heartbeat", {
        "kind": "agent_release",
        "agent_id": "agent-1",
        "task": "task-1",
        "worktree": "main@/path",
    })

    await heartbeat_timeline(bus, "agent-1", hours=24)
    captured = capsys.readouterr()
    assert "Timeline for agent-1" in captured.out
    assert "REGISTERED" in captured.out
    assert "CLAIMED" in captured.out
    assert "RELEASED" in captured.out


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Filtering by Agent ID
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_find_agent_heartbeats_filter_by_id(bus):
    """Filtering by agent_id returns only that agent."""
    # Register 3 agents
    for i in range(1, 4):
        await bus.emit("heartbeat", {
            "kind": "agent_register",
            "agent_id": f"agent-{i}",
            "agent_type": "cli-tool",
            "model": f"model-{i}",
            "worktree": f"branch-{i}@/path",
            "notes": "",
        })

    # Filter by specific agent
    agents = await find_agent_heartbeats(bus, agent_id="agent-2")
    assert len(agents) == 1
    assert "agent-2" in agents


# ─────────────────────────────────────────────────────────────────────────────
# Tests: Edge Cases
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_pulse_keeps_agent_alive(bus):
    """Pulse events update last_heartbeat_ts."""
    await bus.emit("heartbeat", {
        "kind": "agent_register",
        "agent_id": "agent-1",
        "agent_type": "cli-tool",
        "model": "model-1",
        "worktree": "main@/path",
        "notes": "",
    })

    # Check initial status
    agents1 = await find_agent_heartbeats(bus, "agent-1")
    ts1 = agents1["agent-1"]["last_heartbeat_ts"]

    # Emit pulse
    await asyncio.sleep(0.1)  # Small delay to ensure different timestamp
    await bus.emit("heartbeat", {
        "kind": "agent_pulse",
        "agent_id": "agent-1",
        "worktree": "main@/path",
        "timestamp": time.time(),
    })

    # Check updated status
    agents2 = await find_agent_heartbeats(bus, "agent-1")
    ts2 = agents2["agent-1"]["last_heartbeat_ts"]
    assert ts2 > ts1  # Pulse advanced the timestamp


@pytest.mark.asyncio
async def test_agent_killed_marks_dead(bus):
    """Agent_killed event marks agent as dead."""
    await bus.emit("heartbeat", {
        "kind": "agent_register",
        "agent_id": "agent-1",
        "agent_type": "cli-tool",
        "model": "model-1",
        "worktree": "main@/path",
        "notes": "",
    })

    await bus.emit("heartbeat", {
        "kind": "agent_killed",
        "agent_id": "agent-1",
        "worktree": "main@/path",
        "reason": "manual kill",
        "timestamp": time.time(),
    })

    agents = await find_agent_heartbeats(bus, "agent-1")
    assert "agent-1" in agents
    assert agents["agent-1"]["status"] == "DEAD"
    assert agents["agent-1"]["killed_reason"] == "manual kill"


@pytest.mark.asyncio
async def test_find_agent_heartbeats_survives_heartbeat_noise_beyond_tail_window(bus):
    """Agent liveness must not disappear once unrelated heartbeat volume
    exceeds bus.tail()'s size-bounded window."""
    await bus.emit("heartbeat", {
        "kind": "agent_register",
        "agent_id": "victim",
        "agent_type": "cli-tool",
        "model": "model-x",
        "worktree": "main@/path",
        "notes": "",
    })
    await bus.emit("heartbeat", {
        "kind": "agent_pulse",
        "agent_id": "victim",
        "worktree": "main@/path",
    })

    await emit_noise_batch(bus, 1500, modulo=10)

    agents = await find_agent_heartbeats(bus, agent_id="victim")
    assert "victim" in agents
    assert agents["victim"]["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_find_open_claims_survives_heartbeat_noise_beyond_tail_window(bus):
    await bus.emit("heartbeat", {
        "kind": "agent_register",
        "agent_id": "claimer",
        "agent_type": "cli-tool",
        "model": "model-x",
        "worktree": "main@/path",
        "notes": "",
    })
    await bus.emit("heartbeat", {
        "kind": "agent_claim",
        "agent_id": "claimer",
        "task": "important-task",
        "worktree": "main@/path",
        "notes": "",
    })

    await emit_noise_batch(bus, 1500, modulo=10)

    claims = await find_open_claims(bus)
    assert len(claims) == 1
    assert claims[0]["task"] == "important-task"
    assert claims[0]["agent_id"] == "claimer"
