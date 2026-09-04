"""Typed v1 handoff packets for safe agent-dispatch admission."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Sequence

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)


_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
_TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_SPAN_ID_RE = re.compile(r"^[0-9a-f]{16}$")
_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_OPAQUE_REFERENCE_RE = re.compile(r"^(?:evidence|sealed|grant)_[0-9a-f]{16,64}$")
_MONITORABILITY_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")


@dataclass(frozen=True)
class HandoffDiagnostic:
    """One stable, machine-readable handoff validation finding."""

    field: str
    code: str
    message: str


class HandoffValidationError(ValueError):
    """A handoff packet is malformed, incomplete, or requests forbidden authority."""

    def __init__(self, diagnostics: Sequence[HandoffDiagnostic]) -> None:
        self.diagnostics = tuple(diagnostics)
        super().__init__(
            "; ".join(f"{item.field}: {item.message}" for item in self.diagnostics)
        )


class TestEvidenceV1(BaseModel):
    """One executable verification command and its observed result."""

    model_config = ConfigDict(strict=True, extra="forbid")

    command: str = Field(min_length=1)
    result: str = Field(min_length=1)

    @field_validator("command", "result")
    @classmethod
    def _nonblank_evidence(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class OTelGenAiContextV1(BaseModel):
    """Redacted OTel-compatible context for a monitorability handoff."""

    model_config = ConfigDict(strict=True, extra="forbid")

    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    operation_name: Literal["invoke_agent", "invoke_workflow", "plan", "execute_tool"]
    provider_name: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    agent_name: str | None = None
    agent_version: str | None = None
    request_model: str | None = None
    conversation_id: str | None = None

    @field_validator("trace_id")
    @classmethod
    def _valid_trace_id(cls, value: str | None) -> str | None:
        if value is not None and not _TRACE_ID_RE.fullmatch(value):
            raise ValueError("must be a 32 character lowercase hexadecimal W3C trace ID")
        return value

    @field_validator("span_id", "parent_span_id")
    @classmethod
    def _valid_span_id(cls, value: str | None) -> str | None:
        if value is not None and not _SPAN_ID_RE.fullmatch(value):
            raise ValueError("must be a 16 character lowercase hexadecimal W3C span ID")
        return value

    @field_validator("provider_name", "agent_id", "agent_name", "agent_version", "request_model", "conversation_id")
    @classmethod
    def _bounded_identifier(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _MONITORABILITY_IDENTIFIER_RE.fullmatch(value):
            raise ValueError("must be a bounded identifier, not free-form content")
        return value

    @model_validator(mode="after")
    def _trace_and_span_are_paired(self) -> "OTelGenAiContextV1":
        if (self.trace_id is None) != (self.span_id is None):
            raise ValueError("trace_id and span_id must be supplied together or both absent")
        if self.parent_span_id is not None and self.trace_id is None:
            raise ValueError("parent_span_id requires trace_id and span_id")
        if self.parent_span_id == self.span_id and self.parent_span_id is not None:
            raise ValueError("parent_span_id must not equal span_id")
        return self


class PhylaxMonitorabilityContextV1(BaseModel):
    """Caller-reported, redacted v1 monitorability context without authority."""

    model_config = ConfigDict(strict=True, extra="forbid")

    policy_pack_id: str = Field(min_length=1)
    policy_pack_version: str = Field(min_length=1)
    risk_tier: Literal["low", "medium", "high", "critical"]
    capability_grant_ids: list[str] = Field(min_length=1)
    reported_monitor_decision: Literal["allow", "warn", "escalate"]
    severity: Literal["info", "low", "medium", "high", "critical"]
    confidence: float
    escalation_state: Literal["none", "queued_for_review", "human_review_required"]
    retention_class: Literal["ephemeral", "incident_scoped", "user_authorized"]
    reasoning_availability: Literal["none", "provider_summary", "user_owned_raw", "sealed_reference"]
    sealed_evidence_ref: str | None = None
    evidence_refs: list[str] = Field(min_length=1)

    @field_validator("policy_pack_id", "policy_pack_version")
    @classmethod
    def _bounded_policy_identifier(cls, value: str) -> str:
        if not _MONITORABILITY_IDENTIFIER_RE.fullmatch(value):
            raise ValueError("must be a bounded identifier, not free-form content")
        return value

    @field_validator("capability_grant_ids", "evidence_refs")
    @classmethod
    def _opaque_reference_list(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("must not contain duplicate opaque references")
        if any(not _OPAQUE_REFERENCE_RE.fullmatch(item) for item in value):
            raise ValueError("must contain only opaque evidence, sealed, or grant references")
        return value

    @field_validator("sealed_evidence_ref")
    @classmethod
    def _opaque_sealed_reference(cls, value: str | None) -> str | None:
        if value is not None and not _OPAQUE_REFERENCE_RE.fullmatch(value):
            raise ValueError("must be an opaque sealed reference")
        return value

    @field_validator("confidence")
    @classmethod
    def _finite_confidence(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("must be between 0.0 and 1.0")
        return value

    @model_validator(mode="after")
    def _sealed_reference_matches_availability(self) -> "PhylaxMonitorabilityContextV1":
        if (self.reasoning_availability == "sealed_reference") != (self.sealed_evidence_ref is not None):
            raise ValueError("sealed_evidence_ref is required only for sealed_reference availability")
        return self


class RedactedEvidencePolicyV1(BaseModel):
    """Packet-local privacy facts; separate policy controls authorize export later."""

    model_config = ConfigDict(strict=True, extra="forbid")

    classification: Literal["redacted"]
    redaction_profile_id: str = Field(min_length=1)
    export_allowed: Literal[False]
    raw_reasoning_persisted_in_packet: Literal[False]
    raw_reasoning_exported: Literal[False]

    @field_validator("redaction_profile_id")
    @classmethod
    def _bounded_profile_identifier(cls, value: str) -> str:
        if not _MONITORABILITY_IDENTIFIER_RE.fullmatch(value):
            raise ValueError("must be a bounded identifier, not free-form content")
        return value


class EvidenceIntegrityV1(BaseModel):
    """Syntax and ordering checks for redacted evidence provenance in v1."""

    model_config = ConfigDict(strict=True, extra="forbid")

    provenance_commit_sha: str
    ordered_evidence_refs: list[str] = Field(min_length=1)
    redacted_manifest_sha256: str

    @field_validator("provenance_commit_sha")
    @classmethod
    def _full_lowercase_sha(cls, value: str) -> str:
        if not _FULL_SHA_RE.fullmatch(value):
            raise ValueError("must be a 40 character lowercase hexadecimal Git SHA")
        return value

    @field_validator("redacted_manifest_sha256")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if not _SHA256_RE.fullmatch(value):
            raise ValueError("must be a 64 character lowercase hexadecimal SHA-256 digest")
        return value

    @field_validator("ordered_evidence_refs")
    @classmethod
    def _ordered_opaque_references(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value) or any(not _OPAQUE_REFERENCE_RE.fullmatch(item) for item in value):
            raise ValueError("must contain unique opaque references")
        return value


class MonitorabilityEnvelopeV1(BaseModel):
    """Strict, privacy-redacted v1 bridge from PT handoffs to future Phylax."""

    model_config = ConfigDict(strict=True, extra="forbid")

    schema_version: Literal[1]
    otel: OTelGenAiContextV1 | None = None
    phylax: PhylaxMonitorabilityContextV1
    privacy: RedactedEvidencePolicyV1
    integrity: EvidenceIntegrityV1

    @model_validator(mode="after")
    def _evidence_order_matches_context(self) -> "MonitorabilityEnvelopeV1":
        if self.integrity.ordered_evidence_refs != self.phylax.evidence_refs:
            raise ValueError("integrity.ordered_evidence_refs must equal phylax.evidence_refs")
        return self


class HandoffPacketV1(BaseModel):
    """Machine source of truth for one pre-dispatch handoff in v1."""

    model_config = ConfigDict(strict=True, extra="forbid")

    schema_version: Literal[1]
    session_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    assigned_agent_id: str = Field(min_length=1)
    role: Literal["orchestrator", "researcher", "autoresearcher", "coder", "verifier", "executor"]
    intent: str = Field(min_length=1)
    branch: str = Field(min_length=1)
    worktree: str = Field(min_length=1)
    starting_head: str
    current_head: str
    commit_sha: str
    files_changed: list[str] = Field(min_length=1)
    root_cause_addressed: str = Field(min_length=1)
    tests: list[TestEvidenceV1] = Field(min_length=1)
    known_risks_or_follow_up: str = Field(min_length=1)
    human_authorized: Literal[True]
    merge_authorized: Literal[False]
    deployment_authorized: Literal[False]
    monitorability: MonitorabilityEnvelopeV1 | None = None

    @field_validator("schema_version", mode="before")
    @classmethod
    def _schema_version_is_plain_int(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("must be the integer 1, not a coerced value")
        return value

    @field_validator(
        "human_authorized", "merge_authorized", "deployment_authorized", mode="before"
    )
    @classmethod
    def _authority_is_plain_bool(cls, value: object) -> object:
        if type(value) is not bool:
            raise ValueError("must be a JSON boolean, not a coerced value")
        return value

    @field_validator(
        "session_id",
        "job_id",
        "task_id",
        "assigned_agent_id",
        "intent",
        "branch",
        "worktree",
        "root_cause_addressed",
        "known_risks_or_follow_up",
    )
    @classmethod
    def _nonblank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("starting_head", "current_head", "commit_sha")
    @classmethod
    def _valid_sha(cls, value: str) -> str:
        if not _SHA_RE.fullmatch(value):
            raise ValueError("must be a 7-40 character hexadecimal Git SHA")
        return value.lower()

    @field_validator("files_changed")
    @classmethod
    def _nonempty_changed_paths(cls, value: list[str]) -> list[str]:
        if any(not path.strip() for path in value):
            raise ValueError("must not contain empty paths")
        return value

    @model_validator(mode="after")
    def _head_matches_commit(self) -> "HandoffPacketV1":
        if self.current_head != self.commit_sha:
            raise ValueError("commit_sha must equal current_head")
        return self

    @property
    def source_ref(self) -> str:
        """The existing queue field that records the branch source line."""
        return self.branch

    @property
    def expected_base_sha(self) -> str:
        """The existing queue field that records the starting source SHA."""
        return self.starting_head


def _validation_diagnostics(error: ValidationError) -> tuple[HandoffDiagnostic, ...]:
    details: list[HandoffDiagnostic] = []
    for item in error.errors(include_url=False):
        location = ".".join(str(part) for part in item["loc"]) or "packet"
        details.append(
            HandoffDiagnostic(
                field=location,
                code=item["type"],
                message=item["msg"],
            )
        )
    return tuple(details)


def validate_handoff_packet(payload: Any) -> HandoffPacketV1:
    """Validate parsed JSON and expose only a stable caller-facing exception."""
    try:
        return HandoffPacketV1.model_validate(payload)
    except ValidationError as exc:
        raise HandoffValidationError(_validation_diagnostics(exc)) from exc


def load_handoff_packet(path: Path) -> HandoffPacketV1:
    """Load and validate a UTF-8 JSON handoff file without leaking parser internals."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HandoffValidationError(
            (HandoffDiagnostic("packet", "invalid_json", f"invalid JSON at {path}: {exc}"),)
        ) from exc
    return validate_handoff_packet(payload)


__all__ = [
    "EvidenceIntegrityV1",
    "HandoffPacketV1",
    "HandoffDiagnostic",
    "HandoffValidationError",
    "MonitorabilityEnvelopeV1",
    "OTelGenAiContextV1",
    "PhylaxMonitorabilityContextV1",
    "RedactedEvidencePolicyV1",
    "TestEvidenceV1",
    "load_handoff_packet",
    "validate_handoff_packet",
]
