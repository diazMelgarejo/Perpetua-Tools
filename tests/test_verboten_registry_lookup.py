"""The forbidden-literal registry must be found from any worktree, not only under the tree.

The lookup walks up looking for a directory that contains a sibling ``orama-system``
checkout. A worktree kept elsewhere has no such ancestor, so the registry was not found
and every local gate ran with no forbidden fragments: it passed locally while CI, which
injects the registry, failed. ``OPENCLAW_ROOT`` is the deliberate, exported pointer to
the workspace and is used only when the ancestor walk finds nothing.

Three implementations exist (two Python modules and a shell library) and must agree.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GIT_DIR = ROOT / "scripts" / "git"
LIB = GIT_DIR / "banned_attribution_lib.sh"
KEY = "owner_name"
VALUE = "SamplePlaceholder"


def _load(name: str, path: Path):
    """Import a script module by path without requiring it to be a package."""
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module  # dataclasses resolve their module through sys.modules
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def _audit_engine(root: Path) -> list[str]:
    """Resolve the key through scripts/git/audit_engine.py."""
    return _load("audit_engine_under_test", GIT_DIR / "audit_engine.py").private_literal_values(root, KEY)


def _repo_hygiene(root: Path) -> list[str]:
    """Resolve the key through scripts/review/repo_hygiene.py."""
    path = ROOT / "scripts" / "review" / "repo_hygiene.py"
    return _load("repo_hygiene_under_test", path).private_literal_values(root, KEY)


def _shell(root: Path) -> list[str]:
    """Resolve the key through the shell library the pre-commit scanners source."""
    result = subprocess.run(
        ["bash", "-c", f'source "{LIB}"; list_private_literal_values "$1" "$2"', "_", str(root), KEY],
        capture_output=True, text=True, check=False,
    )
    return [line for line in result.stdout.splitlines() if line]


IMPLEMENTATIONS: list[tuple[str, Callable[[Path], list[str]]]] = [
    ("audit_engine", _audit_engine),
    ("repo_hygiene", _repo_hygiene),
    ("shell", _shell),
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every case with neither pointer set so each test states its own."""
    monkeypatch.delenv("OPENCLAW_VERBOTEN_LITERALS", raising=False)
    monkeypatch.delenv("OPENCLAW_ROOT", raising=False)


def _workspace(base: Path, name: str, value: str = VALUE) -> Path:
    """Create a workspace directory that holds a registry."""
    ws = base / name
    ws.mkdir(parents=True)
    (ws / ".verboten-literals.local").write_text(f"{KEY}={value}\n", encoding="utf-8")
    return ws


def _outside_tree(base: Path) -> Path:
    """A checkout with no ancestor containing orama-system, like a hub worktree."""
    path = base / "hub" / "worktree"
    path.mkdir(parents=True)
    return path


@pytest.mark.parametrize(("label", "resolve"), IMPLEMENTATIONS)
def test_registry_is_found_through_openclaw_root_when_there_is_no_ancestor(
    label: str, resolve: Callable[[Path], list[str]], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A checkout outside the tree still gets the real registry via the exported root."""
    workspace = _workspace(tmp_path, "workspace")
    checkout = _outside_tree(tmp_path)
    monkeypatch.setenv("OPENCLAW_ROOT", str(workspace))

    assert resolve(checkout) == [VALUE], label


@pytest.mark.parametrize(("label", "resolve"), IMPLEMENTATIONS)
def test_openclaw_root_without_a_registry_changes_nothing(
    label: str, resolve: Callable[[Path], list[str]], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unset or registry-less root yields no values and raises nothing."""
    empty = tmp_path / "empty"
    empty.mkdir()
    checkout = _outside_tree(tmp_path)
    monkeypatch.setenv("OPENCLAW_ROOT", str(empty))

    assert resolve(checkout) == [], label


@pytest.mark.parametrize(("label", "resolve"), IMPLEMENTATIONS)
def test_the_ancestor_walk_still_wins_over_openclaw_root(
    label: str, resolve: Callable[[Path], list[str]], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Existing behaviour is preserved: a found ancestor is authoritative."""
    ancestor = _workspace(tmp_path, "ancestor", "FromAncestor")
    (ancestor / "orama-system").mkdir()
    checkout = ancestor / "repo"
    checkout.mkdir()
    other = _workspace(tmp_path, "other", "FromEnvRoot")
    monkeypatch.setenv("OPENCLAW_ROOT", str(other))

    assert resolve(checkout) == ["FromAncestor"], label


@pytest.mark.parametrize(("label", "resolve"), IMPLEMENTATIONS)
def test_an_explicit_registry_path_still_wins_over_everything(
    label: str, resolve: Callable[[Path], list[str]], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OPENCLAW_VERBOTEN_LITERALS is the highest-priority source, as CI uses it."""
    explicit = _workspace(tmp_path, "explicit", "FromExplicit") / ".verboten-literals.local"
    workspace = _workspace(tmp_path, "workspace")
    checkout = _outside_tree(tmp_path)
    monkeypatch.setenv("OPENCLAW_VERBOTEN_LITERALS", str(explicit))
    monkeypatch.setenv("OPENCLAW_ROOT", str(workspace))

    assert resolve(checkout) == ["FromExplicit"], label
