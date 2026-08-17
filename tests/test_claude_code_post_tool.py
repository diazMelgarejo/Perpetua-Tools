"""Tests for Claude Code post-tool episodic summaries."""
import json
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


def test_fallback_detail_persists_tool_and_output_size_not_output():
    marker = "PT_SECRET_MARKER_DO_NOT_PERSIST"
    output = f"Task completed with {marker} in generated notes"
    detail = hook._detail(
        "Task",
        {},
        {"output": output},
        True,
    )
    payload = json.loads(detail)

    assert payload == {"tool": "Task", "output_chars": len(output)}
    assert marker not in detail
    assert "generated notes" not in detail


def test_bash_detail_persists_safe_metadata_not_raw_command_or_output():
    marker = "RAW_OUTPUT_MUST_NOT_PERSIST"
    command = "git show --format=fuller --token=local-value"
    detail = hook._detail(
        "Bash",
        {"command": command},
        {"output": f"Author: {marker}"},
        True,
    )
    payload = json.loads(detail)

    assert payload == {
        "command": "git",
        "command_chars": len(command),
        "output_chars": len(f"Author: {marker}"),
    }
    assert command not in detail
    assert marker not in detail


def test_bash_failure_reflection_and_detail_exclude_raw_error_text():
    marker = "RAW_ERROR_MUST_NOT_PERSIST"
    tool_input = {"command": "deploy --credential=local-value"}
    response = {"error": marker, "exit_code": 1}

    reflection = hook._reflection("Bash", tool_input, response, False)
    detail = hook._detail("Bash", tool_input, response, False)

    assert marker not in reflection
    assert marker not in detail
    assert "local-value" not in reflection
    assert "local-value" not in detail
    assert json.loads(detail)["error_chars"] == len(marker)


def test_non_bash_action_labels_exclude_user_supplied_content():
    secret = "SECRET_MUST_NOT_PERSIST"

    assert hook._action_label(
        "Task", {"description": f"Investigate {secret}"}
    ) == "task: delegated"
    assert hook._action_label(
        "TodoWrite", {"todos": [{"content": secret, "status": "in_progress"}]}
    ) == "todo: updated task list (1 items)"
    assert hook._action_label(
        "WebFetch", {"url": f"https://example.invalid/path?token={secret}"}
    ) == "fetch: https://example.invalid"

    reflection = hook._reflection(
        "TodoWrite",
        {"todos": [{"content": secret, "status": "in_progress"}]},
        {},
        True,
    )
    assert secret not in reflection


def test_action_label_normalizes_repo_paths():
    path = Path(__file__).parent.parent / ".agent" / "memory" / "note.md"

    assert hook._action_label("Read", {"file_path": str(path)}) == (
        "read: $REPO_ROOT/.agent/memory/note.md"
    )
