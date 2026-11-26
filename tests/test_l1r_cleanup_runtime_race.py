"""L-1r cleanup runtime race tests: reproducing and verifying the pre-generation
refusal and hold guards for alive-but-silent workers.

References:
- 2026-11-16-authenticated-queue-recovery-synthesis-plan.md (§2, §8 O1)
- QUEUE-FENCING-AND-RECOVERY-CONSOLIDATED-PLAN-2026-11-11.md (§4.3, §7, lines 56-58)
- L-1r contract migration ledger (docs/coordination/l1r-contract-migration-2026-11-20.md)

Tests:
1. Stale worker attempting queue_complete after same-agent-name reclaim is REFUSED.
2. Stale worker attempting queue_fail after same-agent-name reclaim is REFUSED without incrementing retries.
3. Resumed worker attempting complete or fail after release/requeue is REFUSED.
4. Cleanup on an alive-but-silent worker HOLDS the claim without fabricating claimant pulses or resetting retries.
5. Real-process schedule: a paused worker resumed after same-agent-name reclaim is refused and aborts external effects.
6. Real-process schedule: a paused worker during cleanup hold is preserved and completes cleanly upon resume.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

import pytest

from orchestrator.coordination import task_queue
from orchestrator.coordination.task_queue import (
    capture_stale_queue_claims,
    cleanup_stale_queue_claims,
    latest_task_snapshots,
    queue_add,
    queue_complete,
    queue_fail,
    release_captured_queue_claims,
    try_atomic_claim,
)
from orchestrator.coordination.types import ClaimResult, QueuedTaskState
from orchestrator.gossip_bus import GossipBus
from orchestrator.heartbeat_monitor import (
    LIVENESS_STALLED_SEC,
    cleanup_stale_claims,
    find_agent_heartbeats,
)

T_CLAIM_1 = 1000.0
T_CLAIM_2 = 2000.0


@pytest.fixture
async def bus(tmp_path: Path) -> GossipBus:
    """Return an isolated GossipBus for L-1r tests."""
    db_path = tmp_path / "l1r.db"
    instance = GossipBus(str(db_path))
    await instance.init_db()
    return instance


@pytest.fixture
def fake_clock(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Replace time.time with a controllable clock handle."""
    clock = {"now": T_CLAIM_1}
    monkeypatch.setattr(time, "time", lambda: clock["now"])
    return clock


async def _claim_row(bus: GossipBus, task_id: str) -> tuple | None:
    """Fetch (agent_id, claimed_at) directly from task_claims."""
    async with bus.connect() as db:
        cursor = await db.execute(
            "SELECT agent_id, claimed_at FROM task_claims WHERE task_id = ?",
            (task_id,),
        )
        return await cursor.fetchone()


async def _task_event_count(bus: GossipBus, task_id: str, kind: str) -> int:
    """Count heartbeat events of a given kind recorded for task_id."""
    async with bus.connect() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM gossip WHERE event_type = 'heartbeat' "
            "AND json_extract(payload_json, '$.kind') = ? "
            "AND json_extract(payload_json, '$.task_id') = ?",
            (kind, task_id),
        )
        (count,) = await cursor.fetchone()
    return count


# ── Defect / Invariant Tests ──────────────────────────────────────────────────


