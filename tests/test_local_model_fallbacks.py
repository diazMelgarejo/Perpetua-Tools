"""When another model holds the host, callers carry on without one: memory search answers from keywords."""

from __future__ import annotations

import asyncio
import re
import sqlite3
import subprocess
import time
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from orchestrator import memory_node
from orchestrator.gossip_bus import GossipBus
from perpetua_tools import local_model_gate as gate

ROOT = Path(__file__).resolve().parents[1]
POSTS = re.compile(r"""/api/(generate|chat|embed|embeddings)\b|/v1/(chat/completions|embeddings)\b""")
# These name an endpoint path for a remote provider and never send a request to this host themselves.
PATH_ONLY = {"orchestrator/model_registry.py"}


def busy(*args, **kwargs):
    raise gate.LocalModelBusy("another model is loaded (ollama:chat)", "ollama:chat")


@pytest.fixture()
def host_is_busy(monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    asked: list[tuple] = []

    @asynccontextmanager
    async def refuse(engine: str, model: str, url: str):
        asked.append((engine, model, url))
        busy()
        yield

    monkeypatch.setattr(gate, "local_slot_async", refuse)
    monkeypatch.setattr(gate, "local_slot", busy)
    return asked


@pytest.mark.asyncio
async def test_embedding_asks_the_gate_before_any_request(host_is_busy, monkeypatch: pytest.MonkeyPatch) -> None:
    from orchestrator import memory_embed

    def no_network(*args, **kwargs):
        raise AssertionError("no request may be sent when the gate refuses")

    monkeypatch.setattr(memory_embed.httpx, "AsyncClient", no_network)

    with pytest.raises(gate.LocalModelBusy):
        await memory_embed.get_embedding("hello")
    assert host_is_busy[0][:2] == ("ollama", "bge-m3")


@pytest.mark.asyncio
async def test_memory_search_still_answers_from_keywords_when_the_host_is_busy(
    host_is_busy, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Bus:
        async def search(self, query: str, limit: int = 10):
            return [{"row_id": 1, "uuid": "u1", "ts": "t", "event_type": "note", "payload": {"text": "keyword hit"}}]

    class Store:
        async def search(self, vector, limit: int = 10):
            raise AssertionError("the vector store cannot be searched without an embedding")

    async def ready(bus) -> None:
        return None

    monkeypatch.setattr(memory_node, "ensure_gossip_db_ready", ready)
    monkeypatch.setattr("orchestrator.memory_store.lancedb_available", lambda: True)

    hits = await memory_node.retrieve_context("keyword", top_n=3, use_gbrain=False, gossip_bus=Bus(), lance_store=Store())

    assert hits and "keyword hit" in str(hits[0])
    assert host_is_busy, "the vector path must have tried the gate"


@pytest.mark.asyncio
async def test_an_event_skipped_because_the_host_is_busy_stays_pending(
    host_is_busy, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    recorded: list[str] = []
    bus = GossipBus(str(tmp_path / "bus.db"))

    async def record(row_id: int, status: str) -> None:
        recorded.append(status)

    monkeypatch.setattr(bus, "_update_embed_status", record)

    await bus._embed_and_store(1, {"text": "x"})

    assert recorded == ["pending"], "a busy host is not a failed embedding"


def test_every_file_that_talks_to_a_model_endpoint_goes_through_the_gate() -> None:
    listed = subprocess.run(["git", "ls-files", "-z", "--", "orchestrator/*.py", "src/*.py", "scripts/*.py",
                             "utils/*.py", "packages/*.py"], cwd=ROOT, capture_output=True, text=True, check=True)
    ungated = []
    for name in listed.stdout.split("\0"):
        path = ROOT / name
        if not name or "/tests/" in f"/{name}" or name in PATH_ONLY or name.endswith("local_model_gate.py"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if POSTS.search(text) and "local_slot" not in text:
            ungated.append(name)
    assert ungated == []


def test_only_the_swap_command_may_change_the_loaded_model() -> None:
    listed = subprocess.run(["git", "grep", "-lE", r"\.swap\(", "--", "orchestrator", "src", "scripts", "utils"],
                            cwd=ROOT, capture_output=True, text=True, check=False).stdout.split()
    users = [name for name in listed if "local_model_gate" in (ROOT / name).read_text(encoding="utf-8")]
    assert users == ["src/perpetua_tools/local_model_gate.py"]


# --------------------------------------------------------------- events the gate refused are embedded later, boundedly


class _Store:
    def __init__(self) -> None:
        self.added: list[int] = []

    async def add(self, *, row_id: int, text: str, embedding: list[float]) -> None:
        self.added.append(row_id)


def _bus_with(tmp_path: Path, statuses: list[str], *, age_s: float = 3600) -> GossipBus:
    """A database holding one old event per status, ids 1..n, plus a fresh trigger event as the last row."""
    path = tmp_path / "bus.db"
    bus = GossipBus(str(path))
    asyncio.run(bus._ensure_initialized())
    now = time.time()
    with sqlite3.connect(path) as db:
        for number, status in enumerate([*statuses, "pending"], start=1):
            ts = now if number > len(statuses) else now - age_s
            db.execute("INSERT INTO gossip (event_uuid, ts, event_type, payload_json, embed_status) "
                       "VALUES (?, ?, 'note', '{\"n\": 1}', ?)", (f"u{number}", ts, status))
    return bus


def _statuses(bus_path: Path) -> list[str]:
    with sqlite3.connect(bus_path) as db:
        return [row[0] for row in db.execute("SELECT embed_status FROM gossip ORDER BY id")]


@pytest.fixture()
def embeds(monkeypatch: pytest.MonkeyPatch):
    """An embedder that succeeds ``allowed`` times and is refused by the gate afterwards."""
    state = {"allowed": 10_000, "calls": 0, "dims": []}
    store = _Store()

    async def embed(text: str) -> list[float]:
        state["calls"] += 1
        await asyncio.sleep(0)
        if state["calls"] > state["allowed"]:
            busy()
        return [0.0] * 7

    def get_store(*args, dim=None, **kwargs):
        state["dims"].append(dim)
        return store

    monkeypatch.setattr("orchestrator.memory_embed.get_embedding", embed)
    monkeypatch.setattr("orchestrator.memory_store.get_lance_store", get_store)
    state["store"] = store
    return state


def test_a_success_retries_older_pending_events_and_sizes_the_store_from_the_vector(tmp_path, embeds) -> None:
    bus = _bus_with(tmp_path, ["pending", "failed", "pending", "embedded"])

    asyncio.run(bus._embed_and_store(5, {"n": 1}))

    assert _statuses(tmp_path / "bus.db") == ["embedded", "failed", "embedded", "embedded", "embedded"]
    assert embeds["store"].added == [5, 1, 3] and set(embeds["dims"]) == {7}


def test_one_success_retries_at_most_one_batch(tmp_path, embeds) -> None:
    bus = _bus_with(tmp_path, ["pending"] * 25)

    asyncio.run(bus._embed_and_store(26, {"n": 1}))

    assert embeds["calls"] == 21 and _statuses(tmp_path / "bus.db").count("pending") == 5


def test_a_refusal_during_a_retry_ends_it(tmp_path, embeds) -> None:
    embeds["allowed"] = 2
    bus = _bus_with(tmp_path, ["pending"] * 4)

    asyncio.run(bus._embed_and_store(5, {"n": 1}))

    assert embeds["calls"] == 3
    assert _statuses(tmp_path / "bus.db") == ["embedded", "pending", "pending", "pending", "embedded"]


def test_a_refused_event_starts_no_retry(tmp_path, embeds) -> None:
    embeds["allowed"] = 0
    bus = _bus_with(tmp_path, ["pending"] * 4)

    asyncio.run(bus._embed_and_store(5, {"n": 1}))

    assert embeds["calls"] == 1 and _statuses(tmp_path / "bus.db") == ["pending"] * 5


def test_a_recent_pending_event_is_left_to_whoever_is_embedding_it(tmp_path, embeds) -> None:
    bus = _bus_with(tmp_path, ["pending"] * 3, age_s=60)

    asyncio.run(bus._embed_and_store(4, {"n": 1}))

    assert embeds["calls"] == 1


def test_two_processes_never_retry_the_same_event_and_an_abandoned_claim_is_taken_over(tmp_path, embeds) -> None:
    abandoned = f"retrying:{int(time.time()) - 7200}"
    live = f"retrying:{int(time.time())}"
    bus = _bus_with(tmp_path, ["pending"] * 6 + [abandoned, live])
    other = GossipBus(str(tmp_path / "bus.db"))

    async def both() -> None:
        await asyncio.gather(bus._retry_pending(), other._retry_pending())

    asyncio.run(both())

    assert sorted(embeds["store"].added) == [1, 2, 3, 4, 5, 6, 7]
    assert _statuses(tmp_path / "bus.db")[6:8] == ["embedded", live]


def test_an_unreadable_old_event_is_marked_failed_and_does_not_block_the_rest(tmp_path, embeds) -> None:
    bus = _bus_with(tmp_path, ["pending", "pending"])
    with sqlite3.connect(tmp_path / "bus.db") as db:
        db.execute("UPDATE gossip SET payload_json = '{torn' WHERE id = 1")

    asyncio.run(bus._embed_and_store(3, {"n": 1}))

    assert _statuses(tmp_path / "bus.db") == ["failed", "embedded", "embedded"]


# ---------------------------------------------------------------- the vector size is never guessed from a refusal


def test_a_refused_probe_leaves_the_size_unknown_and_builds_no_store(host_is_busy, monkeypatch) -> None:
    from orchestrator import memory_embed, memory_store

    monkeypatch.setattr(memory_embed, "_PROBED_DIM", None)
    monkeypatch.delenv("EMBED_DIM", raising=False)
    monkeypatch.setattr(memory_store, "_lance_stores", {})

    with pytest.raises(gate.LocalModelRefused):
        memory_store.get_lance_store("unused.lance")

    assert memory_embed._PROBED_DIM is None and memory_store._lance_stores == {}


# --------------------------------------------------------------------------- requests are sent while the gate is held


@pytest.fixture()
def tracked_slot(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    events: list[str] = []

    @asynccontextmanager
    async def slot(engine: str, model: str, url: str):
        events.append("held")
        try:
            yield
        finally:
            events.append("released")

    class Reply:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"embedding": [0.0], "message": {"content": "ok"}, "choices": [{"message": {"content": "ok"}}]}

    class Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc) -> None:
            return None

        async def post(self, *args, **kwargs):
            events.append("sent")
            return Reply()

    monkeypatch.setattr(gate, "local_slot_async", slot)
    monkeypatch.setattr("httpx.AsyncClient", Client)
    return events


def test_the_embedding_request_is_sent_while_the_gate_is_held(tracked_slot) -> None:
    from orchestrator import memory_embed

    asyncio.run(memory_embed.get_embedding("hello"))

    assert tracked_slot == ["held", "sent", "released"]


@pytest.mark.parametrize("worker", ["_ollama_mac_worker", "_lmstudio_mac_worker"])
def test_a_local_worker_sends_while_the_gate_is_held(tracked_slot, monkeypatch, worker: str) -> None:
    from orchestrator import worker_registry

    monkeypatch.setattr("utils.dispatch_models.resolve_dispatch_model", lambda *a, **k: "some-model")

    class Spec:
        prompt = "hi"
        metadata: dict = {}
        constraints: dict = {}

    asyncio.run(getattr(worker_registry, worker)(Spec()))

    assert tracked_slot == ["held", "sent", "released"]


def test_no_caller_asks_the_gate_without_holding_it() -> None:
    listed = subprocess.run(["git", "grep", "-nE", r"local_slot(_async)?\(", "--", "orchestrator", "src", "scripts"],
                            cwd=ROOT, capture_output=True, text=True, check=False).stdout.splitlines()
    loose = [line for line in listed
             if "local_model_gate.py" not in line and not re.search(r":\s*(async )?with ", line)]
    assert listed and loose == []
