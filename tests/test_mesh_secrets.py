from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any, Protocol

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1]
MESH = ROOT / "scripts" / "mesh"


class DotenvModule(Protocol):
    def harmonize_dotenv_keys(
        self,
        path: Path,
        values: dict[str, str],
        *,
        managed_keys: frozenset[str] | None = None,
        header_comment: str | None = None,
        replace_keys: frozenset[str] | None = None,
        supersede_timestamp: str | None = None,
    ) -> list[str]: ...

    def read_dotenv_key(self, path: Path, key: str) -> str: ...


class SecretsModule(Protocol):
    ROOT: Path
    SECRETS_JSON: Path

    def ensure_gossip_secret(self, *, force: bool = False) -> str: ...


def _load_module(name: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def dotenv_mod() -> DotenvModule:
    return _load_module("dotenv_merge", MESH / "dotenv_merge.py")  # type: ignore[return-value]


@pytest.fixture
def secrets_mod(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SecretsModule:
    monkeypatch.delenv("ORAMA_SYSTEM_PATH", raising=False)
    return _load_module("ensure_local_mesh_secrets", MESH / "ensure_local_mesh_secrets.py")  # type: ignore[return-value]


def test_harmonize_dotenv_updates_last_duplicate_declaration(
    dotenv_mod: DotenvModule, tmp_path: Path
) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "GOSSIP_SHARED_SECRET=\n"
        "GOSSIP_SHARED_SECRET=\n",
        encoding="utf-8",
    )
    dotenv_mod.harmonize_dotenv_keys(
        env_file,
        {"GOSSIP_SHARED_SECRET": "new-secret"},
        managed_keys=frozenset({"GOSSIP_SHARED_SECRET"}),
    )
    text = env_file.read_text(encoding="utf-8")
    assert "# duplicate (inactive; effective declaration follows):" in text
    assert text.strip().endswith("GOSSIP_SHARED_SECRET=new-secret")


def test_harmonize_dotenv_rotation_supersedes_without_deleting(
    dotenv_mod: DotenvModule, tmp_path: Path
) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text("GOSSIP_SHARED_SECRET=old-secret\n", encoding="utf-8")
    dotenv_mod.harmonize_dotenv_keys(
        env_file,
        {"GOSSIP_SHARED_SECRET": "new-secret"},
        managed_keys=frozenset({"GOSSIP_SHARED_SECRET"}),
        replace_keys=frozenset({"GOSSIP_SHARED_SECRET"}),
        supersede_timestamp="2026-07-26T19:00:00+00:00",
    )
    text = env_file.read_text(encoding="utf-8")
    assert "# superseded 2026-07-26T19:00:00+00:00: GOSSIP_SHARED_SECRET=old-secret" in text
    assert "GOSSIP_SHARED_SECRET=new-secret" in text
    assert "old-secret" in text


def test_harmonize_dotenv_keeps_existing_without_appending_duplicate(
    dotenv_mod: DotenvModule, tmp_path: Path
) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text("GOSSIP_SHARED_SECRET=keep-me\n", encoding="utf-8")
    dotenv_mod.harmonize_dotenv_keys(
        env_file,
        {"GOSSIP_SHARED_SECRET": "keep-me"},
        managed_keys=frozenset({"GOSSIP_SHARED_SECRET"}),
    )
    text = env_file.read_text(encoding="utf-8")
    assert text.count("GOSSIP_SHARED_SECRET=") == 1
    assert "keep-me" in text


def test_adopts_existing_env_local_secret_without_mesh_store(
    secrets_mod: SecretsModule, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo_root = tmp_path / "perpetua"
    repo_root.mkdir()
    (repo_root / ".local").mkdir()
    monkeypatch.setattr(secrets_mod, "ROOT", repo_root)
    monkeypatch.setattr(secrets_mod, "LOCAL_DIR", repo_root / ".local")
    monkeypatch.setattr(secrets_mod, "SECRETS_JSON", repo_root / ".local" / "mesh-secrets.json")

    env_file = repo_root / ".env.local"
    env_file.write_text("GOSSIP_SHARED_SECRET=env-only-secret\n", encoding="utf-8")

    secret = secrets_mod.ensure_gossip_secret(force=False)
    assert secret == "env-only-secret"
    assert env_file.read_text(encoding="utf-8").count("GOSSIP_SHARED_SECRET=") == 1
    store = __import__("json").loads(secrets_mod.SECRETS_JSON.read_text(encoding="utf-8"))
    assert store["GOSSIP_SHARED_SECRET"] == "env-only-secret"


def test_force_rotation_updates_env_and_archive(
    secrets_mod: SecretsModule, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo_root = tmp_path / "perpetua"
    repo_root.mkdir()
    (repo_root / ".local").mkdir()
    monkeypatch.setattr(secrets_mod, "ROOT", repo_root)
    monkeypatch.setattr(secrets_mod, "LOCAL_DIR", repo_root / ".local")
    monkeypatch.setattr(secrets_mod, "SECRETS_JSON", repo_root / ".local" / "mesh-secrets.json")

    env_file = repo_root / ".env.local"
    env_file.write_text("GOSSIP_SHARED_SECRET=peer-old\n", encoding="utf-8")
    secrets_mod.SECRETS_JSON.write_text(
        '{"GOSSIP_SHARED_SECRET": "peer-old"}', encoding="utf-8"
    )

    new_secret = secrets_mod.ensure_gossip_secret(force=True)
    assert new_secret != "peer-old"
    assert f"GOSSIP_SHARED_SECRET={new_secret}" in env_file.read_text(encoding="utf-8")
    store = __import__("json").loads(secrets_mod.SECRETS_JSON.read_text(encoding="utf-8"))
    assert store["GOSSIP_SHARED_SECRET"] == new_secret
    assert "peer-old" in env_file.read_text(encoding="utf-8")
    assert any(k.startswith("GOSSIP_SHARED_SECRET__PREVIOUS_") for k in store)


def test_adopts_existing_orama_secret_store(
    secrets_mod: SecretsModule, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo_root = tmp_path / "perpetua"
    orama_root = tmp_path / "orama"
    repo_root.mkdir(parents=True)
    (repo_root / ".local").mkdir()
    orama_root.mkdir(parents=True)
    (orama_root / ".local").mkdir()
    monkeypatch.setenv("ORAMA_SYSTEM_PATH", str(orama_root))
    monkeypatch.setattr(secrets_mod, "ROOT", repo_root)
    monkeypatch.setattr(secrets_mod, "LOCAL_DIR", repo_root / ".local")
    monkeypatch.setattr(secrets_mod, "SECRETS_JSON", repo_root / ".local" / "mesh-secrets.json")

    orama_store = orama_root / ".local" / "mesh-secrets.json"
    orama_store.write_text('{"GOSSIP_SHARED_SECRET": "shared-from-orama"}', encoding="utf-8")

    secret = secrets_mod.ensure_gossip_secret(force=False)
    assert secret == "shared-from-orama"
    assert "shared-from-orama" in (repo_root / ".env.local").read_text(encoding="utf-8")