async def test_stale_worker_refused_on_same_agent_name_reclaim_complete(
    bus: GossipBus, fake_clock: dict
) -> None:
    """O1 race: Worker 1 claims at T1, is paused/silent, task is reclaimed under
    the SAME agent name at T2. Resumed Worker 1 attempts queue_complete with T1;
    must be REFUSED without deleting Worker 2's claim or completing the task."""
    fake_clock["now"] = T_CLAIM_1
    await queue_add(bus, "l1r task", "Phase-1", "NORMAL", "", None)
    snaps = await latest_task_snapshots(bus)
    task_id = next(tid for tid, s in snaps.items() if s.get("task_name") == "l1r task")
    assert await try_atomic_claim(bus, task_id, "worker-1") is ClaimResult.WON
    assert await _claim_row(bus, task_id) == ("worker-1", T_CLAIM_1)

    # Reclaim under same agent name at T2
    fake_clock["now"] = T_CLAIM_2
    async with bus.connect() as db:
        await db.execute(
            "UPDATE task_claims SET claimed_at = ? WHERE task_id = ?",
            (T_CLAIM_2, task_id),
        )
        await db.commit()

    # Stale Worker 1 attempts to complete using its original claim timestamp T1
    result = await queue_complete(
        bus, task_id, "worker-1", "stale complete attempt", expected_claimed_at=T_CLAIM_1
    )
    assert result is False, "stale worker complete must be refused on same-name reclaim"

    # Worker 2's claim row must be intact
    assert await _claim_row(bus, task_id) == ("worker-1", T_CLAIM_2)
    snaps = await latest_task_snapshots(bus)
    assert snaps[task_id]["status"] == QueuedTaskState.CLAIMED.value
    assert await _task_event_count(bus, task_id, "task_complete") == 0

    # Worker 2 with matching timestamp completes successfully
    valid_result = await queue_complete(
        bus, task_id, "worker-1", "valid complete", expected_claimed_at=T_CLAIM_2
    )
    assert valid_result is not False
    assert await _claim_row(bus, task_id) is None
    snaps = await latest_task_snapshots(bus)
    assert snaps[task_id]["status"] == QueuedTaskState.COMPLETED.value
    assert await _task_event_count(bus, task_id, "task_complete") == 1


async def test_stale_worker_refused_on_same_agent_name_reclaim_fail(
    bus: GossipBus, fake_clock: dict
) -> None:
    """O1 race: Worker 1 attempts queue_fail after same-agent-name reclaim.
    Must be REFUSED: retry_count is not incremented, task is not requeued,
    and Worker 2's claim row is preserved."""
    fake_clock["now"] = T_CLAIM_1
    await queue_add(bus, "l1r fail task", "Phase-1", "NORMAL", "", None)
    snaps = await latest_task_snapshots(bus)
    task_id = next(tid for tid, s in snaps.items() if s.get("task_name") == "l1r fail task")
    assert await try_atomic_claim(bus, task_id, "worker-1") is ClaimResult.WON

    # Reclaim at T2
    fake_clock["now"] = T_CLAIM_2
    async with bus.connect() as db:
        await db.execute(
            "UPDATE task_claims SET claimed_at = ? WHERE task_id = ?",
            (T_CLAIM_2, task_id),
        )
        await db.commit()

    # Stale worker attempts queue_fail with T1
    result = await queue_fail(
        bus, task_id, "worker-1", "stale fail attempt", expected_claimed_at=T_CLAIM_1
    )
    assert result is False, "stale worker fail must be refused on same-name reclaim"

    # Claim row and task state remain intact
    assert await _claim_row(bus, task_id) == ("worker-1", T_CLAIM_2)
    snaps = await latest_task_snapshots(bus)
    assert snaps[task_id]["status"] == QueuedTaskState.CLAIMED.value
    assert snaps[task_id].get("retry_count", 0) == 0
    assert await _task_event_count(bus, task_id, "task_failed") == 0


async def test_resumed_worker_refused_when_claim_released_or_requeued(
    bus: GossipBus, fake_clock: dict
) -> None:
    """Resumed worker attempting complete or fail on a task no longer claimed
    is refused immediately."""
    fake_clock["now"] = T_CLAIM_1
    await queue_add(bus, "released task", "Phase-1", "NORMAL", "", None)
    snaps = await latest_task_snapshots(bus)
    task_id = next(tid for tid, s in snaps.items() if s.get("task_name") == "released task")
    assert await try_atomic_claim(bus, task_id, "worker-1") is ClaimResult.WON

    # Simulate release/requeue
    async with bus.connect() as db:
        await db.execute("DELETE FROM task_claims WHERE task_id = ?", (task_id,))
        await db.commit()
    await bus.emit("heartbeat", {
        "kind": "task_failed",
        "task_id": task_id,
        "status": QueuedTaskState.QUEUED.value,
        "retry_count": 1,
        "max_retries": 3,
        "assigned_agent": None,
    })

    # Resumed worker tries complete
    assert await queue_complete(
        bus, task_id, "worker-1", "late", expected_claimed_at=T_CLAIM_1
    ) is False
    # Resumed worker tries fail
    assert await queue_fail(
        bus, task_id, "worker-1", "late", expected_claimed_at=T_CLAIM_1
    ) is False
    assert await _task_event_count(bus, task_id, "task_complete") == 0


