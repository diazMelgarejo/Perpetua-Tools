import json
import logging
import os
import tempfile
import time
from pathlib import Path

import pytest

from orchestrator.periscope_adapter import (
    AGENT_ALPHACLAW_ROUTING,
    AGENT_PT_SUPERVISOR,
    DEFAULT_JOB_SESSION_MAX_AGE_DAYS,
    ROUTING_SESSION_ID,
    build_routing_event_payload,
    emit_openclaw_session,
    emit_routing_state,
    job_session_max_age_days,
    maybe_emit_job_observation,
    maybe_emit_routing_observation,
    periscope_agents_dir,
    prune_stale_job_sessions,
    summarize_routing_state,
)


def _lines(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_emitter_is_disabled_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PERISCOPE_EMITTER_ENABLED", raising=False)

    result = emit_openclaw_session(
        state_dir=tmp_path,
        agent_id="pt-supervisor",
        session_id="job-1",
        user_text="plan",
        assistant_text="done",
        started_at="2026-07-28T05:00:00+00:00",
        ended_at="2026-07-28T05:01:00+00:00",
    )

    assert result is None
    assert not (tmp_path / "periscope").exists()


@pytest.mark.parametrize("enabled_value", ["true", "yes", "on", "TRUE"])
def test_emitter_rejects_non_exact_opt_in_values(
    enabled_value: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("PERISCOPE_EMITTER_ENABLED", enabled_value)

    result = emit_openclaw_session(
        state_dir=tmp_path,
        agent_id="pt-supervisor",
        session_id="job-1",
        user_text="plan",
        assistant_text="done",
        started_at="2026-07-28T05:00:00+00:00",
        ended_at="2026-07-28T05:01:00+00:00",
    )

    assert result is None
    assert not (tmp_path / "periscope").exists()


def test_emits_existing_openclaw_session_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("PERISCOPE_EMITTER_ENABLED", "1")

    result = emit_openclaw_session(
        state_dir=tmp_path,
        agent_id="pt-supervisor",
        session_id="job-1",
        user_text="inspect the build",
        assistant_text='{"status":"ok"}',
        started_at="2026-07-28T05:00:00+00:00",
        ended_at="2026-07-28T05:01:00+00:00",
        model="codex",
        cwd="/workspace",
    )

    assert result == (
        tmp_path
        / "periscope"
        / "agents"
        / "pt-supervisor"
        / "sessions"
        / "job-1.jsonl"
    )
    entries = _lines(result)
    assert [entry["type"] for entry in entries] == [
        "session",
        "message",
        "message",
    ]
    assert entries[0] == {
        "type": "session",
        "version": 3,
        "id": "job-1",
        "timestamp": "2026-07-28T05:00:00+00:00",
        "cwd": "/workspace",
    }
    assert entries[1]["message"]["role"] == "user"
    assert entries[1]["message"]["content"] == [
        {"type": "text", "text": "inspect the build"}
    ]
    assert entries[2]["message"]["role"] == "assistant"
    assert entries[2]["message"]["model"] == "codex"
    assert entries[2]["message"]["content"] == [
        {"type": "text", "text": '{"status":"ok"}'}
    ]
    assert "usage" not in entries[2]["message"]
    if os.name != "nt":
        assert result.stat().st_mode & 0o777 == 0o600


def test_agents_dir_is_owned_by_pt_state(tmp_path: Path):
    assert periscope_agents_dir(tmp_path) == tmp_path / "periscope" / "agents"


def test_emission_is_idempotent_for_same_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("PERISCOPE_EMITTER_ENABLED", "1")
    kwargs = {
        "state_dir": tmp_path,
        "agent_id": "pt-supervisor",
        "session_id": "job-1",
        "user_text": "plan",
        "started_at": "2026-07-28T05:00:00+00:00",
        "ended_at": "2026-07-28T05:01:00+00:00",
    }

    first = emit_openclaw_session(assistant_text="first", **kwargs)
    second = emit_openclaw_session(assistant_text="updated", **kwargs)

    assert first == second
    assert _lines(second)[2]["message"]["content"][0]["text"] == "updated"
    assert not list(second.parent.glob("*.tmp"))


def test_failed_fsync_removes_partial_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("PERISCOPE_EMITTER_ENABLED", "1")

    def fail_fsync(_fd: int) -> None:
        raise OSError("simulated fsync failure")

    monkeypatch.setattr(os, "fsync", fail_fsync)
    with pytest.raises(OSError, match="simulated fsync failure"):
        emit_openclaw_session(
            state_dir=tmp_path,
            agent_id="pt-supervisor",
            session_id="job-1",
            user_text="plan",
            assistant_text="done",
            started_at="2026-07-28T05:00:00+00:00",
            ended_at="2026-07-28T05:01:00+00:00",
        )

    session_dir = (
        tmp_path / "periscope" / "agents" / "pt-supervisor" / "sessions"
    )
    assert not list(session_dir.glob("*.tmp"))
    assert not (session_dir / "job-1.jsonl").exists()


@pytest.mark.parametrize(
    ("agent_id", "session_id"),
    [
        ("", "job-1"),
        ("pt-supervisor", ""),
        (".", "job-1"),
        ("..", "job-1"),
        ("../escape", "job-1"),
        ("a/b", "job-1"),
        ("a\\b", "job-1"),
    ],
)
def test_rejects_unsafe_path_components(
    agent_id: str,
    session_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("PERISCOPE_EMITTER_ENABLED", "1")

    with pytest.raises(ValueError):
        emit_openclaw_session(
            state_dir=tmp_path,
            agent_id=agent_id,
            session_id=session_id,
            user_text="plan",
            assistant_text="done",
            started_at="2026-07-28T05:00:00+00:00",
            ended_at="2026-07-28T05:01:00+00:00",
        )


def test_routing_event_payload_materializes_planned_shape():
    state = {
        "manager_backend": "mac-lmstudio",
        "coder_backend": "windows-lmstudio",
        "coder_endpoint": "http://192.168.1.10:1234",
        "distributed": True,
        "scenario_name": "distributed-lmstudio",
    }
    payload = build_routing_event_payload(
        state, ts="2026-07-28T06:00:00+00:00"
    )
    assert payload["event"] == "route"
    assert payload["chosen_backend"] == "windows-lmstudio"
    assert payload["distributed"] is True
    assert payload["scenario_name"] == "distributed-lmstudio"


def test_emit_routing_state_writes_alphaclaw_routing_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("PERISCOPE_EMITTER_ENABLED", "1")
    state = {
        "manager_backend": "mac-lmstudio",
        "coder_backend": "windows-lmstudio",
        "coder_model": "codex",
        "distributed": True,
    }

    result = emit_routing_state(
        state_dir=tmp_path,
        routing_state=state,
        observed_at="2026-07-28T06:00:00+00:00",
    )

    assert result == (
        tmp_path
        / "periscope"
        / "agents"
        / AGENT_ALPHACLAW_ROUTING
        / "sessions"
        / f"{ROUTING_SESSION_ID}.jsonl"
    )
    entries = _lines(result)
    user_payload = json.loads(entries[1]["message"]["content"][0]["text"])
    assert user_payload["event"] == "route"
    assert user_payload["chosen_backend"] == "windows-lmstudio"
    assert entries[2]["message"]["content"][0]["text"] == summarize_routing_state(
        state
    )


def test_routing_emission_is_disabled_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("PERISCOPE_EMITTER_ENABLED", raising=False)

    result = emit_routing_state(
        state_dir=tmp_path,
        routing_state={"coder_backend": "mac-degraded", "distributed": False},
    )

    assert result is None
    assert not (tmp_path / "periscope").exists()


def test_maybe_emit_job_observation_never_raises_and_logs_debug(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    monkeypatch.setenv("PERISCOPE_EMITTER_ENABLED", "1")
    caplog.set_level(logging.DEBUG, logger="orchestrator.periscope_adapter")

    def boom(**_kwargs: object) -> None:
        raise RuntimeError("simulated job emit failure")

    monkeypatch.setattr(
        "orchestrator.periscope_adapter.emit_openclaw_session",
        boom,
    )

    maybe_emit_job_observation(
        state_dir=tmp_path,
        job_id="job-1",
        user_text="plan",
        assistant_text="done",
        started_at="2026-07-28T05:00:00+00:00",
    )

    assert any(
        record.levelname == "DEBUG"
        and "periscope job observation skipped: simulated job emit failure"
        in record.getMessage()
        for record in caplog.records
    )


def test_save_routing_state_emits_to_canonical_state_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    canonical = tmp_path / "canonical-state"
    monkeypatch.chdir(worktree)
    monkeypatch.setenv("PT_STATE_DIR", str(canonical))
    monkeypatch.setenv("PERISCOPE_EMITTER_ENABLED", "1")

    observed_dirs: list[Path] = []

    def capture_emit(
        state_dir: Path | str,
        routing_state: dict,
        *,
        observed_at: str | None = None,
    ) -> None:
        observed_dirs.append(Path(state_dir))

    monkeypatch.setattr(
        "orchestrator.periscope_adapter.resolve_observation_state_dir",
        lambda: canonical,
    )
    monkeypatch.setattr(
        "orchestrator.periscope_adapter.maybe_emit_routing_observation",
        capture_emit,
    )

    from perpetua_tools.agent_launcher import save_routing_state

    save_routing_state({"coder_backend": "mac-degraded", "distributed": False})

    assert observed_dirs == [canonical]
    assert (worktree / ".state" / "routing.json").exists()


def test_maybe_emit_routing_observation_never_raises_and_logs_debug(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    monkeypatch.setenv("PERISCOPE_EMITTER_ENABLED", "1")
    caplog.set_level(logging.DEBUG, logger="orchestrator.periscope_adapter")

    def boom(**_kwargs: object) -> None:
        raise RuntimeError("simulated routing emit failure")

    monkeypatch.setattr(
        "orchestrator.periscope_adapter.emit_routing_state",
        boom,
    )

    maybe_emit_routing_observation(
        tmp_path,
        {"coder_backend": "mac-degraded", "distributed": False},
    )

    assert any(
        record.levelname == "DEBUG"
        and "periscope routing observation skipped: simulated routing emit failure"
        in record.getMessage()
        for record in caplog.records
    )


def test_job_session_max_age_days_defaults_to_33(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("PERISCOPE_JOB_SESSION_MAX_AGE_DAYS", raising=False)
    assert job_session_max_age_days() == DEFAULT_JOB_SESSION_MAX_AGE_DAYS


def test_prune_stale_job_sessions_removes_old_files_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("PERISCOPE_EMITTER_ENABLED", "1")
    session_dir = (
        tmp_path / "periscope" / "agents" / AGENT_PT_SUPERVISOR / "sessions"
    )
    session_dir.mkdir(parents=True)
    stale = session_dir / "old-job.jsonl"
    fresh = session_dir / "new-job.jsonl"
    stale.write_text("stale\n", encoding="utf-8")
    fresh.write_text("fresh\n", encoding="utf-8")

    now = time.time()
    stale_age = now - (DEFAULT_JOB_SESSION_MAX_AGE_DAYS + 1) * 86400
    os.utime(stale, (stale_age, stale_age))
    os.utime(fresh, (now, now))

    removed = prune_stale_job_sessions(tmp_path, now=now)

    assert removed == 1
    assert not stale.exists()
    assert fresh.exists()


def test_prune_skips_when_emitter_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("PERISCOPE_EMITTER_ENABLED", raising=False)
    session_dir = (
        tmp_path / "periscope" / "agents" / AGENT_PT_SUPERVISOR / "sessions"
    )
    session_dir.mkdir(parents=True)
    stale = session_dir / "old-job.jsonl"
    stale.write_text("stale\n", encoding="utf-8")
    old = time.time() - 100 * 86400
    os.utime(stale, (old, old))

    assert prune_stale_job_sessions(tmp_path, now=time.time()) == 0
    assert stale.exists()


def test_maybe_emit_job_observation_prunes_after_emit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("PERISCOPE_EMITTER_ENABLED", "1")
    session_dir = (
        tmp_path / "periscope" / "agents" / AGENT_PT_SUPERVISOR / "sessions"
    )
    session_dir.mkdir(parents=True)
    stale = session_dir / "legacy-job.jsonl"
    stale.write_text("stale\n", encoding="utf-8")
    now = time.time()
    os.utime(stale, (now - 40 * 86400, now - 40 * 86400))

    maybe_emit_job_observation(
        state_dir=tmp_path,
        job_id="job-new",
        user_text="plan",
        assistant_text="done",
        started_at="2026-07-28T05:00:00+00:00",
    )

    assert not stale.exists()
    assert (session_dir / "job-new.jsonl").exists()


def test_periscope_adapter_rejects_remote_url_destination():
    from orchestrator.periscope_adapter import _validate_local_path

    with pytest.raises(ValueError, match="Remote destination URLs and Windows UNC paths are forbidden"):
        _validate_local_path("http://remote-server:8080/trajectories")
    with pytest.raises(ValueError, match="Remote destination URLs and Windows UNC paths are forbidden"):
        _validate_local_path("s3://bucket/trajectories")


def test_periscope_adapter_rejects_unc_path_destinations():
    from orchestrator.periscope_adapter import _validate_local_path

    with pytest.raises(ValueError, match="Remote destination URLs and Windows UNC paths are forbidden"):
        _validate_local_path(r"\\server\share\trajectories")
    with pytest.raises(ValueError, match="Remote destination URLs and Windows UNC paths are forbidden"):
        _validate_local_path("//server/share/trajectories")


def test_periscope_trajectory_strictly_contained_in_state_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PERISCOPE_EMITTER_ENABLED", "1")
    path = emit_openclaw_session(
        state_dir=tmp_path,
        agent_id="pt-supervisor",
        session_id="job-safe-1",
        user_text="test",
        assistant_text="test",
        started_at="2026-08-24T12:00:00Z",
        ended_at="2026-08-24T12:01:00Z",
    )
    assert path is not None
    assert str(path.resolve()).startswith(str(tmp_path.resolve()))


def test_periscope_adapter_never_imports_or_calls_otel():
    import orchestrator.periscope_adapter as pa

    # Verify periscope_adapter has zero imports or dependencies on OTel / OTLP exporter
    assert not hasattr(pa, "export_observation_to_otel")
    assert not hasattr(pa, "OTLPSpanExporter")
    assert not hasattr(pa, "TracerProvider")


def test_rich_trajectory_data_remains_local_and_never_in_redacted_otel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PERISCOPE_EMITTER_ENABLED", "1")
    secret_text = "CRITICAL_INTERNAL_PROMPT_12345"
    path = emit_openclaw_session(
        state_dir=tmp_path,
        agent_id="pt-supervisor",
        session_id="job-local-secret",
        user_text=secret_text,
        assistant_text="Response with internal details",
        started_at="2026-08-24T12:00:00Z",
        ended_at="2026-08-24T12:01:00Z",
    )
    assert path is not None
    local_content = path.read_text(encoding="utf-8")
    assert secret_text in local_content

    # Now verify that OTel projections NEVER contain the secret text
    from src.observability.core import AgentIdentity, EgressCompleteObservation, SourceProvenance
    from src.observability.otel_exporter import project_to_otel_attributes

    obs = EgressCompleteObservation(
        agent=AgentIdentity(id="pt-supervisor", harness="gemini"),
        source=SourceProvenance(
            repo="diazMelgarejo/Perpetua-Tools",
            commit="38ad105116fedcf22959f373d259890c6508849a",
            component="orchestrator.periscope_adapter",
        ),
        endpoint_class="remote",
        transport="pinned_requests",
        outcome="completed",
        status_code=200,
        duration_ms=100.0,
        destination_hash="sha256:abcd",
    )
    otel_attrs = project_to_otel_attributes(obs)
    for val in otel_attrs.values():
        assert secret_text not in str(val)


def test_periscope_boundary_declares_internal_only_classification() -> None:
    import orchestrator.periscope_adapter as adapter

    assert (
        getattr(adapter, "TRAJECTORY_PRIVACY_CLASSIFICATION", None)
        == "internal_only"
    )


@pytest.mark.skipif(os.name == "nt", reason="POSIX dir-fd race regression")
def test_atomic_write_cannot_be_redirected_by_late_session_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PERISCOPE_EMITTER_ENABLED", "1")
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    real_named_temporary_file = tempfile.NamedTemporaryFile

    def swap_session_directory(*args: object, **kwargs: object):
        session_dir = Path(str(kwargs["dir"]))
        session_dir.rmdir()
        session_dir.symlink_to(outside, target_is_directory=True)
        return real_named_temporary_file(*args, **kwargs)

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", swap_session_directory)

    result = emit_openclaw_session(
        state_dir=tmp_path,
        agent_id="pt-supervisor",
        session_id="job-race",
        user_text="private prompt",
        assistant_text="private response",
        started_at="2026-08-24T12:00:00Z",
        ended_at="2026-08-24T12:01:00Z",
    )

    assert result is not None
    assert result.resolve().is_relative_to(tmp_path.resolve())
    assert list(outside.iterdir()) == []
