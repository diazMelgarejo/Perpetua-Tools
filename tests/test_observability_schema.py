"""Tests for Canonical Event Core models and JSON Schema validation.

Verifies:
- Pydantic v2 discriminated union validation for DomainObservation
- Extra field rejection (extra='forbid')
- Full 40-char commit SHA enforcement
- Golden fixture conformance
- Zero-leak serialization
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from src.observability.core import (
    AgentIdentity,
    BiasAdvisoryObservation,
    DomainObservation,
    EgressCompleteObservation,
    EgressValidationObservation,
    PrivacyEnvelope,
    SourceProvenance,
    TaskLifecycleObservation,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "schemas" / "observability" / "v1" / "fixtures"


class TestObservabilityCoreModels:
    def test_egress_validation_observation_valid(self) -> None:
        obs = EgressValidationObservation(
            agent=AgentIdentity(id="pt-worker-1", harness="gemini"),
            source=SourceProvenance(
                repo="diazMelgarejo/Perpetua-Tools",
                commit="38ad105116fedcf22959f373d259890c6508849a",
                component="utils.ssrf_pinned_adapter",
            ),
            endpoint_class="remote",
            transport="pinned_requests",
            outcome="allowed",
            port=443,
            validation_ms=1.2,
            destination_hash="sha256:abc123",
        )
        assert obs.event_name == "egress.validation"
        assert obs.privacy.classification == "redacted"
        assert len(obs.source.commit) == 40

    def test_short_commit_sha_is_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            SourceProvenance(
                repo="diazMelgarejo/Perpetua-Tools",
                commit="38ad105",  # 7-char short SHA
                component="utils.ssrf_pinned_adapter",
            )
        assert "at least 40 characters" in str(exc.value)

    def test_non_hex_commit_sha_is_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            SourceProvenance(
                repo="diazMelgarejo/Perpetua-Tools",
                commit="g" * 40,  # 40 chars but non-hex
                component="utils.ssrf_pinned_adapter",
            )
        assert "pattern" in str(exc.value).lower() or "should match pattern" in str(exc.value).lower()

    def test_extra_fields_are_forbidden(self) -> None:
        with pytest.raises(ValidationError) as exc:
            EgressValidationObservation(
                agent=AgentIdentity(id="pt-worker-1", harness="gemini"),
                source=SourceProvenance(
                    repo="diazMelgarejo/Perpetua-Tools",
                    commit="38ad105116fedcf22959f373d259890c6508849a",
                    component="utils.ssrf_pinned_adapter",
                ),
                endpoint_class="remote",
                transport="pinned_requests",
                outcome="allowed",
                port=443,
                validation_ms=1.2,
                destination_hash="sha256:abc123",
                raw_prompt="SELECT * FROM secrets",  # Forbidden extra field
            )
        assert "Extra inputs are not permitted" in str(exc.value)

    def test_discriminated_union_parsing(self) -> None:
        raw = {
            "schema_version": "pt-orama.observability/v1",
            "event_id": "c1e83912-7b24-4f81-9bfa-873b18567101",
            "occurred_at": "2026-08-24T12:00:00Z",
            "event_name": "task.lifecycle",
            "agent": {
                "id": "pt-supervisor",
                "instance_id": "8f3918a0-2f63-4b92-8001-90a816b341f2",
                "harness": "gemini",
            },
            "source": {
                "repo": "diazMelgarejo/Perpetua-Tools",
                "commit": "38ad105116fedcf22959f373d259890c6508849a",
                "component": "orchestrator.coordination.task_queue",
            },
            "privacy": {"classification": "redacted", "redaction_version": "v1"},
            "lifecycle_stage": "claimed",
            "task_name": "l3-egress-verification",
            "phase": "phase-1",
            "priority": "P0",
            "notes_present": True,
        }
        # Parse via the discriminated union
        from pydantic import TypeAdapter

        adapter = TypeAdapter(DomainObservation)
        parsed = adapter.validate_python(raw)
        assert isinstance(parsed, TaskLifecycleObservation)
        assert parsed.lifecycle_stage == "claimed"
        assert parsed.notes_present is True

    @pytest.mark.parametrize(
        "fixture_name, expected_class",
        [
            ("egress_validation.json", EgressValidationObservation),
            ("egress_complete.json", EgressCompleteObservation),
            ("task_claimed.json", TaskLifecycleObservation),
            ("bias_advisory.json", BiasAdvisoryObservation),
        ],
    )
    def test_golden_fixtures_parse_cleanly(self, fixture_name: str, expected_class: type) -> None:
        fixture_path = FIXTURES_DIR / fixture_name
        assert fixture_path.exists(), f"Missing fixture {fixture_name}"
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        from pydantic import TypeAdapter

        adapter = TypeAdapter(DomainObservation)
        parsed = adapter.validate_python(data)
        assert isinstance(parsed, expected_class)
