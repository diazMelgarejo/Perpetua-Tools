import json
import os
from pathlib import Path

import pytest

from orchestrator.periscope_adapter import (
    emit_openclaw_session,
    periscope_agents_dir,
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
    monkeypatch.setenv("PERISCOPE_EMITTER_ENABLED", "true")
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
