"""tests/test_lan_gossip_bridge.py

Tests for the LAN gossip bridge that extends the intra-host job board to
peers on the same LAN.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import fastapi_app
from orchestrator.gossip_bus import GossipBus
from orchestrator.lan_gossip_bridge import LanGossipBridge, make_gossip_bus


@pytest.fixture
def tmp_db_path(tmp_path):
    return str(tmp_path / "lan_gossip.db")


@pytest.fixture
async def local_bus(tmp_db_path):
    bus = GossipBus(db_path=tmp_db_path)
    await bus.init_db()
    return bus


@pytest.mark.asyncio
async def test_bridge_no_peers_is_local(tmp_db_path):
    """Without peers, the bridge behaves like a plain GossipBus."""
    bridge = LanGossipBridge(db_path=tmp_db_path)
    await bridge.init_db()

    await bridge.emit("heartbeat", {"kind": "test", "value": 1})
    events = await bridge.tail(limit=10, event_type="heartbeat")

    assert len(events) == 1
    assert events[0]["payload"]["value"] == 1


@pytest.mark.asyncio
async def test_bridge_init_db_delegates_to_local_bus(tmp_db_path):
    """LanGossipBridge supports the same initialization API as GossipBus."""
    bridge = LanGossipBridge(db_path=tmp_db_path, peers=["http://peer-a.example:8000"])
    await bridge.init_db()


@pytest.mark.asyncio
async def test_bridge_connect_is_usable_directly_with_async_with(tmp_db_path):
    """Regression: connect() must be a plain method returning the context
    manager directly, matching GossipBus.connect()'s own contract -- not
    `async def`, which would make `bridge.connect()` return a coroutine
    instead, breaking `async with bridge.connect() as db:` for every caller
    (_ensure_claims_table, the claim/release helpers) that relies on the
    same drop-in usage as the plain GossipBus this class wraps.
    """
    bridge = LanGossipBridge(db_path=tmp_db_path)
    await bridge.init_db()

    async with bridge.connect() as db:
        cursor = await db.execute("SELECT 1")
        row = await cursor.fetchone()
        assert row == (1,)

    await bridge.local.emit("heartbeat", {"kind": "local", "value": 7})
    events = await bridge.local.tail(limit=10, event_type="heartbeat")
    assert events[0]["payload"]["value"] == 7


@pytest.mark.asyncio
@respx.mock
async def test_bridge_forwards_emit_to_peers(tmp_db_path):
    """Emitting an event POSTs it to every configured peer with a stable UUID."""
    route = respx.post("http://peer-a.example:8000/gossip/emit").mock(
        return_value=Response(200, json={"ok": True})
    )
    peer_b = respx.post("http://peer-b.example:8000/gossip/emit").mock(
        return_value=Response(200, json={"ok": True})
    )

    bridge = LanGossipBridge(
        db_path=tmp_db_path,
        peers=["http://peer-a.example:8000", "http://peer-b.example:8000"],
        timeout=1.0,
    )
    await bridge.init_db()

    event_uuid = await bridge.emit("heartbeat", {"kind": "task_enqueue", "task_id": "t1"})

    assert route.called
    assert peer_b.called
    body = json.loads(route.calls.last.request.content)
    assert body["event_type"] == "heartbeat"
    assert body["payload"]["task_id"] == "t1"
    assert body["payload"]["_gossip_uuid"] == event_uuid
    assert body["uuid"] == event_uuid


@pytest.mark.asyncio
@respx.mock
async def test_bridge_forwards_gossip_secret_header(tmp_db_path, monkeypatch):
    """Configured peer auth is forwarded to peer gossip endpoints."""
    monkeypatch.setenv("GOSSIP_SHARED_SECRET", "shared-test-secret")
    route = respx.post("http://peer-a.example:8000/gossip/emit").mock(
        return_value=Response(200, json={"ok": True})
    )

    bridge = LanGossipBridge(
        db_path=tmp_db_path,
        peers=["http://peer-a.example:8000"],
        timeout=1.0,
    )
    await bridge.init_db()

    await bridge.emit("heartbeat", {"kind": "task_enqueue", "task_id": "t1"})

    assert route.called
    assert route.calls.last.request.headers["X-Gossip-Secret"] == "shared-test-secret"


@pytest.mark.asyncio
@respx.mock
async def test_bridge_tail_merges_peer_events(tmp_db_path):
    """tail() merges local events with UUID-backed events fetched from peers."""
    peer_payload = {
        "events": [
            {
                "row_id": 99,
                "uuid": "remote-uuid",
                "ts": 1.0,
                "event_type": "heartbeat",
                "payload": {"task_id": "remote"},
            }
        ]
    }
    respx.get("http://peer-a.example:8000/gossip/tail").mock(
        return_value=Response(200, json=peer_payload)
    )

    bridge = LanGossipBridge(
        db_path=tmp_db_path,
        peers=["http://peer-a.example:8000"],
        timeout=1.0,
    )
    await bridge.init_db()
    await bridge.emit("heartbeat", {"kind": "task_enqueue", "task_id": "local"})

    events = await bridge.tail(limit=10, event_type="heartbeat")
    task_ids = {ev["payload"]["task_id"] for ev in events}

    assert "local" in task_ids
    assert "remote" in task_ids


@pytest.mark.asyncio
@respx.mock
async def test_bridge_tail_deduplicates_by_uuid_with_distinct_row_ids(tmp_db_path):
    """The same logical event deduplicates even when peer row_id differs."""
    bridge = LanGossipBridge(
        db_path=tmp_db_path,
        peers=["http://peer-a.example:8000"],
        timeout=1.0,
    )
    await bridge.init_db()
    event_uuid = await bridge.emit("heartbeat", {"kind": "task_enqueue", "task_id": "shared"})

    peer_payload = {
        "events": [
            {
                "row_id": 99,
                "uuid": event_uuid,
                "ts": 1.0,
                "event_type": "heartbeat",
                "payload": {"task_id": "shared"},
            }
        ]
    }
    respx.get("http://peer-a.example:8000/gossip/tail").mock(
        return_value=Response(200, json=peer_payload)
    )

    events = await bridge.tail(limit=10, event_type="heartbeat")
    assert [ev["uuid"] for ev in events].count(event_uuid) == 1


@pytest.mark.asyncio
async def test_gossip_bus_strips_forwarded_uuid_from_stored_payload(tmp_db_path):
    """Legacy FastAPI endpoint compatibility envelope is not persisted."""
    bus = GossipBus(db_path=tmp_db_path)
    event_uuid = await bus.emit(
        "heartbeat",
        {"kind": "task_enqueue", "task_id": "t1", "_gossip_uuid": "peer-event-uuid"},
    )

    events = await bus.tail(limit=10, event_type="heartbeat")
    assert event_uuid == "peer-event-uuid"
    assert events[0]["uuid"] == "peer-event-uuid"
    assert events[0]["payload"] == {"kind": "task_enqueue", "task_id": "t1"}


@pytest.mark.asyncio
@respx.mock
async def test_bridge_unreachable_peer_is_best_effort(tmp_db_path):
    """An unreachable peer does not break local emit or tail."""
    peer_url = "http://peer-down.example:8000"
    respx.post(f"{peer_url}/gossip/emit").mock(
        side_effect=httpx.ConnectError("peer unreachable")
    )
    respx.get(f"{peer_url}/gossip/tail").mock(
        side_effect=httpx.ConnectError("peer unreachable")
    )

    bridge = LanGossipBridge(
        db_path=tmp_db_path,
        peers=[peer_url],
        timeout=0.1,
    )
    await bridge.init_db()

    await bridge.emit("heartbeat", {"kind": "test", "value": 2})
    events = await bridge.tail(limit=10)

    assert len(events) == 1
    assert events[0]["payload"]["value"] == 2


def test_make_gossip_bus_no_peers_returns_plain_bus(tmp_db_path, monkeypatch):
    """make_gossip_bus returns a plain GossipBus when GOSSIP_PEERS is unset."""
    monkeypatch.delenv("GOSSIP_PEERS", raising=False)
    bus = make_gossip_bus(db_path=tmp_db_path)
    assert isinstance(bus, GossipBus)
    assert not isinstance(bus, LanGossipBridge)


def test_make_gossip_bus_with_peers_returns_bridge(tmp_db_path, monkeypatch):
    """make_gossip_bus returns a LanGossipBridge when GOSSIP_PEERS is set."""
    monkeypatch.setenv("GOSSIP_PEERS", "http://peer-a:8000,http://peer-b:8000")
    bus = make_gossip_bus(db_path=tmp_db_path)
    assert isinstance(bus, LanGossipBridge)
    assert bus.peers == ["http://peer-a:8000", "http://peer-b:8000"]


class _FakeBus:
    """Minimal stand-in for GossipBus in endpoint tests."""

    def __init__(self):
        self.events: list[dict] = []

    async def emit(self, event_type: str, payload: dict, *, event_uuid: str | None = None) -> str:
        stored_uuid = event_uuid or payload.get("_gossip_uuid") or "fake-uuid"
        clean_payload = dict(payload)
        clean_payload.pop("_gossip_uuid", None)
        self.events.append({"uuid": stored_uuid, "event_type": event_type, "payload": clean_payload})
        return stored_uuid

    async def tail(self, limit: int = 20, event_type: str | None = None):
        return [
            {
                "row_id": i + 1,
                "uuid": ev["uuid"],
                "ts": 1.0,
                "event_type": ev["event_type"],
                "payload": ev["payload"],
            }
            for i, ev in enumerate(reversed(self.events))
            if event_type is None or ev["event_type"] == event_type
        ][:limit]

    async def init_db(self):
        pass


def test_gossip_emit_endpoint(monkeypatch, tmp_path):
    """POST /gossip/emit persists an event through the local GossipBus."""
    monkeypatch.delenv("GOSSIP_SHARED_SECRET", raising=False)
    monkeypatch.delenv("PT_BIND_LAN", raising=False)
    fake = _FakeBus()
    monkeypatch.setattr(fastapi_app, "_gossip_bus", fake)
    client = TestClient(fastapi_app.app)

    response = client.post(
        "/gossip/emit",
        json={
            "event_type": "heartbeat",
            "payload": {
                "kind": "task_enqueue",
                "task_id": "t1",
                "_gossip_uuid": "peer-event-uuid",
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["uuid"] == "peer-event-uuid"
    assert fake.events[0]["payload"] == {"kind": "task_enqueue", "task_id": "t1"}


def test_gossip_tail_endpoint(monkeypatch, tmp_path):
    """GET /gossip/tail returns local events and configured peers."""
    monkeypatch.delenv("GOSSIP_SHARED_SECRET", raising=False)
    monkeypatch.delenv("PT_BIND_LAN", raising=False)
    fake = _FakeBus()
    fake.events.append({"uuid": "fake-uuid", "event_type": "heartbeat", "payload": {"task_id": "t1"}})
    monkeypatch.setattr(fastapi_app, "_gossip_bus", fake)
    monkeypatch.setenv("GOSSIP_PEERS", "http://peer-a:8000")
    client = TestClient(fastapi_app.app)

    response = client.get("/gossip/tail?limit=10&event_type=heartbeat")

    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) == 1
    assert data["events"][0]["payload"]["task_id"] == "t1"
    assert "http://peer-a:8000" in data["peers"]
