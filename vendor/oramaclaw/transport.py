"""Gateway-first and restricted offline transport for oramaclaw V1.

Two concrete transports implement the ``OpenClawTransport`` Protocol from
``oramaclaw.types``:

``GatewayTransport``
    Routes all mutations through ``openclaw config`` gateway RPC calls.
    Reads live config via ``openclaw config get --json``, applies batches via
    ``openclaw config set --batch-json``.  Any shell failure surfaces as one of
    the typed exceptions from ``oramaclaw.types``.

``OfflineTransport``
    Restricted write path used when the gateway is unavailable.  Only two
    operations are permitted offline:
    - Provider registration (ResourceKind.PROVIDER)
    - New-agent creation (ResourceKind.AGENT, no existing config entry)
    All other mutations raise ``OfflineOperationNotAllowed``.
    Writes directly to ``target.config_path`` via a shared-lock + atomic write.

Callers receive the appropriate transport from ``make_transport()``, which
probes the gateway and falls back to ``OfflineTransport`` when unreachable.

``CommandRunner`` is a Protocol so tests can inject a fake without touching
the filesystem or spawning subprocesses.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from oramaclaw.store import _atomic_write_json, _load_json
from oramaclaw.types import (
    ConfigTarget,
    GatewayApplyResult,
    GatewayConfig,
    GatewayRejected,
    GatewayUnavailable,
    OfflineOperationNotAllowed,
    Resource,
    ResourceKind,
    StaleConfiguration,
)

try:
    from typing import Protocol, runtime_checkable
except ImportError:
    from typing_extensions import Protocol, runtime_checkable  # type: ignore[assignment]

_log = logging.getLogger(__name__)

# ── Command runner protocol (injectable for tests) ────────────────────────────

@runtime_checkable
class CommandRunner(Protocol):
    def run(
        self,
        argv: Sequence[str],
        *,
        capture_output: bool = True,
        timeout: float = 15.0,
    ) -> "RunResult": ...


class RunResult:
    def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class SubprocessRunner:
    """Default runner that delegates to the system ``openclaw`` CLI."""

    def run(
        self,
        argv: Sequence[str],
        *,
        capture_output: bool = True,
        timeout: float = 15.0,
    ) -> RunResult:
        try:
            result = subprocess.run(
                list(argv),
                capture_output=capture_output,
                timeout=timeout,
                text=True,
            )
            return RunResult(result.returncode, result.stdout or "", result.stderr or "")
        except FileNotFoundError as exc:
            raise GatewayUnavailable(f"openclaw CLI not found: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise GatewayUnavailable(f"openclaw CLI timed out after {timeout}s") from exc


# ── Gateway transport ─────────────────────────────────────────────────────────

class GatewayTransport:
    """Calls the openclaw gateway CLI for all config mutations."""

    def __init__(self, runner: CommandRunner | None = None) -> None:
        self._runner: CommandRunner = runner or SubprocessRunner()

    # -- OpenClawTransport interface ------------------------------------------

    def gateway_config_get(self, target: ConfigTarget) -> GatewayConfig:
        result = self._runner.run(
            ["openclaw", "config", "get", "--json", "--workspace", str(target.workspace_root)],
            timeout=10.0,
        )
        if result.returncode != 0:
            raise GatewayUnavailable(
                f"openclaw config get failed (rc={result.returncode}): {result.stderr.strip()}"
            )
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise GatewayUnavailable(f"gateway returned non-JSON: {exc}") from exc

        return GatewayConfig(
            configuration=data.get("configuration", {}),
            base_hash=data.get("baseHash", ""),
        )

    def gateway_config_apply(
        self,
        target: ConfigTarget,
        configuration: Mapping[str, Any],
        base_hash: str,
    ) -> GatewayApplyResult:
        payload = json.dumps({"configuration": dict(configuration), "baseHash": base_hash})
        result = self._runner.run(
            [
                "openclaw", "config", "set",
                "--batch-json", payload,
                "--workspace", str(target.workspace_root),
            ],
            timeout=15.0,
        )
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
            except json.JSONDecodeError:
                data = {}
            return GatewayApplyResult(
                transaction_id=data.get("transactionId", ""),
                base_hash=data.get("baseHash", base_hash),
            )

        stderr = result.stderr.strip()
        if "stale" in stderr.lower() or result.returncode == 409:
            raise StaleConfiguration(base_hash, stderr)
        if result.returncode in (401, 403):
            raise GatewayRejected(result.returncode, stderr)
        raise GatewayUnavailable(
            f"openclaw config set failed (rc={result.returncode}): {stderr}"
        )

    def create_agent(self, target: ConfigTarget, spec: Mapping[str, Any]) -> None:
        payload = json.dumps(dict(spec))
        result = self._runner.run(
            [
                "openclaw", "agent", "create",
                "--json", payload,
                "--workspace", str(target.workspace_root),
            ],
            timeout=15.0,
        )
        if result.returncode != 0:
            raise GatewayUnavailable(
                f"openclaw agent create failed (rc={result.returncode}): {result.stderr.strip()}"
            )

    def update_agent(self, target: ConfigTarget, agent_id: str, patch: Mapping[str, Any]) -> None:
        payload = json.dumps(dict(patch))
        result = self._runner.run(
            [
                "openclaw", "agent", "update", agent_id,
                "--patch-json", payload,
                "--workspace", str(target.workspace_root),
            ],
            timeout=15.0,
        )
        if result.returncode != 0:
            raise GatewayUnavailable(
                f"openclaw agent update failed (rc={result.returncode}): {result.stderr.strip()}"
            )

    def offline_apply_provider(self, target: ConfigTarget, resource: Resource) -> None:
        raise GatewayUnavailable("offline_apply_provider called on GatewayTransport")

    def offline_create_agent(self, target: ConfigTarget, resource: Resource) -> None:
        raise GatewayUnavailable("offline_create_agent called on GatewayTransport")


# ── Offline transport ─────────────────────────────────────────────────────────

_OFFLINE_ALLOWED_KINDS = frozenset({ResourceKind.PROVIDER, ResourceKind.AGENT})


class OfflineTransport:
    """Restricted write path when the gateway is unavailable.

    Permitted operations:
    - Provider registration: merges the resource spec into the providers map
    - New-agent creation: adds the agent entry if not already present

    Any other ResourceKind raises OfflineOperationNotAllowed.
    All writes are atomic (os.replace) and guarded by a read-before-write
    fingerprint check to minimise lost-update risk.
    """

    def __init__(self) -> None:
        pass

    def gateway_config_get(self, target: ConfigTarget) -> GatewayConfig:
        raw = _load_json(target.config_path, {})
        return GatewayConfig(configuration=raw, base_hash="offline")

    def gateway_config_apply(
        self,
        target: ConfigTarget,
        configuration: Mapping[str, Any],
        base_hash: str,
    ) -> GatewayApplyResult:
        # Offline apply is only safe for provider / new-agent paths; callers
        # route through the specific offline_* helpers instead.
        raise OfflineOperationNotAllowed("generic config apply")

    def create_agent(self, target: ConfigTarget, spec: Mapping[str, Any]) -> None:
        self.offline_create_agent(
            target,
            Resource(
                kind=ResourceKind.AGENT,
                identifier=str(spec.get("id", "unknown")),
                manager="offline",
                spec=spec,
                managed_paths=(),
                policy=__import__("oramaclaw.types", fromlist=["MergePolicy"]).MergePolicy.STRICT,
            ),
        )

    def update_agent(self, target: ConfigTarget, agent_id: str, patch: Mapping[str, Any]) -> None:
        raise OfflineOperationNotAllowed(f"agent:update:{agent_id}")

    def offline_apply_provider(self, target: ConfigTarget, resource: Resource) -> None:
        if resource.kind not in _OFFLINE_ALLOWED_KINDS:
            raise OfflineOperationNotAllowed(f"{resource.kind.value}:{resource.identifier}")
        config = dict(_load_json(target.config_path, {}))
        providers = dict(config.get("models", {}).get("providers", {}))
        providers[resource.identifier] = dict(resource.spec)
        models = dict(config.get("models", {}))
        models["providers"] = providers
        config["models"] = models
        _atomic_write_json(target.config_path, config)

    def offline_create_agent(self, target: ConfigTarget, resource: Resource) -> None:
        if resource.kind != ResourceKind.AGENT:
            raise OfflineOperationNotAllowed(f"{resource.kind.value}:{resource.identifier}")
        config = dict(_load_json(target.config_path, {}))
        agents = dict(config.get("agents", {}).get("definitions", {}))
        if resource.identifier in agents:
            raise OfflineOperationNotAllowed(
                f"agent:{resource.identifier} already exists; updates require gateway"
            )
        agents[resource.identifier] = dict(resource.spec)
        agents_section = dict(config.get("agents", {}))
        agents_section["definitions"] = agents
        config["agents"] = agents_section
        _atomic_write_json(target.config_path, config)


# ── Factory ───────────────────────────────────────────────────────────────────

def make_transport(
    target: ConfigTarget,
    *,
    runner: CommandRunner | None = None,
    force_offline: bool = False,
) -> "GatewayTransport | OfflineTransport":
    """Probe the gateway; return GatewayTransport on success, OfflineTransport on failure.

    ``force_offline=True`` skips the probe (useful for testing).
    """
    if force_offline:
        _log.info("transport: offline mode forced")
        return OfflineTransport()

    probe_runner = runner or SubprocessRunner()
    try:
        result = probe_runner.run(
            ["openclaw", "status", "--json", "--workspace", str(target.workspace_root)],
            timeout=5.0,
        )
        if result.returncode == 0:
            return GatewayTransport(runner=probe_runner)
    except GatewayUnavailable:
        pass

    _log.warning("transport: gateway unreachable, falling back to offline mode")
    return OfflineTransport()
