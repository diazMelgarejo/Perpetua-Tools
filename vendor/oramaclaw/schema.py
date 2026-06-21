"""Manifest JSON schema validation for oramaclaw V1.

Entry point: ``parse_manifest(path) -> ControlManifest``

The schema enforces:
- ``version == 1``
- Non-empty ``resources`` array
- Each resource has a unique ``kind:id`` key
- Each resource has a non-empty ``manager`` string
- ``policy`` is one of strict / cooperative / conflict
- Delegation resources may not carry cooperative or strict policy when
  ``security_topology`` is set (they must use conflict)
- No raw credentials in any ``spec`` value (auth is reference-only)

Validation is intentionally structural, not semantic — it does not
resolve targets or contact the gateway.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from oramaclaw.types import (
    ConfigTarget,
    ControlManifest,
    MergePolicy,
    Resource,
    ResourceKind,
)

# ── JSON schema (inline; no external dependency required for V1) ─────────────

_MANIFEST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["version", "resources"],
    "properties": {
        "version": {"type": "integer", "const": 1},
        "target": {
            "type": "object",
            "properties": {
                "workspace_root": {"type": "string"},
                "config_path": {"type": "string"},
                "state_dir": {"type": "string"},
            },
        },
        "resources": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["kind", "id", "manager", "policy", "spec", "managed_paths"],
                "properties": {
                    "kind": {"type": "string", "enum": [k.value for k in ResourceKind]},
                    "id": {"type": "string", "minLength": 1},
                    "manager": {"type": "string", "minLength": 1},
                    "policy": {"type": "string", "enum": [p.value for p in MergePolicy]},
                    "spec": {"type": "object"},
                    "managed_paths": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string"},
                    },
                    "security_topology": {"type": "boolean"},
                },
            },
        },
    },
}

# ── Credential guard ─────────────────────────────────────────────────────────

_FORBIDDEN_SPEC_KEYS = frozenset({
    "apiKey", "api_key", "token", "secret", "password",
    "bearer", "credential", "auth_token", "access_token",
})


def _check_no_raw_credentials(spec: Any, resource_key: str, path: str = "spec") -> None:
    if isinstance(spec, dict):
        for key, value in spec.items():
            key_text = str(key)
            if key_text in _FORBIDDEN_SPEC_KEYS:
                raise ManifestValidationError(
                    f"{resource_key}: {path}.{key_text} looks like a raw credential. "
                    "Use an authReference path instead (e.g. '~/.codex/config.toml')."
                )
            _check_no_raw_credentials(value, resource_key, f"{path}.{key_text}")
    elif isinstance(spec, list):
        for index, value in enumerate(spec):
            _check_no_raw_credentials(value, resource_key, f"{path}[{index}]")


# ── Errors ───────────────────────────────────────────────────────────────────

class ManifestValidationError(ValueError):
    """Raised when a manifest fails schema or semantic validation."""


# ── Public API ───────────────────────────────────────────────────────────────

def parse_manifest(path: Path) -> ControlManifest:
    """Read and validate a manifest JSON file; return a frozen ControlManifest.

    Raises ManifestValidationError on any structural or semantic violation.
    Does not resolve targets or contact the gateway.
    """
    path = Path(path).expanduser().resolve()
    raw_bytes = path.read_bytes()
    fingerprint = hashlib.sha256(raw_bytes).hexdigest()

    try:
        data = json.loads(raw_bytes)
    except json.JSONDecodeError as exc:
        raise ManifestValidationError(f"Invalid JSON in {path}: {exc}") from exc

    _validate_schema(data, path)

    resources = _parse_resources(data["resources"])

    # Target is optional in manifest (may be supplied via CLI flags).
    target_data = data.get("target", {})
    target = _parse_target(target_data, path) if target_data else None

    return ControlManifest(
        version=data["version"],
        target=target,
        resources=resources,
        source_path=path,
        source_fingerprint=fingerprint,
    )


def _validate_schema(data: Any, path: Path) -> None:
    if not isinstance(data, dict):
        raise ManifestValidationError(f"{path}: manifest must be a JSON object")
    if data.get("version") != 1:
        raise ManifestValidationError(
            f"{path}: unsupported manifest version {data.get('version')!r} (expected 1)"
        )
    if not isinstance(data.get("resources"), list) or not data["resources"]:
        raise ManifestValidationError(f"{path}: 'resources' must be a non-empty array")

    seen_keys: set[str] = set()
    for i, res in enumerate(data["resources"]):
        if not isinstance(res, dict):
            raise ManifestValidationError(f"{path}: resource[{i}] must be an object")
        for required in ("kind", "id", "manager", "policy", "spec", "managed_paths"):
            if required not in res:
                raise ManifestValidationError(
                    f"{path}: resource[{i}] missing required field '{required}'"
                )
        if not res["manager"]:
            raise ManifestValidationError(
                f"{path}: resource[{i}] 'manager' must be a non-empty string"
            )
        resource_key = f"{res['kind']}:{res['id']}"
        if resource_key in seen_keys:
            raise ManifestValidationError(
                f"{path}: duplicate resource key '{resource_key}'"
            )
        seen_keys.add(resource_key)
        if res.get("security_topology") and res.get("policy") != MergePolicy.CONFLICT.value:
            raise ManifestValidationError(
                f"{path}: {resource_key} has security_topology=true but policy="
                f"'{res['policy']}'; security topology resources must use 'conflict' policy"
            )
        _check_no_raw_credentials(res.get("spec", {}), resource_key)


def _parse_resources(raw: list[dict[str, Any]]) -> tuple[Resource, ...]:
    resources = []
    for res in raw:
        resources.append(Resource(
            kind=ResourceKind(res["kind"]),
            identifier=res["id"],
            manager=res["manager"],
            spec=res["spec"],
            managed_paths=tuple(res["managed_paths"]),
            policy=MergePolicy(res["policy"]),
        ))
    return tuple(resources)


def _parse_target(data: dict[str, Any], path: Path) -> ConfigTarget:
    for field in ("workspace_root", "config_path", "state_dir"):
        if field not in data:
            raise ManifestValidationError(
                f"{path}: target.{field} is required when 'target' is present"
            )
        if not isinstance(data[field], str) or not data[field]:
            raise ManifestValidationError(
                f"{path}: target.{field} must be a non-empty string"
            )
    return ConfigTarget(
        workspace_root=Path(data["workspace_root"]).expanduser().resolve()
        if not data["workspace_root"].startswith("__TMP__") else Path(data["workspace_root"]),
        config_path=Path(data["config_path"]).expanduser().resolve()
        if not data["config_path"].startswith("__TMP__") else Path(data["config_path"]),
        state_dir=Path(data["state_dir"]).expanduser().resolve()
        if not data["state_dir"].startswith("__TMP__") else Path(data["state_dir"]),
    )
