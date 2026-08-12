#!/usr/bin/env python3
"""Validate configured model IDs against their in-repository provenance.

This deliberately does not maintain a second, hardcoded model catalogue.
``config/models.yml`` is the source of truth: an externally dispatched cloud
model must name its provider wire ID and preserve the official source that
verified it.  Environment examples may select only a configured routing alias
or wire ID.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parent.parent
MODEL_YML = ROOT / "config" / "models.yml"
PROVIDERS_YML = ROOT / "config" / "providers.yml"
ENV_EXAMPLE = ROOT / ".env.example"
_ENV_MODEL_RE = re.compile(r"^([A-Z][A-Z0-9_]*_MODEL)=([^\s#]+)", re.MULTILINE)
_PROVENANCE_KINDS = frozenset({"provider-api", "catalog", "local-deployment"})


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return path.name


def _normalize(model_id: str) -> str:
    return model_id.strip().strip('"').strip("'").lower()


def _read_models() -> tuple[list[dict[str, Any]], list[str]]:
    if not MODEL_YML.is_file():
        return [], [f"missing required file: {_rel(MODEL_YML)}"]
    try:
        raw = yaml.safe_load(MODEL_YML.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return [], [f"invalid {_rel(MODEL_YML)}: {exc}"]
    rows = raw.get("models") if isinstance(raw, dict) else None
    if not isinstance(rows, list):
        return [], [f"{_rel(MODEL_YML)}: models must be a list"]
    return [row for row in rows if isinstance(row, dict)], []


def _documentation_hosts() -> tuple[dict[str, set[str]], list[str]]:
    if not PROVIDERS_YML.is_file():
        return {}, [f"missing required file: {_rel(PROVIDERS_YML)}"]
    try:
        raw = yaml.safe_load(PROVIDERS_YML.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return {}, [f"invalid {_rel(PROVIDERS_YML)}: {exc}"]
    if not isinstance(raw, dict):
        return {}, [f"{_rel(PROVIDERS_YML)}: root must be a mapping"]
    rows = dict(raw.get("providers") or {})
    rows.update(dict(raw.get("model_provenance") or {}))
    hosts: dict[str, set[str]] = {}
    errors: list[str] = []
    for backend, row in rows.items():
        documented = row.get("documentation_hosts") if isinstance(row, dict) else None
        if not isinstance(documented, list) or not all(isinstance(host, str) and host for host in documented):
            errors.append(f"{_rel(PROVIDERS_YML)}: {backend!r} requires documentation_hosts")
            continue
        hosts[str(backend)] = {host.lower() for host in documented}
    return hosts, errors


def _validate_provenance(
    row: dict[str, Any], index: int, documentation_hosts: dict[str, set[str]]
) -> list[str]:
    name = row.get("name", f"row {index}")
    api_model = row.get("api_model")
    cloud = row.get("device") == "cloud"
    if cloud and (not isinstance(api_model, str) or not api_model.strip()):
        return [f"{_rel(MODEL_YML)}: cloud model {name!r} requires api_model"]
    if not isinstance(api_model, str) or not api_model.strip():
        return []

    provenance = row.get("provenance")
    if not isinstance(provenance, dict):
        return [f"{_rel(MODEL_YML)}: api_model {api_model!r} requires provenance"]
    kind = provenance.get("kind")
    source_model_id = provenance.get("source_model_id")
    source_url = provenance.get("source_url")
    verified_on = provenance.get("verified_on")
    parsed = urlparse(source_url) if isinstance(source_url, str) else None
    errors: list[str] = []
    if kind not in _PROVENANCE_KINDS:
        errors.append(f"{_rel(MODEL_YML)}: model {name!r} has invalid provenance kind")
    if source_model_id != api_model:
        errors.append(f"{_rel(MODEL_YML)}: model {name!r} provenance source_model_id must equal api_model")
    if parsed is None or parsed.scheme != "https" or not parsed.hostname:
        errors.append(f"{_rel(MODEL_YML)}: model {name!r} provenance source_url must be HTTPS")
    expected_hosts = documentation_hosts.get(str(row.get("backend")))
    if not expected_hosts:
        errors.append(f"{_rel(MODEL_YML)}: model {name!r} backend lacks documentation authority")
    elif parsed is not None and parsed.hostname and parsed.hostname.lower() not in expected_hosts:
        errors.append(
            f"{_rel(MODEL_YML)}: model {name!r} source_url is outside its provider documentation authority"
        )
    if not isinstance(verified_on, str) or not verified_on.strip():
        errors.append(f"{_rel(MODEL_YML)}: model {name!r} provenance requires verified_on")
    if cloud and kind != "provider-api":
        errors.append(f"{_rel(MODEL_YML)}: cloud model {name!r} must use provider-api provenance")
    return errors


def configured_model_ids() -> tuple[set[str], list[str]]:
    """Return config-derived aliases/wire IDs after validating provenance."""
    rows, errors = _read_models()
    documentation_hosts, host_errors = _documentation_hosts()
    errors.extend(host_errors)
    ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        errors.extend(_validate_provenance(row, index, documentation_hosts))
        for key in ("name", "api_model"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                ids.add(_normalize(value))
    return ids, errors


def scan_models_yml() -> list[str]:
    _, errors = configured_model_ids()
    return errors


def _check_model_id(model_id: str, configured_ids: set[str], source: str, line_hint: str) -> str | None:
    normalized = _normalize(model_id)
    if not normalized or normalized.startswith("${"):
        return None
    if normalized in configured_ids:
        return None
    return f"{source}: model ID {model_id!r} ({line_hint}) is absent from config/models.yml"


def scan_env_example() -> list[str]:
    configured_ids, errors = configured_model_ids()
    if not ENV_EXAMPLE.is_file():
        return errors + [f"missing required file: {_rel(ENV_EXAMPLE)}"]
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    for match in _ENV_MODEL_RE.finditer(text):
        key, value = match.groups()
        error = _check_model_id(value, configured_ids, _rel(ENV_EXAMPLE), key)
        if error:
            errors.append(error)
    return errors


def main() -> int:
    violations = scan_models_yml() + scan_env_example()
    # scan_env_example includes model provenance errors so present each once.
    violations = list(dict.fromkeys(violations))
    if violations:
        print("\n".join(violations), file=sys.stderr)
        return 1
    print("OK: configured model IDs have source provenance and environment examples reference the registry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
