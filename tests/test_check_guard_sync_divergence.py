"""Tests for scripts/git/check-guard-sync-divergence.sh."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/git/check-guard-sync-divergence.sh"

pytestmark = pytest.mark.unit


def _init_repo(path: Path, name: str, email: str) -> None:
    """Initialize a git fixture repository with a fixed identity."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", email],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", name],
        cwd=path,
        check=True,
        capture_output=True,
    )


def _commit_file(repo: Path, rel: str, content: str, msg: str) -> None:
    """Add and commit one file in a fixture repository."""
    dest = repo / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", rel], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _run_checker(workspace: Path, canon: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["WORKSPACE_ROOT"] = str(workspace)
    env["GUARD_SYNC_CANON_ROOT"] = str(canon)
    return subprocess.run(
        ["bash", str(CHECKER), "--workspace"],
        cwd=canon,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def test_byte_identical_siblings_pass(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    canon = workspace / "orama-system"
    sibling = workspace / "Perpetua-Tools"
    rel = "scripts/git/audit_engine.py"
    body = "# canonical v1\n"

    for repo in (canon, sibling):
        _init_repo(repo, "Tester", "tester@example.com")
        _commit_file(repo, rel, body, "init")

    result = _run_checker(workspace, canon)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "byte-identical" in result.stdout


def test_sibling_lagging_canonical_history_passes(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    canon = workspace / "orama-system"
    sibling = workspace / "Perpetua-Tools"
    rel = "scripts/git/audit_engine.py"

    _init_repo(canon, "Tester", "tester@example.com")
    _commit_file(canon, rel, "# v1\n", "v1")
    _commit_file(canon, rel, "# v2\n", "v2")

    _init_repo(sibling, "Tester", "tester@example.com")
    _commit_file(sibling, rel, "# v1\n", "stale copy")

    result = _run_checker(workspace, canon)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "lags canonical history" in result.stdout


def test_hook_git_environment_does_not_rebind_independent_siblings(tmp_path: Path) -> None:
    """Git env from a hook must not rebind an independent sibling checkout."""
    workspace = tmp_path / "ws"
    canon = workspace / "orama-system"
    sibling = workspace / "Perpetua-Tools"
    rel = "scripts/git/audit_engine.py"
    body = "# canonical v1\n"

    for repo in (canon, sibling):
        _init_repo(repo, "Tester", "tester@example.com")
        _commit_file(repo, rel, body, "init")

    env = os.environ.copy()
    env["WORKSPACE_ROOT"] = str(workspace)
    env["GUARD_SYNC_CANON_ROOT"] = str(canon)
    env["GIT_DIR"] = str(canon / ".git")
    result = subprocess.run(
        ["bash", str(CHECKER), "--workspace"],
        cwd=canon,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "byte-identical" in result.stdout
    assert "shares canonical git history" not in result.stdout


def test_sibling_ahead_of_canonical_fails_closed(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    canon = workspace / "orama-system"
    sibling = workspace / "Perpetua-Tools"
    rel = "scripts/git/audit_engine.py"
    shared = "# canonical\n"

    _init_repo(canon, "Tester", "tester@example.com")
    _commit_file(canon, rel, shared, "canon")

    _init_repo(sibling, "Tester", "tester@example.com")
    _commit_file(sibling, rel, shared, "shared base")
    _commit_file(sibling, rel, "# sibling innovation\n", "sibling ahead")

    result = _run_checker(workspace, canon)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "GUARD_SYNC_E_DIVERGENCE" in result.stderr


def test_cursor_helper_ahead_of_canonical_fails_closed(tmp_path: Path) -> None:
    """Cursor helpers are synced payloads, not an unchecked side channel."""
    sibling = tmp_path / "Perpetua-Tools"
    rel = "scripts/cursor/append-pr-body.sh"

    _init_repo(sibling, "Tester", "tester@example.com")
    _commit_file(sibling, rel, "# sibling innovation\n", "cursor helper ahead")

    env = os.environ.copy()
    env["GUARD_SYNC_CANON_ROOT"] = str(ROOT)
    result = subprocess.run(
        ["bash", str(CHECKER), str(sibling)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "scripts/cursor/append-pr-body.sh" in result.stdout
    assert "GUARD_SYNC_E_DIVERGENCE" in result.stderr


def test_githooks_directory_without_effective_hookspath_is_not_scanned(tmp_path: Path) -> None:
    """Inactive .githooks copies are ignored until core.hooksPath selects them."""
    workspace = tmp_path / "ws"
    canon = workspace / "orama-system"
    sibling = workspace / "Perpetua-Tools"
    rel = ".githooks/pre-push"

    _init_repo(canon, "Tester", "tester@example.com")
    _commit_file(canon, rel, "# canonical hook\n", "canon hook")

    _init_repo(sibling, "Tester", "tester@example.com")
    _commit_file(sibling, rel, "# divergent but inactive hook\n", "inactive divergent hook")

    result = _run_checker(workspace, canon)

    assert result.returncode == 0, result.stdout + result.stderr
    assert ".githooks/pre-push" not in result.stdout


def test_githooks_with_effective_hookspath_is_scanned(tmp_path: Path) -> None:
    """An active sibling pre-push ahead of canonical history fails closed for promotion."""
    workspace = tmp_path / "ws"
    canon = workspace / "orama-system"
    sibling = workspace / "Perpetua-Tools"
    rel = ".githooks/pre-push"

    _init_repo(canon, "Tester", "tester@example.com")
    _commit_file(canon, rel, "# canonical hook\n", "canon hook")

    _init_repo(sibling, "Tester", "tester@example.com")
    subprocess.run(["git", "config", "core.hooksPath", ".githooks"], cwd=sibling, check=True)
    _commit_file(sibling, rel, "# canonical hook\n", "mirror canonical hook")
    _commit_file(sibling, rel, "# sibling hook ahead of canonical\n", "promote this hook first")

    result = _run_checker(workspace, canon)

    assert result.returncode == 1, result.stdout + result.stderr
    assert ".githooks/pre-push" in result.stdout
    assert "canonical lags sibling" in result.stdout
    assert "promote sibling" in result.stdout
    assert "GUARD_SYNC_E_DIVERGENCE" in result.stderr


def test_rejects_surplus_arguments(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    canon = workspace / "orama-system"
    _init_repo(canon, "Tester", "tester@example.com")
    env = os.environ.copy()
    env["WORKSPACE_ROOT"] = str(workspace)
    env["GUARD_SYNC_CANON_ROOT"] = str(canon)
    result = subprocess.run(
        ["bash", str(CHECKER), "--workspace", "extra-arg"],
        cwd=canon,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 2, result.stdout + result.stderr


def test_linked_worktree_sibling_discovered(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    canon = workspace / "orama-system"
    sibling = workspace / "Perpetua-Tools"
    worktree_link = workspace / "pt-linked"
    rel = "scripts/git/audit_engine.py"
    body = "# v1\n"

    _init_repo(sibling, "Tester", "tester@example.com")
    _commit_file(sibling, rel, body, "init")
    subprocess.run(
        ["git", "worktree", "add", "-b", "linked-branch", str(worktree_link)],
        cwd=sibling,
        check=True,
        capture_output=True,
    )

    _init_repo(canon, "Tester", "tester@example.com")
    _commit_file(canon, rel, body, "init")

    result = _run_checker(workspace, canon)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "pt-linked" in result.stdout
    assert "byte-identical" in result.stdout


def test_canonical_linked_worktree_is_not_a_downstream_sync_target(tmp_path: Path) -> None:
    """A linked worktree of canonical history is not a downstream mirror."""
    workspace = tmp_path / "ws"
    canon = workspace / "orama-system"
    linked_worktree = workspace / "orama-linked"
    rel = "scripts/git/audit_engine.py"

    _init_repo(canon, "Tester", "tester@example.com")
    _commit_file(canon, rel, "# canonical v1\n", "init")
    subprocess.run(
        ["git", "worktree", "add", "-b", "linked-branch", str(linked_worktree)],
        cwd=canon,
        check=True,
        capture_output=True,
    )

    result = _run_checker(workspace, canon)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "shares canonical git history; skipped" in result.stdout


def _plant_checker_copy(repo: Path, *, is_canonical: bool) -> Path:
    """Copy check-guard-sync-divergence.sh + its sourced dependencies into
    repo/scripts/git/ and return the copy's path. The canonical-root
    resolution logic under test keys off where the SCRIPT FILE itself
    lives (${BASH_SOURCE[0]}), not the process's cwd — so a test that
    wants to exercise "invoked from a non-canonical checkout" must run an
    actual copy of the checker sitting inside that checkout, not the real
    module-level CHECKER with a spoofed cwd (which always resolves
    self-detection against this real repo, wherever it happens to run).
    """
    git_dir = repo / "scripts" / "git"
    git_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "check-guard-sync-divergence.sh",
        "guard-sync-manifest.sh",
        "resolve_sibling_git_repo.sh",
    ):
        dest = git_dir / name
        dest.write_bytes((ROOT / "scripts" / "git" / name).read_bytes())
        dest.chmod(0o755)
    if is_canonical:
        marker = repo / "bin" / "orama-system" / "SKILL.md"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("# marker\n", encoding="utf-8")
    return git_dir / "check-guard-sync-divergence.sh"


def test_self_is_canonical_when_orama_marker_present_no_override(tmp_path: Path) -> None:
    """Regression matrix row 3 (ECC push-gate analysis 2026-08-14): run from
    the real canonical checkout — the scan must use it directly, no override
    required, and it must not be mistaken for a downstream self-nomination."""
    workspace = tmp_path / "ws"
    canon = workspace / "orama-system"
    sibling = workspace / "Perpetua-Tools"
    rel = "scripts/git/audit_engine.py"
    body = "# canonical v1\n"

    for repo in (canon, sibling):
        _init_repo(repo, "Tester", "tester@example.com")
        _commit_file(repo, rel, body, "init")
    checker_copy = _plant_checker_copy(canon, is_canonical=True)
    subprocess.run(["git", "add", "-A"], cwd=canon, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "plant checker + marker"],
        cwd=canon,
        check=True,
        capture_output=True,
    )

    env = os.environ.copy()
    env["WORKSPACE_ROOT"] = str(workspace)
    env.pop("GUARD_SYNC_CANON_ROOT", None)
    result = subprocess.run(
        ["bash", str(checker_copy), "--workspace"],
        cwd=canon,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "canonical=orama-system" in result.stdout, result.stdout
    assert "byte-identical" in result.stdout


def test_downstream_checkout_auto_resolves_orama_sibling_without_override(
    tmp_path: Path,
) -> None:
    """Regression matrix row 4 (success path): a downstream checkout with no
    explicit GUARD_SYNC_CANON_ROOT must auto-resolve the real orama-system
    sibling rather than self-nominate as canonical. Self-contained: only
    resolve_sibling_git_repo.sh (already part of this manifest) is needed —
    no repo-specific resolver script."""
    workspace = tmp_path / "ws"
    canon = workspace / "orama-system"
    downstream = workspace / "perplexity-api" / "Perpetua-Tools"
    rel = "scripts/git/audit_engine.py"
    body = "# canonical v1\n"

    _init_repo(canon, "Tester", "tester@example.com")
    _commit_file(canon, rel, body, "init")
    _commit_file(canon, "bin/orama-system/SKILL.md", "# marker\n", "marker")

    _init_repo(downstream, "Tester", "tester@example.com")
    _commit_file(downstream, rel, body, "init")
    checker_copy = _plant_checker_copy(downstream, is_canonical=False)
    subprocess.run(["git", "add", "-A"], cwd=downstream, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "plant checker copy"],
        cwd=downstream,
        check=True,
        capture_output=True,
    )

    env = os.environ.copy()
    env["WORKSPACE_ROOT"] = str(workspace)
    env.pop("GUARD_SYNC_CANON_ROOT", None)
    result = subprocess.run(
        ["bash", str(checker_copy), "--workspace"],
        cwd=downstream,  # invoked FROM the downstream checkout, not canon
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # canonical=orama-system in the banner proves it resolved the real
    # sibling, not itself (which would print canonical=Perpetua-Tools).
    assert "canonical=orama-system" in result.stdout, result.stdout


def test_downstream_checkout_without_resolver_errors_never_self_nominates(
    tmp_path: Path,
) -> None:
    """Regression matrix row 4 (failure path): no override, no orama marker,
    and no resolvable orama-system sibling anywhere in the workspace — must
    fail with an actionable config error, and must NEVER silently treat
    itself as canonical."""
    workspace = tmp_path / "ws"
    downstream = workspace / "perplexity-api" / "Perpetua-Tools"
    rel = "scripts/git/audit_engine.py"

    _init_repo(downstream, "Tester", "tester@example.com")
    _commit_file(downstream, rel, "# some content\n", "init")
    checker_copy = _plant_checker_copy(downstream, is_canonical=False)
    subprocess.run(["git", "add", "-A"], cwd=downstream, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "plant checker copy"],
        cwd=downstream,
        check=True,
        capture_output=True,
    )

    env = os.environ.copy()
    env["WORKSPACE_ROOT"] = str(workspace)
    env.pop("GUARD_SYNC_CANON_ROOT", None)
    result = subprocess.run(
        ["bash", str(checker_copy), "--workspace"],
        cwd=downstream,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "GUARD_SYNC_CANON_ROOT" in result.stderr
    # Must not have proceeded to scan anything as if self were canonical.
    assert "canonical=Perpetua-Tools" not in result.stdout
    assert "DIVERGENCE:" not in result.stdout
