"""Tests for .agent/memory/review_state.py helpers."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".agent" / "memory"))

from path_hygiene import REVIEW_QUEUE_DYNAMIC_MARKER, sanitize_tracked_path_leaks  # noqa: E402
from review_state import _read_review_queue_preamble  # noqa: E402

_UNIX_HOME = "/" + "Users" + "/lab/Downloads/SKILLS.md/ultrathink"
_WIN_HOME = "C:" + r"\Users\lab\Downloads\SKILLS.md\ultrathink"


def test_sanitize_tracked_path_leaks_unix_home():
    raw = f"Use {_UNIX_HOME} as canonical"
    assert sanitize_tracked_path_leaks(raw) == "Use $HOME/Downloads/SKILLS.md/ultrathink as canonical"


def test_sanitize_tracked_path_leaks_windows_home():
    raw = f"Use {_WIN_HOME} as canonical"
    assert sanitize_tracked_path_leaks(raw) == r"Use %USERPROFILE%\Downloads\SKILLS.md\ultrathink as canonical"


def test_read_review_queue_preamble_ignores_inline_marker_mentions(tmp_path):
    summary = tmp_path / "REVIEW_QUEUE.md"
    summary.write_text(
        "# Review Queue\n\n"
        f"Docs may cite {REVIEW_QUEUE_DYNAMIC_MARKER} inline.\n\n"
        "**Pending:** 2\n",
        encoding="utf-8",
    )
    preamble = _read_review_queue_preamble(str(summary))
    assert "Docs may cite" in preamble
    assert REVIEW_QUEUE_DYNAMIC_MARKER in preamble
    assert "**Pending:**" not in preamble


def test_read_review_queue_preamble_splits_on_line_anchored_marker(tmp_path):
    summary = tmp_path / "REVIEW_QUEUE.md"
    summary.write_text(
        "# Review Queue\n\n"
        f"Docs may cite {REVIEW_QUEUE_DYNAMIC_MARKER} inline.\n\n"
        f"{REVIEW_QUEUE_DYNAMIC_MARKER}\n\n"
        "**Pending:** 2\n",
        encoding="utf-8",
    )
    preamble = _read_review_queue_preamble(str(summary))
    assert "Docs may cite" in preamble
    assert REVIEW_QUEUE_DYNAMIC_MARKER in preamble
    assert "**Pending:**" not in preamble
