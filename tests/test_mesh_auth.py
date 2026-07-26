from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import fastapi_app
from orchestrator.mesh_auth import require_gossip_auth


def test_require_gossip_auth_allows_loopback_without_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOSSIP_SHARED_SECRET", raising=False)
    monkeypatch.delenv("PT_BIND_LAN", raising=False)

    scope = {"type": "http", "headers": [], "method": "GET", "path": "/gossip/tail"}
    require_gossip_auth(Request(scope))


def test_require_gossip_auth_blocks_lan_bind_without_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GOSSIP_SHARED_SECRET", raising=False)
    monkeypatch.setenv("PT_BIND_LAN", "1")

    scope = {"type": "http", "headers": [], "method": "POST", "path": "/gossip/emit"}
    with pytest.raises(Exception) as exc:
        require_gossip_auth(Request(scope))
    assert getattr(exc.value, "status_code", None) == 503


def test_gossip_emit_503_when_lan_bind_without_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("GOSSIP_SHARED_SECRET", raising=False)
    monkeypatch.setenv("PT_BIND_LAN", "1")
    monkeypatch.setattr(fastapi_app, "_gossip_bus", object())

    client = TestClient(fastapi_app.app)
    response = client.post(
        "/gossip/emit",
        json={"event_type": "heartbeat", "payload": {"kind": "test"}},
    )
    assert response.status_code == 503
