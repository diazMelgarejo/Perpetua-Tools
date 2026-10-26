"""Focused regression coverage for fleet-update verification helpers."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC_COVERAGE = ROOT / ".agent" / "tools" / "doc_coverage.py"
DOC_ONLY_DIFF = ROOT / ".agent" / "tools" / "doc_only_diff.py"


def _load_doc_only_diff() -> object:
    """Load the standalone documentation-diff helper without executing its CLI."""
    spec = importlib.util.spec_from_file_location("doc_only_diff", DOC_ONLY_DIFF)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_doc_coverage_fails_for_a_requested_missing_file(tmp_path: Path) -> None:
    """A misspelled requested path is a failed coverage check, not a skipped file."""
    result = subprocess.run(
        [sys.executable, "-I", str(DOC_COVERAGE), str(tmp_path), "missing.py"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "missing.py: absent" in result.stdout


def test_doc_only_shell_comparison_preserves_here_document_hash_lines() -> None:
    """Hash-prefixed here-document content remains semantic shell content."""
    module = _load_doc_only_diff()
    original = b'cat <<EOF\n# payload\nEOF\n'
    changed = b'cat <<EOF\n# changed payload\nEOF\n'

    assert module.strip_sh(original) != module.strip_sh(changed)


def test_doc_only_shell_comparison_rejects_unterminated_here_document() -> None:
    """An uncertain here-document boundary fails closed instead of dropping content."""
    module = _load_doc_only_diff()

    try:
        module.strip_sh(b"cat <<EOF\n# payload\n")
    except ValueError as error:
        assert "unterminated here-document" in str(error)
    else:
        raise AssertionError("unterminated here-document must not be comparable")
