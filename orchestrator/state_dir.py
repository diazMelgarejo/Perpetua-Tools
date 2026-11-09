"""Shared runtime state-directory resolution without database dependencies."""
from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path


PT_ROOT = Path(__file__).resolve().parent.parent


def _unique_record_fields(pairs: list[tuple[str, object]]) -> dict:
    """Reject ambiguous duplicate JSON keys in an authority record."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate record field")
        result[key] = value
    return result


def _verified_authority_file(path: str, common_path: Path) -> Path:
    """Read a private operator record binding the metadata and existing ledger."""
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("state authority: protected record verification is unavailable on this platform")
    record_path = Path(path)
    if not record_path.is_absolute() or ".." in record_path.parts:
        raise RuntimeError("state authority: record path must be absolute and canonical")
    descriptors = []
    try:
        directory = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        descriptors.append(directory)
        for component in record_path.parts[1:-1]:
            directory = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            descriptors.append(directory)
        parent = os.fstat(directory)
        if parent.st_uid != os.getuid() or stat.S_IMODE(parent.st_mode) & 0o077:
            raise ValueError("record directory is not private and owned by the current user")
        fd = os.open(record_path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        descriptors.append(fd)
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077 or info.st_nlink != 1):
            raise ValueError("record is not a private regular file owned by the current user")
        if info.st_size > 16384:
            raise ValueError("record is too large")
        content = os.read(fd, 16385)
        if len(content) > 16384:
            raise ValueError("record is too large")
        record = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_record_fields)
        if not isinstance(record, dict) or set(record) != {"schema_version", "owner", "git_common_dir", "git_device", "git_inode", "ledger_dir", "ledger_device", "ledger_inode", "db_device", "db_inode"}:
            raise ValueError("invalid record schema")
        if type(record["schema_version"]) is not int or record["schema_version"] != 1 or record["owner"] != str(os.getuid()):
            raise ValueError("invalid record version or owner")
        if any(type(record[key]) is not int for key in ("git_device", "git_inode", "ledger_device", "ledger_inode", "db_device", "db_inode")):
            raise ValueError("invalid record identity types")
        ledger = Path(record["ledger_dir"])
        if not ledger.is_absolute() or str(ledger.resolve(strict=True)) != record["ledger_dir"]:
            raise ValueError("ledger path is not canonical")
        metadata_stat = common_path.stat()
        ledger_stat = ledger.stat()
        if (record["git_common_dir"] != str(common_path) or
                (record["git_device"], record["git_inode"]) != (metadata_stat.st_dev, metadata_stat.st_ino) or
                (record["ledger_device"], record["ledger_inode"]) != (ledger_stat.st_dev, ledger_stat.st_ino) or
                not stat.S_ISDIR(ledger_stat.st_mode)):
            raise ValueError("record identity mismatch")
        if ledger_stat.st_uid != os.getuid() or stat.S_IMODE(ledger_stat.st_mode) & 0o022:
            raise ValueError("ledger directory is not protected and owned by the current user")
        db = ledger / "perpetua_core.db"
        db_stat = db.lstat()
        if (not stat.S_ISREG(db_stat.st_mode) or db_stat.st_uid != os.getuid()
                or stat.S_IMODE(db_stat.st_mode) & 0o077
                or (record["db_device"], record["db_inode"]) != (db_stat.st_dev, db_stat.st_ino)):
            raise ValueError("existing ledger database identity mismatch")
        return ledger
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        raise RuntimeError("state authority: invalid or unprotected operator record") from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _is_installed_package(path: Path | None = None) -> bool:
    """Return True if running from an installed package (e.g. site-packages)."""
    target = path if path is not None else Path(__file__).resolve()
    return any(part in ("site-packages", "dist-packages") for part in target.parts)


def _canonical_repo_state_dir(root: Path | None = None) -> Path | None:
    """Find shared Git-worktree state; stop old processes before upgrading.

    Linked or separate Git layouts require an operator authority record.
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
    authority = os.environ.get("PT_STATE_AUTHORITY_FILE", "").strip()
    if authority:
        return _verified_authority_file(authority, common_path)
    if is_bare:
        return common_path / ".state"
    git_entry = repo_root / ".git"
    if git_entry.is_dir() and not git_entry.is_symlink() and git_entry.resolve() == common_path:
        return repo_root.resolve() / ".state"
    raise RuntimeError(
        "state authority: linked or separate Git layout requires a verified "
        "PT_STATE_AUTHORITY_FILE or explicit PT_STATE_DIR"
    )


def resolve_default_state_dir() -> Path:
    """Return the configured or shared runtime state directory."""
    env_dir = os.environ.get("PT_STATE_DIR", "").strip()
    if env_dir:
        return Path(env_dir)
    return _canonical_repo_state_dir() or (PT_ROOT / ".state")
