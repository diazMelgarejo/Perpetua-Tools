"""tests/test_agent_coordination_reorder_buffer.py

Tests for Phase 1.3.2: Reorder Buffer + Watermark functionality.

Tests cover:
- Single gap buffering and resolution
- Multiple gaps buffering and resolution
- Sequential (no gap) processing
- Gap resolution with multiple outstanding claims
- Force-drain behavior
- Duplicate claim handling (already-emitted drops)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

# Ensure project root is on path for scripts/agent_coordination + orchestrator.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.agent_coordination import (
    ClaimSequence,
    ReorderBuffer,
    _buffer_drain,
    _buffer_status,
    _claim_with_seq,
    _get_reorder_buffers,
)
from orchestrator.gossip_bus import GossipBus


@pytest.fixture
def make_bus(tmp_path):
    """Factory for temporary, freshly-initialised GossipBus instances."""

    async def _factory():
        db_path = str(tmp_path / "coordination_test.db")
        bus = GossipBus(db_path)
        await bus.init_db()
        return bus

    return _factory


# ─────────────────────────────────────────────────────────────────────────────
# ClaimSequence Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_claim_sequence_to_payload():
    """ClaimSequence serializes to dict correctly."""
    ts = time.time()
    claim = ClaimSequence(
        agent_id="test-agent",
        claim_num=5,
        task="task/alpha",
        timestamp=ts,
        notes="test notes",
        worktree="branch@/path",
    )
    payload = claim.to_payload()
    assert payload["kind"] == "claim_sequence"
    assert payload["agent_id"] == "test-agent"
    assert payload["claim_num"] == 5
    assert payload["task"] == "task/alpha"
    assert payload["timestamp"] == ts
    assert payload["notes"] == "test notes"
    assert payload["worktree"] == "branch@/path"


def test_claim_sequence_from_payload():
    """ClaimSequence deserializes from dict correctly."""
    ts = time.time()
    payload = {
        "kind": "claim_sequence",
        "agent_id": "test-agent",
        "claim_num": 3,
        "task": "task/beta",
        "timestamp": ts,
        "notes": "deserialize test",
        "worktree": "main@/home",
    }
    claim = ClaimSequence.from_payload(payload)
    assert claim.agent_id == "test-agent"
    assert claim.claim_num == 3
    assert claim.task == "task/beta"
    assert claim.timestamp == ts
    assert claim.notes == "deserialize test"
    assert claim.worktree == "main@/home"


# ─────────────────────────────────────────────────────────────────────────────
# ReorderBuffer Logic Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_reorder_buffer_init():
    """ReorderBuffer initializes with correct defaults."""
    buf = ReorderBuffer(agent_id="agent-1")
    assert buf.agent_id == "agent-1"
    assert buf.watermark == 0
    assert len(buf.buffer) == 0


def test_reorder_buffer_sequential_claims():
    """Sequential claims (no gaps) emit immediately."""
    buf = ReorderBuffer(agent_id="agent-1")

    # Claim 0 (matches watermark 0)
    claim0 = ClaimSequence("agent-1", 0, "task/a", time.time())
    emitted, watermark = buf.add_claim(claim0)
    assert len(emitted) == 1
    assert emitted[0].claim_num == 0
    assert watermark == 1
    assert len(buf.buffer) == 0

    # Claim 1 (matches watermark 1)
    claim1 = ClaimSequence("agent-1", 1, "task/b", time.time())
    emitted, watermark = buf.add_claim(claim1)
    assert len(emitted) == 1
    assert emitted[0].claim_num == 1
    assert watermark == 2
    assert len(buf.buffer) == 0


def test_reorder_buffer_single_gap():
    """Single gap: claim 2 arrives before claim 1."""
    buf = ReorderBuffer(agent_id="agent-1")

    # Claim 0 (matches watermark 0)
    claim0 = ClaimSequence("agent-1", 0, "task/a", time.time())
    emitted, watermark = buf.add_claim(claim0)
    assert len(emitted) == 1
    assert watermark == 1

    # Claim 2 (gap: watermark is 1)
    claim2 = ClaimSequence("agent-1", 2, "task/c", time.time())
    emitted, watermark = buf.add_claim(claim2)
    assert len(emitted) == 0  # Buffered, no emit
    assert watermark == 1  # Watermark unchanged
    assert 2 in buf.buffer

    # Claim 1 (fills gap, watermark advances)
    claim1 = ClaimSequence("agent-1", 1, "task/b", time.time())
    emitted, watermark = buf.add_claim(claim1)
    assert len(emitted) == 2  # Both claim 1 and claim 2 emitted
    assert emitted[0].claim_num == 1
    assert emitted[1].claim_num == 2
    assert watermark == 3
    assert len(buf.buffer) == 0


def test_reorder_buffer_multiple_gaps():
    """Multiple gaps: claims 5, 2 arrive; filled by 3, 1, 4."""
    buf = ReorderBuffer(agent_id="agent-1")

    # Claim 0 (matches watermark 0)
    claim0 = ClaimSequence("agent-1", 0, "task/0", time.time())
    emitted, watermark = buf.add_claim(claim0)
    assert len(emitted) == 1
    assert watermark == 1

    # Claim 5 (big gap)
    claim5 = ClaimSequence("agent-1", 5, "task/5", time.time())
    emitted, watermark = buf.add_claim(claim5)
    assert len(emitted) == 0
    assert watermark == 1
    assert len(buf.buffer) == 1

    # Claim 2 (still a gap)
    claim2 = ClaimSequence("agent-1", 2, "task/2", time.time())
    emitted, watermark = buf.add_claim(claim2)
    assert len(emitted) == 0
    assert watermark == 1
    assert len(buf.buffer) == 2

    # Claim 3 (still gaps before)
    claim3 = ClaimSequence("agent-1", 3, "task/3", time.time())
    emitted, watermark = buf.add_claim(claim3)
    assert len(emitted) == 0
    assert len(buf.buffer) == 3

    # Claim 1 (fills gap 1, should trigger cascade)
    claim1 = ClaimSequence("agent-1", 1, "task/1", time.time())
    emitted, watermark = buf.add_claim(claim1)
    # Emits 1, 2, 3, 5 stops at gap (4 missing)
    assert len(emitted) == 3  # 1, 2, 3
    assert [e.claim_num for e in emitted] == [1, 2, 3]
    assert watermark == 4
    assert 5 in buf.buffer

    # Claim 4 (fills gap 4)
    claim4 = ClaimSequence("agent-1", 4, "task/4", time.time())
    emitted, watermark = buf.add_claim(claim4)
    assert len(emitted) == 2  # 4, 5
    assert [e.claim_num for e in emitted] == [4, 5]
    assert watermark == 6
    assert len(buf.buffer) == 0


def test_reorder_buffer_duplicate_drop():
    """Claim with seq < watermark is silently dropped (already emitted)."""
    buf = ReorderBuffer(agent_id="agent-1")

    # Emit claims 0, 1
    claim0 = ClaimSequence("agent-1", 0, "task/a", time.time())
    buf.add_claim(claim0)  # watermark → 1
    claim1 = ClaimSequence("agent-1", 1, "task/b", time.time())
    buf.add_claim(claim1)  # watermark → 2

    # Try to re-emit claim 0 (seq 0 < watermark 2)
    dup_claim0 = ClaimSequence("agent-1", 0, "task/a-dup", time.time())
    emitted, watermark = buf.add_claim(dup_claim0)
    assert len(emitted) == 0  # Not re-emitted
    assert watermark == 2  # Watermark unchanged


def test_reorder_buffer_status():
    """status() returns correct dict representation."""
    buf = ReorderBuffer(agent_id="agent-1")

    # Add some buffered claims
    buf.buffer[3] = ClaimSequence("agent-1", 3, "task/c", time.time())
    buf.buffer[5] = ClaimSequence("agent-1", 5, "task/e", time.time())
    buf.watermark = 2

    status = buf.status()
    assert status["agent_id"] == "agent-1"
    assert status["watermark"] == 2
    assert status["buffered_count"] == 2
    assert status["buffered_seqs"] == [3, 5]


def test_reorder_buffer_drain():
    """drain() emits all buffered claims and advances watermark."""
    buf = ReorderBuffer(agent_id="agent-1")

    # Manually set up buffer state (watermark 2, buffered 3, 5)
    buf.watermark = 2
    buf.buffer[3] = ClaimSequence("agent-1", 3, "task/c", time.time())
    buf.buffer[5] = ClaimSequence("agent-1", 5, "task/e", time.time())

    emitted, new_watermark = buf.drain()
    assert len(emitted) == 2
    assert emitted[0].claim_num == 3
    assert emitted[1].claim_num == 5
    assert new_watermark == 6  # max(5) + 1
    assert len(buf.buffer) == 0


def test_reorder_buffer_drain_empty():
    """drain() on empty buffer returns empty list."""
    buf = ReorderBuffer(agent_id="agent-1")
    buf.watermark = 5

    emitted, new_watermark = buf.drain()
    assert len(emitted) == 0
    assert new_watermark == 5


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests with GossipBus
# ─────────────────────────────────────────────────────────────────────────────


async def test_claim_with_seq_sequential(make_bus, capsys):
    """claim with --seq for sequential claims (no gaps)."""
    bus = await make_bus()

    await _claim_with_seq(bus, "agent-1", 0, "task/a", "first claim")
    await _claim_with_seq(bus, "agent-1", 1, "task/b", "second claim")

    captured = capsys.readouterr()
    assert "watermark now 1" in captured.out
    assert "watermark now 2" in captured.out
    assert "emitted 1 claim(s)" in captured.out


async def test_claim_with_seq_gap_then_fill(make_bus, capsys):
    """claim with --seq creates gap, then fills it."""
    bus = await make_bus()

    # Emit claim 0, then claim 2 (gap at 1)
    await _claim_with_seq(bus, "agent-1", 0, "task/a", "")
    await _claim_with_seq(bus, "agent-1", 2, "task/c", "")

    captured = capsys.readouterr()
    assert "watermark now 1" in captured.out
    assert "buffered (seq 2)" in captured.out
    assert "buffered seqs: [2]" in captured.out

    # Fill the gap with claim 1
    await _claim_with_seq(bus, "agent-1", 1, "task/b", "")

    captured = capsys.readouterr()
    assert "watermark now 3" in captured.out
    assert "emitted 2 claim(s)" in captured.out


async def test_get_reorder_buffers_from_bus(make_bus):
    """_get_reorder_buffers reconstructs buffer state from GossipBus events."""
    bus = await make_bus()

    # Emit some claims
    await _claim_with_seq(bus, "agent-1", 0, "task/a", "")
    await _claim_with_seq(bus, "agent-1", 2, "task/c", "")
    await _claim_with_seq(bus, "agent-2", 0, "task/x", "")

    buffers = await _get_reorder_buffers(bus)

    assert "agent-1" in buffers
    assert "agent-2" in buffers

    # agent-1 should have claim 2 buffered
    buf1 = buffers["agent-1"]
    assert buf1.watermark == 1
    assert 2 in buf1.buffer

    # agent-2 should have no buffer
    buf2 = buffers["agent-2"]
    assert buf2.watermark == 1
    assert len(buf2.buffer) == 0


async def test_buffer_status_command(make_bus, capsys):
    """buffer status command shows status for all agents."""
    bus = await make_bus()

    await _claim_with_seq(bus, "agent-1", 0, "task/a", "")
    await _claim_with_seq(bus, "agent-1", 3, "task/d", "")
    await _claim_with_seq(bus, "agent-2", 0, "task/x", "")

    await _buffer_status(bus)

    captured = capsys.readouterr()
    assert "Reorder Buffer Status" in captured.out
    assert "agent-1" in captured.out
    assert "watermark=1" in captured.out
    assert "buffered=1" in captured.out


async def test_buffer_status_filtered(make_bus, capsys):
    """buffer status --agent filters to specific agent."""
    bus = await make_bus()

    await _claim_with_seq(bus, "agent-1", 0, "task/a", "")
    await _claim_with_seq(bus, "agent-1", 3, "task/d", "")
    await _claim_with_seq(bus, "agent-2", 0, "task/x", "")

    capsys.readouterr()  # Clear previous output

    await _buffer_status(bus, agent_filter="agent-1")

    captured = capsys.readouterr()
    # The status output should have agent-1 but not agent-2
    # (Note: agent-2 may appear in earlier claim outputs, but not in the status section)
    assert "agent-1:" in captured.out  # status section for agent-1
    status_section = captured.out[captured.out.find("=== Reorder Buffer Status ==="):]
    assert "agent-1" in status_section
    assert "agent-2" not in status_section


async def test_buffer_drain_command(make_bus, capsys):
    """buffer drain command force-emits all buffered claims."""
    bus = await make_bus()

    await _claim_with_seq(bus, "agent-1", 0, "task/a", "")
    await _claim_with_seq(bus, "agent-1", 3, "task/d", "")
    await _claim_with_seq(bus, "agent-1", 5, "task/f", "")

    await _buffer_drain(bus, "agent-1")

    captured = capsys.readouterr()
    assert "drained: agent-1" in captured.out
    assert "2 claims" in captured.out
    assert "seq 3: task/d" in captured.out
    assert "seq 5: task/f" in captured.out


async def test_buffer_drain_empty_buffer(make_bus, capsys):
    """buffer drain on non-existent agent reports error."""
    bus = await make_bus()

    await _buffer_drain(bus, "agent-nonexistent")

    captured = capsys.readouterr()
    assert "ERROR: no buffer state" in captured.err


# ─────────────────────────────────────────────────────────────────────────────
# Complex Scenarios
# ─────────────────────────────────────────────────────────────────────────────


def test_reorder_buffer_many_interleaved_gaps():
    """Complex scenario: many gaps filled in random order."""
    buf = ReorderBuffer(agent_id="agent-stress")

    # Add claims in order: 0, 2, 5, 1, 4, 3, 6
    # Trace through:
    # 0: seq=0, watermark=0 → emit 0, watermark→1, count=1
    # 2: seq=2, watermark=1 → buffer, watermark=1, count=0
    # 5: seq=5, watermark=1 → buffer, watermark=1, count=0
    # 1: seq=1, watermark=1 → emit 1, check 2 (yes) emit 2, check 3 (no), watermark→3, count=2
    # 4: seq=4, watermark=3 → buffer, watermark=3, count=0
    # 3: seq=3, watermark=3 → emit 3, check 4 (yes) emit 4, check 5 (yes) emit 5, check 6 (no), watermark→6, count=3
    # 6: seq=6, watermark=6 → emit 6, watermark→7, count=1
    claims = [
        ClaimSequence("agent-stress", 0, "task/0", time.time()),
        ClaimSequence("agent-stress", 2, "task/2", time.time()),
        ClaimSequence("agent-stress", 5, "task/5", time.time()),
        ClaimSequence("agent-stress", 1, "task/1", time.time()),
        ClaimSequence("agent-stress", 4, "task/4", time.time()),
        ClaimSequence("agent-stress", 3, "task/3", time.time()),
        ClaimSequence("agent-stress", 6, "task/6", time.time()),
    ]

    expected_watermarks = [1, 1, 1, 3, 3, 6, 7]  # Watermark after each claim
    emitted_counts = [1, 0, 0, 2, 0, 3, 1]

    for i, claim in enumerate(claims):
        emitted, watermark = buf.add_claim(claim)
        assert len(emitted) == emitted_counts[i], f"Claim {i}: expected {emitted_counts[i]} emitted, got {len(emitted)}"
        assert watermark == expected_watermarks[i], f"Claim {i}: expected watermark {expected_watermarks[i]}, got {watermark}"

    # All claims should be emitted, no buffer left
    assert len(buf.buffer) == 0
    assert buf.watermark == 7


def test_reorder_buffer_wrap_around_high_seq_nums():
    """Buffer handles large sequence numbers correctly."""
    buf = ReorderBuffer(agent_id="agent-large")

    # Skip ahead to seq 1000
    claim1000 = ClaimSequence("agent-large", 1000, "task/1000", time.time())
    emitted, watermark = buf.add_claim(claim1000)
    assert len(emitted) == 0  # Buffered (watermark was 0)
    assert watermark == 0

    # Add seq 999
    claim999 = ClaimSequence("agent-large", 999, "task/999", time.time())
    emitted, watermark = buf.add_claim(claim999)
    assert len(emitted) == 0  # Still gap at 0-998
    assert watermark == 0

    # Fill the gap with intermediate claim
    claim500 = ClaimSequence("agent-large", 500, "task/500", time.time())
    emitted, watermark = buf.add_claim(claim500)
    assert len(emitted) == 0  # Still gaps
    assert watermark == 0

    # Fill gap at 0 (watermark-matching)
    # This emits 0, then checks buffer for 1 (not found), stops
    claim0 = ClaimSequence("agent-large", 0, "task/0", time.time())
    emitted, watermark = buf.add_claim(claim0)
    # Should emit only 0 and stop at gap (1-499 missing)
    assert len(emitted) == 1
    assert emitted[0].claim_num == 0
    assert watermark == 1

    # Now fill gap at 500
    claim500_retry = ClaimSequence("agent-large", 500, "task/500", time.time())
    emitted, watermark = buf.add_claim(claim500_retry)
    assert len(emitted) == 0  # Still gap at 1-499
    assert watermark == 1
