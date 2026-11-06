"""Concurrency and replication coverage for v1 coordination (closure row C5).

Evidence labels used below:

* SIMULATED-LOCAL: one host, temporary SQLite files, in-process asyncio or
  local OS processes. Peers are respx mocks, not network hosts.
* Nothing here is live LAN, crash or multi-host evidence. That evidence is
  owner-held and must be recorded separately.

The race assertions follow the master plan's revised scope: exactly one
committed winner and a valid outcome vocabulary, never a fixed distribution of
loser outcomes across timing schedules.
"""
from __future__ import annotations

import asyncio
import multiprocessing
import random
import sqlite3
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import aiosqlite
import httpx
import pytest
import respx

import orchestrator.coordination.task_queue as task_queue
from orchestrator.coordination.reorder_buffer import get_reorder_buffers
from orchestrator.coordination.task_queue import (
    queue_add,
    queue_claim,
    latest_task_snapshots,
    release_claim_with_event,
    try_atomic_claim,
)
from orchestrator.coordination.types import (
    ClaimResult,
    ClaimSequence,
    ReleaseResult,
    ReorderBuffer,
)
from orchestrator.gossip_bus import (
    GossipBus,
    GossipBusError,
    cancel_pending_embeddings_for_current_loop,
)
from orchestrator.heartbeat_monitor import find_open_claims
from orchestrator.lan_gossip_bridge import LanGossipBridge

WORKERS = 10
_CLAIM_VOCABULARY = {ClaimResult.WON, ClaimResult.LOST_RACE, ClaimResult.CONTENTION}


@pytest.fixture
async def bus(tmp_path: Path) -> GossipBus:
    """Return a freshly initialized, isolated GossipBus."""
    instance = GossipBus(str(tmp_path / "c5.db"))
    await instance.init_db()
    await task_queue.ensure_claims_table(instance)
    return instance


async def _claim_rows(bus: GossipBus, task_id: str) -> list[str]:
    """Return holders of task_claims rows for ``task_id``."""
    async with bus.connect() as db:
        cursor = await db.execute("SELECT agent_id FROM task_claims WHERE task_id = ?", (task_id,))
        return [row[0] for row in await cursor.fetchall()]


async def _claim_events(bus: GossipBus, task_id: str) -> list[dict]:
    """Return committed task_claim events for ``task_id``."""
    async with bus.connect() as db:
        cursor = await db.execute(
            "SELECT payload_json FROM gossip WHERE json_extract(payload_json, '$.kind') = "
            "'task_claim' AND json_extract(payload_json, '$.task_id') = ?",
            (task_id,),
        )
        import json

        return [json.loads(row[0]) for row in await cursor.fetchall()]


# ── Ten-worker claim race ───────────────────────────────────────────────────


async def test_ten_async_workers_commit_exactly_one_claim(bus: GossipBus) -> None:
    """SIMULATED-LOCAL: ten coroutines, ten connections, one committed winner."""
    task_id = "race-10-async"
    workers = [GossipBus(bus.db_path) for _ in range(WORKERS)]
    results = await asyncio.gather(
        *(try_atomic_claim(w, task_id, f"agent-{i}") for i, w in enumerate(workers))
    )
    assert set(results) <= _CLAIM_VOCABULARY
    assert results.count(ClaimResult.WON) == 1
    winner = f"agent-{results.index(ClaimResult.WON)}"
    assert await _claim_rows(bus, task_id) == [winner]
    events = await _claim_events(bus, task_id)
    assert [e["assigned_agent"] for e in events] == [winner]


def _process_claim(db_path: str, task_id: str, agent_id: str, barrier: object, out: object) -> None:
    """Child process body: wait at the barrier, then attempt one atomic claim."""
    try:
        barrier.wait(timeout=30)
        result = asyncio.run(try_atomic_claim(GossipBus(db_path), task_id, agent_id))
        out.put((agent_id, result.value))
    except (GossipBusError, threading.BrokenBarrierError) as exc:  # recorded, not hidden
        out.put((agent_id, f"error:{type(exc).__name__}"))


def _run_claim_processes(procs: list, out: object) -> dict:
    """Collect worker results and always reap every successfully started process."""
    started = []
    try:
        for proc in procs:
            proc.start()
            started.append(proc)
        results = dict(out.get(timeout=120) for _ in started)
        for proc in started:
            proc.join(timeout=30)
            assert proc.exitcode == 0
        return results
    finally:
        for proc in started:
            if proc.is_alive():
                proc.terminate()
        for proc in started:
            proc.join(timeout=5)
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=5)
        out.close()
        out.cancel_join_thread()


