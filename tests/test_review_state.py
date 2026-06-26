"""Tests for .agent/memory/review_state.py helpers."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".agent" / "memory"))

from path_hygiene import sanitize_tracked_path_leaks  # noqa: E402

_UNIX_HOME = "/" + "Users" + "/lab/Downloads/SKILLS.md/ultrathink"
_WIN_HOME = "C:" + r"\Users\lab\Downloads\SKILLS.md\ultrathink"


def test_sanitize_tracked_path_leaks_unix_home():
    raw = f"Use {_UNIX_HOME} as canonical"
    assert sanitize_tracked_path_leaks(raw) == "Use $HOME/Downloads/SKILLS.md/ultrathink as canonical"


def test_sanitize_tracked_path_leaks_windows_home():
    raw = f"Use {_WIN_HOME} as canonical"
    assert sanitize_tracked_path_leaks(raw) == r"Use %USERPROFILE%\Downloads\SKILLS.md\ultrathink as canonical"
