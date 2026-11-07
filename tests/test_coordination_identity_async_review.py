"""Identity discovery must not block any asynchronous coordination emit path."""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from orchestrator.coordination import claims, liveness, reorder_buffer, task_queue
from orchestrator.gossip_bus import GossipBus


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["register", "claim", "release", "pulse", "kill", "sequence", "atomic", "queue", "complete", "fail", "abandon"])
async def test_identity_resolution_runs_off_event_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str,
) -> None:
    """Every original identity read is fresh but occurs in a worker thread."""
    loop_thread = threading.get_ident()
    calls: list[int] = []

    def label() -> str:
        """Catch blocking discovery before it can run on the event loop."""
        current = threading.get_ident()
        assert current != loop_thread
        calls.append(current)
        return "ptp-" + "a" * 32

    for module in (claims, liveness, reorder_buffer, task_queue):
        monkeypatch.setattr(module, "current_worktree_label", label)
    monkeypatch.setattr(GossipBus, "schedule_embedding", lambda *args: None)
    bus = GossipBus(str(tmp_path / "events.db"))
    await bus.init_db()
    if operation == "register":
        await claims.register_agent(bus, "actor", "test", "test", "")
    elif operation == "claim":
        await claims.claim_task(bus, "actor", "task", "")
    elif operation == "release":
        await claims.release_task(bus, "actor", "task")
    elif operation == "pulse":
        await liveness._heartbeat_pulse(bus, "actor")
    elif operation == "kill":
        await liveness._heartbeat_kill(bus, "actor", "test")
    elif operation == "sequence":
        await reorder_buffer.claim_with_seq(bus, "actor", 1, "task", "")
    elif operation == "atomic":
        await task_queue.try_atomic_claim(bus, "task", "actor")
    else:
        task = await task_queue.queue_add(bus, "task", "phase", "normal", "", None)
        assert isinstance(task, str)
        await task_queue.queue_claim(bus, task, "actor")
        assert len(calls) == 2  # claim identity AND the successful presence pulse
        if operation == "complete":
            await task_queue.queue_complete(bus, task, "actor", "verified")
        elif operation == "fail":
            await task_queue.queue_fail(bus, task, "actor", "retry")
        elif operation == "abandon":
            for _ in range(4):
                await task_queue.queue_fail(bus, task, "actor", "exhaust")
                state = (await task_queue.latest_task_snapshots(bus))[task]
                if state["status"] == "queued":
                    await task_queue.queue_claim(bus, task, "actor")
    assert calls
