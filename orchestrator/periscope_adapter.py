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
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EMITTER_ENABLED_ENV = "PERISCOPE_EMITTER_ENABLED"
JOB_SESSION_MAX_AGE_DAYS_ENV = "PERISCOPE_JOB_SESSION_MAX_AGE_DAYS"
DEFAULT_JOB_SESSION_MAX_AGE_DAYS = 33
SECONDS_PER_DAY = 86400
AGENT_PT_SUPERVISOR = "pt-supervisor"
AGENT_ALPHACLAW_ROUTING = "alphaclaw-routing"
ROUTING_SESSION_ID = "routing-latest"
TRAJECTORY_PRIVACY_CLASSIFICATION = "internal_only"
_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_LOG = logging.getLogger(__name__)


def emitter_enabled() -> bool:
    """Return whether optional Periscope observation emission is enabled."""

    return os.getenv(EMITTER_ENABLED_ENV, "").strip() == "1"


def job_session_max_age_days() -> int:
    """Return retention window for per-job supervisor session JSONL files."""

    raw = os.getenv(JOB_SESSION_MAX_AGE_DAYS_ENV, "").strip()
    if not raw:
        return DEFAULT_JOB_SESSION_MAX_AGE_DAYS
    try:
        days = int(raw)
    except ValueError:
        return DEFAULT_JOB_SESSION_MAX_AGE_DAYS
    return max(1, days)


def prune_stale_job_sessions(
    state_dir: Path | str,
    *,
    agent_id: str = AGENT_PT_SUPERVISOR,
    max_age_days: int | None = None,
    now: float | None = None,
) -> int:
    """Delete per-job session JSONL older than the retention window.

    Routing observations reuse a fixed session id and are not pruned here.
    Returns the number of files removed.
    """

    if not emitter_enabled():
        return 0

    safe_agent = _validate_component("agent_id", agent_id)
    session_dir = periscope_agents_dir(state_dir) / safe_agent / "sessions"
    if not session_dir.is_dir():
        return 0

    age_days = max_age_days if max_age_days is not None else job_session_max_age_days()
    cutoff = (now if now is not None else time.time()) - age_days * SECONDS_PER_DAY
    removed = 0
    for path in session_dir.glob("*.jsonl"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError as exc:
            _LOG.debug("prune_stale_job_sessions: skip %s — %s", path.name, exc)
    if removed:
        _LOG.debug(
            "prune_stale_job_sessions: removed %d file(s) older than %d days under %s",
            removed,
            age_days,
            session_dir,
        )
    return removed


def periscope_agents_dir(state_dir: Path | str) -> Path:
    """Return the PT-owned agent root to add to Periscope ``openclaw_dirs``."""

    return Path(state_dir) / "periscope" / "agents"


def resolve_observation_state_dir() -> Path:
    """Return the canonical PT state directory for observation emission."""

    from orchestrator.gossip_bus import resolve_default_state_dir

    return resolve_default_state_dir()


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


def _validate_local_path(path: Path | str) -> Path:
    raw = str(path or "").strip()
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+-.]*://", raw) or raw.startswith(r"\\") or raw.startswith("//"):
        raise ValueError(
            f"Remote destination URLs and Windows UNC paths are forbidden for local Periscope trajectory sink: {raw}"
        )
    return Path(path).resolve()


def _open_local_directory(parent_fd: int, component: str) -> int:
    """Open one directory component without following a symlink."""

    try:
        os.mkdir(component, mode=0o700, dir_fd=parent_fd)
    except FileExistsError:
        pass

    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    child_fd = os.open(component, flags, dir_fd=parent_fd)
    os.fchmod(child_fd, 0o700)
    return child_fd


