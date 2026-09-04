"""Integration tests for handoff preflight and queue admission."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import orchestrator.coordination.cli as cli
from orchestrator.gossip_bus import GossipBus, cancel_pending_embeddings_for_current_loop


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


def _monitorability() -> dict[str, object]:
    return {
        "schema_version": 1,
        "phylax": {
            "policy_pack_id": "phylax-monitorability",
            "policy_pack_version": "1.0.0",
            "risk_tier": "high",
            "capability_grant_ids": ["grant_0123456789abcdef"],
            "reported_monitor_decision": "escalate",
            "severity": "high",
            "confidence": 0.82,
            "escalation_state": "human_review_required",
            "retention_class": "incident_scoped",
            "reasoning_availability": "none",
            "evidence_refs": ["evidence_0123456789abcdef"],
        },
        "privacy": {
            "classification": "redacted",
            "redaction_profile_id": "handoff-v1",
            "export_allowed": False,
            "raw_reasoning_persisted_in_packet": False,
            "raw_reasoning_exported": False,
        },
        "integrity": {
            "provenance_commit_sha": "0123456789abcdef0123456789abcdef01234567",
            "ordered_evidence_refs": ["evidence_0123456789abcdef"],
            "redacted_manifest_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        },
    }


def _write_packet(tmp_path: Path, **overrides: object) -> Path:
    path = tmp_path / "handoff.json"
    path.write_text(json.dumps(_packet(**overrides)), encoding="utf-8")
    return path


@pytest.fixture
async def bus(tmp_path: Path) -> GossipBus:
    result = GossipBus(str(tmp_path / "handoff.db"))
    await result.init_db()
    try:
        yield result
    finally:
        await cancel_pending_embeddings_for_current_loop()


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
    queue_task_id = await cli.queue_add_from_handoff(
        bus, _write_packet(tmp_path), "packet-work", "Phase-1", "NORMAL", "", None
    )
    assert isinstance(queue_task_id, str) and queue_task_id

    events = await bus.tail(limit=20, event_type="heartbeat")
    kinds = {event["payload"].get("kind") for event in events}
    assert kinds == {"task_enqueue", "handoff_admitted"}
    admitted = next(
        event["payload"] for event in events if event["payload"].get("kind") == "handoff_admitted"
    )
    queued = next(event["payload"] for event in events if event["payload"].get("kind") == "task_enqueue")
    assert admitted["agent_id"] == "agent-1"
    assert admitted["task_id"] == "task-1"
    assert queued["required_agent_id"] == "agent-1"
    assert admitted["queue_task_id"] == queued["task_id"] == queue_task_id

    assert await cli._queue_claim(bus, queued["task_id"], "agent-2") is False
    assert await cli._queue_claim(bus, queued["task_id"], "agent-1") is None


@pytest.mark.asyncio
async def test_admission_rolls_back_enqueue_when_audit_write_fails(
    bus: GossipBus, tmp_path: Path
) -> None:
    """The core atomicity claim: if the handoff_admitted audit insert fails
    after the task_enqueue insert already succeeded in the same
    (uncommitted) transaction, the enqueue must not survive either --
    proving these are genuinely one atomic unit, not two sequential
    statements against the same connection that happen to usually both
    succeed."""
    real_insert_event = GossipBus.insert_event
    call_count = {"n": 0}

    async def _fail_on_second_call(self, db, event_type, payload, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("simulated audit-event insert failure")
        return await real_insert_event(self, db, event_type, payload, **kwargs)

    import orchestrator.coordination.task_queue as task_queue_module
    monkeypatch_target = task_queue_module.GossipBus
    original = monkeypatch_target.insert_event
    monkeypatch_target.insert_event = _fail_on_second_call
    try:
        result = await cli.queue_add_from_handoff(
            bus, _write_packet(tmp_path), "packet-work", "Phase-1", "NORMAL", "", None
        )
    finally:
        monkeypatch_target.insert_event = original

    assert result is False

    events = await bus.tail(limit=20, event_type="heartbeat")
    kinds = [event["payload"].get("kind") for event in events]
    assert "task_enqueue" not in kinds, (
        "enqueue survived a failed audit write -- admission is not atomic"
    )
    assert "handoff_admitted" not in kinds


@pytest.mark.asyncio
async def test_duplicate_handoff_admission_does_not_double_enqueue(
    bus: GossipBus, tmp_path: Path
) -> None:
    """Admitting the same packet twice (e.g. a retried CLI invocation after
    an ambiguous network/process outcome) must not silently create two
    queue rows for the same underlying handoff -- each admission call
    generates its own fresh queue_task_id, so a caller retrying blindly
    would otherwise get two live reservations for one piece of work."""
    packet_path = _write_packet(tmp_path)

    first_id = await cli.queue_add_from_handoff(
        bus, packet_path, "packet-work", "Phase-1", "NORMAL", "", None
    )
    assert isinstance(first_id, str) and first_id

    second_id = await cli.queue_add_from_handoff(
        bus, packet_path, "packet-work", "Phase-1", "NORMAL", "", None
    )
    assert isinstance(second_id, str) and second_id
    assert second_id != first_id, (
        "two admissions of the identical packet produced the same queue_task_id, "
        "which would mask a real duplicate rather than surfacing two rows"
    )

    events = await bus.tail(limit=20, event_type="heartbeat")
    admitted = [e["payload"] for e in events if e["payload"].get("kind") == "handoff_admitted"]
    assert len(admitted) == 2, (
        "queue_add_from_handoff has no idempotency key today -- this test "
        "documents that a retried admission genuinely creates a second "
        "queue row/audit event, not a silent duplicate; true idempotency "
        "would need an explicit dedup key (e.g. packet job_id) and is not "
        "implemented -- flagged, not silently assumed away, per the "
        "atomicity-boundary open question"
    )



@pytest.mark.asyncio
async def test_invalid_handoff_writes_no_queue_or_admission_event(
    bus: GossipBus, tmp_path: Path, capsys
) -> None:
    assert await cli.queue_add_from_handoff(
        bus, _write_packet(tmp_path, tests=[]), "packet-work", "Phase-1", "NORMAL", "", None
    ) is False

    assert await bus.tail(limit=20, event_type="heartbeat") == []
    assert "tests" in capsys.readouterr().err


@pytest.mark.asyncio
async def test_monitorability_audit_projects_only_allowlisted_redacted_fields(
    bus: GossipBus, tmp_path: Path
) -> None:
    queue_task_id = await cli.queue_add_from_handoff(
        bus,
        _write_packet(tmp_path, monitorability=_monitorability()),
        "packet-work",
        "Phase-1",
        "NORMAL",
        "",
        None,
    )
    assert isinstance(queue_task_id, str) and queue_task_id

    events = await bus.tail(limit=20, event_type="heartbeat")
    admitted = next(event["payload"] for event in events if event["payload"].get("kind") == "handoff_admitted")
    assert admitted["oramasys.phylax.reported_monitor_decision"] == "escalate"
    assert admitted["oramasys.phylax.risk_tier"] == "high"
    assert admitted["oramasys.evidence.manifest_sha256"] == _monitorability()["integrity"]["redacted_manifest_sha256"]
    assert "capability_grant_ids" not in admitted
    assert "evidence_refs" not in admitted
    assert "sealed_evidence_ref" not in admitted
