"""Tests for scripts/audit_policy_enforcement.py (T1-C policy checker)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest import mock

import pytest

# Load the script as a module (it lives in scripts/, not a package)
_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "audit_policy_enforcement.py"
_spec = importlib.util.spec_from_file_location("audit_policy_enforcement", _SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

_is_exempt = _mod._is_exempt
main = _mod.main
POLICY_KEYWORDS = _mod.POLICY_KEYWORDS
EXEMPT_PREFIXES = _mod.EXEMPT_PREFIXES


# ---------------------------------------------------------------------------
# _is_exempt
# ---------------------------------------------------------------------------


class TestIsExempt:
    def test_hardware_policy_source_is_exempt(self):
        assert _is_exempt("src/utils/hardware_policy.py") is True

    def test_tests_prefix_is_exempt(self):
        assert _is_exempt("tests/test_foo.py") is True

    def test_nested_tests_dir_is_exempt(self):
        assert _is_exempt("src/sub/tests/test_bar.py") is True

    def test_vendor_prefix_is_exempt(self):
        assert _is_exempt("vendor/some_lib.py") is True

    def test_venv_prefix_is_exempt(self):
        assert _is_exempt(".venv/lib/site-packages/foo.py") is True

    def test_regular_source_is_not_exempt(self):
        assert _is_exempt("src/perpetua_tools/alphaclaw_bootstrap.py") is False

    def test_scripts_dir_is_not_exempt(self):
        assert _is_exempt("scripts/some_script.py") is False

    def test_orchestrator_is_not_exempt(self):
        assert _is_exempt("orchestrator/main.py") is False

    def test_partial_match_not_exempt(self):
        """'src/utils/hardware_policy_extra.py' must NOT be exempt (prefix mismatch)."""
        # startswith("src/utils/hardware_policy.py") is False for a longer name
        # because we check exact prefix — but the path IS "src/utils/hardware_policy.py"
        # exactly, so a file with a different name won't match
        assert _is_exempt("src/utils/hardware_policy_extra.py") is False

    def test_pycache_files_are_handled_by_caller(self):
        """__pycache__ handling is in main(), _is_exempt itself doesn't block it."""
        # _is_exempt doesn't check __pycache__; caller filters it separately
        result = _is_exempt("src/__pycache__/foo.cpython-311.pyc")
        # Not exempt by any of the exempt rules
        assert result is False


# ---------------------------------------------------------------------------
# main() — integration via temp files
# ---------------------------------------------------------------------------


def _write_py(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


class TestMain:
    def test_ok_when_no_policy_keywords(self, tmp_path, capsys, monkeypatch):
        """Files without policy keywords must not generate violations."""
        src = tmp_path / "no_keywords.py"
        _write_py(src, "x = 1\n")
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        result = main()
        assert result == 0
        captured = capsys.readouterr()
        assert "OK" in captured.out

    def test_ok_when_keyword_with_canonical_marker(self, tmp_path, capsys, monkeypatch):
        """File with NEVER_MAC AND a canonical marker must pass."""
        src = tmp_path / "policy_user.py"
        _write_py(
            src,
            "from utils.hardware_policy import get_policy\nif NEVER_MAC:\n    pass\n",
        )
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        result = main()
        assert result == 0

    def test_violation_when_keyword_without_marker(self, tmp_path, capsys, monkeypatch):
        """File with NEVER_WIN but NO canonical marker must be a violation."""
        src = tmp_path / "bad_policy.py"
        _write_py(src, "if NEVER_WIN:\n    do_something()\n")
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        result = main()
        assert result == 1
        captured = capsys.readouterr()
        assert "bad_policy.py" in captured.err
        assert "utils.hardware_policy" in captured.err

    def test_violation_lists_all_offenders(self, tmp_path, capsys, monkeypatch):
        """Multiple violating files must all appear in stderr."""
        for name in ("a.py", "b.py"):
            _write_py(tmp_path / name, f"ALWAYS_MAC = True\n")
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        result = main()
        assert result == 1
        captured = capsys.readouterr()
        assert "a.py" in captured.err
        assert "b.py" in captured.err

    def test_exempt_tests_dir_not_scanned(self, tmp_path, capsys, monkeypatch):
        """Files inside a tests/ subdirectory must be ignored even with keywords."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        _write_py(tests_dir / "test_x.py", "ALWAYS_WIN = True\n")
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        result = main()
        assert result == 0

    def test_exempt_hardware_policy_source_itself(self, tmp_path, capsys, monkeypatch):
        """The hardware_policy.py source file must be exempt from the check."""
        utils = tmp_path / "src" / "utils"
        utils.mkdir(parents=True)
        _write_py(utils / "hardware_policy.py", "NEVER_MAC = False\nNEVER_WIN = False\n")
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        result = main()
        assert result == 0

    def test_pycache_files_ignored(self, tmp_path, capsys, monkeypatch):
        """__pycache__ .py files must be skipped."""
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        _write_py(cache / "bad.cpython-311.pyc", "NEVER_MAC\n")
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        result = main()
        assert result == 0

    def test_all_four_keywords_trigger_scan(self, tmp_path, capsys, monkeypatch):
        """Each of the four keywords must independently trigger a violation check."""
        for i, kw in enumerate(("NEVER_MAC", "NEVER_WIN", "ALWAYS_MAC", "ALWAYS_WIN")):
            f = tmp_path / f"kw_{i}.py"
            _write_py(f, f"{kw} = True\n")
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        result = main()
        assert result == 1
        captured = capsys.readouterr()
        # All four files should be in violations
        for i in range(4):
            assert f"kw_{i}.py" in captured.err

    def test_import_utils_hardware_policy_marker_clears(self, tmp_path, capsys, monkeypatch):
        """'import utils.hardware_policy' (not 'from ... import') also clears violation."""
        src = tmp_path / "direct_import.py"
        _write_py(src, "import utils.hardware_policy\nif NEVER_WIN:\n    pass\n")
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        result = main()
        assert result == 0

    def test_dotted_usage_marker_clears(self, tmp_path, capsys, monkeypatch):
        """A call like 'utils.hardware_policy.get()' also clears the violation."""
        src = tmp_path / "dotted_usage.py"
        _write_py(src, "x = utils.hardware_policy.get()\nif ALWAYS_MAC:\n    pass\n")
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        result = main()
        assert result == 0

    def test_comment_bypass_in_import_does_not_clear(self, tmp_path, capsys, monkeypatch):
        """Substring markers in comments must not satisfy the import requirement."""
        src = tmp_path / "comment_bypass.py"
        _write_py(
            src,
            "# from utils.hardware_policy import get_policy\nif NEVER_WIN:\n    pass\n",
        )
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        result = main()
        assert result == 1

    def test_oserror_on_read_is_skipped(self, tmp_path, capsys, monkeypatch):
        src = tmp_path / "unreadable.py"
        src.write_bytes(b"NEVER_MAC\n")
        # Patch read_text to raise OSError for this file
        original_read_text = Path.read_text

        def mock_read_text(self, **kwargs):
            if self == src:
                raise OSError("permission denied")
            return original_read_text(self, **kwargs)

        monkeypatch.setattr(Path, "read_text", mock_read_text)
        monkeypatch.setattr(_mod, "ROOT", tmp_path)
        result = main()
        # Skipped, no violation recorded
        assert result == 0