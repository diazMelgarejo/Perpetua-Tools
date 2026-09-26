"""Staged prohibited-address gate for scripts/review/repo_hygiene.py.

Fixtures use documentation forms only (RFC1918 192.168.0.1, TEST-NET-1
192.0.2.1, generic loopback / ULA / CGNAT examples). No host inventory.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parent.parent
HYGIENE_PATH = ROOT / "scripts" / "review" / "repo_hygiene.py"


def load_repo_hygiene():
    spec = importlib.util.spec_from_file_location("repo_hygiene_private_ranges", HYGIENE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> None:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr.strip() or f"git {' '.join(args)} failed")


def _init_hygiene_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.name", "Codex")
    _git(repo, "config", "user.email", "codex@openai.com")
    (repo / "README.md").write_text("placeholder\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")


def test_staged_rfc1918_literal_blocks_hygiene_gate(tmp_path: Path) -> None:
    """A staged documentation-form RFC1918 literal fails the pre-commit entrypoint."""
    repo = tmp_path / "repo"
    _init_hygiene_repo(repo)
    note = repo / "docs" / "note.md"
    note.parent.mkdir()
    note.write_text("gateway example 192.168.0.1\n", encoding="utf-8")
    _git(repo, "add", "docs/note.md")

    mod = load_repo_hygiene()
    errors = mod.scan_staged_prohibited_address_literals(repo)
    assert len(errors) == 1
    assert "rfc1918" in errors[0]
    assert "docs/note.md:1" in errors[0]
    assert "192.168.0.1" not in errors[0]

    proc = subprocess.run(
        [sys.executable, str(HYGIENE_PATH), str(repo)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.returncode == 1
    assert (
        "prohibited private-range literal (rfc1918) in staged file: docs/note.md:1"
        in proc.stderr
    )


def test_staged_documentation_address_is_not_prohibited(tmp_path: Path) -> None:
    """192.0.2.1 is TEST-NET-1 documentation space, not a private-range literal."""
    repo = tmp_path / "repo"
    _init_hygiene_repo(repo)
    note = repo / "docs" / "note.md"
    note.parent.mkdir()
    note.write_text("documentation host 192.0.2.1\n", encoding="utf-8")
    _git(repo, "add", "docs/note.md")

    mod = load_repo_hygiene()
    assert mod.scan_staged_prohibited_address_literals(repo) == []


def test_unstaged_private_range_literal_does_not_block(tmp_path: Path) -> None:
    """Working-tree drift that is not staged is outside the commit gate."""
    repo = tmp_path / "repo"
    _init_hygiene_repo(repo)
    note = repo / "docs" / "note.md"
    note.parent.mkdir()
    note.write_text("gateway example 192.168.0.1\n", encoding="utf-8")

    mod = load_repo_hygiene()
    assert mod.scan_staged_prohibited_address_literals(repo) == []


def test_staged_prohibited_address_classes_match_dialer(tmp_path: Path) -> None:
    """Loopback, ULA, and CGNAT use the same families as the SSRF dialer denylist."""
    samples = {
        "10.0.0.1": "rfc1918",
        "172.16.0.1": "rfc1918",
        "192.168.0.1": "rfc1918",
        "127.0.0.1": "loopback",
        "::1": "loopback",
        "fc00::1": "ula",
        "100.64.0.1": "cgnat",
        "::ffff:192.168.0.1": "rfc1918",
    }
    repo = tmp_path / "repo"
    _init_hygiene_repo(repo)
    mod = load_repo_hygiene()
    note = repo / "docs" / "note.md"
    note.parent.mkdir()
    for literal, kind in samples.items():
        note.write_text(f"example {literal}\n", encoding="utf-8")
        _git(repo, "add", "docs/note.md")
        errors = mod.scan_staged_prohibited_address_literals(repo)
        assert errors, literal
        assert f"({kind})" in errors[0]
        assert literal not in errors[0]
        _git(repo, "reset", "-q", "HEAD", "--", "docs/note.md")


def test_public_and_adjacent_ranges_are_not_prohibited(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_hygiene_repo(repo)
    note = repo / "docs" / "note.md"
    note.parent.mkdir()
    note.write_text(
        "\n".join(
            [
                "192.0.2.1",
                "172.15.0.1",
                "172.32.0.1",
                "11.0.0.1",
                "8.8.8.8",
                "2001:db8::1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", "docs/note.md")
    mod = load_repo_hygiene()
    assert mod.scan_staged_prohibited_address_literals(repo) == []


def test_scanner_source_exception_allows_range_definitions(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_hygiene_repo(repo)
    path = repo / "scripts" / "review" / "repo_hygiene_core.py"
    path.parent.mkdir(parents=True)
    path.write_text('NET = "10.0.0.0/8"\n', encoding="utf-8")
    _git(repo, "add", "scripts/review/repo_hygiene_core.py")
    mod = load_repo_hygiene()
    assert mod.scan_staged_prohibited_address_literals(repo) == []