def test_process_claim_reports_broken_barrier() -> None:
    """A broken worker barrier reports a result instead of leaving the parent waiting."""
    barrier = MagicMock()
    barrier.wait.side_effect = threading.BrokenBarrierError
    out = MagicMock()
    _process_claim("unused", "task", "agent", barrier, out)
    out.put.assert_called_once_with(("agent", "error:BrokenBarrierError"))


@pytest.mark.parametrize("failure", ["start", "result", "exit"])
def test_claim_processes_cleanup_on_failure(failure: str) -> None:
    """Started workers are terminated and reaped on each parent failure path."""
    first, second = MagicMock(), MagicMock()
    first.is_alive.side_effect = [True, True]
    first.exitcode = 1 if failure == "exit" else 0
    second.is_alive.return_value = True
    second.exitcode = 0
    out = MagicMock()
    out.get.side_effect = [("a", "won"), ("b", "lost_race")]
    if failure == "start":
        second.start.side_effect = RuntimeError("start failed")
    elif failure == "result":
        out.get.side_effect = RuntimeError("result failed")
    with pytest.raises((RuntimeError, AssertionError)):
        _run_claim_processes([first, second], out)
    first.terminate.assert_called_once()
    first.kill.assert_called_once()
    assert first.join.call_count >= 2
    if failure != "start":
        second.terminate.assert_called_once()
        second.kill.assert_called_once()
    out.close.assert_called_once()
    out.cancel_join_thread.assert_called_once()


