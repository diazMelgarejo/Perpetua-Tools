"""Immutable public types for oramaclaw V1.

All types are frozen dataclasses. Mutable inputs must be normalized at
parsing boundaries: list → tuple, Path.expanduser().resolve().
Fingerprints use SHA-256 hex over canonical JSON.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Mapping

try:
    from typing import runtime_checkable, Protocol
except ImportError:  # Python < 3.8
    from typing_extensions import runtime_checkable, Protocol  # type: ignore[assignment]


# ── Enumerations ─────────────────────────────────────────────────────────────

class ResourceKind(str, Enum):
    PROVIDER = "provider"
    BINDING = "binding"
    AGENT = "agent"
    DELEGATION = "delegation"
    EXECUTION_POLICY = "execution_policy"
    PROFILE = "profile"


class MergePolicy(str, Enum):
    STRICT = "strict"
    COOPERATIVE = "cooperative"
    CONFLICT = "conflict"


# ── Core target and resource ─────────────────────────────────────────────────

@dataclass(frozen=True)
class ConfigTarget:
    workspace_root: Path
    config_path: Path
    state_dir: Path


@dataclass(frozen=True)
class Resource:
    kind: ResourceKind
    identifier: str
    manager: str
    spec: Mapping[str, Any]
    managed_paths: tuple[str, ...]
    policy: MergePolicy


# ── Manifest ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ControlManifest:
    """Parsed and validated declarative manifest (from JSON on disk)."""
    version: int                    # must be 1 for V1
    target: ConfigTarget | None
    resources: tuple[Resource, ...]
    source_path: Path               # original file path (for error messages)
    source_fingerprint: str         # SHA-256 of raw bytes


# ── Conflict resolution ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class Conflict:
    """A field that cannot be automatically resolved."""
    resource_key: str               # e.g. "provider:example-provider"
    manager: str
    managed_path: str               # JSON Pointer e.g. "/effort"
    base_fingerprint: str | None
    observed_fingerprint: str | None
    desired_fingerprint: str
    security_topology: bool
    choices: tuple[str, ...]        # e.g. ("apply-desired", "keep-current", "show-diff")
    resolution_id: str              # stable opaque id for CLI/portal resolve


@dataclass(frozen=True)
class PendingResolution:
    """Durable record stored in pending-resolutions.json for portal/CLI pick-up."""
    resolution_id: str
    conflict: Conflict
    transaction_id: str
    created_at: str                 # ISO-8601
    resolved_at: str | None = None
    chosen: str | None = None


# ── Engine result ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ControlResult:
    """Returned by ControlEngine.apply_manifest()."""
    transaction_id: str
    state: Literal[
        "committed",
        "auto_woven",
        "conflicted",
        "needs_input",
        "gateway_unavailable",
        "failed",
    ]
    applied: tuple[str, ...]        # resource_keys successfully committed
    auto_woven: tuple[str, ...]     # resource_key + path pairs auto-woven
    conflicts: tuple[Conflict, ...]
    warnings: tuple[str, ...]


# ── Gateway transport types ───────────────────────────────────────────────────

@dataclass(frozen=True)
class GatewayConfig:
    """Live configuration fetched from the gateway, plus its hash."""
    configuration: Mapping[str, Any]   # parsed openclaw.json document
    base_hash: str                     # opaque hash from gateway; thread back on apply


@dataclass(frozen=True)
class GatewayApplyResult:
    """Returned by a successful gateway config.apply call."""
    transaction_id: str
    base_hash: str                     # new hash after apply, for chained operations


class StaleConfiguration(Exception):
    """Raised when the gateway rejects a write because baseHash is outdated."""
    def __init__(self, stale_hash: str, message: str = "") -> None:
        self.stale_hash = stale_hash
        super().__init__(message or f"stale hash: {stale_hash}")


class GatewayUnavailable(Exception):
    """Raised when the gateway cannot be reached."""


class GatewayRejected(Exception):
    """Raised when the gateway returns an explicit rejection (non-stale)."""
    def __init__(self, code: int, message: str) -> None:
        self.code = code
        super().__init__(f"gateway rejected (code={code}): {message}")


class OfflineOperationNotAllowed(Exception):
    """Raised when a mutation is attempted offline for an ineligible resource."""
    def __init__(self, resource_key: str) -> None:
        self.resource_key = resource_key
        super().__init__(
            f"offline mutations are only allowed for provider registration and new-agent "
            f"creation; rejected: {resource_key}"
        )


# ── Transport protocol ────────────────────────────────────────────────────────

@runtime_checkable
class OpenClawTransport(Protocol):
    def gateway_config_get(self, target: ConfigTarget) -> GatewayConfig: ...
    def gateway_config_apply(
        self,
        target: ConfigTarget,
        configuration: Mapping[str, Any],
        base_hash: str,
    ) -> GatewayApplyResult: ...
    def create_agent(self, target: ConfigTarget, spec: Mapping[str, Any]) -> None: ...
    def update_agent(self, target: ConfigTarget, agent_id: str, patch: Mapping[str, Any]) -> None: ...
    def offline_apply_provider(self, target: ConfigTarget, resource: Resource) -> None: ...
    def offline_create_agent(self, target: ConfigTarget, resource: Resource) -> None: ...
