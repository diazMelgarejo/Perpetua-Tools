from __future__ import annotations

from pathlib import Path

import pytest

from utils.env_paths import resolve_alphaclaw_install_dir, resolve_env_path


def test_resolve_env_path_expands_tilde() -> None:
    home = Path.home()
    assert resolve_env_path("~/.alphaclaw") == (home / ".alphaclaw").resolve()


def test_resolve_env_path_empty_uses_default() -> None:
    default = Path.home() / ".alphaclaw"
    assert resolve_env_path(None, default=default) == default.resolve()
    assert resolve_env_path("", default=default) == default.resolve()


def test_resolve_alphaclaw_install_dir_from_environ() -> None:
    home = Path.home()
    env = {"ALPHACLAW_INSTALL_DIR": "~/.alphaclaw"}
    assert resolve_alphaclaw_install_dir(env) == (home / ".alphaclaw").resolve()


def test_resolve_alphaclaw_install_dir_unset_uses_home() -> None:
    assert resolve_alphaclaw_install_dir({}) == (Path.home() / ".alphaclaw").resolve()