async def test_cleanup_holds_silent_worker_claim_preventing_reclaim(
    bus: GossipBus, fake_clock: dict
) -> None:
    """Silence past DEAD threshold does not authorize claim release.
    Cleanup returns [] (held), preventing contenders or same-name reclaims."""
    fake_clock["now"] = T_CLAIM_1
    await bus.emit("heartbeat", {
        "kind": "agent_register", "agent_id": "silent-worker", "agent_type": "worker"
    })
    await queue_add(bus, "silent task", "Phase-1", "NORMAL", "", None)
    snaps = await latest_task_snapshots(bus)
    task_id = next(tid for tid, s in snaps.items() if s.get("task_name") == "silent task")
    assert await try_atomic_claim(bus, task_id, "silent-worker") is ClaimResult.WON

    # Advance time past DEAD threshold
    t_dead = T_CLAIM_1 + LIVENESS_STALLED_SEC + 100.0
    fake_clock["now"] = t_dead

    agents = await find_agent_heartbeats(bus)
    assert agents["silent-worker"]["status"] == "DEAD"

    # Cleanup must hold the claim
    released = await cleanup_stale_claims(bus)
    assert released == [], "pre-generation cleanup must hold dead-classified claims"

    # Contender cannot take the claim
    assert await try_atomic_claim(bus, task_id, "contender") is ClaimResult.LOST_RACE
    # Same name cannot take a fresh claim over the existing row
    assert await try_atomic_claim(bus, task_id, "silent-worker") is ClaimResult.LOST_RACE

    # Row is still held by original worker
    assert await _claim_row(bus, task_id) == ("silent-worker", T_CLAIM_1)


# ── Real-Process Schedule Tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_real_process_resumed_worker_refused_after_same_name_reclaim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real process schedule: a worker claims a task, pauses, the task is
    reclaimed under the same agent name, worker resumes and is REFUSED completion,
    preventing external side effects."""
    db_path = tmp_path / "gossip_proc.db"
    effect_file = tmp_path / "external_effect.txt"
    bus = GossipBus(str(db_path))
    await bus.init_db()
    await queue_add(bus, "proc task", "Phase-1", "NORMAL", "", None)
    snaps = await latest_task_snapshots(bus)
    task_id = next(iter(snaps))

    # Worker program: claims, reads claimed_at from task_claims, prints READY,
    # pauses for stdin, attempts queue_complete with expected_claimed_at,
    # and only writes effect_file if queue_complete did not return False.
    worker_script = """
import asyncio, sys
from pathlib import Path
from orchestrator.gossip_bus import GossipBus
from orchestrator.coordination.task_queue import queue_claim, queue_complete

async def main():
    db_path, task_id, effect_path = sys.argv[1], sys.argv[2], sys.argv[3]
    bus = GossipBus(db_path)
    await queue_claim(bus, task_id, "worker-proc")
    async with bus.connect() as db:
        cursor = await db.execute("SELECT claimed_at FROM task_claims WHERE task_id = ?", (task_id,))
        (claimed_at,) = await cursor.fetchone()
    print(f"READY:{claimed_at}", flush=True)
    await asyncio.to_thread(sys.stdin.readline)
    res = await queue_complete(bus, task_id, "worker-proc", "resumed", expected_claimed_at=claimed_at)
    if res is not False:
        Path(effect_path).write_text("COMMITTED", encoding="utf-8")
        sys.exit(0)
    else:
        sys.exit(2)  # Refused exit code

