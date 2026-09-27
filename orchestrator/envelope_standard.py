"""v1 implementation of the agent envelope standard (doc 69).

Neutral common header, tier rules, and deterministic validators for v1
artifacts. This module is the v1 standard-implementer surface (Perpetua-Tools);
the v2 neutral schema and validators live in ``oramasys/perpetua-core``.

It does not redefine ``HandoffPacketV1`` (the canonical owner of delivery
``task_id``/assignee) or the doc 68 claim contract (the canonical owner of claim
``task_id``/``principal``). It adds the header those contracts already needed,
plus the projection equality rules from doc 69 section 9.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
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

ENVELOPE_KINDS = ("authorship", "status", "delivery", "claim", "round")

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
_FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_OPAQUE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{3,127}$")

Availability = Literal["active", "inactive", "unknown"]
PrivacyTier = Literal["internal_only", "redacted"]


@dataclass(frozen=True)
class EnvelopeDiagnostic:
    """One stable, machine-readable envelope validation finding."""

    field: str
    code: str
    message: str


class EnvelopeStandardError(ValueError):
    """An envelope violates the doc 69 standard."""

    def __init__(self, diagnostics: Sequence[EnvelopeDiagnostic]) -> None:
        self.diagnostics = tuple(diagnostics)
        super().__init__(
            "; ".join(f"{item.field}: {item.message}" for item in self.diagnostics)
        )


def _tz_aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value


def _coerce_dt(value: Any, field: str) -> datetime:
    """Parse the JSON wire form deterministically, then require a timezone.

    JSON has no datetime type, so a string is the only wire representation; the
    parse is explicit here rather than left to lenient coercion.
    """

    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            value = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"{field} must be an ISO-8601 datetime") from exc
    if not isinstance(value, datetime):
        raise ValueError(f"{field} must be an ISO-8601 datetime string")
    return _tz_aware(value, field)


def _coerce_date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise ValueError(f"{field} must be an ISO-8601 date") from exc
    if not isinstance(value, date):
        raise ValueError(f"{field} must be an ISO-8601 date string")
    return value


class AuthorPanel(BaseModel):
    """The card's back face: who the work is about (doc 69 section 3)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    agent_id: str = Field(min_length=1)
    model: str | None = None
    availability: Availability

    @field_validator("agent_id")
    @classmethod
    def _opaque_agent(cls, value: str) -> str:
        if not _OPAQUE_ID_RE.match(value):
            raise ValueError("author.agent_id must be an opaque identifier")
        return value


class ActorPanel(BaseModel):
    """The card's front face: who presents this record now.

    ``principal_id`` is claim-only and is never authentication by itself; Phylax
    verifies the capability proof (doc 69 sections 7 and 9).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    agent_id: str = Field(min_length=1)
    instance_id: str = Field(min_length=1)
    identity_verified: bool
    principal_id: str | None = None

    @field_validator("agent_id", "instance_id")
    @classmethod
    def _opaque_actor(cls, value: str) -> str:
        if not _OPAQUE_ID_RE.match(value):
            raise ValueError("actor identifiers must be opaque")
        return value


class LineagePanel(BaseModel):
    """Present only when author and actor differ; its presence is the signal."""

    model_config = ConfigDict(strict=True, extra="forbid")

    on_behalf_of: str | None = None
    prior_agent: str | None = None
    prior_agent_status: Availability | None = None
    takeover: bool = False
    superseded_ref: str | None = None

    @model_validator(mode="after")
    def _takeover_needs_status(self) -> LineagePanel:
        if self.takeover and self.prior_agent_status is None:
            raise ValueError("lineage.takeover requires prior_agent_status")
        return self


class RedactionPanel(BaseModel):
    """Redaction receipt carried on the card (tamper evidence)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    applied: bool
    policy_version: str | None = None
    fields_dropped: list[str] | None = None
    allowlist_digest: str | None = None

    @field_validator("allowlist_digest")
    @classmethod
    def _digest_shape(cls, value: str | None) -> str | None:
        if value is not None and not _HEX64_RE.match(value):
            raise ValueError("allowlist_digest must be a 64-character hex digest")
        return value


class CorrelationPanel(BaseModel):
    """Conditional correlation identifiers; projections never grant authority."""

    model_config = ConfigDict(strict=True, extra="forbid")

    trace_id: str | None = None
    span_id: str | None = None
    run_id: str | None = None
    task_id: str | None = None
    round_ref: str | None = None


