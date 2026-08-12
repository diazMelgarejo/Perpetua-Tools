"""Pure-ASGI control-plane authentication boundary.

This deliberately avoids FastAPI's ``@app.middleware(\"http\")`` decorator,
which is backed by Starlette ``BaseHTTPMiddleware``.  That adapter buffers the
response path and is a poor fit for unbounded streaming responses.
"""
from __future__ import annotations

from fastapi import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from orchestrator.control_plane_auth import (
    control_plane_auth_failure,
    pt_path_requires_auth,
)


class ControlPlaneAuthMiddleware:
    """Require bearer auth for PT operator routes without buffering responses."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")
        if pt_path_requires_auth(path, method):
            failure = control_plane_auth_failure(Request(scope, receive=receive))
            if failure is not None:
                await failure(scope, receive, send)
                return

        await self.app(scope, receive, send)
