"""board_snapshot: log_message keeps the JSON snapshot current."""
import json

import pytest

from orchestrator.coordination.board_snapshot import read_notes, refresh_snapshot
from orchestrator.coordination.claims import log_message
from orchestrator.gossip_bus import GossipBus


@pytest.mark.asyncio
async def test_log_message_writes_snapshot_when_path_configured(tmp_path, monkeypatch):
    out = tmp_path / "snap.json"
    monkeypatch.setenv("GOSSIP_BOARD_SNAPSHOT", str(out))
    bus = GossipBus(db_path=str(tmp_path / "board.db"))
    await bus.ensure_ready() if hasattr(bus, "ensure_ready") else None

    await log_message(bus, "agent-a", "first note")

    snap = json.loads(out.read_text())
    assert snap["recent_notes"][-1]["message"] == "first note"
    assert snap["recent_notes"][-1]["agent_id"] == "agent-a"


@pytest.mark.asyncio
async def test_log_message_skips_snapshot_for_non_default_db(tmp_path, monkeypatch):
    monkeypatch.delenv("GOSSIP_BOARD_SNAPSHOT", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    bus = GossipBus(db_path=str(tmp_path / "board.db"))

    await log_message(bus, "agent-a", "note")

    assert not (tmp_path / ".openclaw" / "state" / "gossip_board_snapshot.json").exists()


def test_refresh_snapshot_never_raises_and_keeps_foreign_keys(tmp_path, monkeypatch):
    out = tmp_path / "snap.json"
    out.write_text(json.dumps({"envelope_review": {"verdict": "kept"}}))
    monkeypatch.setenv("GOSSIP_BOARD_SNAPSHOT", str(out))

    refresh_snapshot(str(tmp_path / "missing.db"), str(tmp_path / "other.db"))

    assert json.loads(out.read_text()) == {"envelope_review": {"verdict": "kept"}}
