"""Shared LAN gossip authentication for FastAPI and legacy entrypoints."""

from __future__ import annotations

import hmac
import os

from fastapi import HTTPException, Request


def gossip_shared_secret() -> str:
    return os.getenv("GOSSIP_SHARED_SECRET", "").strip()


def pt_bind_lan() -> bool:
    return os.getenv("PT_BIND_LAN", "").strip().lower() in ("1", "true", "yes")


def require_gossip_auth(request: Request) -> None:
    """Require GOSSIP_SHARED_SECRET when LAN-bound; validate header when set."""
    secret = gossip_shared_secret()
    if pt_bind_lan() and not secret:
        raise HTTPException(
            status_code=503,
            detail=(
                "GOSSIP_SHARED_SECRET required when PT_BIND_LAN=1 — "
                "run: python3 scripts/mesh/ensure_local_mesh_secrets.py"
            ),
        )
    if not secret:
        return
    header = request.headers.get("x-gossip-secret", "")
    if not hmac.compare_digest(header, secret):
        raise HTTPException(status_code=403, detail="Invalid gossip secret")
