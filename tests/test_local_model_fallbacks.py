"""When another model holds the host, callers carry on without one: memory search answers from keywords."""

from __future__ import annotations

import re
import subprocess
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

    async def refuse(engine: str, model: str, url: str):
        asked.append((engine, model, url))
        busy()

    monkeypatch.setattr(gate, "require_local_slot_async", refuse)
    monkeypatch.setattr(gate, "require_local_slot", busy)
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
        if POSTS.search(text) and "require_local_slot" not in text:
            ungated.append(name)
    assert ungated == []


def test_only_the_swap_command_may_change_the_loaded_model() -> None:
    listed = subprocess.run(["git", "grep", "-lE", r"\.swap\(", "--", "orchestrator", "src", "scripts", "utils"],
                            cwd=ROOT, capture_output=True, text=True, check=False).stdout.split()
    users = [name for name in listed if "local_model_gate" in (ROOT / name).read_text(encoding="utf-8")]
    assert users == ["src/perpetua_tools/local_model_gate.py"]