class EnvelopeHeader(BaseModel):
    """Tier U — universal, no default. A missing field is a validation error."""

    model_config = ConfigDict(strict=True, extra="forbid")

    envelope_id: str = Field(min_length=1)
    envelope_schema_version: str = Field(min_length=1)
    envelope_kind: Literal["authorship", "status", "delivery", "claim", "round"]
    created_at: datetime
    privacy_tier: PrivacyTier
    author: AuthorPanel
    actor: ActorPanel
    redaction: RedactionPanel
    content_class: str | None = None
    lineage: LineagePanel | None = None
    correlation: CorrelationPanel | None = None
    expires_at: datetime | None = None

    @field_validator("created_at", mode="before")
    @classmethod
    def _created_tz(cls, value: Any) -> datetime:
        return _coerce_dt(value, "created_at")

    @field_validator("expires_at", mode="before")
    @classmethod
    def _expires_tz(cls, value: Any) -> Any:
        return None if value is None else _coerce_dt(value, "expires_at")

    @model_validator(mode="after")
    def _lineage_iff_divergence(self) -> EnvelopeHeader:
        diverged = self.author.agent_id != self.actor.agent_id
        if diverged and self.lineage is None:
            raise ValueError(
                "lineage is required when author.agent_id != actor.agent_id"
            )
        if not diverged and self.lineage is not None:
            raise ValueError(
                "lineage must be absent when author.agent_id == actor.agent_id"
            )
        if self.actor.principal_id is not None and self.envelope_kind != "claim":
            raise ValueError("actor.principal_id is allowed only on a claim envelope")
        return self


class AuthorshipPanel(BaseModel):
    """Kind panel for ``authorship`` (doc 69 section 4)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    date: date
    evidence_anchors: list[str] = Field(min_length=1)
    rationale_digest: str
    session_id: str = Field(min_length=1)
    salt_mode: Literal["session", "per_record_fallback"]
    salt_chain_ref: str | None = None

    @field_validator("date", mode="before")
    @classmethod
    def _wire_date(cls, value: Any) -> date:
        return _coerce_date(value, "authorship.date")

    @field_validator("rationale_digest")
    @classmethod
    def _digest_never_salt_less(cls, value: str) -> str:
        if not _HEX64_RE.match(value):
            raise ValueError(
                "rationale_digest must be a 64-character hex digest; "
                "a plain hash is non-conformant"
            )
        return value

    @model_validator(mode="after")
    def _fallback_is_recorded(self) -> AuthorshipPanel:
        if self.salt_mode == "per_record_fallback" and not self.salt_chain_ref:
            raise ValueError(
                "per_record_fallback requires salt_chain_ref: the last-resort salt "
                "must be recorded in the hash chain as well as alongside the digest"
            )
        return self


class StatusPanel(BaseModel):
    """Kind panel for ``status`` — observation, never a liveness write."""

    model_config = ConfigDict(strict=True, extra="forbid")

    authority: Literal["read_only"]
    liveness_effect: Literal["none"]
    observed_at: datetime

    @field_validator("observed_at", mode="before")
    @classmethod
    def _observed_tz(cls, value: Any) -> datetime:
        return _coerce_dt(value, "status.observed_at")


class DeliveryPanel(BaseModel):
    """Kind panel for ``delivery`` (doc 69 section 6)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    session_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    assigned_agent_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    branch: str = Field(min_length=1)
    worktree_ref: str = Field(min_length=1)
    starting_head: str
    current_head: str
    commit_sha: str
    files_changed: list[str]
    tests: list[str]
    human_authorized: bool
    merge_authorized: Literal[False]
    deployment_authorized: Literal[False]
    round_ref: str | None = None

    @field_validator("starting_head", "current_head")
    @classmethod
    def _short_sha(cls, value: str) -> str:
        if not _SHA_RE.match(value):
            raise ValueError("must be 7-40 hex characters")
        return value

    @field_validator("commit_sha")
    @classmethod
    def _full_sha(cls, value: str) -> str:
        if not _FULL_SHA_RE.match(value):
            raise ValueError("commit_sha must be exactly 40 hex characters")
        return value