def _write_posix_local_trajectory(
    state_path: Path,
    *,
    agent_id: str,
    filename: str,
    payload: str,
) -> Path:
    """Write beneath an opened root using descriptor-relative operations."""

    root_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    root_fd = os.open(state_path, root_flags)
    opened_fds = [root_fd]
    temp_name = f".{filename}.{uuid.uuid4().hex}.tmp"
    session_fd: int | None = None
    try:
        parent_fd = root_fd
        for component in ("periscope", "agents", agent_id, "sessions"):
            parent_fd = _open_local_directory(parent_fd, component)
            opened_fds.append(parent_fd)
        session_fd = parent_fd

        temp_fd = os.open(
            temp_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=session_fd,
        )
        with os.fdopen(temp_fd, "w", encoding="utf-8") as temp:
            temp.write(payload)
            temp.flush()
            os.fsync(temp.fileno())

        os.replace(
            temp_name,
            filename,
            src_dir_fd=session_fd,
            dst_dir_fd=session_fd,
        )
        os.fsync(session_fd)
    finally:
        if session_fd is not None:
            try:
                os.unlink(temp_name, dir_fd=session_fd)
            except FileNotFoundError:
                pass
        for directory_fd in reversed(opened_fds):
            os.close(directory_fd)

    return (
        state_path
        / "periscope"
        / "agents"
        / agent_id
        / "sessions"
        / filename
    )


def _write_portable_local_trajectory(
    session_dir: Path,
    *,
    filename: str,
    payload: str,
) -> Path:
    """Portable fallback for platforms without POSIX descriptor semantics."""

    for directory in (
        session_dir.parent.parent.parent,
        session_dir.parent.parent,
        session_dir.parent,
        session_dir,
    ):
        if directory.exists() and directory.is_symlink():
            raise ValueError(
                f"Symlinked Periscope directory is forbidden: {directory}"
            )
        directory.mkdir(exist_ok=True, mode=0o700)

    final_path = session_dir / filename
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=session_dir,
            prefix=f".{filename}.",
            suffix=".tmp",
            delete=False,
        ) as temp:
            temp_path = Path(temp.name)
            temp.write(payload)
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_path, final_path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return final_path


def write_internal_trajectory(
    *,
    state_dir: Path | str,
    agent_id: str,
    session_id: str,
    entries: list[dict[str, Any]],
) -> Path | None:
    """Write trajectory strictly to local workstation storage beneath state_dir.

    Enforces the local-only trust boundary: rejects URL destinations, prevents
    directory traversal outside the resolved periscope root, and never forwards
    to remote OTLP or HTTP endpoints.
    """
    if not emitter_enabled():
        return None

    safe_agent = _validate_component("agent_id", agent_id)
    safe_session = _validate_component("session_id", session_id)

    state_path = _validate_local_path(state_dir)
    state_path.mkdir(parents=True, exist_ok=True)
    agents_dir = periscope_agents_dir(state_path).resolve()
    session_dir = (agents_dir / safe_agent / "sessions").resolve()

    # Assert strict containment below both state_path and periscope agents root
    try:
        session_dir.relative_to(state_path)
        session_dir.relative_to(agents_dir)
    except ValueError:
        raise ValueError(f"Destination path escape detected outside configured state root: {session_dir}")

    payload = "".join(
        json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n"
        for entry in entries
    )
    filename = f"{safe_session}.jsonl"
    if os.name != "nt" and all(
        hasattr(os, name) for name in ("O_DIRECTORY", "O_NOFOLLOW")
    ):
        return _write_posix_local_trajectory(
            state_path,
            agent_id=safe_agent,
            filename=filename,
            payload=payload,
        )
    return _write_portable_local_trajectory(
        session_dir,
        filename=filename,
        payload=payload,
    )


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

    safe_session = _validate_component("session_id", session_id)
    if not started_at or not ended_at:
        raise ValueError("started_at and ended_at are required")

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

    return write_internal_trajectory(
        state_dir=state_dir,
        agent_id=agent_id,
        session_id=session_id,
        entries=entries,
    )


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
        emitted = emit_openclaw_session(
            state_dir=state_dir,
            agent_id=AGENT_PT_SUPERVISOR,
            session_id=job_id,
            user_text=user_text,
            assistant_text=assistant_text,
            started_at=started,
            ended_at=ended,
            model=model,
        )
        if emitted is not None:
            prune_stale_job_sessions(state_dir)
    except Exception as exc:  # pragma: no cover - defensive guardrail
        _LOG.debug("periscope job observation skipped: %s", exc)
