"""Trusted dispatch approvals must carry the configured frontier budget evidence."""
import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from orchestrator.dispatch_guard import DispatchGuard, DispatchRequest
from perpetua_tools.model_governance import EscalationProof
from perpetua_tools.model_governance import ModelGovernanceError


def request() -> DispatchRequest:
    """Build an explicitly scoped frontier-model request without invoking a provider."""
    return DispatchRequest("scope-a", "google", "gemini-4-argon", "goal", "prompt",
                           effort="medium", fast=False)


def test_boolean_approval_cannot_attest_frontier_budget(tmp_path: Path) -> None:
    """An old Boolean verifier cannot lift a separately required budget cap."""
    calls = []

    async def effect() -> dict[str, bool]:
        """Record whether any provider effect was entered."""
        calls.append(True)
        return {"ok": True}

    with pytest.raises(PermissionError, match="budget"):
        asyncio.run(DispatchGuard(tmp_path, approval_verifier=lambda _: True).execute(request(), effect))
    assert not calls
    assert not (tmp_path / "dispatch_claims.sqlite3").exists()


def test_trusted_structured_approval_binds_scope_and_budget(tmp_path: Path) -> None:
    """An exact trusted proof with budget evidence can authorize the existing boundary."""
    proof = EscalationProof(
        "control_plane_online_signer", "verified-reference", "gemini-4-argon",
        datetime.now(timezone.utc) + timedelta(minutes=1), effort="medium", fast=False,
        budget_cap="max_tokens=8192", path="google", scope="scope-a",
    )

    async def effect() -> dict[str, bool]:
        """Return a synthetic local result, never a model invocation."""
        return {"ok": True}

    assert asyncio.run(DispatchGuard(tmp_path, approval_verifier=lambda _: proof).execute(request(), effect)) == {"ok": True}


@pytest.mark.parametrize("invalid_field", ["scope", "expired", "budget", "path"])
def test_structured_approval_refuses_invalid_evidence(tmp_path: Path, invalid_field: str) -> None:
    """Reject mismatched or incomplete trusted evidence before creating durable state."""
    proof = EscalationProof(
        "control_plane_online_signer", "verified-reference", "gemini-4-argon",
        datetime.now(timezone.utc) + timedelta(minutes=1), effort="medium", fast=False,
        budget_cap="max_tokens=8192", path="google", scope="scope-a",
    )
    changes = {
        "scope": {"scope": "scope-b"},
        "expired": {"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)},
        "budget": {"budget_cap": None},
        "path": {"path": "openai"},
    }
    proof = replace(proof, **changes[invalid_field])
    calls: list[bool] = []

    async def effect() -> dict[str, bool]:
        """Detect accidental provider entry without invoking an external service."""
        calls.append(True)
        return {"ok": True}

    with pytest.raises(ModelGovernanceError):
        asyncio.run(DispatchGuard(tmp_path, approval_verifier=lambda _: proof).execute(request(), effect))
    assert not calls
    assert not (tmp_path / "dispatch_claims.sqlite3").exists()
