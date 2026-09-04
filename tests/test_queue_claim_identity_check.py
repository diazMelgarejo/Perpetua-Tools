"""tests/test_queue_claim_identity_check.py

Regression coverage for the PT_AGENT_ID environment-based identity check
in queue_claim, added for pullrequestreview-5110750810's finding that
required_agent_id was compared only against a caller-supplied CLI
argument with no independent verification.

This is not cryptographic authentication -- no such mechanism exists
anywhere in this codebase (confirmed before adding this check). It is
the strongest signal achievable without building new auth
infrastructure: PT_AGENT_ID, when set, reflects the calling agent's own
launch environment rather than a per-call argument, so these tests
verify it as a defense-in-depth signal, not a security boundary.
"""
from __future__ import annotations

import pytest

from orchestrator.coordination.task_queue import queue_add, queue_claim, latest_task_snapshots
from orchestrator.gossip_bus import GossipBus


@pytest.fixture
async def bus(tmp_path):
    db = str(tmp_path / "test.db")
    b = GossipBus(db)
    await b.init_db()
    return b


async def _add_reserved_task(bus: GossipBus, required_agent_id: str) -> str:
    await queue_add(
        bus, "identity-check-work", "Phase-1", "NORMAL", "", None,
        required_agent_id=required_agent_id,
    )
    snapshots = await latest_task_snapshots(bus)
    return next(iter(snapshots))


async def test_claim_succeeds_when_no_env_var_is_set(bus, monkeypatch):
    monkeypatch.delenv("PT_AGENT_ID", raising=False)
    task_id = await _add_reserved_task(bus, "agent-a")

    result = await queue_claim(bus, task_id, "agent-a")

    assert result is not False


async def test_claim_succeeds_when_env_var_matches_agent_id(bus, monkeypatch):
    monkeypatch.setenv("PT_AGENT_ID", "agent-a")
    task_id = await _add_reserved_task(bus, "agent-a")

    result = await queue_claim(bus, task_id, "agent-a")

    assert result is not False


async def test_claim_rejected_when_env_var_disagrees_with_agent_id(bus, monkeypatch, capsys):
    """The core defense: PT_AGENT_ID=agent-b trying to claim as agent-a
    is rejected, even though agent-a is genuinely the reservation holder --
    this is exactly the impersonation case the review named."""
    monkeypatch.setenv("PT_AGENT_ID", "agent-b")
    task_id = await _add_reserved_task(bus, "agent-a")

    result = await queue_claim(bus, task_id, "agent-a")

    assert result is False
    captured = capsys.readouterr()
    assert "does not match this process's PT_AGENT_ID" in captured.err


async def test_claim_still_rejected_for_genuinely_wrong_reservation(bus, monkeypatch):
    """Regression: the pre-existing reservation-mismatch check must still
    fire when PT_AGENT_ID is unset and the caller simply isn't the
    reserved agent."""
    monkeypatch.delenv("PT_AGENT_ID", raising=False)
    task_id = await _add_reserved_task(bus, "agent-a")

    result = await queue_claim(bus, task_id, "agent-c")

    assert result is False
