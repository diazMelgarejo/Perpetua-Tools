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

    Separate-Git-directory layouts refuse unowned legacy state and use an
    isolated location only when no legacy directory exists.
    Mixed-version processes cannot safely negotiate a location concurrently.
    """
    repo_root = root if root is not None else PT_ROOT
    if _is_installed_package(Path(__file__).resolve()) or _is_installed_package(repo_root):
        return None
    if not repo_root.is_dir():
        raise RuntimeError("state authority: source root is unavailable; set PT_STATE_DIR explicitly")
    has_checkout = (repo_root / ".git").exists() or (repo_root / ".git").is_symlink()
    has_bare_markers = (repo_root / "HEAD").exists() and (repo_root / "objects").is_dir()
    if not has_checkout and not has_bare_markers:
        return None  # Source archive, not a Git checkout.
    git_env = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    git_env["GIT_CONFIG_NOSYSTEM"] = "1"
    git_env["GIT_CONFIG_GLOBAL"] = os.devnull
    try:
        output = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "--git-common-dir", "--is-bare-repository"],
            text=True,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
            timeout=5,
            env=git_env,
        ).splitlines()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        raise RuntimeError("state authority: Git discovery failed; set PT_STATE_DIR explicitly") from exc
    if len(output) != 2 or not output[0].strip() or output[1].strip() not in ("true", "false"):
        raise RuntimeError("state authority: malformed Git discovery; set PT_STATE_DIR explicitly")
    common_dir = output[0].strip()
    is_bare = output[1].strip().lower() == "true"
    if not is_bare:
        try:
            top = subprocess.check_output(
                ["git", "-C", str(repo_root), "rev-parse", "--show-toplevel"],
                text=True, encoding="utf-8", stderr=subprocess.DEVNULL,
                timeout=5, env=git_env,
            ).strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            raise RuntimeError("state authority: Git root discovery failed; set PT_STATE_DIR explicitly") from exc
        if not top or Path(top).resolve() != repo_root.resolve():
            raise RuntimeError("state authority: Git root mismatch; set PT_STATE_DIR explicitly")
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
    if legacy_state.exists() or legacy_state.is_symlink():
        raise RuntimeError(
            "ambiguous separate-Git-directory state: legacy ownership is unverified; "
            "stop dispatch, review the ledgers, and set PT_STATE_DIR explicitly"
        )
    return isolated_state


def resolve_default_state_dir() -> Path:
    """Return the configured or shared runtime state directory."""
    env_dir = os.environ.get("PT_STATE_DIR", "").strip()
    if env_dir:
        return Path(env_dir)
    return _canonical_repo_state_dir() or (PT_ROOT / ".state")
