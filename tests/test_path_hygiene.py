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


def test_json_structure_sanitized():
    from path_hygiene import sanitize_json_strings
    obj = {"path": "/Users/alice/config.json", "count": 5}
    out = sanitize_json_strings(obj)
    assert "alice" not in out["path"]
    assert out["count"] == 5
