"""Conformance tests for the v1 agent envelope standard (doc 69)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from orchestrator.envelope_standard import (
    EnvelopeStandardError,
    load_envelope,
    validate_envelope,
)
from orchestrator.handoff_validation import HandoffPacketV1

_NOW = "2026-09-27T00:00:00+00:00"
_FULL_SHA = "a" * 40
_SHA7 = "b" * 7
_DIGEST = "c" * 64


def _header(**overrides: object) -> dict[str, object]:
    header: dict[str, object] = {
        "envelope_id": "env-0001",
        "envelope_schema_version": "1",
        "envelope_kind": "status",
        "created_at": _NOW,
        "privacy_tier": "internal_only",
        "author": {
            "agent_id": "agent-a",
            "model": "grok-4.7",
            "availability": "active",
        },
        "actor": {
            "agent_id": "agent-a",
            "instance_id": "inst-1",
            "identity_verified": True,
        },
        "redaction": {"applied": True},
    }
    header.update(overrides)
    return header


def _status_envelope(**overrides: object) -> dict[str, object]:
    envelope: dict[str, object] = {
        "header": _header(),
        "status": {
            "authority": "read_only",
            "liveness_effect": "none",
            "observed_at": _NOW,
        },
    }
    envelope.update(overrides)
    return envelope


def _authorship_panel(**overrides: object) -> dict[str, object]:
    panel: dict[str, object] = {
        "date": "2026-09-27",
        "evidence_anchors": ["board-record-3770"],
        "rationale_digest": _DIGEST,
        "session_id": "sess-1",
        "salt_mode": "session",
    }
    panel.update(overrides)
    return panel


def _claim_panel(**overrides: object) -> dict[str, object]:
    panel: dict[str, object] = {
        "operation": "claim",
        "task_id": "task-1",
        "principal": "principal-a",
        "idempotency_key": "idem-1",
        "expected_task_version": 1,
        "source_ref": "refs/heads/main",
        "expected_base_sha": _FULL_SHA,
        "capability_proof": "opaque-proof",
    }
    panel.update(overrides)
    return panel


def _handoff_packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "schema_version": 1,
        "session_id": "session-376",
        "job_id": "job-376",
        "task_id": "task-1",
        "assigned_agent_id": "agent-a",
        "role": "coder",
        "intent": "Validate the packet before dispatch.",
        "branch": "feat/envelope-standard",
        "worktree": "feature-worktree",
        "starting_head": _SHA7,
        "current_head": _FULL_SHA,
        "commit_sha": _FULL_SHA,
        "files_changed": ["orchestrator/envelope_standard.py"],
        "root_cause_addressed": "Delivery must retain its native validator.",
        "tests": [{"command": "pytest -q", "result": "passed"}],
        "known_risks_or_follow_up": "none",
        "human_authorized": True,
        "merge_authorized": False,
        "deployment_authorized": False,
    }
    packet.update(overrides)
    return packet


def test_minimal_status_envelope_is_conformant() -> None:
    envelope = validate_envelope(_status_envelope())
    assert envelope.header.envelope_kind == "status"
    assert envelope.status is not None


@pytest.mark.parametrize(
    "field", ["envelope_id", "envelope_schema_version", "created_at", "privacy_tier"]
)
def test_tier_u_fields_carry_no_default(field: str) -> None:
    header = _header()
    header.pop(field)
    with pytest.raises(EnvelopeStandardError) as excinfo:
        validate_envelope(_status_envelope(header=header))
    assert any(field in item.field for item in excinfo.value.diagnostics)


def test_unknown_field_is_forbidden() -> None:
    header = _header()
    header["relay_path"] = "/tmp/secret"
    with pytest.raises(EnvelopeStandardError):
        validate_envelope(_status_envelope(header=header))


def test_created_at_must_be_timezone_aware() -> None:
    header = _header(created_at="2026-09-27T00:00:00")
    with pytest.raises(EnvelopeStandardError):
        validate_envelope(_status_envelope(header=header))


def test_lineage_required_when_author_and_actor_differ() -> None:
    header = _header(
        actor={
            "agent_id": "agent-b",
            "instance_id": "inst-2",
            "identity_verified": True,
        }
    )
    with pytest.raises(EnvelopeStandardError):
        validate_envelope(_status_envelope(header=header))
    header["lineage"] = {"prior_agent": "agent-a", "prior_agent_status": "inactive"}
    envelope = validate_envelope(_status_envelope(header=header))
    assert envelope.header.lineage is not None


def test_lineage_must_be_absent_when_ids_match() -> None:
    header = _header(lineage={"prior_agent": "agent-a"})
    with pytest.raises(EnvelopeStandardError):
        validate_envelope(_status_envelope(header=header))


def test_takeover_requires_prior_agent_status() -> None:
    header = _header(
        actor={
            "agent_id": "agent-b",
            "instance_id": "inst-2",
            "identity_verified": True,
        },
        lineage={"takeover": True},
    )
    with pytest.raises(EnvelopeStandardError):
        validate_envelope(_status_envelope(header=header))


def test_availability_is_an_observation_not_authority() -> None:
    header = _header(
        author={"agent_id": "agent-a", "model": "grok-4.7", "availability": "unknown"}
    )
    envelope = validate_envelope(_status_envelope(header=header))
    assert envelope.header.author.availability == "unknown"
    assert "liveness_effect" not in envelope.header.author.model_dump()


def test_digest_never_salt_less() -> None:
    panel = _authorship_panel(rationale_digest="deadbeef")
    with pytest.raises(EnvelopeStandardError):
        validate_envelope(
            {"header": _header(envelope_kind="authorship"), "authorship": panel}
        )


def test_digest_requires_session_id() -> None:
    panel = _authorship_panel()
    panel.pop("session_id")
    with pytest.raises(EnvelopeStandardError):
        validate_envelope(
            {"header": _header(envelope_kind="authorship"), "authorship": panel}
        )


def test_per_record_fallback_must_be_recorded_in_hash_chain() -> None:
    panel = _authorship_panel(salt_mode="per_record_fallback")
    with pytest.raises(EnvelopeStandardError):
        validate_envelope(
            {"header": _header(envelope_kind="authorship"), "authorship": panel}
        )
    panel["salt_chain_ref"] = "chain-0001"
    envelope = validate_envelope(
        {"header": _header(envelope_kind="authorship"), "authorship": panel}
    )
    assert envelope.authorship is not None


def test_kind_requires_exactly_its_own_panel() -> None:
    with pytest.raises(EnvelopeStandardError):
        validate_envelope({"header": _header(envelope_kind="delivery"), "status": None})
    with pytest.raises(EnvelopeStandardError):
        validate_envelope(
            {
                "header": _header(envelope_kind="status"),
                "status": {
                    "authority": "read_only",
                    "liveness_effect": "none",
                    "observed_at": _NOW,
                },
                "delivery": _handoff_packet(),
            }
        )


def test_status_panel_literals_are_enforced() -> None:
    with pytest.raises(EnvelopeStandardError):
        validate_envelope(
            _status_envelope(
                status={
                    "authority": "write",
                    "liveness_effect": "none",
                    "observed_at": _NOW,
                }
            )
        )


def test_delivery_uses_the_native_handoff_sha_rules() -> None:
    envelope = validate_envelope(
        {
            "header": _header(envelope_kind="delivery"),
            "delivery": _handoff_packet(),
        }
    )
    assert envelope.delivery is not None
    with pytest.raises(EnvelopeStandardError):
        validate_envelope(
            {
                "header": _header(envelope_kind="delivery"),
                "delivery": _handoff_packet(commit_sha="not-a-sha"),
            }
        )


def test_delivery_cannot_authorize_merge_or_deployment() -> None:
    with pytest.raises(EnvelopeStandardError):
        validate_envelope(
            {
                "header": _header(envelope_kind="delivery"),
                "delivery": _handoff_packet(merge_authorized=True),
            }
        )


def test_claim_panel_maps_doc68_and_forbids_unknown_fields() -> None:
    envelope = validate_envelope(
        {"header": _header(envelope_kind="claim"), "claim": _claim_panel()}
    )
    assert envelope.claim is not None
    assert set(envelope.claim.model_dump()) == {
        "operation",
        "task_id",
        "principal",
        "idempotency_key",
        "expected_task_version",
        "source_ref",
        "expected_base_sha",
        "capability_proof",
    }
    with pytest.raises(EnvelopeStandardError):
        validate_envelope(
            {
                "header": _header(envelope_kind="claim"),
                "claim": _claim_panel(lease_token="not-doc68"),
            }
        )


def test_actor_principal_id_is_claim_only() -> None:
    header = _header(
        actor={
            "agent_id": "agent-a",
            "instance_id": "inst-1",
            "identity_verified": True,
            "principal_id": "principal-a",
        }
    )
    with pytest.raises(EnvelopeStandardError):
        validate_envelope(_status_envelope(header=header))


def test_projection_mismatch_rejects_before_lookup() -> None:
    header = _header(envelope_kind="claim", correlation={"task_id": "other-task"})
    with pytest.raises(EnvelopeStandardError):
        validate_envelope({"header": header, "claim": _claim_panel()})
    matching = _header(envelope_kind="claim", correlation={"task_id": "task-1"})
    envelope = validate_envelope({"header": matching, "claim": _claim_panel()})
    assert envelope.header.correlation is not None


def test_round_ref_projection_must_match_delivery() -> None:
    # both sides present and disagreeing -> reject (doc 69 section 9)
    mismatch = _header(envelope_kind="delivery", correlation={"round_ref": "round-9"})
    with pytest.raises(EnvelopeStandardError):
        validate_envelope(
            {"header": mismatch, "delivery": _handoff_packet(round_ref="r-1")}
        )
    # both sides present and equal -> accept
    matching = _header(envelope_kind="delivery", correlation={"round_ref": "r-1"})
    envelope = validate_envelope(
        {"header": matching, "delivery": _handoff_packet(round_ref="r-1")}
    )
    assert envelope.delivery is not None
    # only the projection appears: the rule applies when both appear
    lone = _header(envelope_kind="delivery", correlation={"round_ref": "round-9"})
    assert validate_envelope({"header": lone, "delivery": _handoff_packet()})


def test_claim_principal_projection_must_match_canonical() -> None:
    header = _header(
        envelope_kind="claim",
        actor={
            "agent_id": "agent-a",
            "instance_id": "inst-1",
            "identity_verified": True,
            "principal_id": "principal-b",
        },
    )
    with pytest.raises(EnvelopeStandardError):
        validate_envelope({"header": header, "claim": _claim_panel()})


def test_privacy_tier_vocabulary_and_content_class_are_orthogonal() -> None:
    header = _header(privacy_tier="secret")
    with pytest.raises(EnvelopeStandardError):
        validate_envelope(_status_envelope(header=header))
    header = _header(privacy_tier="internal_only", content_class="telemetry")
    envelope = validate_envelope(_status_envelope(header=header))
    assert envelope.header.content_class == "telemetry"


def test_non_mapping_and_unreadable_file_are_diagnosed(tmp_path: Path) -> None:
    with pytest.raises(EnvelopeStandardError) as excinfo:
        validate_envelope(["not", "a", "mapping"])
    assert excinfo.value.diagnostics[0].code == "not_an_object"
    with pytest.raises(EnvelopeStandardError) as missing:
        load_envelope(tmp_path / "absent.json")
    assert missing.value.diagnostics[0].code == "unreadable"


def test_load_envelope_round_trips_a_valid_file(tmp_path: Path) -> None:
    path = tmp_path / "envelope.json"
    path.write_text(json.dumps(_status_envelope()), encoding="utf-8")
    envelope = load_envelope(path)
    assert envelope.header.envelope_id == "env-0001"


def test_delivery_delegates_to_the_native_handoff_validator() -> None:
    envelope = validate_envelope(
        {
            "header": _header(envelope_kind="delivery"),
            "delivery": _handoff_packet(),
        }
    )
    assert isinstance(envelope.delivery, HandoffPacketV1)


def test_round_is_not_an_agent_envelope_kind() -> None:
    with pytest.raises(EnvelopeStandardError):
        validate_envelope(
            {
                "header": _header(envelope_kind="round"),
                "round": {
                    "round_id": "round-1",
                    "session_id": "session-376",
                    "objective_ref": "objective-1",
                    "stop_condition_codes": ["complete"],
                    "ordered_handoff_refs": ["handoff-1"],
                    "authority": "coordination_only",
                    "liveness_effect": "none",
                    "expires_at": _NOW,
                },
            }
        )
