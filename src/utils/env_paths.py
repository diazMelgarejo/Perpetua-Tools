"""Resolve filesystem paths from environment variables (dotenv-safe)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

_DEFAULT_ALPHACLAW_INSTALL = Path.home() / ".alphaclaw"


def resolve_env_path(
    raw: str | None,
    *,
    default: Path | None = None,
) -> Path:
    """Expand ``~`` and resolve a path from an env string.

    python-dotenv loads values literally — ``~/.foo`` is not expanded by the
    shell. Always use this before ``mkdir``, subprocess ``cwd=``, or writing
    path keys back into ``.env`` files.
    """
    if not raw or not str(raw).strip():
        base = default if default is not None else Path.cwd()
        return base.expanduser().resolve()
    return Path(raw).expanduser().resolve()


def resolve_alphaclaw_install_dir(
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Canonical AlphaClaw npm install / gateway root directory."""
    env = environ if environ is not None else os.environ
    return resolve_env_path(
        env.get("ALPHACLAW_INSTALL_DIR"),
        default=_DEFAULT_ALPHACLAW_INSTALL,
    )
