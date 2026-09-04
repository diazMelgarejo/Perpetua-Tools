"""Contract tests for machine-readable v1 agent handoffs."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orchestrator.handoff_validation import HandoffValidationError, load_handoff_packet


def _packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "schema_version": 1,
        "session_id": "session-376",
        "job_id": "job-376",
        "task_id": "handoff-validation-v1",
        "assigned_agent_id": "win-autoresearcher",
        "role": "autoresearcher",
        "intent": "Validate the packet before dispatch.",
        "branch": "feat/agent-handoff-validation-v1",
        "worktree": "feature-worktree",
        "starting_head": "1234567",
        "current_head": "89abcde",
        "commit_sha": "89abcde",
        "files_changed": ["orchestrator/handoff_validation.py"],
        "root_cause_addressed": "Free-form handoffs were not machine validated.",
        "tests": [{"command": "python -m pytest tests/test_handoff_validation.py -q", "result": "passed"}],
        "known_risks_or_follow_up": "none",
        "human_authorized": True,
        "merge_authorized": False,
        "deployment_authorized": False,
    }
    packet.update(overrides)
    return packet


def _write_packet(tmp_path: Path, **overrides: object) -> Path:
    path = tmp_path / "handoff.json"
    path.write_text(json.dumps(_packet(**overrides)), encoding="utf-8")
    return path


def test_valid_packet_loads(tmp_path: Path) -> None:
    packet = load_handoff_packet(_write_packet(tmp_path))

    assert packet.current_head == packet.commit_sha
    assert packet.source_ref == packet.branch


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"starting_head": "not-a-sha"}, "starting_head"),
        ({"current_head": "0123456", "commit_sha": "89abcde"}, "commit_sha"),
        ({"tests": []}, "tests"),
        ({"merge_authorized": True}, "merge_authorized"),
        ({"deployment_authorized": True}, "deployment_authorized"),
        ({"human_authorized": 1}, "human_authorized"),
        ({"merge_authorized": 0}, "merge_authorized"),
        ({"schema_version": True}, "schema_version"),
        ({"publish_authorized": True}, "publish_authorized"),
    ],
)
def test_packet_rejects_invalid_or_unauthorized_values(
    tmp_path: Path, overrides: dict[str, object], field: str
) -> None:
    with pytest.raises(HandoffValidationError, match=field):
        load_handoff_packet(_write_packet(tmp_path, **overrides))


def test_packet_exposes_machine_readable_validation_diagnostics(tmp_path: Path) -> None:
    with pytest.raises(HandoffValidationError) as raised:
        load_handoff_packet(
            _write_packet(
                tmp_path,
                starting_head="not-a-sha",
                merge_authorized=True,
            )
        )

    assert {(item.field, item.code) for item in raised.value.diagnostics} >= {
        ("starting_head", "value_error"),
        ("merge_authorized", "literal_error"),
    }


@pytest.mark.parametrize(
    "overrides",
    [
        {"intent": "   "},
        {"files_changed": ["   "]},
        {"tests": [{"command": "  ", "result": "passed"}]},
        {"tests": [{"command": "pytest -q", "result": "  "}]},
    ],
)
def test_packet_rejects_whitespace_only_evidence(tmp_path: Path, overrides: dict[str, object]) -> None:
    with pytest.raises(HandoffValidationError):
        load_handoff_packet(_write_packet(tmp_path, **overrides))


def test_packet_rejects_malformed_json(tmp_path: Path) -> None:
    packet = tmp_path / "broken.json"
    packet.write_text("{not json", encoding="utf-8")

    with pytest.raises(HandoffValidationError, match="JSON"):
        load_handoff_packet(packet)


def test_documented_example_is_valid() -> None:
    example = Path(__file__).parents[1] / "docs" / "coordination" / "examples" / "handoff-packet-v1.json"

    assert load_handoff_packet(example).schema_version == 1
