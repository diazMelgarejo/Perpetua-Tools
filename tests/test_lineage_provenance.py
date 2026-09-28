"""Lineage trust boundary for job submit and replay.

Audit (P2): ``JobSpec.session_id`` and ``parent_orchestrator_id`` are stored
and replayed as correlation metadata. Supervisor dispatch, artifact writes,
and hardware affinity do not read them as authorization. Periscope and
handoff ``session_id`` fields are different types and are out of this contract.
``lineage_trust="verified"`` is reserved and is not produced by HTTP submit
or replay.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orchestrator.fastapi_app import app
from orchestrator.supervisor import (
    JobSpec,
    OrchestrationSupervisor,
    _load_events,
    caller_reported_lineage_metadata,
)


def _queued_spec(sup: OrchestrationSupervisor, job_id: str) -> dict:
    for event in _load_events(sup._jobs_file):
        if event.get("job_id") == job_id and event.get("status") == "queued":
            return event["spec"]
    raise AssertionError(f"no queued spec for {job_id}")
    stamped = caller_reported_lineage_metadata(
        {"lineage_trust": "verified", "model": "qwen"},
        session_id="someone-elses-session",
        parent_orchestrator_id="someone-elses-parent",
    )
    assert stamped["lineage_trust"] == "caller_reported"
    assert stamped["model"] == "qwen"
    assert "verified" not in stamped.values()


def test_helper_omits_trust_label_without_lineage_ids() -> None:
    stamped = caller_reported_lineage_metadata(
        {"lineage_trust": "verified"},
        session_id=None,
        parent_orchestrator_id=None,
    )
    assert "lineage_trust" not in stamped


@pytest.mark.asyncio
async def test_replay_downgrades_stored_verified_lineage(tmp_path: Path) -> None:
    sup = OrchestrationSupervisor(state_dir=tmp_path)
    original = JobSpec(
        intent="echo",
        prompt="hello",
        backend_hint="echo",
        session_id="someone-elses-session",
        parent_orchestrator_id="someone-elses-parent",
        metadata={"lineage_trust": "verified"},
        lineage_trust="verified",
        authenticated_lane="orama",
    )
    job_id = await sup.submit_job(original)
    new_id = await sup.replay(
        job_id,
        overrides={
            "authenticated_lane": "pt",
            "lineage_trust": "verified",
        },
    )
    spec = _queued_spec(sup, new_id)
    assert spec["session_id"] == "someone-elses-session"
    assert spec["parent_orchestrator_id"] == "someone-elses-parent"
    assert spec["lineage_trust"] == "caller_reported"
    assert spec["authenticated_lane"] == "pt"
    assert spec["metadata"]["lineage_trust"] == "caller_reported"


@pytest.mark.asyncio
async def test_replay_without_lineage_stays_compatible(tmp_path: Path) -> None:
    sup = OrchestrationSupervisor(state_dir=tmp_path)
    job_id = await sup.submit_job(
        JobSpec(intent="echo", prompt="hello", backend_hint="echo")
    )
    new_id = await sup.replay(job_id)
    spec = _queued_spec(sup, new_id)
    assert spec["lineage_trust"] == "caller_reported"
    assert spec["session_id"] is None
    assert "lineage_trust" not in spec["metadata"]


def test_insecure_dev_submit_records_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORAMA_INSECURE_DEV", "1")
    captured: dict = {}

    class _Fake:
        async def submit_job(self, spec):
            captured["spec"] = spec
            return spec.job_id

    monkeypatch.setattr("orchestrator.fastapi_app._supervisor", _Fake())
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/v1/jobs",
            json={
                "prompt": "hello",
                "session_id": "someone-elses-session",
                "parent_orchestrator_id": "someone-elses-parent",
                "metadata": {"lineage_trust": "verified"},
            },
        )
    assert response.status_code == 200, response.text
    spec = captured["spec"]
    assert spec.lineage_trust == "caller_reported"
    assert spec.authenticated_lane == "insecure_dev"
    assert spec.metadata["lineage_trust"] == "caller_reported"
