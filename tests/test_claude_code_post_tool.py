"""Tests for Claude Code post-tool episodic summaries."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / ".agent" / "harness"))

from hooks import claude_code_post_tool as hook  # noqa: E402


def test_write_detail_persists_metadata_not_content():
    path = Path(__file__).parent.parent / "docs" / "secret.md"
    detail = hook._detail(
        "Write",
        {
            "file_path": str(path),
            "content": "token=secret\nsecond line\n",
        },
        {},
        True,
    )

    assert "$REPO_ROOT/docs/secret.md" in detail
    assert "content_lines" in detail
    assert "content_chars" in detail
    assert "token=secret" not in detail
    assert "second line" not in detail
    assert "content\":\"" not in detail


def test_edit_detail_persists_lengths_not_old_or_new_strings():
    detail = hook._detail(
        "Edit",
        {
            "file_path": "$HOME/project/app.py",
            "old_string": "private old content",
            "new_string": "private new content",
        },
        {},
        True,
    )

    assert "old_string_chars" in detail
    assert "new_string_chars" in detail
    assert "private old content" not in detail
    assert "private new content" not in detail
    assert "$HOME" not in detail
    assert "~/" in detail


def test_action_label_normalizes_repo_paths():
    path = Path(__file__).parent.parent / ".agent" / "memory" / "note.md"

    assert hook._action_label("Read", {"file_path": str(path)}) == (
        "read: $REPO_ROOT/.agent/memory/note.md"
    )