class ClaimPanel(BaseModel):
    """Kind panel for ``claim`` — the doc 68 section 4.2 request fields.

    This standard adds the header only; it never redefines the claim contract.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    operation: Literal[
        "claim", "renew", "complete", "release", "fail", "recover-expired"
    ]
    task_id: str = Field(min_length=1)
    principal: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    expected_task_version: int = Field(ge=0)
    source_ref: str = Field(min_length=1)
    expected_base_sha: str
    capability_proof: str = Field(min_length=1)

    @field_validator("expected_base_sha")
    @classmethod
    def _base_sha(cls, value: str) -> str:
        if not _SHA_RE.match(value):
            raise ValueError("expected_base_sha must be 7-40 hex characters")
        return value


class RoundPanel(BaseModel):
    """Kind panel for the ``round`` sibling (doc 69 section 8)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    round_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    controller_id: str | None = None
    objective_ref: str = Field(min_length=1)
    stop_condition_codes: list[str] = Field(min_length=1)
    ordered_handoff_refs: list[str] = Field(min_length=1)
    authorization_ref: str | None = None
    authority: Literal["coordination_only"]
    liveness_effect: Literal["none"]
    expires_at: datetime

    @field_validator("expires_at", mode="before")
    @classmethod
    def _round_tz(cls, value: Any) -> datetime:
        return _coerce_dt(value, "round.expires_at")


_PANEL_FIELDS = ("authorship", "status", "delivery", "claim", "round")


class AgentEnvelope(BaseModel):
    """A header plus exactly the kind panel its ``envelope_kind`` names.

    Projections are checked for exact equality with their canonical values; a
    mismatch rejects before any state or capability lookup (doc 69 section 9).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    header: EnvelopeHeader
    authorship: AuthorshipPanel | None = None
    status: StatusPanel | None = None
    delivery: DeliveryPanel | None = None
    claim: ClaimPanel | None = None
    round: RoundPanel | None = None

    @model_validator(mode="after")
    def _exactly_one_matching_panel(self) -> AgentEnvelope:
        kind = self.header.envelope_kind
        present = [name for name in _PANEL_FIELDS if getattr(self, name) is not None]
        if present != [kind]:
            raise ValueError(
                f"envelope_kind={kind!r} requires exactly the {kind!r} panel; "
                f"found {present or 'none'}"
            )
        return self

    @model_validator(mode="after")
    def _projections_match_canonical(self) -> AgentEnvelope:
        if self.delivery is not None:
            canonical_task = self.delivery.task_id
        elif self.claim is not None:
            canonical_task = self.claim.task_id
        else:
            canonical_task = None
        correlation = self.header.correlation
        if correlation is not None:
            if (
                correlation.task_id is not None
                and canonical_task is not None
                and correlation.task_id != canonical_task
            ):
                raise ValueError(
                    "correlation.task_id must equal its canonical value; a mismatch "
                    "rejects before state or capability lookup"
                )
            if (
                self.delivery is not None
                and self.delivery.round_ref is not None
                and correlation.round_ref is not None
                and correlation.round_ref != self.delivery.round_ref
            ):
                raise ValueError(
                    "correlation.round_ref must equal delivery.round_ref exactly "
                    "when both appear"
                )
        principal = self.header.actor.principal_id
        if (
            principal is not None
            and self.claim is not None
            and principal != self.claim.principal
        ):
            raise ValueError(
                "actor.principal_id must equal the canonical claim principal"
            )
        return self


def _diagnostics(exc: ValidationError) -> list[EnvelopeDiagnostic]:
    out: list[EnvelopeDiagnostic] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ()))
        out.append(
            EnvelopeDiagnostic(
                field=location or "<envelope>",
                code=str(error.get("type", "invalid")),
                message=str(error.get("msg", "invalid")),
            )
        )
    return out


def validate_envelope(payload: Any) -> AgentEnvelope:
    """Validate one envelope payload against the doc 69 standard."""

    if not isinstance(payload, dict):
        raise EnvelopeStandardError(
            [
                EnvelopeDiagnostic(
                    field="<envelope>",
                    code="not_an_object",
                    message="an envelope must be a mapping",
                )
            ]
        )
    try:
        return AgentEnvelope.model_validate(payload)
    except ValidationError as exc:
        raise EnvelopeStandardError(_diagnostics(exc)) from exc


def load_envelope(path: Path) -> AgentEnvelope:
    """Load and validate an envelope from a JSON file."""

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EnvelopeStandardError(
            [EnvelopeDiagnostic(field=str(path), code="unreadable", message=str(exc))]
        ) from exc
    return validate_envelope(payload)
