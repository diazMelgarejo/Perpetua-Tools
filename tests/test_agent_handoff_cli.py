"""Integration tests for handoff preflight and queue admission."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import orchestrator.coordination.cli as cli
from orchestrator.gossip_bus import GossipBus


def _packet(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "session_id": "session-1",
        "job_id": "job-1",
        "task_id": "task-1",
        "assigned_agent_id": "agent-1",
        "role": "coder",
        "intent": "Add a queue admission validator.",
        "branch": "feat/agent-handoff-validation-v1",
        "worktree": "feature-worktree",
        "starting_head": "1234567",
        "current_head": "89abcde",
        "commit_sha": "89abcde",
        "files_changed": ["orchestrator/handoff_validation.py"],
        "root_cause_addressed": "No machine-checkable handoff exists.",
        "tests": [{"command": "python -m pytest -q", "result": "passed"}],
        "known_risks_or_follow_up": "none",
        "human_authorized": True,
        "merge_authorized": False,
        "deployment_authorized": False,
    }
    payload.update(overrides)
    return payload


def _write_packet(tmp_path: Path, **overrides: object) -> Path:
    path = tmp_path / "handoff.json"
    path.write_text(json.dumps(_packet(**overrides)), encoding="utf-8")
    return path


@pytest.fixture
async def bus(tmp_path: Path) -> GossipBus:
    result = GossipBus(str(tmp_path / "handoff.db"))
    await result.init_db()
    return result


@pytest.mark.asyncio
async def test_handoff_validate_cli_accepts_a_valid_packet(tmp_path: Path, monkeypatch, capsys) -> None:
    class DummyBus:
        async def init_db(self) -> None:
            return None

    monkeypatch.setattr(cli, "canonical_db_path", lambda: ":memory:")
    monkeypatch.setattr(cli, "make_gossip_bus", lambda _path: DummyBus())
    args = cli.build_parser().parse_args(["handoff", "validate", str(_write_packet(tmp_path))])

    assert await cli._amain(args) == 0
    assert "valid handoff" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_handoff_validate_cli_rejects_an_invalid_packet(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    class DummyBus:
        async def init_db(self) -> None:
            return None

    monkeypatch.setattr(cli, "canonical_db_path", lambda: ":memory:")
    monkeypatch.setattr(cli, "make_gossip_bus", lambda _path: DummyBus())
    args = cli.build_parser().parse_args(
        ["handoff", "validate", str(_write_packet(tmp_path, tests=[]))]
    )

    assert await cli._amain(args) == 1
    assert "tests" in capsys.readouterr().err


@pytest.mark.asyncio
async def test_valid_handoff_enqueues_and_records_non_liveness_admission(
    bus: GossipBus, tmp_path: Path
) -> None:
    assert await cli.queue_add_from_handoff(
        bus, _write_packet(tmp_path), "packet-work", "Phase-1", "NORMAL", "", None
    ) is None

    events = await bus.tail(limit=20, event_type="heartbeat")
    kinds = {event["payload"].get("kind") for event in events}
    assert kinds == {"task_enqueue", "handoff_admitted"}
    admitted = next(
        event["payload"] for event in events if event["payload"].get("kind") == "handoff_admitted"
    )
    assert admitted["agent_id"] == "agent-1"
    assert admitted["task_id"] == "task-1"


@pytest.mark.asyncio
async def test_invalid_handoff_writes_no_queue_or_admission_event(
    bus: GossipBus, tmp_path: Path, capsys
) -> None:
    assert await cli.queue_add_from_handoff(
        bus, _write_packet(tmp_path, tests=[]), "packet-work", "Phase-1", "NORMAL", "", None
    ) is False

    assert await bus.tail(limit=20, event_type="heartbeat") == []
    assert "tests" in capsys.readouterr().err
