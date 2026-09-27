"""TDD RED: topology probe for Cursor worker Mode A / Mode B selection.

Encodes the Phase 0 / I1 contract from the cursor self-hosted worker
coordination plan. Production logic lives in scripts/cursor/topology_probe.py
— these tests land first and must fail until the probe is implemented.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROBE_SCRIPT = ROOT / "scripts" / "cursor" / "topology_probe.py"

REQUIRED_KEYS = {
    "cwd",
    "toplevel",
    "git_common_dir",
    "board_present",
    "board_dev",
    "board_ino",
    "board_size",
    "topology_match",
    "queue_write_authority",
    "mode",
}


def _load_probe_module() -> ModuleType:
    import importlib.util

    spec = importlib.util.spec_from_file_location("topology_probe", PROBE_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git_env() -> dict[str, str]:
    """Drop inherited repo-location variables so fixtures init the temp checkout."""
    env = os.environ.copy()
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    return env


def _git_init(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-q"],
        cwd=path,
        check=True,
        env=_git_env(),
    )
    return path


def _write_board(repo: Path, payload: bytes = b"fake-perpetua-core-db") -> Path:
    state = repo / ".state"
    state.mkdir(parents=True, exist_ok=True)
    board = state / "perpetua_core.db"
    board.write_bytes(payload)
    return board


def _stat_board(board: Path) -> os.stat_result:
    return board.stat()


@pytest.fixture
def probe_mod() -> ModuleType:
    return _load_probe_module()


def test_probe_returns_required_keys(tmp_path: Path, probe_mod: ModuleType) -> None:
    repo = _git_init(tmp_path / "repo")
    result = probe_mod.probe(repo)

    assert isinstance(result, dict)
    assert REQUIRED_KEYS <= set(result.keys())
    assert Path(result["cwd"]).resolve() == repo.resolve()
    assert isinstance(result["board_present"], bool)
    assert result["mode"] in ("A", "B")
    assert result["board_size"] is None or isinstance(result["board_size"], int)


def test_mode_a_when_full_orchestrator_identity_matches(
    tmp_path: Path, probe_mod: ModuleType
) -> None:
    repo = _git_init(tmp_path / "coord-root")
    board = _write_board(repo)
    st = _stat_board(board)

    result = probe_mod.probe(
        repo,
        orchestrator_ino=st.st_ino,
        orchestrator_dev=st.st_dev,
        orchestrator_size=st.st_size,
    )

    assert result["mode"] == "A"
    assert result["topology_match"] is True
    assert result["queue_write_authority"] is False
    assert result["board_present"] is True
    assert result["board_ino"] == st.st_ino
    assert result["board_dev"] == st.st_dev
    assert result["board_size"] == st.st_size
    assert Path(result["toplevel"]).resolve() == repo.resolve()


def test_mode_b_when_board_missing(tmp_path: Path, probe_mod: ModuleType) -> None:
    repo = _git_init(tmp_path / "no-board")

    result = probe_mod.probe(repo, orchestrator_ino=12345)

    assert result["mode"] == "B"
    assert result["board_present"] is False
    assert result["board_ino"] is None
    assert result["board_dev"] is None
    assert result["board_size"] is None


def test_mode_b_when_orchestrator_ino_mismatches(
    tmp_path: Path, probe_mod: ModuleType
) -> None:
    repo = _git_init(tmp_path / "inode-mismatch")
    board = _write_board(repo)
    st = _stat_board(board)

    result = probe_mod.probe(
        repo,
        orchestrator_ino=st.st_ino + 999_999,
        orchestrator_dev=st.st_dev,
        orchestrator_size=st.st_size,
    )

    assert result["mode"] == "B"
    assert result["board_present"] is True
    assert result["board_ino"] == st.st_ino


def test_mode_b_when_orchestrator_device_mismatches(
    tmp_path: Path, probe_mod: ModuleType
) -> None:
    repo = _git_init(tmp_path / "device-mismatch")
    board = _write_board(repo)
    st = _stat_board(board)

    result = probe_mod.probe(
        repo,
        orchestrator_ino=st.st_ino,
        orchestrator_dev=st.st_dev + 1,
        orchestrator_size=st.st_size,
    )

    assert result["mode"] == "B"
    assert result["board_dev"] == st.st_dev


def test_mode_b_when_orchestrator_size_mismatches(
    tmp_path: Path, probe_mod: ModuleType
) -> None:
    repo = _git_init(tmp_path / "size-mismatch")
    board = _write_board(repo)
    st = _stat_board(board)

    result = probe_mod.probe(
        repo,
        orchestrator_ino=st.st_ino,
        orchestrator_dev=st.st_dev,
        orchestrator_size=st.st_size + 1,
    )

    assert result["mode"] == "B"
    assert result["topology_match"] is False
    assert result["queue_write_authority"] is False


def test_mode_b_when_toplevel_differs_from_repo_root_via_symlink(
    tmp_path: Path, probe_mod: ModuleType
) -> None:
    """Mode B when caller's repo_root resolves differently from git toplevel.

    Uses a nested path under the real checkout (and a symlink layer) so that
    ``git rev-parse --show-toplevel`` returns the repo root while the caller
    passed a different resolved path — matching the plan's Mode B rule.
    """
    real = _git_init(tmp_path / "real-repo")
    board = _write_board(real)
    st = _stat_board(board)

    nested = real / "pkgs" / "nested"
    nested.mkdir(parents=True)
    link_root = tmp_path / "via-symlink"
    link_root.symlink_to(nested)

    result = probe_mod.probe(
        link_root,
        orchestrator_ino=st.st_ino,
        orchestrator_dev=st.st_dev,
        orchestrator_size=st.st_size,
    )

    assert result["mode"] == "B"
    assert Path(result["toplevel"]).resolve() == real.resolve()
    assert Path(result["toplevel"]).resolve() != link_root.resolve()


def test_mode_b_without_complete_orchestrator_identity_even_if_board_present(
    tmp_path: Path, probe_mod: ModuleType
) -> None:
    repo = _git_init(tmp_path / "no-orchestrator-ino")
    board = _write_board(repo)

    result = probe_mod.probe(repo, orchestrator_ino=_stat_board(board).st_ino)

    assert result["mode"] == "B"
    assert result["board_present"] is True


def test_probe_module_does_not_import_gossip_or_coordination() -> None:
    """Static guarantee: probe must not pull GossipBus / agent_coordination."""
    source = PROBE_SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(PROBE_SCRIPT))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            imported.add(mod)
            for alias in node.names:
                imported.add(f"{mod}.{alias.name}" if mod else alias.name)

    forbidden_prefixes = (
        "orchestrator.gossip_bus",
        "orchestrator.agent_coordination",
        "agent_coordination",
    )
    offenders = [
        name
        for name in imported
        if any(
            name == prefix or name.startswith(prefix + ".")
            for prefix in forbidden_prefixes
        )
        or name.endswith("gossip_bus")
        or name.endswith("agent_coordination")
    ]
    # Also ban relative script imports that exec coordination CLIs.
    text_offenders = []
    for needle in (
        "orchestrator.gossip_bus",
        "orchestrator.agent_coordination",
        "scripts.agent_coordination",
        "agent_coordination.py",
    ):
        if needle in source:
            text_offenders.append(needle)

    assert not offenders, f"forbidden imports: {offenders}"
    assert not text_offenders, f"forbidden references in source: {text_offenders}"


def test_cli_prints_json_and_exits_zero(tmp_path: Path) -> None:
    repo = _git_init(tmp_path / "cli-repo")
    board = _write_board(repo)
    st = _stat_board(board)

    result = subprocess.run(
        [
            sys.executable,
            str(PROBE_SCRIPT),
            "--orchestrator-ino",
            str(st.st_ino),
            "--orchestrator-dev",
            str(st.st_dev),
            "--orchestrator-size",
            str(st.st_size),
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=_git_env(),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert REQUIRED_KEYS <= set(payload.keys())
    assert payload["mode"] in ("A", "B")


def test_cli_accepts_missing_orchestrator_ino_flag(tmp_path: Path) -> None:
    repo = _git_init(tmp_path / "cli-no-ino")

    result = subprocess.run(
        [sys.executable, str(PROBE_SCRIPT)],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=_git_env(),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "B"


def test_mode_b_when_not_a_git_repo(tmp_path: Path) -> None:
    """Non-git directories must be Mode B, not a subprocess crash."""
    from scripts.cursor.topology_probe import probe

    bare = tmp_path / "not-a-repo"
    bare.mkdir()
    result = probe(bare, orchestrator_ino=1)
    assert result["mode"] == "B"
    assert result["board_present"] is False
    assert result["toplevel"] is None or result["toplevel"] == ""


def test_rev_parse_timeout_classifies_mode_b(
    tmp_path: Path, probe_mod: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _git_init(tmp_path / "stalled-git")

    def _timeout(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="git", timeout=5)

    monkeypatch.setattr(probe_mod.subprocess, "run", _timeout)
    result = probe_mod.probe(repo, orchestrator_ino=1, orchestrator_dev=1, orchestrator_size=1)
    assert result["mode"] == "B"
    assert result["toplevel"] is None
    assert result["queue_write_authority"] is False


def test_probe_ignores_inherited_git_location(
    tmp_path: Path, probe_mod: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _git_init(tmp_path / "real-checkout")
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "not-a-git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path))
    result = probe_mod.probe(repo)
    assert Path(result["toplevel"]).resolve() == repo.resolve()


def test_mode_b_when_board_path_is_a_directory(
    tmp_path: Path, probe_mod: ModuleType
) -> None:
    repo = _git_init(tmp_path / "dir-board")
    (repo / ".state" / "perpetua_core.db").mkdir(parents=True)
    result = probe_mod.probe(
        repo,
        orchestrator_ino=1,
        orchestrator_dev=1,
        orchestrator_size=1,
    )
    assert result["board_present"] is False
    assert result["board_ino"] is None
    assert result["mode"] == "B"
