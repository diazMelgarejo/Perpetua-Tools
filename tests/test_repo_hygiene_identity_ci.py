"""Regression tests for deterministic private-identity authorization in CI."""
from __future__ import annotations

import hashlib
import importlib.util
import subprocess
from pathlib import Path


ROOT = Path(__file__).parent.parent
HYGIENE_PATH = ROOT / "scripts" / "review" / "repo_hygiene.py"


def load_repo_hygiene():
    spec = importlib.util.spec_from_file_location("repo_hygiene_identity_ci", HYGIENE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_git_config(name: str, email: str):
    def _run_git(_root: Path, *args: str):
        key = args[-1]
        value = name if key == "user.name" else email if key == "user.email" else ""
        return subprocess.CompletedProcess([], 0, stdout=f"{value}\n", stderr="")

    return _run_git


def test_check_identity_accepts_tracked_fingerprint_without_private_registry(
    tmp_path, monkeypatch
):
    hygiene = load_repo_hygiene()
    name = "Synthetic Owner"
    email = "owner@private.invalid"
    canonical = f"{name.casefold()} <{email.casefold()}>"
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    registry = tmp_path / ".github" / "authorized-private-identities.sha256"
    registry.parent.mkdir(parents=True)
    registry.write_text(f"# test identity\n{digest}\n", encoding="utf-8")

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("OPENCLAW_VERBOTEN_LITERALS", raising=False)
    monkeypatch.setattr(hygiene._core, "run_git", fake_git_config(name, email))

    assert not (tmp_path / ".verboten-literals.local").exists()
    assert hygiene.check_identity(tmp_path) == []


def test_check_identity_rejects_unregistered_private_identity(tmp_path, monkeypatch):
    hygiene = load_repo_hygiene()
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("OPENCLAW_VERBOTEN_LITERALS", raising=False)
    monkeypatch.setattr(
        hygiene._core,
        "run_git",
        fake_git_config("Unregistered Owner", "other@private.invalid"),
    )

    errors = hygiene.check_identity(tmp_path)
    assert len(errors) == 1
    assert "identity mismatch" in errors[0]
