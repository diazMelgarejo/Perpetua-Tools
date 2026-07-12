"""Tests for .agent/memory/memory_search.py's index-staleness detection."""

import importlib.util
import sqlite3
import sys
import time
from pathlib import Path

import pytest


def _load_module(monkeypatch, tmp_path):
    """Load memory_search.py fresh with MEMORY_DIR/INDEX_PATH pointed at tmp_path.

    The module resolves these paths at import time from its own file location,
    so a fresh spec-based import (rather than a plain `import`) lets each test
    get an isolated module object with monkeypatched constants.
    """
    module_path = (
        Path(__file__).parent.parent / ".agent" / "memory" / "memory_search.py"
    )
    spec = importlib.util.spec_from_file_location("memory_search_test", module_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["memory_search_test"] = mod
    spec.loader.exec_module(mod)

    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    index_dir = memory_dir / ".index"
    index_dir.mkdir()
    monkeypatch.setattr(mod, "MEMORY_DIR", memory_dir)
    monkeypatch.setattr(mod, "INDEX_DIR", index_dir)
    monkeypatch.setattr(mod, "INDEX_PATH", index_dir / "memory.db")
    return mod, memory_dir


def _build_index(mod, filenames):
    """Write a minimal memories table listing exactly `filenames`."""
    with sqlite3.connect(mod.INDEX_PATH) as conn:
        conn.execute("CREATE TABLE memories (filename TEXT, content TEXT)")
        for f in filenames:
            conn.execute("INSERT INTO memories VALUES (?, ?)", (f, ""))


def test_needs_rebuild_false_when_index_matches_filesystem(monkeypatch, tmp_path):
    mod, memory_dir = _load_module(monkeypatch, tmp_path)
    (memory_dir / "a.md").write_text("hello", encoding="utf-8")
    _build_index(mod, ["a.md"])
    # Index must be newer than the source file's mtime for the fast-path
    # mtime check to pass.
    time.sleep(0.01)
    mod.INDEX_PATH.touch()
    assert mod.needs_rebuild() is False


def test_needs_rebuild_true_when_indexed_file_deleted(monkeypatch, tmp_path):
    """indexed - current: a row exists for a file no longer on disk."""
    mod, memory_dir = _load_module(monkeypatch, tmp_path)
    _build_index(mod, ["deleted.md"])
    mod.INDEX_PATH.touch()
    assert mod.needs_rebuild() is True


def test_needs_rebuild_true_when_filesystem_file_never_indexed(monkeypatch, tmp_path):
    """current - indexed: regression case for the CR fix.

    Previously `needs_rebuild()` only checked `indexed - current`, so a file
    present on disk but absent from the index (current - indexed) was
    invisible to staleness detection whenever its mtime happened to be <=
    the index mtime — e.g. an index rebuilt from a narrower glob in an
    older run, or same-tick file creation. The fix (symmetric difference)
    must catch this direction too.
    """
    mod, memory_dir = _load_module(monkeypatch, tmp_path)
    (memory_dir / "untracked.md").write_text("hello", encoding="utf-8")
    _build_index(mod, [])  # index knows about nothing
    # Force the index to be newer than the file, so the mtime fast-path
    # cannot catch this — only the symmetric-difference check can.
    time.sleep(0.01)
    mod.INDEX_PATH.touch()
    assert mod.needs_rebuild() is True
