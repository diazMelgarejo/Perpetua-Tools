"""Canonical Event Core & Domain Observations for pt-orama.

Pydantic v2 discriminated union models enforcing strict schema validation,
zero-leak privacy by construction, full 40-char SHA provenance, and
W3C trace correlation.
Reference: orama-system docs/v2/55-oramasys-agent-observability-contract-adr.md
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field

from utils.egress_telemetry import DenyReason as EgressDenyReason


class AgentIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(..., pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    instance_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    harness: Literal["claude-code", "codex", "hermes", "gemini", "cursor", "standalone"]


class SourceProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    repo: str
    commit: str = Field(..., min_length=40, max_length=40)
    component: str


class PrivacyEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    classification: Literal["redacted", "internal_only"] = "redacted"
    redaction_version: str = "v1"


class BaseObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: str = "pt-orama.observability/v1"
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    run_id: Optional[str] = None
    task_id: Optional[str] = None
    agent: AgentIdentity
    source: SourceProvenance
    privacy: PrivacyEnvelope = Field(default_factory=PrivacyEnvelope)


class EgressValidationObservation(BaseObservation):
    event_name: Literal["egress.validation"] = "egress.validation"
    endpoint_class: Literal["local", "remote"]
    transport: Literal["local_http", "pinned_requests", "vendor_httpx"]
    outcome: Literal["allowed", "denied"]
    deny_reason: Optional[EgressDenyReason] = None
    port: int
    validation_ms: float
    redirect_hop: int = 0
    destination_hash: str


class EgressCompleteObservation(BaseObservation):
    event_name: Literal["egress.request.complete"] = "egress.request.complete"
    endpoint_class: Literal["local", "remote"]
    transport: Literal["local_http", "pinned_requests", "vendor_httpx"]
    outcome: Literal["completed", "failed"]
    status_code: Optional[int] = None
    duration_ms: float
    destination_hash: str


class TaskLifecycleObservation(BaseObservation):
    event_name: Literal["task.lifecycle"] = "task.lifecycle"
    lifecycle_stage: Literal["enqueued", "claimed", "completed", "failed", "abandoned"]
    task_name: str
    phase: str
    priority: str
    assigned_agent: Optional[str] = None
    source_ref: Optional[str] = None
    expected_base_sha: Optional[str] = None
    notes_present: bool = False


class BiasAdvisoryObservation(BaseObservation):
    event_name: Literal["coordination.bias_advisory"] = "coordination.bias_advisory"
    coordination_risk: Literal["low", "medium", "high", "insufficient_evidence"]
    confidence_mean: float
    confidence_stdev: float
    distinct_agent_count: int
    evidence_window_size: int
    rationale_codes: List[str] = Field(default_factory=list)


DomainObservation = Annotated[
    Union[
        EgressValidationObservation,
        EgressCompleteObservation,
        TaskLifecycleObservation,
        BiasAdvisoryObservation,
    ],
    Field(discriminator="event_name"),
]
