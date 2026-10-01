"""Tests for .githooks/pre-push's guard-managed-path trigger precision.

Regression matrix rows 1-2 from the ECC push-gate analysis (2026-08-14):
a helper script that merely lives under scripts/git/ (but isn't a manifest-
managed guard file) must never trigger guard validation; canonical guard
publication validates its local manifest without scanning unrelated worktrees.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PRE_PUSH = ROOT / ".githooks" / "pre-push"

pytestmark = pytest.mark.unit


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    # An approved human identity (see tests/test_audit_engine.py), not an
    # arbitrary "Tester" — audit_attribution.sh runs for real against these
    # fixture commits once pre-push reaches its attribution-audit stage,
    # and a non-allowlisted author blocks the push for a reason unrelated
    # to what these tests actually check (found via review, PR 311).
    subprocess.run(
        ["git", "config", "user.email", "lawrence@cyre.me"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "cyre"], cwd=path, check=True, capture_output=True
    )


def _commit_file(repo: Path, rel: str, content: str, msg: str) -> None:
    dest = repo / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", rel], cwd=repo, check=True, capture_output=True)
    # --no-verify: these are fixture setup commits for testing pre-push
    # specifically. Once core.hooksPath=.githooks is configured (needed to
    # satisfy ensure_hooks_installed.sh), pre-commit/commit-msg become
    # active too — real policy hooks unrelated to what this file tests.
    subprocess.run(
        ["git", "commit", "--no-verify", "-m", msg],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _setup_repo_with_origin(base: Path) -> Path:
    """Bare origin + a local clone with main pushed, so origin/main resolves
    as the base for range_for_ref's diff — matching how the real hook is
    always invoked (a configured upstream must exist)."""
    bare = base / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(bare)], check=True, capture_output=True
    )
    local = base / "local"
    _init_repo(local)
    # Pre-push unconditionally shells out to several real scripts/git/
    # dependencies (check_no_pending_merge.sh, ensure_hooks_installed.sh,
    # audit_attribution.sh, ...) — and ensure_hooks_installed.sh itself
    # hard-requires core.hooksPath=.githooks plus executable pre-commit/
    # commit-msg/pre-push files — before ever reaching the guard-touch
    # logic under test. A hand-picked subset silently made earlier versions
    # of this fixture crash before reaching that logic at all, which made a
    # negative assertion pass for the wrong reason. Bring the real tooling
    # over wholesale instead of guessing which files matter.
    shutil.copytree(ROOT / "scripts", local / "scripts", dirs_exist_ok=True)
    shutil.copytree(ROOT / ".githooks", local / ".githooks", dirs_exist_ok=True)
    shutil.copytree(ROOT / ".cursor", local / ".cursor", dirs_exist_ok=True)
    subprocess.run(
        ["git", "config", "core.hooksPath", ".githooks"],
        cwd=local,
        check=True,
        capture_output=True,
    )
    _commit_file(local, "README.md", "init\n", "init")
    subprocess.run(["git", "add", "-A"], cwd=local, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "--no-verify", "-m", "vendor real scripts/git dependencies"],
        cwd=local,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare)], cwd=local, check=True, capture_output=True
    )
    # --no-verify: this setup push establishes origin/main as the fixture's
    # base. It is not the push under test (that's the direct pre-push
    # subprocess invocation in _run_pre_push below) — real hooks are active
    # here too since core.hooksPath is configured, and Phase 0's direct-to-
    # main guard would otherwise reject this legitimate setup step.
    subprocess.run(
        ["git", "push", "--no-verify", "-u", "origin", "main"],
        cwd=local,
        check=True,
        capture_output=True,
    )
    return local


def _run_pre_push(
    repo: Path, workspace_root: Path, canon_root: Path
) -> subprocess.CompletedProcess[str]:
    local_sha = _head(repo)
    remote_sha = "0" * 40
    # Deliberately NOT refs/heads/main — avoids the unrelated Phase 0
    # direct-push-to-main guard so the test isolates the guard-sync trigger
    # specifically, not every later stage of the hook.
    stdin = f"refs/heads/feature-test {local_sha} refs/heads/feature-test {remote_sha}\n"
    env = os.environ.copy()
    env["WORKSPACE_ROOT"] = str(workspace_root)
    env["GUARD_SYNC_CANON_ROOT"] = str(canon_root)
    return subprocess.run(
        ["bash", str(PRE_PUSH), "origin", "file://" + str(repo)],
        cwd=repo,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def test_helper_only_change_does_not_trigger_divergence_scan(tmp_path: Path) -> None:
    """Row 1: a scripts/git/ file NOT in the guard-sync manifest, with a
    divergent sibling elsewhere in the workspace, must not trigger the
    cross-worktree divergence scan at all."""
    workspace = tmp_path / "ws"
    repo = _setup_repo_with_origin(workspace)
    _commit_file(
        repo,
        "scripts/git/ecc-overlay-helper-test-only.sh",
        "#!/usr/bin/env bash\necho helper\n",
        "add ecc helper (not manifest-managed)",
    )

    sibling = workspace / "Perpetua-Tools"
    _init_repo(sibling)
    _commit_file(
        sibling,
        "scripts/git/audit_engine.py",
        "# sibling mutation absent from canonical\n",
        "sibling mutation",
    )

    result = _run_pre_push(repo, workspace, repo)
    combined = result.stdout + result.stderr
    # returncode == 0, not just "divergence text absent" — the weaker form
    # could pass vacuously if the hook crashed early for an unrelated
    # reason (caught once already in this file's own history: see the
    # fixture-setup commits above). Reviewed in PR 311.
    assert result.returncode == 0, combined
    assert "guard-sync divergence" not in combined, combined
    assert "GUARD_SYNC_E_DIVERGENCE" not in combined, combined


def test_canonical_guard_change_ignores_unrelated_sibling_workspace(
    tmp_path: Path,
) -> None:
    """Canonical publication does not overwrite siblings, so it must not let
    an unrelated temporary checkout block a valid source-guard push."""
    workspace = tmp_path / "ws"
    repo = _setup_repo_with_origin(workspace)
    marker = repo / "bin/orama-system/SKILL.md"
    marker.parent.mkdir(parents=True)
    marker.write_text("# canonical marker\n", encoding="utf-8")
    _commit_file(
        repo,
        "scripts/git/audit_engine.py",
        "# canonical v2\n",
        "modify guard-managed file",
    )

    sibling = workspace / "Perpetua-Tools"
    _init_repo(sibling)
    _commit_file(
        sibling,
        "scripts/git/audit_engine.py",
        "# sibling mutation absent from canonical\n",
        "sibling mutation",
    )

    result = _run_pre_push(repo, workspace, repo)
    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    assert "guard-sync divergence" not in combined, combined


def test_githooks_change_triggers_scan_even_when_manifest_unavailable(
    tmp_path: Path,
) -> None:
    """Reviewed in PR 311 (record 1343): the degraded fallback (manifest
    file missing/unloadable) originally only recognized scripts/git/ paths
    as guard-managed, even though the manifest also governs .githooks/
    (GUARD_SYNC_GITHOOKS). A changed .githooks/commit-msg could therefore
    skip divergence validation silently — fail-open in exactly the case
    meant to be the safety net. With guard-sync-manifest.sh genuinely
    absent, a .githooks/commit-msg change must still be treated as
    guard-managed and attempt the divergence path (never a silent,
    unblocked exit 0)."""
    workspace = tmp_path / "ws"
    repo = _setup_repo_with_origin(workspace)
    # Remove the manifest from THIS fixture only, after setup, so the
    # baseline commit history still has it (matching how a real repo would
    # look right up until the moment of a corrupted/incomplete checkout) —
    # what matters is that it's absent at push time, when pre-push sources it.
    manifest = repo / "scripts" / "git" / "guard-sync-manifest.sh"
    manifest.unlink()
    _commit_file(
        repo,
        ".githooks/commit-msg",
        "#!/usr/bin/env bash\necho changed\n",
        "modify manifest-managed githook",
    )

    sibling = workspace / "Perpetua-Tools"
    _init_repo(sibling)
    _commit_file(
        sibling,
        "scripts/git/audit_engine.py",
        "# sibling mutation absent from canonical\n",
        "sibling mutation",
    )

    result = _run_pre_push(repo, workspace, repo)
    combined = result.stdout + result.stderr
    # A missing manifest means the hook cannot establish the managed-path
    # contract. It must fail before choosing either canonical or downstream
    # validation, never silently pass the changed hook through.
    assert result.returncode == 1, combined
    assert "guard-sync manifest unavailable" in combined, combined