asyncio.run(main())
"""
    root = Path(__file__).resolve().parent.parent
    env = {**os.environ, "PYTHONPATH": str(root)}
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-c", worker_script, str(db_path), task_id, str(effect_file),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, env=env, cwd=str(root),
    )
    assert proc.stdout is not None and proc.stdin is not None

    try:
        while True:
            ready_line = await asyncio.wait_for(proc.stdout.readline(), timeout=10)
            assert ready_line, "worker process exited unexpectedly"
            if ready_line.startswith(b"READY:"):
                break
        orig_claimed_at = float(ready_line.decode().strip().split(":")[1])

        # Simulate same-name reclaim by advancing claimed_at in task_claims
        new_claimed_at = orig_claimed_at + 1000.0
        async with bus.connect() as db:
            await db.execute(
                "UPDATE task_claims SET claimed_at = ? WHERE task_id = ?",
                (new_claimed_at, task_id),
            )
            await db.commit()

        # Resume the paused worker
        proc.stdin.write(b"resume\n")
        await proc.stdin.drain()

        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        assert proc.returncode == 2, f"Worker should have exited with code 2 (refused), got {proc.returncode}. stderr: {stderr.decode()}"
        assert not effect_file.exists(), "External effect must NOT be committed by refused worker"

        # The claim row still belongs to the second claimant
        assert await _claim_row(bus, task_id) == ("worker-proc", new_claimed_at)
        snaps = await latest_task_snapshots(bus)
        assert snaps[task_id]["status"] == QueuedTaskState.CLAIMED.value
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()


@pytest.mark.asyncio
async def test_real_process_paused_worker_silent_cleanup_holds_and_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real process schedule: a worker claims a task and pauses. Parent sees
    it scored DEAD and runs cleanup. Cleanup HOLDS the claim (pre-generation
    refusal/hold guard); contender fails to claim. When paused worker resumes,
    it completes cleanly and writes its external effect."""
    db_path = tmp_path / "gossip_proc_hold.db"
    effect_file = tmp_path / "external_effect_hold.txt"
    bus = GossipBus(str(db_path))
    await bus.init_db()
    await queue_add(bus, "proc hold task", "Phase-1", "NORMAL", "", None)
    snaps = await latest_task_snapshots(bus)
    task_id = next(iter(snaps))

    worker_script = """
import asyncio, sys
from pathlib import Path
from orchestrator.gossip_bus import GossipBus
from orchestrator.coordination.task_queue import queue_claim, queue_complete

async def main():
    db_path, task_id, effect_path = sys.argv[1], sys.argv[2], sys.argv[3]
    bus = GossipBus(db_path)
    await queue_claim(bus, task_id, "worker-hold")
    async with bus.connect() as db:
        cursor = await db.execute("SELECT claimed_at FROM task_claims WHERE task_id = ?", (task_id,))
        (claimed_at,) = await cursor.fetchone()
    print(f"READY:{claimed_at}", flush=True)
    await asyncio.to_thread(sys.stdin.readline)
    res = await queue_complete(bus, task_id, "worker-hold", "resumed clean", expected_claimed_at=claimed_at)
    if res is not False:
        Path(effect_path).write_text("COMMITTED", encoding="utf-8")
        sys.exit(0)
    else:
        sys.exit(2)

asyncio.run(main())
"""
    root = Path(__file__).resolve().parent.parent
    env = {**os.environ, "PYTHONPATH": str(root)}
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-c", worker_script, str(db_path), task_id, str(effect_file),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, env=env, cwd=str(root),
    )
    assert proc.stdout is not None and proc.stdin is not None

    try:
        while True:
            ready_line = await asyncio.wait_for(proc.stdout.readline(), timeout=10)
            assert ready_line, "worker process exited unexpectedly"
            if ready_line.startswith(b"READY:"):
                break
        claimed_at = float(ready_line.decode().strip().split(":")[1])

        # Shift parent clock past DEAD threshold
        shifted_now = time.time() + LIVENESS_STALLED_SEC + 60.0
        monkeypatch.setattr(time, "time", lambda: shifted_now)

        agents = await find_agent_heartbeats(bus)
        assert agents["worker-hold"]["status"] == "DEAD"

        # Cleanup must hold the claim
        released = await cleanup_stale_claims(bus)
        assert released == []

        # Contender cannot claim the held task
        assert await try_atomic_claim(bus, task_id, "contender") is ClaimResult.LOST_RACE

        # Resume the worker process
        proc.stdin.write(b"resume\n")
        await proc.stdin.drain()

        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        assert proc.returncode == 0, f"Worker exited with code {proc.returncode}, stderr: {stderr.decode()}"
        assert effect_file.exists()
        assert effect_file.read_text(encoding="utf-8") == "COMMITTED"

        # Verify task is completed and claim row deleted
        assert await _claim_row(bus, task_id) is None
        snaps = await latest_task_snapshots(bus)
        assert snaps[task_id]["status"] == QueuedTaskState.COMPLETED.value
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
