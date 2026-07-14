"""Tests for .agent/memory/path_hygiene.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / ".agent" / "memory"))
from path_hygiene import sanitize_tracked_path_leaks


def test_unix_home_with_trailing_slash():
    assert sanitize_tracked_path_leaks("/Users/alice/repos/foo") == "$HOME/repos/foo"


def test_unix_home_tail_end_of_string():
    """Regression: /Users/alice at end-of-string was not sanitized before this fix."""
    assert sanitize_tracked_path_leaks("failed at /Users/alice") == "failed at $HOME"


def test_unix_home_tail_before_whitespace():
    result = sanitize_tracked_path_leaks("path /Users/alice is invalid")
    assert "alice" not in result
    assert "$HOME" in result


def test_linux_home_with_trailing_slash():
    assert sanitize_tracked_path_leaks("/home/bob/work/project") == "$HOME/work/project"


def test_linux_home_tail_end_of_string():
    """Regression: /home/bob at end-of-string was not sanitized before this fix."""
    assert sanitize_tracked_path_leaks("see /home/bob") == "see $HOME"


def test_windows_home_tail():
    result = sanitize_tracked_path_leaks("see C:\\Users\\lab")
    assert "lab" not in result
    assert "%USERPROFILE%" in result


def test_no_false_positive_on_system_path():
    # /usr/local/bin should never be touched
    text = "installed at /usr/local/bin/python3"
    assert sanitize_tracked_path_leaks(text) == text


def test_workspace_doxx_win_after_home_substitution():
    raw = r"Use %USERPROFILE%\Downloads\SKILLS.md\ultrathink as canonical"
    assert sanitize_tracked_path_leaks(raw) == "Use <workspace-root> as canonical"


def test_workspace_doxx_unix_after_home_substitution():
    raw = "Use $HOME/Downloads/SKILLS.md/ultrathink as canonical"
    assert sanitize_tracked_path_leaks(raw) == "Use <workspace-root> as canonical"


def test_workspace_doxx_full_windows_path():
    raw = r"Use C:\Users\lab\Downloads\SKILLS.md\ultrathink as canonical"
    assert sanitize_tracked_path_leaks(raw) == "Use <workspace-root> as canonical"


def test_json_structure_sanitized():
    from path_hygiene import sanitize_json_strings
    obj = {"path": "/Users/alice/config.json", "count": 5}
    out = sanitize_json_strings(obj)
    assert "alice" not in out["path"]
    assert out["count"] == 5


def test_decay_archive_id_matches_sanitized_persisted_json(tmp_path):
    """Archive duplicate checks must use the same sanitized row that is persisted."""
    import datetime
    import json

    from decay import _archive_entry_id, decay_old_entries

    old = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=120)
    entry = {
        "id": "/Users/alice/private/project.log",
        "timestamp": old.isoformat(),
        "event": "tool_error",
        "path": "/Users/alice/private/project.log",
        "salience": 0,
    }

    kept, archived = decay_old_entries([entry], tmp_path)

    assert kept == []
    assert archived == [entry]

    archive_path = next(tmp_path.glob("archive_*.jsonl"))
    rows = [json.loads(line) for line in archive_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["id"] == "$HOME/private/project.log"
    assert rows[0]["path"] == "$HOME/private/project.log"
    assert _archive_entry_id(rows[0]) != _archive_entry_id(entry)
    assert _archive_entry_id(rows[0]) == "id:$HOME/private/project.log"

    decay_old_entries([entry], tmp_path)
    rows_after_retry = archive_path.read_text(encoding="utf-8").splitlines()
    assert len(rows_after_retry) == 1
