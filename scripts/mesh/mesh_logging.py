"""Cross-platform local mesh logging — append-only `.local/mesh.log` (Windows + Unix)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_CONFIGURED: set[str] = set()


def local_log_dir(repo_root: Path) -> Path:
    """Gitignored log directory; pathlib works on Windows and POSIX."""
    path = repo_root / ".local"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_mesh_logger(name: str, *, repo_root: Path | None = None) -> logging.Logger:
    """Logger writing to `.local/mesh.log` and stderr."""
    root = repo_root or Path(__file__).resolve().parents[2]
    logger = logging.getLogger(name)
    if name in _CONFIGURED:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    log_path = local_log_dir(root) / "mesh.log"
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(stream_handler)

    _CONFIGURED.add(name)
    return logger


def harden_local_file(path: Path) -> None:
    """Best-effort restrictive permissions (no-op on Windows when unsupported)."""
    import os

    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