def test_ten_os_processes_commit_exactly_one_claim(tmp_path: Path) -> None:
    """SIMULATED-LOCAL: ten local OS processes released by one barrier."""
    db_path = str(tmp_path / "c5-processes.db")
    seed = GossipBus(db_path)
    asyncio.run(seed.init_db())
    asyncio.run(task_queue.ensure_claims_table(seed))
    ctx = multiprocessing.get_context("spawn")
    barrier = ctx.Barrier(WORKERS)
    out = ctx.Queue()
    procs = [
        ctx.Process(target=_process_claim, args=(db_path, "race-10-proc", f"p-{i}", barrier, out))
        for i in range(WORKERS)
    ]
    results = _run_claim_processes(procs, out)
    values = list(results.values())
    assert set(values) <= {r.value for r in _CLAIM_VOCABULARY}, values
    assert values.count(ClaimResult.WON.value) == 1
    winner = next(a for a, v in results.items() if v == ClaimResult.WON.value)
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT agent_id FROM task_claims WHERE task_id = 'race-10-proc'"
        ).fetchall()
        events = conn.execute(
            "SELECT COUNT(*) FROM gossip WHERE json_extract(payload_json, '$.kind') = 'task_claim'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert rows == [(winner,)]
    assert events == 1


async def test_ten_cli_level_workers_report_one_success(
    bus: GossipBus, capsys: pytest.CaptureFixture[str]
) -> None:
    """SIMULATED-LOCAL: queue_claim prints one success; losers get a known error."""
    await queue_add(bus, "contested", "Phase-1", "NORMAL", "", None)
    task_id = next(iter(await latest_task_snapshots(bus)))
    outcomes = await asyncio.gather(*(queue_claim(bus, task_id, f"w-{i}") for i in range(WORKERS)))
    captured = capsys.readouterr()
    assert outcomes.count(None) == 1
    assert outcomes.count(False) == WORKERS - 1
    assert captured.out.count("claimed:") == 1
    allowed = ("already claimed by", "another agent won the race", "remained busy")
    errors = [line for line in captured.err.splitlines() if line.startswith("ERROR")]
    assert len(errors) == WORKERS - 1
    assert all(any(token in line for token in allowed) for line in errors)
    assert len(await _claim_rows(bus, task_id)) == 1


# ── Bounded lock handling ───────────────────────────────────────────────────


def _short_timeout_connect(db_path: str, counter: dict[str, int]):
    """Return a connect() replacement with a 50 ms busy timeout that counts calls."""
    def connect():
        """Open a short-timeout connection and count each retry."""
        counter["n"] += 1
        return aiosqlite.connect(db_path, timeout=0.05)
    return connect


async def test_claim_under_held_write_lock_returns_contention_after_bounded_retries(
    bus: GossipBus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A held lock yields CONTENTION after exactly _LOCK_RETRIES attempts."""
    counter = {"n": 0}
    monkeypatch.setattr(bus, "connect", _short_timeout_connect(bus.db_path, counter))
    blocker = sqlite3.connect(bus.db_path, timeout=0)
    blocker.execute("BEGIN EXCLUSIVE")
    try:
        started = time.monotonic()
        result = await try_atomic_claim(bus, "locked-task", "agent-a")
        elapsed = time.monotonic() - started
    finally:
        blocker.rollback()
        blocker.close()
    assert result == ClaimResult.CONTENTION
    assert counter["n"] == task_queue._LOCK_RETRIES
    assert elapsed < 5.0
    assert await _claim_rows(bus, "locked-task") == []
    assert await _claim_events(bus, "locked-task") == []


async def test_release_under_held_write_lock_keeps_the_claim(
    bus: GossipBus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Release contention leaves both the row and the event log unchanged."""
    assert await try_atomic_claim(bus, "held", "agent-a") == ClaimResult.WON
    # The claim scheduled a background embedding that also opens a connection.
    await cancel_pending_embeddings_for_current_loop()
    async with bus.connect() as db:
        cursor = await db.execute("SELECT * FROM gossip ORDER BY id")
        before = await cursor.fetchall()
    counter = {"n": 0}
    monkeypatch.setattr(bus, "connect", _short_timeout_connect(bus.db_path, counter))
    blocker = sqlite3.connect(bus.db_path, timeout=0)
    blocker.execute("BEGIN EXCLUSIVE")
    try:
        result = await release_claim_with_event(
            bus, "held", "heartbeat", {"kind": "task_complete", "task_id": "held"},
            expected_agent_id="agent-a",
        )
    finally:
        blocker.rollback()
        blocker.close()
    assert result == ReleaseResult.CONTENTION
    assert counter["n"] == task_queue._LOCK_RETRIES
    monkeypatch.undo()
    assert await _claim_rows(bus, "held") == ["agent-a"]
    async with bus.connect() as db:
        cursor = await db.execute("SELECT * FROM gossip ORDER BY id")
        assert await cursor.fetchall() == before


# ── Duplicate and reordered events ──────────────────────────────────────────


async def test_duplicate_event_uuid_is_stored_once(bus: GossipBus) -> None:
    """Re-delivery of the same event UUID is idempotent and not re-acknowledged as new."""
    first = await bus.emit("heartbeat", {"kind": "agent_pulse", "agent_id": "a"}, event_uuid="u-1")
    second = await bus.emit("heartbeat", {"kind": "agent_pulse", "agent_id": "a"}, event_uuid="u-1")
    forwarded = await bus.emit("heartbeat", {"kind": "agent_pulse", "agent_id": "a", "_gossip_uuid": "u-1"})
    assert first == second == forwarded == "u-1"
    async with bus.connect() as db:
        _row_id, _uuid, _payload, inserted = await bus.insert_event(
            db, "heartbeat", {"kind": "agent_pulse"}, event_uuid="u-1"
        )
        cursor = await db.execute("SELECT COUNT(*) FROM gossip WHERE event_uuid = 'u-1'")
        (count,) = await cursor.fetchone()
    assert inserted is False
    assert count == 1


async def test_shuffled_duplicated_replay_converges_on_the_same_event_set(
    tmp_path: Path,
) -> None:
    """No event is dropped or duplicated when a peer receives a shuffled replay."""
    source = GossipBus(str(tmp_path / "source.db"))
    replica = GossipBus(str(tmp_path / "replica.db"))
    await source.init_db()
    await replica.init_db()
    for i in range(40):
        await source.emit("heartbeat", {"kind": "agent_pulse", "agent_id": f"a-{i % 4}", "seq": i})
    events = await source.tail(limit=1000)
    deliveries = events + events[::3]  # every third event delivered twice
    random.Random(7).shuffle(deliveries)
    for event in deliveries:
        await replica.emit(event["event_type"], event["payload"], event_uuid=event["uuid"])
    replica_events = await replica.tail(limit=1000)
    assert sorted(e["uuid"] for e in replica_events) == sorted(e["uuid"] for e in events)


async def test_reordered_claim_release_replay_diverges_on_a_replica(tmp_path: Path) -> None:
    """Characterization: v1 folds by local arrival order, so reordering changes state.

    The source sees claim-then-release (closed). A replica that receives the
    release first and the claim second reports the claim as open. Gossip
    therefore cannot carry claim authority; doc 68 keeps authority in the v2
    Controller's transaction, not in replicated events.
    """
    source = GossipBus(str(tmp_path / "source.db"))
    replica = GossipBus(str(tmp_path / "replica.db"))
    await source.init_db()
    await replica.init_db()
    await source.emit("heartbeat", {"kind": "agent_claim", "agent_id": "a", "task": "t"})
    await source.emit("heartbeat", {"kind": "agent_release", "agent_id": "a", "task": "t"})
    assert await find_open_claims(source) == []
    claim, release = sorted(await source.tail(limit=10), key=lambda e: e["row_id"])
    for event in (release, claim):
        await replica.emit(event["event_type"], event["payload"], event_uuid=event["uuid"])
    assert [c["task"] for c in await find_open_claims(replica)] == ["t"]


# ── No dropped or falsely acknowledged events ───────────────────────────────


async def test_bridge_acknowledges_local_durability_only(tmp_path: Path) -> None:
    """A returned UUID means the local row committed; peer failures do not change it."""
    bridge = LanGossipBridge(
        db_path=str(tmp_path / "bridge.db"),
        peers=["http://peer-500.example:8000", "http://peer-down.example:8000"],
        timeout=0.1,
    )
    await bridge.init_db()
    with respx.mock(assert_all_called=True) as router:
        router.post("http://peer-500.example:8000/gossip/emit").mock(
            return_value=httpx.Response(500)
        )
        router.post("http://peer-down.example:8000/gossip/emit").mock(
            side_effect=httpx.ConnectError("down")
        )
        event_uuid = await bridge.emit("heartbeat", {"kind": "agent_pulse", "agent_id": "a"})
    assert isinstance(event_uuid, str)
    local = await bridge.local.tail(limit=10)
    assert [e["uuid"] for e in local] == [event_uuid]


async def test_bridge_never_forwards_or_acknowledges_a_failed_local_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If local persistence fails, the caller gets an error and no peer is contacted."""
    bridge = LanGossipBridge(
        db_path=str(tmp_path / "bridge.db"), peers=["http://peer.example:8000"], timeout=0.1
    )
    await bridge.init_db()

    async def failing_emit(*_args: object, **_kwargs: object) -> str:
        """Refuse source persistence before the bridge contacts any peer."""
        raise GossipBusError("injected local failure")

    monkeypatch.setattr(bridge.local, "emit", failing_emit)
    with respx.mock(assert_all_called=False) as router:
        route = router.post("http://peer.example:8000/gossip/emit").mock(
            return_value=httpx.Response(200)
        )
        with pytest.raises(GossipBusError):
            await bridge.emit("heartbeat", {"kind": "agent_pulse", "agent_id": "a"})
    assert route.call_count == 0


async def test_every_acknowledged_concurrent_emit_is_durable(bus: GossipBus) -> None:
    """Fifty concurrent emits: every returned UUID is stored, and nothing else."""
    uuids = await asyncio.gather(
        *(bus.emit("heartbeat", {"kind": "agent_pulse", "agent_id": f"a-{i}"}) for i in range(50))
    )
    stored = [e["uuid"] for e in await bus.tail(limit=1000)]
    assert sorted(stored) == sorted(uuids)
    assert len(set(uuids)) == 50


# ── Reorder buffer: actual capacity and refusal contract ────────────────────


def _seq(n: int, task: str = "t") -> ClaimSequence:
    """Build a claim with sequence number ``n``."""
    return ClaimSequence(agent_id="a", claim_num=n, task=f"{task}-{n}", timestamp=0.0)


def test_reorder_buffer_has_no_capacity_bound_or_refusal() -> None:
    """Characterization: future claims are buffered without limit; none is refused.

    There is no configured capacity, so this pins the absence of a bound rather
    than inventing one. 2000 out-of-order claims are all held.
    """
    buffer = ReorderBuffer(agent_id="a")
    for n in range(2000, 0, -1):
        emitted, watermark = buffer.add_claim(_seq(n))
        assert emitted == [] and watermark == 0
    assert buffer.status()["buffered_count"] == 2000
    emitted, watermark = buffer.add_claim(_seq(0))
    assert [c.claim_num for c in emitted] == list(range(2001))
    assert watermark == 2001 and buffer.buffer == {}


def test_reorder_buffer_duplicates_and_stale_claims_are_dropped_silently() -> None:
    """First buffered claim wins; anything below the watermark is dropped with no signal."""
    buffer = ReorderBuffer(agent_id="a")
    buffer.add_claim(_seq(2, "first"))
    buffer.add_claim(_seq(2, "second"))
    assert buffer.buffer[2].task == "first-2"
    buffer.add_claim(_seq(0))
    buffer.add_claim(_seq(1))
    assert buffer.watermark == 3
    assert buffer.add_claim(_seq(1, "late")) == ([], 3)


def test_reorder_buffer_drain_skips_gaps_and_then_drops_the_late_claim() -> None:
    """Characterization: a forced drain advances past a gap; the gap claim is then lost."""
    buffer = ReorderBuffer(agent_id="a")
    buffer.add_claim(_seq(0))
    buffer.add_claim(_seq(3))
    emitted, watermark = buffer.drain()
    assert [c.claim_num for c in emitted] == [3] and watermark == 4
    assert buffer.add_claim(_seq(1)) == ([], 4)


async def test_reorder_buffer_reconstruction_tolerates_duplicate_events(bus: GossipBus) -> None:
    """Re-emitted claim_sequence events (new UUIDs) do not double-advance the watermark."""
    for n in (1, 0, 1, 2, 2):
        await bus.emit("heartbeat", _seq(n).to_payload())
    buffers = await get_reorder_buffers(bus)
    assert buffers["a"].watermark == 3
    assert buffers["a"].buffer == {}
