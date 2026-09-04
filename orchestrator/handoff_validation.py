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
    except (OSError, json.JSONDecodeError) as exc:
        raise HandoffValidationError(
            (HandoffDiagnostic("packet", "invalid_json", f"invalid JSON at {path}: {exc}"),)
        ) from exc
    return validate_handoff_packet(payload)


__all__ = [
    "HandoffPacketV1",
    "HandoffDiagnostic",
    "HandoffValidationError",
    "TestEvidenceV1",
    "load_handoff_packet",
    "validate_handoff_packet",
]
