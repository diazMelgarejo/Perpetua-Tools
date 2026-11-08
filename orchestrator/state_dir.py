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
    """Find the shared Git-worktree state directory, or None outside Git."""
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
    state_anchor = common_path if is_bare else common_path.parent
    return state_anchor / ".state"


def resolve_default_state_dir() -> Path:
    """Return the configured or shared runtime state directory."""
    env_dir = os.environ.get("PT_STATE_DIR", "").strip()
    if env_dir:
        return Path(env_dir)
    return _canonical_repo_state_dir() or Path(".state")
