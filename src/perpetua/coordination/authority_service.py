"""In-process dispatcher for the private authority's control-plane routes.

It binds no socket and starts nothing on its own. A request is admitted only when the injected verifier, given
the credential and the scope the route needs, answers exactly ``True``. There is no default verifier. Nothing a
verifier or the store raised is repeated to the caller: only this module's own messages and the authority's typed,
caller-safe errors leave it.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict
import logging
from typing import Any

from perpetua.coordination.private_authority import (
    AuthorityError,
    ClaimHandle,
    Forbidden,
    InvalidRequest,
    Unauthenticated,
    Unavailable,
)

logger = logging.getLogger(__name__)

READ_SCOPE = "authority:read"
WRITE_SCOPE = "authority:write"
TASKS_PATH = "/authority/tasks"
HANDLE_FIELDS = ("task_id", "claim_id", "generation", "version", "incarnation", "claimed_at")

# ``(credential, scope) -> True`` admits. Raise ``Forbidden`` for a known caller without the scope.
Verifier = Callable[[Any, str], bool]


class AuthorityService:
    """Explicit POSIX primary service for queue authority on the PT control-plane route."""

    def __init__(self, authority: Any, authenticate: Verifier | None = None) -> None:
        self.authority = authority
        self.authenticate = authenticate
        self._running = False

    def start(self) -> None:
        """Start the authority service explicitly."""
        self._running = True

    def stop(self) -> None:
        """Stop the authority service explicitly (e.g. outage)."""
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def handle_request(self, method: str, path: str, body: Any = None, auth: Any = None) -> tuple[int, dict]:
        """Answer one request with a status and a body. Never raises."""
        try:
            if not self._running:
                raise Unavailable("service unavailable")
            reading = method == "GET" and path.startswith(TASKS_PATH + "/")
            self._check_auth(auth, READ_SCOPE if reading else WRITE_SCOPE)
            if reading:
                return self._read(path[len(TASKS_PATH) + 1:])
            return self._write(method, path, body)
        except AuthorityError as exc:
            return exc.status, exc.to_dict()
        except Exception as exc:  # anything unexpected is a generic outage to the caller
            logger.error("authority request failed: %s", type(exc).__name__)
            error = Unavailable("service unavailable")
            return error.status, error.to_dict()

    def _check_auth(self, auth: Any, scope: str) -> None:
        """Deny unless the verifier, given the credential and the required scope, returns exactly True."""
        if self.authenticate is None:
            raise Unauthenticated("authentication required")
        try:
            allowed = self.authenticate(auth, scope)
        except Forbidden:
            raise Forbidden("scope not permitted") from None
        except Unavailable:
            raise Unavailable("service unavailable") from None
        except Exception:
            raise Unauthenticated("authentication failed") from None
        if allowed is not True:
            raise Unauthenticated("authentication failed")

    def _read(self, task_id: str) -> tuple[int, dict]:
        if not task_id:
            raise InvalidRequest("missing task_id in path")
        return 200, self.authority.get(task_id)

    def _write(self, method: str, path: str, body: Any) -> tuple[int, dict]:
        """The write routes. There is deliberately no import route: import stays a local operator call."""
        if method == "POST" and path == TASKS_PATH:
            task_id = _fields(body, ("task_id",))["task_id"]
            self.authority.add(task_id)
            return 201, {"task_id": task_id, "state": "queued"}
        if method == "POST" and path == "/authority/claim":
            fields = _fields(body, ("task_id", "incarnation"))
            return 200, asdict(self.authority.claim(fields["task_id"], fields["incarnation"]))
        if method == "POST" and path == "/authority/renew":
            return 200, asdict(self.authority.renew(_handle(body)))
        for action, done in (("release", "released"), ("complete", "completed"), ("fail", "failed")):
            if method == "POST" and path == f"/authority/{action}":
                getattr(self.authority, action)(_handle(body))
                return 200, {"status": done}
        return 404, {"status": 404, "error": {"code": "task_not_found", "message": "unknown route",
                                              "retryable": False}}


def _fields(body: Any, names: tuple[str, ...]) -> Mapping[str, Any]:
    """The body, holding exactly ``names``. The authority checks each value's type and content."""
    if not isinstance(body, Mapping):
        raise InvalidRequest("request body must be a dictionary")
    missing = [name for name in names if name not in body]
    if missing:
        raise InvalidRequest(f"missing required field: {missing[0]}")
    if len(body) != len(names):
        raise InvalidRequest("request body has unexpected fields")
    return body


def _handle(body: Any) -> ClaimHandle:
    fields = _fields(body, HANDLE_FIELDS)
    return ClaimHandle(**{name: fields[name] for name in HANDLE_FIELDS})
