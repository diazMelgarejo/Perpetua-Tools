"""In-process service dispatcher for private authority control-plane routes."""
from __future__ import annotations

from dataclasses import asdict
import inspect
from typing import Any, Callable

from perpetua.coordination.private_authority import (
    Authority,
    AuthorityError,
    ClaimHandle,
    Forbidden,
    InvalidRequest,
    TaskNotFound,
    Unavailable,
    Unauthenticated,
)


class AuthorityService:
    """Explicit POSIX primary service for queue authority on the PT control-plane route."""

    def __init__(
        self,
        authority: Any,
        authenticate: Callable[..., Any] | None = None,
    ) -> None:
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

    def _determine_scope(self, method: str, path: str) -> str:
        if method == "GET" and path.startswith("/authority/tasks/"):
            return "authority:read"
        return "authority:write"

    def _check_auth(self, auth: Any, scope: str) -> None:
        if self.authenticate is None:
            raise Unauthenticated("authentication required")
        try:
            sig = inspect.signature(self.authenticate)
            params = list(sig.parameters.values())
            if len(params) == 0:
                res = self.authenticate()
            elif len(params) == 1:
                res = self.authenticate(auth)
            else:
                res = self.authenticate(auth, scope)
            if res is False:
                raise Unauthenticated("invalid credentials")
        except (Unauthenticated, Forbidden):
            raise
        except AuthorityError:
            raise
        except Exception as exc:
            raise Unauthenticated(f"authentication failed: {exc}") from exc

    def handle_request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        auth: Any = None,
        **kwargs: Any,
    ) -> tuple[int, dict]:
        """Dispatch control-plane route requests to the authority with typed error mapping."""
        if not self._running:
            err = Unavailable("service unavailable")
            return err.status, err.to_dict()

        scope = self._determine_scope(method, path)
        try:
            self._check_auth(auth, scope)
        except AuthorityError as exc:
            return exc.status, exc.to_dict()

        if path == "/authority/import" or path.startswith("/authority/import"):
            return 404, {
                "status": 404,
                "error": {
                    "code": "task_not_found",
                    "message": "import route is not exposed via service",
                    "retryable": False,
                },
            }

        body = body if body is not None else {}
        if not isinstance(body, dict):
            err = InvalidRequest("request body must be a dictionary")
            return err.status, err.to_dict()

        try:
            if method == "POST" and path == "/authority/tasks":
                if "task_id" not in body or not isinstance(body["task_id"], str) or not body["task_id"].strip():
                    raise InvalidRequest("task_id must be a nonempty string")
                task_id = body["task_id"]
                self.authority.add(task_id)
                return 201, {"task_id": task_id, "state": "queued"}

            elif method == "POST" and path == "/authority/claim":
                if "task_id" not in body or not isinstance(body["task_id"], str) or not body["task_id"].strip():
                    raise InvalidRequest("task_id must be a nonempty string")
                if "incarnation" not in body or not isinstance(body["incarnation"], str) or not body["incarnation"].strip():
                    raise InvalidRequest("incarnation must not be empty")
                handle = self.authority.claim(body["task_id"], body["incarnation"])
                return 200, asdict(handle)

            elif method == "POST" and path == "/authority/renew":
                self._validate_handle_fields(body)
                handle = self._extract_handle(body)
                new_handle = self.authority.renew(handle)
                return 200, asdict(new_handle)

            elif method == "POST" and path == "/authority/release":
                self._validate_handle_fields(body)
                handle = self._extract_handle(body)
                self.authority.release(handle)
                return 200, {"status": "released"}

            elif method == "POST" and path == "/authority/complete":
                self._validate_handle_fields(body)
                handle = self._extract_handle(body)
                self.authority.complete(handle)
                return 200, {"status": "completed"}

            elif method == "POST" and path == "/authority/fail":
                self._validate_handle_fields(body)
                handle = self._extract_handle(body)
                self.authority.fail(handle, detail=body.get("detail", ""))
                return 200, {"status": "failed"}

            elif method == "GET" and path.startswith("/authority/tasks/"):
                task_id = path.split("/authority/tasks/", 1)[1]
                if not task_id:
                    raise InvalidRequest("missing task_id in path")
                return 200, self.authority.get(task_id)

            else:
                return 404, {
                    "status": 404,
                    "error": {
                        "code": "task_not_found",
                        "message": f"not found: {method} {path}",
                        "retryable": False,
                    },
                }

        except AuthorityError as exc:
            return exc.status, exc.to_dict()
        except KeyError as exc:
            err = InvalidRequest(f"missing field: {exc}")
            return err.status, err.to_dict()
        except TypeError as exc:
            err = InvalidRequest(f"invalid field type: {exc}")
            return err.status, err.to_dict()
        except Exception:
            err = Unavailable("service unavailable")
            return err.status, err.to_dict()

    @staticmethod
    def _validate_handle_fields(body: dict) -> None:
        required = ("task_id", "claim_id", "generation", "version", "incarnation", "claimed_at")
        for f in required:
            if f not in body:
                raise InvalidRequest(f"missing required field: {f}")

    @staticmethod
    def _extract_handle(body: dict) -> ClaimHandle:
        return ClaimHandle(
            task_id=body["task_id"],
            claim_id=body["claim_id"],
            generation=body["generation"],
            version=body["version"],
            incarnation=body["incarnation"],
            claimed_at=body["claimed_at"],
        )
