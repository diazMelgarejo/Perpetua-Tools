#!/usr/bin/env python3
"""Ensure gitignored local mesh secrets exist (never committed).

Writes to .env.local (Perpetua + optional orama-system sibling) and
.local/mesh-secrets.json:
  - GOSSIP_SHARED_SECRET — shared across all fleet peers for gossip + discovery handshake

Integrative: harmonizes missing/empty keys only — never replaces operator values
unless ``--force`` rotation is requested (old values migrate to commented lines).

Pair with orama-system scripts/mesh/ensure_local_mesh_secrets.py — either repo can
bootstrap; sibling .env.local files are harmonized when ORAMA_SYSTEM_PATH is set.
"""
from __future__ import annotations

import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

_MESH_DIR = Path(__file__).resolve().parent
if str(_MESH_DIR) not in sys.path:
    sys.path.insert(0, str(_MESH_DIR))
from dotenv_merge import harmonize_dotenv_keys
from mesh_logging import get_mesh_logger, harden_local_file

ROOT = Path(__file__).resolve().parents[2]
LOCAL_DIR = ROOT / ".local"
SECRETS_JSON = LOCAL_DIR / "mesh-secrets.json"
ENV_KEYS = frozenset({"GOSSIP_SHARED_SECRET"})
ENV_HEADER = (
    "# Local mesh secrets — never commit (harmonized by ensure_local_mesh_secrets.py)"
)
log = get_mesh_logger("perpetua.mesh.secrets", repo_root=ROOT)


def _sibling_secret_stores() -> list[Path]:
    stores = [SECRETS_JSON]
    orama = os.environ.get("ORAMA_SYSTEM_PATH", "").strip()
    if orama:
        stores.append(Path(orama) / ".local" / "mesh-secrets.json")
    return stores


def _repo_env_paths() -> list[Path]:
    paths = [ROOT / ".env.local"]
    orama = os.environ.get("ORAMA_SYSTEM_PATH", "").strip()
    if orama:
        paths.append(Path(orama) / ".env.local")
    return paths


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    harden_local_file(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _read_existing_secret() -> str:
    for store_path in _sibling_secret_stores():
        store = _load_json(store_path)
        secret = (store.get("GOSSIP_SHARED_SECRET") or "").strip()
        if secret:
            return secret
    return ""


def _merge_env(path: Path, values: dict[str, str], *, force: bool = False) -> None:
    harmonize_dotenv_keys(
        path,
        values,
        managed_keys=ENV_KEYS,
        header_comment=ENV_HEADER,
        replace_keys=ENV_KEYS if force else frozenset(),
        supersede_timestamp=datetime.now(timezone.utc).isoformat(),
    )
    harden_local_file(path)


def _persist_secret_store(secret: str, *, previous: str = "") -> None:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    payload: dict[str, str] = {
        "GOSSIP_SHARED_SECRET": secret,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if previous:
        payload[
            f"GOSSIP_SHARED_SECRET__PREVIOUS_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        ] = previous
    for store_path in _sibling_secret_stores():
        store_path.parent.mkdir(parents=True, exist_ok=True)
        merged = _load_json(store_path)
        merged.update(payload)
        store_path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        harden_local_file(store_path)


def ensure_gossip_secret(*, force: bool = False) -> str:
    secret = _read_existing_secret()
    if not secret or force:
        previous = secret
        secret = secrets.token_urlsafe(32)
        _persist_secret_store(secret, previous=previous if force and previous else "")
    else:
        for store_path in _sibling_secret_stores():
            harden_local_file(store_path)

    for path in _repo_env_paths():
        if path.parent.exists() or path == ROOT / ".env.local":
            path.parent.mkdir(parents=True, exist_ok=True)
            _merge_env(path, {"GOSSIP_SHARED_SECRET": secret}, force=force)
    os.environ["GOSSIP_SHARED_SECRET"] = secret
    return secret


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Ensure local-only mesh secrets.")
    parser.add_argument("--force", action="store_true", help="Rotate GOSSIP_SHARED_SECRET")
    args = parser.parse_args()
    ensure_gossip_secret(force=args.force)
    log.info("OK: GOSSIP_SHARED_SECRET present in .env.local (value not printed)")
    log.info("     archive: %s", SECRETS_JSON.relative_to(ROOT))
    log.info("     distribute this secret to all mesh peers out-of-band — never commit")
    log.info("     pair: orama-system scripts/mesh/ensure_local_mesh_secrets.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
