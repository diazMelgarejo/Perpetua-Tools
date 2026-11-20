"""Pre-generation cleanup cannot prove that a silent worker stopped."""

import asyncio
import os
import sys
import time
from pathlib import Path

import pytest

from orchestrator.coordination.task_queue import (
    latest_task_snapshots,
    queue_add,
    release_captured_queue_claims,
    try_atomic_claim,
)
from orchestrator.coordination.types import ClaimResult
from orchestrator.gossip_bus import GossipBus
from orchestrator.heartbeat_monitor import (
    LIVENESS_STALLED_SEC,
    _release_legacy_claim_atomically,
    cleanup_stale_claims,
    find_agent_heartbeats,
)


@pytest.mark.asyncio
async def test_captured_queue_claim_is_held_without_touching_bus() -> None:
    """An unresponsive worker remains capable of executing its claim."""
    assert await release_captured_queue_claims(None, [{"task_id": "task"}]) == []


@pytest.mark.asyncio
async def test_legacy_claim_is_held_without_touching_bus() -> None:
    """A name and heartbeat do not fence a resumed legacy worker."""
    assert not await _release_legacy_claim_atomically(None, {"task": "task"})


@pytest.mark.asyncio
@pytest.mark.parametrize("contender", ["worker", "replacement"])
async def test_paused_process_cannot_be_reclaimed_by_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, contender: str
) -> None:
    """A silent live process keeps its claim; its later effects remain possible."""
    db_path = tmp_path / "gossip.db"
    effect = tmp_path / "effect"
    bus = GossipBus(str(db_path))
    await bus.init_db()
    await queue_add(bus, "paused", "Phase-1", "NORMAL", "", None)
    task_id = next(iter(await latest_task_snapshots(bus)))
    program = """
import asyncio, sys
from pathlib import Path
from orchestrator.gossip_bus import GossipBus
from orchestrator.coordination.task_queue import queue_claim, queue_complete
async def main():
    bus = GossipBus(sys.argv[1])
    await queue_claim(bus, sys.argv[2], 'worker')
    print('READY', flush=True)
    await asyncio.to_thread(sys.stdin.readline)
    await queue_complete(bus, sys.argv[2], 'worker', 'resumed')
    Path(sys.argv[3]).write_text('effect', encoding='utf-8')
asyncio.run(main())
"""
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join((str(root), str(root / "src")))}
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", program, str(db_path), task_id, str(effect),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, env=env, cwd=str(root),
    )
    assert process.stdout is not None and process.stdin is not None
    try:
        while True:
            line = await asyncio.wait_for(process.stdout.readline(), timeout=10)
            assert line, "worker exited before acquiring the claim"
            if line.strip() == b"READY":
                break
        shifted = time.time() + LIVENESS_STALLED_SEC + 60
        monkeypatch.setattr(time, "time", lambda: shifted)
        assert (await find_agent_heartbeats(bus))["worker"]["status"] == "DEAD"
        async with bus.connect() as db:
            before = await (await db.execute("SELECT COUNT(*) FROM gossip")).fetchone()
        assert await cleanup_stale_claims(bus) == []
        assert await try_atomic_claim(bus, task_id, contender) is ClaimResult.LOST_RACE
        async with bus.connect() as db:
            after = await (await db.execute("SELECT COUNT(*) FROM gossip")).fetchone()
            holder = await (await db.execute(
                "SELECT agent_id FROM task_claims WHERE task_id = ?", (task_id,)
            )).fetchone()
        assert before == after
        assert holder == ("worker",)
        process.stdin.write(b"resume\n")
        await process.stdin.drain()
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
        assert process.returncode == 0, stderr.decode()
        assert effect.read_text(encoding="utf-8") == "effect"
        assert (await latest_task_snapshots(bus))[task_id]["status"] == "completed"
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
