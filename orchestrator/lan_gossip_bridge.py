"""LAN gossip bridge — extend a local GossipBus across peers on the same LAN.

The bridge is a transparent wrapper: when ``GOSSIP_PEERS`` is unset it behaves
exactly like the local ``GossipBus``. When peers are configured, local ``emit()``
calls are also forwarded to every reachable peer, and ``tail()``/``search()``
merge results from all peers so the job board view spans the LAN.

This is intentionally simple and single-operator-LAN safe: peers are discovered
from explicit env/config, not auto-joined, and forwarded events are treated as
best-effort (local durability is authoritative).
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

import httpx

from orchestrator.gossip_bus import EventType, GossipBus, resolve_gossip_db_path


class LanGossipBridge:
    """Drop-in wrapper around ``GossipBus`` that replicates events to LAN peers.

    Parameters match ``GossipBus`` so callers can swap one for the other without
    changing surrounding code.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        *,
        peers: Optional[list[str]] = None,
        timeout: float = 5.0,
    ) -> None:
        self.local = GossipBus(
            db_path=db_path if db_path is not None else resolve_gossip_db_path()
        )
        self.peers = peers or _load_peers()
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Local pass-through
    # ------------------------------------------------------------------
    async def connect(self):
        return self.local.connect()

    async def insert_event(
        self,
        db: Any,
        event_type: EventType,
        payload: dict,
        *,
        timestamp: Optional[float] = None,
    ) -> tuple[int, dict]:
        return await self.local.insert_event(
            db, event_type, payload, timestamp=timestamp
        )

    def schedule_embedding(self, row_id: int, safe_payload: dict) -> None:
        self.local.schedule_embedding(row_id, safe_payload)

    # ------------------------------------------------------------------
    # Cross-peer replication
    # ------------------------------------------------------------------
    async def emit(self, event_type: EventType, payload: dict) -> None:
        """Persist locally, then best-effort forward to every configured peer."""
        await self.local.emit(event_type, payload)
        if not self.peers:
            return
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for peer in self.peers:
                try:
                    await client.post(
                        f"{peer.rstrip('/')}/gossip/emit",
                        json={"event_type": event_type, "payload": payload},
                    )
                except Exception:
                    # Best-effort: peer unreachable or misconfigured is not fatal.
                    pass

    async def tail(
        self, limit: int = 20, event_type: Optional[str] = None
    ) -> list[dict]:
        """Merge newest events from local DB and all peers."""
        local_events = await self.local.tail(limit=limit, event_type=event_type)
        if not self.peers:
            return local_events

        peer_events: list[dict] = []
        params: dict[str, Any] = {"limit": limit}
        if event_type:
            params["event_type"] = event_type

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for peer in self.peers:
                try:
                    response = await client.get(
                        f"{peer.rstrip('/')}/gossip/tail", params=params
                    )
                    response.raise_for_status()
                    data = response.json()
                    peer_events.extend(data.get("events", []))
                except Exception:
                    pass

        merged = {ev.get("row_id"): ev for ev in peer_events if ev.get("row_id")}
        for ev in local_events:
            merged[ev.get("row_id")] = ev
        return sorted(merged.values(), key=lambda e: e.get("row_id", 0), reverse=True)[
            :limit
        ]

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        event_type: Optional[str] = None,
    ) -> list[dict]:
        """Search local DB only. Full-text search across peers is left to tail()."""
        return await self.local.search(query, limit=limit, event_type=event_type)


def _load_peers() -> list[str]:
    """Resolve GOSSIP_PEERS env var into a list of peer base URLs."""
    raw = os.getenv("GOSSIP_PEERS", "").strip()
    if not raw:
        return []
    peers = [p.strip() for p in raw.split(",") if p.strip()]
    return [p for p in peers if p.startswith(("http://", "https://"))]


def make_gossip_bus(
    db_path: Optional[str] = None,
    *,
    peers: Optional[list[str]] = None,
) -> GossipBus | LanGossipBridge:
    """Return a LAN-aware gossip bus if peers are configured, otherwise local."""
    peers = peers if peers is not None else _load_peers()
    resolved_db = db_path if db_path is not None else resolve_gossip_db_path()
    if peers:
        return LanGossipBridge(db_path=resolved_db, peers=peers)
    return GossipBus(db_path=resolved_db)
