"""Operator-only deterministic smoke for the configured PT OTLP pipeline.

Usage:
    python -m src.observability.smoke

The command accepts no user payload or destination arguments.  The collector
endpoint remains configuration-only through the normal OTel environment.
"""
from __future__ import annotations

import json

from src.observability.core import PrivacyEnvelope
from src.observability.otel_exporter import export_observation_to_otel
from src.observability.runtime import (
    build_egress_observation,
    force_flush_observability,
    initialize_observability,
    observe_egress_event,
)
from utils.egress_telemetry import EgressEvent


def run_smoke() -> dict[str, object]:
    event = EgressEvent(
        event_kind="complete",
        endpoint_class="remote",
        host="pt-otel-smoke.invalid",
        port=443,
        scheme="https",
        duration_ms=1.0,
        status_code=204,
    )
    state = initialize_observability()
    observation = build_egress_observation(event)
    submitted = observe_egress_event(event) if state.enabled and observation is not None else False
    flushed = force_flush_observability(timeout_ms=5000) if submitted else False

    internal_only_rejected = False
    if observation is not None:
        internal_only = observation.model_copy(
            update={"privacy": PrivacyEnvelope(classification="internal_only")}
        )
        try:
            export_observation_to_otel(internal_only)
        except PermissionError:
            internal_only_rejected = True

    return {
        "configured": state.enabled,
        "observation_constructed": observation is not None,
        "export_submitted": submitted,
        "flushed": flushed,
        "privacy_classification": "redacted",
        "internal_only_rejected": internal_only_rejected,
        "reason": state.reason,
    }


def main() -> int:
    result = run_smoke()
    print(json.dumps(result, sort_keys=True))
    return 0 if all(
        result[key]
        for key in (
            "configured",
            "observation_constructed",
            "export_submitted",
            "flushed",
            "internal_only_rejected",
        )
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
