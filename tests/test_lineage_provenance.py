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
    JobStatus,
    OrchestrationSupervisor,
    _append_event,
    _load_events,
    caller_reported_lineage_metadata,
)


def test_helper_strips_forged_verified_trust() -> None:
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
        prompt="preserve this terminal replay prompt",
        backend_hint="echo",
        constraints={"max_tokens": 55},
        metadata={"lineage_trust": "verified", "model": "echo-model"},
        role="reviewer",
        specialization="replay",
        session_id="someone-elses-session",
        parent_orchestrator_id="someone-elses-parent",
        artifact_policy="retain",
        task_type="review",
        lineage_trust="verified",
        authenticated_lane="orama",
    )
    job_id = await sup.submit_job(original)
    task = sup._active.get(job_id)
    assert task is not None
    await task

    terminal = await sup.get_status(job_id)
    assert terminal is not None
    assert terminal["status"] == "succeeded"
    assert "spec" not in terminal

    new_id = await sup.replay(
        job_id,
        overrides={
            "authenticated_lane": "pt",
            "lineage_trust": "verified",
        },
    )
    events = _load_events(sup._jobs_file)
    queued = next(
        event
        for event in events
        if event.get("job_id") == new_id
        and event.get("status") == JobStatus.QUEUED.value
    )
    spec = queued["spec"]
    assert spec["intent"] == "echo"
    assert spec["prompt"] == "preserve this terminal replay prompt"
    assert spec["backend_hint"] == "echo"
    assert spec["constraints"] == {"max_tokens": 55}
    assert spec["metadata"]["model"] == "echo-model"
    assert spec["role"] == "reviewer"
    assert spec["specialization"] == "replay"
    assert spec["session_id"] == "someone-elses-session"
    assert spec["parent_orchestrator_id"] == "someone-elses-parent"
    assert spec["artifact_policy"] == "retain"
    assert spec["task_type"] == "review"
    assert spec["lineage_trust"] == "caller_reported"
    assert spec["authenticated_lane"] == "pt"
    assert spec["metadata"]["lineage_trust"] == "caller_reported"
    assert queued["lineage_trust"] == "caller_reported"

    task = sup._active.get(new_id)
    assert task is not None
    await task
    status = await sup.get_status(new_id)
    assert status is not None
    assert terminal["lineage_trust"] == "verified"
    assert status["lineage_trust"] == "caller_reported"


@pytest.mark.asyncio
async def test_replay_without_lineage_stays_compatible(tmp_path: Path) -> None:
    sup = OrchestrationSupervisor(state_dir=tmp_path)
    job_id = await sup.submit_job(
        JobSpec(intent="echo", prompt="hello", backend_hint="echo")
    )
    original = sup._active.get(job_id)
    assert original is not None
    await original

    new_id = await sup.replay(job_id)
    events = _load_events(sup._jobs_file)
    queued = next(
        event
        for event in events
        if event.get("job_id") == new_id
        and event.get("status") == JobStatus.QUEUED.value
    )
    spec = queued["spec"]
    assert spec["lineage_trust"] == "caller_reported"
    assert spec["session_id"] is None
    assert "lineage_trust" not in spec["metadata"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.WAITING_INPUT],
)
async def test_replay_rejects_a_job_still_in_flight(
    tmp_path: Path,
    status: JobStatus,
) -> None:
    sup = OrchestrationSupervisor(state_dir=tmp_path)
    job_id = "in-flight-job"
    _append_event(
        tmp_path / "jobs.jsonl",
        job_id,
        {
            "status": JobStatus.QUEUED.value,
            "spec": JobSpec(intent="echo", prompt="still running").model_dump(),
        },
    )
    if status is not JobStatus.QUEUED:
        _append_event(
            tmp_path / "jobs.jsonl",
            job_id,
            {"status": status.value},
        )

    with pytest.raises(ValueError, match="not replayable"):
        await sup.replay(job_id)


@pytest.mark.asyncio
async def test_replay_rejects_job_without_a_queued_spec(tmp_path: Path) -> None:
    sup = OrchestrationSupervisor(state_dir=tmp_path)
    _append_event(
        tmp_path / "jobs.jsonl",
        "incomplete-job",
        {"status": JobStatus.SUCCEEDED.value},
    )

    with pytest.raises(ValueError, match="queued specification"):
        await sup.replay("incomplete-job")


def test_insecure_dev_submit_records_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORAMA_INSECURE_DEV", "1")
    captured: dict = {}

    class _Fake:
        async def submit_job(self, spec):
            captured["spec"] = spec
            return spec.job_id

    monkeypatch.setattr(
        "orchestrator.fastapi_app._get_supervisor",
        lambda: _Fake(),
    )
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
