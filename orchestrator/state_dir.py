"""Shared runtime state-directory resolution without database dependencies."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


PT_ROOT = Path(__file__).resolve().parent.parent


def _is_installed_package(path: Path | None = None) -> bool:
    """Return True if running from an installed package (e.g. site-packages)."""
    target = path if path is not None else Path(__file__).resolve()
    return any(part in ("site-packages", "dist-packages") for part in target.parts)


def _canonical_repo_state_dir(root: Path | None = None) -> Path | None:
    """Find shared Git-worktree state; stop old processes before upgrading.

    Separate-Git-directory layouts keep an existing legacy state directory,
    use the isolated location for a fresh layout, and refuse ambiguous state.
    Mixed-version processes cannot safely negotiate a location concurrently.
    """
    repo_root = root if root is not None else PT_ROOT
    if _is_installed_package(Path(__file__).resolve()) or _is_installed_package(repo_root):
        return None
    try:
        output = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "--git-common-dir", "--is-bare-repository"],
            text=True,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
            timeout=5,
            env={key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
        ).splitlines()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if len(output) < 2:
        return None
    common_dir = output[0].strip()
    is_bare = output[1].strip().lower() == "true"
    common_path = Path(common_dir)
    if not common_path.is_absolute():
        common_path = (repo_root / common_path).resolve()
    else:
        common_path = common_path.resolve()
    if is_bare:
        return common_path / ".state"
    if common_path.name == ".git":
        return common_path.parent / ".state"
    legacy_state = common_path.parent / ".state"
    isolated_state = common_path / ".state"
    if legacy_state.exists():
        if isolated_state.exists():
            raise RuntimeError(
                "ambiguous separate-Git-directory state: both legacy and isolated "
                "directories exist; stop and reconcile them before dispatch"
            )
        return legacy_state
    return isolated_state


def resolve_default_state_dir() -> Path:
    """Return the configured or shared runtime state directory."""
    env_dir = os.environ.get("PT_STATE_DIR", "").strip()
    if env_dir:
        return Path(env_dir)
    return _canonical_repo_state_dir() or (PT_ROOT / ".state")
