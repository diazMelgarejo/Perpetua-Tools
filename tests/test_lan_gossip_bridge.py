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

    await bridge.local.emit("heartbeat", {"kind": "local", "value": 7})
    events = await bridge.local.tail(limit=10, event_type="heartbeat")
    assert events[0]["payload"]["value"] == 7


@pytest.mark.asyncio
@respx.mock
async def test_bridge_forwards_emit_to_peers(tmp_db_path):
    """Emitting an event POSTs it to every configured peer."""
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

    await bridge.emit("heartbeat", {"kind": "task_enqueue", "task_id": "t1"})

    assert route.called
    assert peer_b.called
    body = json.loads(route.calls.last.request.content)
    assert body["event_type"] == "heartbeat"
    assert body["payload"]["task_id"] == "t1"


@pytest.mark.asyncio
@respx.mock
async def test_bridge_tail_merges_peer_events(tmp_db_path):
    """tail() merges local events with events fetched from peers."""
    peer_payload = {
        "events": [
            {"row_id": 99, "ts": 1.0, "event_type": "heartbeat", "payload": {"task_id": "remote"}}
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
async def test_bridge_tail_deduplicates_by_row_id(tmp_db_path):
    """When the same row_id appears locally and remotely, it appears once."""
    peer_payload = {
        "events": [
            {"row_id": 1, "ts": 1.0, "event_type": "heartbeat", "payload": {"task_id": "shared"}}
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
    await bridge.emit("heartbeat", {"kind": "task_enqueue", "task_id": "shared"})

    events = await bridge.tail(limit=10, event_type="heartbeat")
    assert len(events) == 1


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

    async def emit(self, event_type: str, payload: dict) -> None:
        self.events.append({"event_type": event_type, "payload": payload})

    async def tail(self, limit: int = 20, event_type: str | None = None):
        return [
            {"row_id": i + 1, "ts": 1.0, "event_type": ev["event_type"], "payload": ev["payload"]}
            for i, ev in enumerate(reversed(self.events))
            if event_type is None or ev["event_type"] == event_type
        ][:limit]

    async def init_db(self):
        pass


def test_gossip_emit_endpoint(monkeypatch, tmp_path):
    """POST /gossip/emit persists an event through the local GossipBus."""
    fake = _FakeBus()
    monkeypatch.setattr(fastapi_app, "GossipBus", lambda: fake)
    client = TestClient(fastapi_app.app)

    response = client.post(
        "/gossip/emit",
        json={"event_type": "heartbeat", "payload": {"kind": "task_enqueue", "task_id": "t1"}},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert fake.events[0]["payload"]["task_id"] == "t1"


def test_gossip_tail_endpoint(monkeypatch, tmp_path):
    """GET /gossip/tail returns local events and configured peers."""
    fake = _FakeBus()
    fake.events.append({"event_type": "heartbeat", "payload": {"task_id": "t1"}})
    monkeypatch.setattr(fastapi_app, "GossipBus", lambda: fake)
    monkeypatch.setenv("GOSSIP_PEERS", "http://peer-a:8000")
    client = TestClient(fastapi_app.app)

    response = client.get("/gossip/tail?limit=10&event_type=heartbeat")

    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) == 1
    assert data["events"][0]["payload"]["task_id"] == "t1"
    assert "http://peer-a:8000" in data["peers"]
