"""PT-owned adapter for Periscope's existing OpenClaw session parser.

The adapter writes observation-only, OpenClaw-compatible JSONL under PT state.
Periscope consumes the directory through its existing ``openclaw_dirs`` setting;
no Periscope parser, route, or orchestration function is required.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EMITTER_ENABLED_ENV = "PERISCOPE_EMITTER_ENABLED"
AGENT_PT_SUPERVISOR = "pt-supervisor"
AGENT_ALPHACLAW_ROUTING = "alphaclaw-routing"
ROUTING_SESSION_ID = "routing-latest"
_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_LOG = logging.getLogger(__name__)


def emitter_enabled() -> bool:
    """Return whether optional Periscope observation emission is enabled."""

    return os.getenv(EMITTER_ENABLED_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def periscope_agents_dir(state_dir: Path | str) -> Path:
    """Return the PT-owned agent root to add to Periscope ``openclaw_dirs``."""

    return Path(state_dir) / "periscope" / "agents"


def _validate_component(label: str, value: str) -> str:
    normalized = str(value or "").strip()
    if not _SAFE_COMPONENT.fullmatch(normalized):
        raise ValueError(
            f"{label} must start with a letter or digit and contain only "
            "[A-Za-z0-9._-]"
        )
    return normalized


def _text_block(text: str) -> list[dict[str, str]]:
    return [{"type": "text", "text": str(text)}]


def _message_entry(
    *,
    message_id: str,
    role: str,
    text: str,
    timestamp: str,
    model: str = "",
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "role": role,
        "content": _text_block(text),
        "timestamp": timestamp,
    }
    if model:
        message["model"] = model
    return {
        "type": "message",
        "id": message_id,
        "timestamp": timestamp,
        "message": message,
    }


def emit_openclaw_session(
    *,
    state_dir: Path | str,
    agent_id: str,
    session_id: str,
    user_text: str,
    assistant_text: str,
    started_at: str,
    ended_at: str,
    model: str = "",
    cwd: str = "",
) -> Path | None:
    """Atomically emit one deterministic OpenClaw-compatible observation.

    Returns ``None`` when the optional adapter is disabled. Re-emitting the same
    ``agent_id``/``session_id`` atomically replaces the prior observation.
    """

    if not emitter_enabled():
        return None

    safe_agent = _validate_component("agent_id", agent_id)
    safe_session = _validate_component("session_id", session_id)
    if not started_at or not ended_at:
        raise ValueError("started_at and ended_at are required")

    state_path = Path(state_dir)
    state_path.mkdir(parents=True, exist_ok=True)
    agents_dir = periscope_agents_dir(state_path)
    session_dir = agents_dir / safe_agent / "sessions"
    for directory in (
        agents_dir.parent,
        agents_dir,
        agents_dir / safe_agent,
        session_dir,
    ):
        directory.mkdir(exist_ok=True, mode=0o700)
        if os.name != "nt":
            directory.chmod(0o700)

    entries = [
        {
            "type": "session",
            "version": 3,
            "id": safe_session,
            "timestamp": started_at,
            "cwd": str(cwd),
        },
        _message_entry(
            message_id=f"{safe_session}-user",
            role="user",
            text=user_text,
            timestamp=started_at,
        ),
        _message_entry(
            message_id=f"{safe_session}-assistant",
            role="assistant",
            text=assistant_text,
            timestamp=ended_at,
            model=model,
        ),
    ]
    payload = "".join(
        json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n"
        for entry in entries
    )

    final_path = session_dir / f"{safe_session}.jsonl"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=session_dir,
            prefix=f".{safe_session}.",
            suffix=".tmp",
            delete=False,
        ) as temp:
            temp_path = Path(temp.name)
            temp.write(payload)
            temp.flush()
            os.fsync(temp.fileno())
        if os.name != "nt":
            temp_path.chmod(0o600)
        os.replace(temp_path, final_path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    return final_path


_ROUTING_EVENT_KEYS = (
    "manager_endpoint",
    "manager_model",
    "manager_backend",
    "coder_endpoint",
    "coder_model",
    "coder_backend",
    "distributed",
    "mac_only",
    "scenario_name",
    "windows_ip",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_routing_event_payload(state: dict[str, Any], *, ts: str | None = None) -> dict[str, Any]:
    """Materialize the planned routing-event shape from PT ``routing.json`` state."""

    payload: dict[str, Any] = {
        "event": "route",
        "ts": ts or _utc_now_iso(),
        "chosen_backend": state.get("coder_backend"),
        "manager_backend": state.get("manager_backend"),
        "distributed": bool(state.get("distributed")),
    }
    for key in _ROUTING_EVENT_KEYS:
        if key in state:
            payload[key] = state[key]
    return payload


def summarize_routing_state(state: dict[str, Any]) -> str:
    mode = "DISTRIBUTED" if state.get("distributed") else "MAC-ONLY"
    return (
        f"Routing resolved: mode={mode}, "
        f"manager={state.get('manager_backend')}, "
        f"coder={state.get('coder_backend')}"
    )


def emit_routing_state(
    *,
    state_dir: Path | str,
    routing_state: dict[str, Any],
    observed_at: str | None = None,
) -> Path | None:
    """Emit the latest PT routing resolution as an OpenClaw-compatible session."""

    timestamp = observed_at or _utc_now_iso()
    event = build_routing_event_payload(routing_state, ts=timestamp)
    return emit_openclaw_session(
        state_dir=state_dir,
        agent_id=AGENT_ALPHACLAW_ROUTING,
        session_id=ROUTING_SESSION_ID,
        user_text=json.dumps(event, ensure_ascii=False, separators=(",", ":")),
        assistant_text=summarize_routing_state(routing_state),
        started_at=timestamp,
        ended_at=timestamp,
        model=str(routing_state.get("coder_model") or ""),
    )


def maybe_emit_routing_observation(
    state_dir: Path | str,
    routing_state: dict[str, Any],
    *,
    observed_at: str | None = None,
) -> None:
    """Best-effort routing observation; never raises."""

    try:
        emit_routing_state(
            state_dir=state_dir,
            routing_state=routing_state,
            observed_at=observed_at,
        )
    except Exception as exc:  # pragma: no cover - defensive guardrail
        _LOG.debug("periscope routing observation skipped: %s", exc)


def maybe_emit_job_observation(
    *,
    state_dir: Path | str,
    job_id: str,
    user_text: str,
    assistant_text: str,
    started_at: str | None = None,
    ended_at: str | None = None,
    model: str = "",
) -> None:
    """Best-effort supervisor job observation; never raises."""

    ended = ended_at or _utc_now_iso()
    started = started_at or ended
    try:
        emit_openclaw_session(
            state_dir=state_dir,
            agent_id=AGENT_PT_SUPERVISOR,
            session_id=job_id,
            user_text=user_text,
            assistant_text=assistant_text,
            started_at=started,
            ended_at=ended,
            model=model,
        )
    except Exception as exc:  # pragma: no cover - defensive guardrail
        _LOG.debug("periscope job observation skipped: %s", exc)
