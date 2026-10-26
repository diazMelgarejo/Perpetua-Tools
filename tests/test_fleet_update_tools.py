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


def test_doc_only_shell_here_document_uses_its_own_delimiter() -> None:
    """A here-document ends at its own delimiter word, not at a literal EOF."""
    module = _load_doc_only_diff()
    original = b"cat <<'DONE'\n# enabled=true\nDONE\n# trailing comment\n"
    comment_only = b"cat <<'DONE'\n# enabled=true\nDONE\n# a different trailing comment\n"
    payload_changed = b"cat <<'DONE'\n# enabled=false\nDONE\n# trailing comment\n"

    assert module.strip_sh(original) == module.strip_sh(comment_only)
    assert module.strip_sh(original) != module.strip_sh(payload_changed)


def test_doc_only_shell_here_string_is_not_a_here_document() -> None:
    """The <<< here-string must not swallow the following comment lines as data."""
    module = _load_doc_only_diff()
    original = b"grep x <<< \"$value\"\n# note one\n"
    changed = b"grep x <<< \"$value\"\n# note two\n"

    assert module.strip_sh(original) == module.strip_sh(changed)


def test_doc_only_python_directive_comment_change_is_code() -> None:
    """Changing a type/lint pragma or the encoding cookie is not a documentation-only change."""
    module = _load_doc_only_diff()
    base = b"import os  # noqa: F401\n# plain comment\n"
    plain_comment_changed = b"import os  # noqa: F401\n# another plain comment\n"
    pragma_changed = b"import os\n# plain comment\n"

    assert module.strip_py(base) == module.strip_py(plain_comment_changed)
    assert module.strip_py(base) != module.strip_py(pragma_changed)


def _git(repo: Path, *args: str) -> None:
    """Run git in a temporary repository with a fixed identity."""
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        check=True, capture_output=True,
    )


def test_doc_only_diff_fails_closed_on_an_unknown_revision(tmp_path: Path) -> None:
    """A failed git diff must never be reported as an empty, documentation-only change."""
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.py").write_text('"""x."""\n', encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    result = subprocess.run(
        [sys.executable, "-I", str(DOC_ONLY_DIFF), str(tmp_path), "no-such-rev", "HEAD"],
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 1
    assert '"doc_only": false' in result.stdout


def test_doc_only_diff_lists_markdown_as_unreviewed_and_can_fail_strict(tmp_path: Path) -> None:
    """Markdown changes are reported as not semantically compared; --strict-markdown rejects them."""
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.md").write_text("one\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "first")
    (tmp_path / "a.md").write_text("two\n", encoding="utf-8")
    _git(tmp_path, "commit", "-q", "-am", "second")

    loose = subprocess.run(
        [sys.executable, "-I", str(DOC_ONLY_DIFF), str(tmp_path), "HEAD~1", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    strict = subprocess.run(
        [sys.executable, "-I", str(DOC_ONLY_DIFF), str(tmp_path), "HEAD~1", "HEAD", "--strict-markdown"],
        capture_output=True, text=True, check=False,
    )

    assert loose.returncode == 0 and '"markdown_unreviewed": [\n  "a.md"\n ]' in loose.stdout
    assert strict.returncode == 1 and "UNPROVABLE" in strict.stdout
